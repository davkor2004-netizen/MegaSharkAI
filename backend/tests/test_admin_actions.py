"""
Тесты безопасных админских действий (block/unblock, change-plan, extend, cancel).

Проверяют:
- доступ только для superuser (обычный пользователь → 403);
- защиты: нельзя заблокировать самого себя и последнего администратора;
- каждое действие пишет AuditLog с санитизированными метаданными;
- ручная смена тарифа создаёт/обновляет подписку и помечается manual;
- продление и отмена работают и логируются;
- никакие платёжные провайдеры (YooKassa) не вызываются.
"""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.core.datetime_utils import utcnow
from app.models.audit import AuditLog
from app.models.tariff import Tariff, UserSubscription
from app.models.user import User


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------
def register_user(client, email: str, password: str = "TestPass123!") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "QA Action"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def auth_headers(client, email: str) -> tuple[dict[str, str], dict]:
    payload = register_user(client, email=email)
    return {"Authorization": f"Bearer {payload['access_token']}"}, payload


async def make_superuser(db_session, user_id: str) -> None:
    user = (
        await db_session.execute(select(User).where(User.id == UUID(user_id)))
    ).scalar_one()
    user.is_superuser = True
    await db_session.commit()


async def create_tariff(db_session, code: str = "pro", name: str = "PRO") -> Tariff:
    tariff = Tariff(
        id=uuid4(),
        name=name,
        code=code,
        price_monthly=1000.0,
        price_yearly=10000.0,
        trial_days=7,
        is_active=True,
    )
    db_session.add(tariff)
    await db_session.commit()
    return tariff


async def create_subscription(db_session, user_id: str, tariff: Tariff, status: str = "active") -> UserSubscription:
    sub = UserSubscription(
        id=uuid4(),
        user_id=UUID(user_id),
        tariff_id=tariff.id,
        status=status,
        is_trial=(status == "trial"),
        started_at=utcnow(),
        expires_at=utcnow() + timedelta(days=30),
        trial_ends_at=utcnow() + timedelta(days=7) if status == "trial" else None,
        billing_cycle="monthly",
    )
    db_session.add(sub)
    await db_session.commit()
    return sub


async def count_audit(db_session, action: str) -> int:
    return int(
        (
            await db_session.execute(
                select(func.count()).select_from(AuditLog).where(AuditLog.action == action)
            )
        ).scalar()
        or 0
    )


ACTION_ENDPOINTS = [
    ("/api/v1/admin/users/{uid}/block", {"reason": "x"}),
    ("/api/v1/admin/users/{uid}/unblock", {"reason": "x"}),
    ("/api/v1/admin/users/{uid}/subscription/change-plan", {"tariff_code": "pro", "reason": "x"}),
    ("/api/v1/admin/users/{uid}/subscription/extend", {"days": 10, "reason": "x"}),
    ("/api/v1/admin/users/{uid}/subscription/cancel", {"reason": "x"}),
]


# ---------------------------------------------------------------------------
# 1. Доступ
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_action_endpoints_forbidden_for_regular_user(client, db_session):
    """Обычный пользователь получает 403 на всех action endpoints."""
    user_headers, payload = auth_headers(client, "act-regular@example.com")
    target_headers, target = auth_headers(client, "act-target@example.com")
    uid = target["user"]["id"]
    for url, body in ACTION_ENDPOINTS:
        response = client.post(url.format(uid=uid), json=body, headers=user_headers)
        assert response.status_code == 403, f"{url} -> {response.status_code}"


