"""
Канонический источник тарифной модели MegaSharkAI.

ЕДИНСТВЕННЫЙ источник правды о тарифах: лимиты, feature-флаги, цены и порядок.
На него опираются:
- enforcement (app/services/feature_access.py, app/services/limits.py);
- админка (/api/v1/admin/tariffs);
- биллинг (/api/v1/billing/usage).

Это исключает рассинхрон между «прайсом», лимитами и реальными проверками доступа.

Резолвинг плана выполняется по `code` подписки (trial/pro/business/agency/enterprise).
Для ENTERPRISE возможны индивидуальные лимиты (берутся из JSON тарифа в БД, если заданы).
"""

from typing import Optional

# Порядок тарифов от младшего к старшему (для upgrade-подсказок и сравнения лимитов).
PLAN_ORDER: list[str] = ["trial", "pro", "business", "agency", "enterprise"]

# Куда вести пользователя за апгрейдом.
UPGRADE_URL = "/billing"

# Канонический список feature-флагов (единая модель).
FEATURE_KEYS: list[str] = [
    "ai_audit_access",
    "competitor_analysis_access",
    "analytics_access",
    "reports_access",
    "repricing_access",
    "auto_repricing_access",
    "widget_access",
    "telegram_notifications_access",
    "bulk_import_access",
    "advanced_reports_access",
    "white_label_reports_access",
    "team_access",
    "priority_queue_access",
    "agency_projects_access",
]

# Ключи числовых лимитов (для usage summary и enforcement).
LIMIT_KEYS: list[str] = [
    "max_users",
    "max_products",
    "max_parsing_requests_per_month",
    "max_ai_actions_per_month",
    "max_ai_audits_per_month",
    "max_seo_generations_per_month",
    "max_review_replies_per_month",
    "max_exports_per_month",
    "max_tracked_competitors",
    "max_marketplace_keys",
    "price_history_days",
]

# -1 означает безлимит.
UNLIMITED = -1


def _flags(**overrides) -> dict:
    """Собрать словарь флагов: всё False, затем переопределения."""
    base = {key: False for key in FEATURE_KEYS}
    base.update(overrides)
    return base