@pytest.mark.asyncio
async def test_action_endpoints_unauthorized(client, db_session):
    """Без авторизации — 401."""
    response = client.post("/api/v1/admin/users/" + str(uuid4()) + "/block", json={"reason": "x"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 2. Блокировка / разблокировка
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_superuser_can_block_and_unblock(client, db_session):
    """Superuser блокирует и разблокирует пользователя, статус меняется."""
    admin_headers, admin = auth_headers(client, "act-admin@example.com")
    await make_superuser(db_session, admin["user"]["id"])
    _, target = auth_headers(client, "act-block@example.com")
    uid = target["user"]["id"]

    block = client.post(f"/api/v1/admin/users/{uid}/block", json={"reason": "abuse"}, headers=admin_headers)
    assert block.status_code == 200
    assert block.json()["is_active"] is False

    user = (await db_session.execute(select(User).where(User.id == UUID(uid)))).scalar_one()
    await db_session.refresh(user)
    assert user.is_active is False

    unblock = client.post(f"/api/v1/admin/users/{uid}/unblock", json={"reason": "ok"}, headers=admin_headers)
    assert unblock.status_code == 200
    assert unblock.json()["is_active"] is True


@pytest.mark.asyncio
async def test_cannot_block_self(client, db_session):
    """Админ не может заблокировать самого себя."""
    admin_headers, admin = auth_headers(client, "act-self@example.com")
    await make_superuser(db_session, admin["user"]["id"])
    uid = admin["user"]["id"]

    response = client.post(f"/api/v1/admin/users/{uid}/block", json={"reason": "x"}, headers=admin_headers)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_cannot_block_last_superuser(client, db_session):
    """Нельзя заблокировать последнего активного администратора (проверка правила сервиса)."""
    from app.services.admin_actions_service import block_user, AdminActionError

    admin1_headers, admin1 = auth_headers(client, "act-admin1@example.com")
    await make_superuser(db_session, admin1["user"]["id"])
    _, admin2 = auth_headers(client, "act-admin2@example.com")
    await make_superuser(db_session, admin2["user"]["id"])

    # Сейчас активных суперюзеров 2 — блокировка admin2 силами admin1 допустима.
    ok = client.post(
        f"/api/v1/admin/users/{admin2['user']['id']}/block",
        json={"reason": "x"},
        headers=admin1_headers,
    )
    assert ok.status_code == 200

    # Остался единственный активный суперюзер admin1. Попытка заблокировать его
    # (актором выступает уже неактивный admin2) должна отклоняться правилом.
    actor = (
        await db_session.execute(select(User).where(User.id == UUID(admin2["user"]["id"])))
    ).scalar_one()
    with pytest.raises(AdminActionError) as exc:
        await block_user(
            db_session, actor=actor, target_user_id=admin1["user"]["id"], reason="x"
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_block_creates_audit(client, db_session):
    """Блокировка пишет AuditLog admin.user.block c old/new статусами."""
    admin_headers, admin = auth_headers(client, "act-audit@example.com")
    await make_superuser(db_session, admin["user"]["id"])
    _, target = auth_headers(client, "act-audit-target@example.com")
    uid = target["user"]["id"]

    before = await count_audit(db_session, "admin.user.block")
    client.post(f"/api/v1/admin/users/{uid}/block", json={"reason": "spam"}, headers=admin_headers)
    after = await count_audit(db_session, "admin.user.block")
    assert after == before + 1

    entry = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "admin.user.block").order_by(AuditLog.id.desc()).limit(1)
        )
    ).scalar_one()
    assert entry.actor_user_id == UUID(admin["user"]["id"])
    assert entry.target_user_id == UUID(uid)
    assert "spam" in (entry.metadata_json or "")
    assert "blocked" in (entry.metadata_json or "")


# ---------------------------------------------------------------------------
# 3. Смена тарифа (manual, без YooKassa)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_change_plan_creates_subscription_and_audit(client, db_session):
    """Смена тарифа создаёт подписку, помечает manual и пишет audit."""
    admin_headers, admin = auth_headers(client, "plan-admin@example.com")
    await make_superuser(db_session, admin["user"]["id"])
    _, target = auth_headers(client, "plan-target@example.com")
    uid = target["user"]["id"]
    await create_tariff(db_session, code="pro", name="PRO")

    before = await count_audit(db_session, "admin.subscription.change_plan")
    response = client.post(
        f"/api/v1/admin/users/{uid}/subscription/change-plan",
        json={"tariff_code": "pro", "reason": "manual upgrade"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["manual"] is True

    sub = (
        await db_session.execute(
            select(UserSubscription).where(UserSubscription.user_id == UUID(uid))
        )
    ).scalar_one()
    assert sub.status == "active"
    assert sub.payment_method == "manual_admin"
    assert sub.auto_renew is False

    after = await count_audit(db_session, "admin.subscription.change_plan")
    assert after == before + 1


@pytest.mark.asyncio
async def test_change_plan_rejects_unknown_tariff(client, db_session):
    """Недопустимый код тарифа → 400, без обращения к платёжному провайдеру."""
    admin_headers, admin = auth_headers(client, "plan-bad@example.com")
    await make_superuser(db_session, admin["user"]["id"])
    _, target = auth_headers(client, "plan-bad-target@example.com")
    uid = target["user"]["id"]

    response = client.post(
        f"/api/v1/admin/users/{uid}/subscription/change-plan",
        json={"tariff_code": "nonexistent", "reason": "x"},
        headers=admin_headers,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_change_plan_does_not_call_payment_provider(client, db_session, monkeypatch):
    """Гарантия: ручная смена тарифа НЕ вызывает реальные платежи YooKassa."""
    called = {"hit": False}

    # Если в проекте есть платёжный модуль — перехватываем любые его вызовы.
    try:
        import app.services.payment as payment_module  # type: ignore

        for attr in dir(payment_module):
            if attr.startswith("_"):
                continue
            obj = getattr(payment_module, attr)
            if callable(obj):
                monkeypatch.setattr(
                    payment_module, attr,
                    lambda *a, **k: called.__setitem__("hit", True),
                    raising=False,
                )
    except ImportError:
        # Модуля платежей нет в этом контексте — значит вызвать его невозможно.
        pass

    admin_headers, admin = auth_headers(client, "plan-nopay@example.com")
    await make_superuser(db_session, admin["user"]["id"])
    _, target = auth_headers(client, "plan-nopay-target@example.com")
    uid = target["user"]["id"]
    await create_tariff(db_session, code="business", name="BUSINESS")

    response = client.post(
        f"/api/v1/admin/users/{uid}/subscription/change-plan",
        json={"tariff_code": "business", "reason": "manual"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert called["hit"] is False


# ---------------------------------------------------------------------------
# 4. Продление и отмена
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_extend_subscription_and_audit(client, db_session):
    """Продление сдвигает дату окончания и пишет audit."""
    admin_headers, admin = auth_headers(client, "ext-admin@example.com")
    await make_superuser(db_session, admin["user"]["id"])
    _, target = auth_headers(client, "ext-target@example.com")
    uid = target["user"]["id"]
    tariff = await create_tariff(db_session, code="pro", name="PRO")
    sub = await create_subscription(db_session, uid, tariff, status="active")
    old_end = sub.expires_at

    before = await count_audit(db_session, "admin.subscription.extend")
    response = client.post(
        f"/api/v1/admin/users/{uid}/subscription/extend",
        json={"days": 15, "reason": "bonus"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text

    await db_session.refresh(sub)
    assert sub.expires_at > old_end
    after = await count_audit(db_session, "admin.subscription.extend")
    assert after == before + 1


@pytest.mark.asyncio
async def test_extend_rejects_too_many_days(client, db_session):
    """Продление более чем на 365 дней отклоняется валидацией (422)."""
    admin_headers, admin = auth_headers(client, "ext-bad@example.com")
    await make_superuser(db_session, admin["user"]["id"])
    _, target = auth_headers(client, "ext-bad-target@example.com")
    uid = target["user"]["id"]

    response = client.post(
        f"/api/v1/admin/users/{uid}/subscription/extend",
        json={"days": 9999, "reason": "x"},
        headers=admin_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_cancel_subscription_and_audit(client, db_session):
    """Отмена меняет статус на cancelled и пишет audit."""
    admin_headers, admin = auth_headers(client, "cancel-admin@example.com")
    await make_superuser(db_session, admin["user"]["id"])
    _, target = auth_headers(client, "cancel-target@example.com")
    uid = target["user"]["id"]
    tariff = await create_tariff(db_session, code="pro", name="PRO")
    sub = await create_subscription(db_session, uid, tariff, status="active")

    before = await count_audit(db_session, "admin.subscription.cancel")
    response = client.post(
        f"/api/v1/admin/users/{uid}/subscription/cancel",
        json={"reason": "user request"},
        headers=admin_headers,
    )
    assert response.status_code == 200

    await db_session.refresh(sub)
    assert sub.status == "cancelled"
    assert sub.auto_renew is False
    after = await count_audit(db_session, "admin.subscription.cancel")
    assert after == before + 1


# ---------------------------------------------------------------------------
# 5. Аудит виден в /admin/audit и не содержит секретов
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_actions_visible_in_audit_endpoint(client, db_session):
    """Действия отображаются в /admin/audit с email актора/цели."""
    admin_headers, admin = auth_headers(client, "vis-admin@example.com")
    await make_superuser(db_session, admin["user"]["id"])
    _, target = auth_headers(client, "vis-target@example.com")
    uid = target["user"]["id"]

    client.post(f"/api/v1/admin/users/{uid}/block", json={"reason": "x"}, headers=admin_headers)

    response = client.get("/api/v1/admin/audit?action=admin.user.block", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    entry = data["items"][0]
    assert entry["action"] == "admin.user.block"
    assert entry["actor"]["email"] == "vis-admin@example.com"
    assert entry["target"]["email"] == "vis-target@example.com"


@pytest.mark.asyncio
async def test_action_audit_does_not_leak_secrets(client, db_session):
    """Если в reason передан секрет-подобный ключ — он не утекает (metadata sanitized)."""
    admin_headers, admin = auth_headers(client, "leak-admin@example.com")
    await make_superuser(db_session, admin["user"]["id"])
    _, target = auth_headers(client, "leak-target@example.com")
    uid = target["user"]["id"]
    await create_tariff(db_session, code="pro", name="PRO")

    # Сменим план — metadata содержит old/new plan, reason. Секретов в схеме нет,
    # но проверяем, что хэш пароля цели и токены админа не попадают в выдачу.
    client.post(
        f"/api/v1/admin/users/{uid}/subscription/change-plan",
        json={"tariff_code": "pro", "reason": "ok"},
        headers=admin_headers,
    )

    response = client.get("/api/v1/admin/audit", headers=admin_headers)
    assert response.status_code == 200
    body = response.text
    assert "hashed_password" not in body
    assert "TestPass123!" not in body