# ====================================================================
# КАНОНИЧЕСКАЯ ТАРИФНАЯ СЕТКА
# ====================================================================
PLAN_CATALOG: dict[str, dict] = {
    "trial": {
        "code": "trial",
        "name": "Trial",
        "price": 0,
        "currency": "RUB",
        "billing_period": "3 дня",
        "is_public": True,
        "is_manual_only": False,
        "limits": {
            "max_users": 1,
            "max_products": 10,
            "max_parsing_requests_per_month": 20,
            "max_ai_actions_per_month": 25,
            "max_ai_audits_per_month": 10,
            "max_seo_generations_per_month": 10,
            "max_review_replies_per_month": 5,
            "max_exports_per_month": 1,
            "max_tracked_competitors": 10,
            "max_marketplace_keys": 1,
            "price_history_days": 7,
        },
        "feature_flags": _flags(
            ai_audit_access=True,
            competitor_analysis_access=True,
            analytics_access=True,
            reports_access=True,
        ),
    },
    "pro": {
        "code": "pro",
        "name": "PRO",
        "price": 2990,
        "currency": "RUB",
        "billing_period": "месяц",
        "is_public": True,
        "is_manual_only": False,
        "limits": {
            "max_users": 1,
            "max_products": 100,
            "max_parsing_requests_per_month": 500,
            "max_ai_actions_per_month": 300,
            "max_ai_audits_per_month": 100,
            "max_seo_generations_per_month": 100,
            "max_review_replies_per_month": 100,
            "max_exports_per_month": 50,
            "max_tracked_competitors": 100,
            "max_marketplace_keys": 1,
            "price_history_days": 30,
        },
        "feature_flags": _flags(
            ai_audit_access=True,
            competitor_analysis_access=True,
            analytics_access=True,
            reports_access=True,
            bulk_import_access=True,
        ),
    },
    "business": {
        "code": "business",
        "name": "BUSINESS",
        "price": 7990,
        "currency": "RUB",
        "billing_period": "месяц",
        "is_public": True,
        "is_manual_only": False,
        "limits": {
            "max_users": 3,
            "max_products": 500,
            "max_parsing_requests_per_month": 3000,
            "max_ai_actions_per_month": 1500,
            "max_ai_audits_per_month": 500,
            "max_seo_generations_per_month": 500,
            "max_review_replies_per_month": 500,
            "max_exports_per_month": 300,
            "max_tracked_competitors": 500,
            "max_marketplace_keys": 3,
            "price_history_days": 180,
        },
        "feature_flags": _flags(
            ai_audit_access=True,
            competitor_analysis_access=True,
            analytics_access=True,
            reports_access=True,
            repricing_access=True,
            auto_repricing_access=True,
            widget_access=True,
            telegram_notifications_access=True,
            bulk_import_access=True,
            advanced_reports_access=True,
            team_access=True,
            priority_queue_access=True,
        ),
    },
    "agency": {
        "code": "agency",
        "name": "AGENCY",
        "price": 14990,
        "currency": "RUB",
        "billing_period": "месяц",
        "is_public": True,
        "is_manual_only": False,
        "limits": {
            "max_users": 10,
            "max_products": 2000,
            "max_parsing_requests_per_month": 10000,
            "max_ai_actions_per_month": 5000,
            "max_ai_audits_per_month": 2000,
            "max_seo_generations_per_month": 2000,
            "max_review_replies_per_month": 2000,
            "max_exports_per_month": 1000,
            "max_tracked_competitors": 2000,
            "max_marketplace_keys": 10,
            "price_history_days": 365,
        },
        "feature_flags": _flags(
            ai_audit_access=True,
            competitor_analysis_access=True,
            analytics_access=True,
            reports_access=True,
            repricing_access=True,
            auto_repricing_access=True,
            widget_access=True,
            telegram_notifications_access=True,
            bulk_import_access=True,
            advanced_reports_access=True,
            white_label_reports_access=True,
            team_access=True,
            priority_queue_access=True,
            agency_projects_access=True,
        ),
    },
    "enterprise": {
        "code": "enterprise",
        "name": "ENTERPRISE",
        "price": None,
        "currency": "RUB",
        "billing_period": "индивидуально",
        "is_public": False,
        "is_manual_only": True,
        "limits": {
            "max_users": UNLIMITED,
            "max_products": UNLIMITED,
            "max_parsing_requests_per_month": UNLIMITED,
            "max_ai_actions_per_month": UNLIMITED,
            "max_ai_audits_per_month": UNLIMITED,
            "max_seo_generations_per_month": UNLIMITED,
            "max_review_replies_per_month": UNLIMITED,
            "max_exports_per_month": UNLIMITED,
            "max_tracked_competitors": UNLIMITED,
            "max_marketplace_keys": UNLIMITED,
            "price_history_days": UNLIMITED,
        },
        # Все возможности включены.
        "feature_flags": {key: True for key in FEATURE_KEYS},
    },
}

# План, применяемый когда у пользователя нет активной подписки.
# Бесплатный режим = ограничения Trial: базовые функции работают, платные — заблокированы.
FREE_FALLBACK_PLAN = "trial"


def get_plan(code: Optional[str]) -> dict:
    """Вернуть определение плана по коду; неизвестный/None → бесплатный (trial)."""
    if not code:
        return PLAN_CATALOG[FREE_FALLBACK_PLAN]
    return PLAN_CATALOG.get(str(code).lower(), PLAN_CATALOG[FREE_FALLBACK_PLAN])


def get_plan_limits(code: Optional[str]) -> dict:
    """Числовые лимиты плана (копия, чтобы вызывающий не мутировал каталог)."""
    return dict(get_plan(code)["limits"])


def get_plan_flags(code: Optional[str]) -> dict:
    """Feature-флаги плана (копия)."""
    return dict(get_plan(code)["feature_flags"])


def plan_rank(code: Optional[str]) -> int:
    """Порядковый номер плана (для сравнения «выше/ниже»)."""
    try:
        return PLAN_ORDER.index(str(code).lower())
    except (ValueError, AttributeError):
        return -1


def feature_min_plan(feature: str) -> Optional[str]:
    """Минимальный план, на котором доступна фича (для upgrade-подсказки)."""
    for code in PLAN_ORDER:
        if PLAN_CATALOG[code]["feature_flags"].get(feature):
            return code
    return None


def limit_min_plan(limit_key: str, needed: int) -> Optional[str]:
    """
    Минимальный план, лимит которого вмещает ``needed`` (или безлимитен).

    Используется для подсказки апгрейда при LIMIT_EXCEEDED.
    """
    for code in PLAN_ORDER:
        value = PLAN_CATALOG[code]["limits"].get(limit_key)
        if value is None:
            continue
        if value == UNLIMITED or value >= needed:
            return code
    return "enterprise"
