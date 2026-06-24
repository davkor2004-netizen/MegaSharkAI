"""
Эндпоинты встраиваемого виджета (MegaShark-ассистент на сайте продавца).

Виджет — платная фича тарифа (widget_access). Состоит из:
- приватных эндпоинтов управления (нужен вход + тариф с widget_access);
- публичных эндпоинтов для самого виджета (без авторизации, по public_key):
  loader-скрипт, HTML-фрейм с чатом, публичный конфиг и обработчик сообщений.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.product import Product
from app.models.user import User
from app.models.widget import WidgetConfig
from app.api.v1.auth import get_current_user
from app.services.ai_service import get_ai_service
from app.services.limits import get_active_limits, require_feature

router = APIRouter()


# ====================
# Схемы
# ====================

class WidgetConfigUpdate(BaseModel):
    """Тело запроса для обновления настроек виджета."""
    is_enabled: bool = True
    title: str = Field(default="Помощник магазина", min_length=1, max_length=120)
    welcome_message: str = Field(default="Здравствуйте! Чем помочь?", min_length=1, max_length=500)
    accent_color: str = Field(default="#6d28d9", pattern=r"^#[0-9a-fA-F]{3,8}$")
    allowed_origins: str | None = Field(default=None, max_length=2000)


class WidgetChatRequest(BaseModel):
    """Сообщение посетителя сайта в виджет."""
    message: str = Field(..., min_length=1, max_length=1000)
    history: list[dict] | None = Field(default=None, max_length=20)


# ====================
# Вспомогательные функции
# ====================

async def get_or_create_widget(db: AsyncSession, user_id) -> WidgetConfig:
    """Получить конфиг виджета пользователя или создать с дефолтными значениями."""
    widget = (
        await db.execute(select(WidgetConfig).where(WidgetConfig.user_id == user_id))
    ).scalar_one_or_none()

    if widget:
        return widget

    widget = WidgetConfig(
        user_id=user_id,
        public_key=secrets.token_urlsafe(18),
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return widget


async def get_widget_by_key(db: AsyncSession, public_key: str) -> WidgetConfig | None:
    """Найти виджет по публичному ключу."""
    return (
        await db.execute(select(WidgetConfig).where(WidgetConfig.public_key == public_key))
    ).scalar_one_or_none()


def _build_embed_code(base_url: str, public_key: str) -> str:
    """Сформировать код вставки для сайта продавца."""
    return f'<script src="{base_url}/api/v1/widget/public/{public_key}/widget.js" async></script>'


# ====================
# Приватные эндпоинты (управление виджетом)
# ====================

@router.get("/config", summary="Настройки виджета", description="Конфиг виджета текущего пользователя (нужен тариф с widget_access)")
async def get_widget_config(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить настройки виджета и код вставки. Требует тариф с widget_access."""
    await require_feature(db, current_user.id, "widget_access")
    widget = await get_or_create_widget(db, current_user.id)
    base_url = str(request.base_url).rstrip("/")

    return {
        "public_key": widget.public_key,
        "is_enabled": widget.is_enabled,
        "title": widget.title,
        "welcome_message": widget.welcome_message,
        "accent_color": widget.accent_color,
        "allowed_origins": widget.allowed_origins,
        "embed_code": _build_embed_code(base_url, widget.public_key),
    }


@router.put("/config", summary="Сохранить настройки виджета")
async def update_widget_config(
    payload: WidgetConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить настройки виджета. Требует тариф с widget_access."""
    await require_feature(db, current_user.id, "widget_access")
    widget = await get_or_create_widget(db, current_user.id)

    widget.is_enabled = payload.is_enabled
    widget.title = payload.title
    widget.welcome_message = payload.welcome_message
    widget.accent_color = payload.accent_color
    widget.allowed_origins = (payload.allowed_origins or "").strip() or None

    await db.commit()
    await db.refresh(widget)

    base_url = str(request.base_url).rstrip("/")
    return {
        "status": "success",
        "public_key": widget.public_key,
        "is_enabled": widget.is_enabled,
        "embed_code": _build_embed_code(base_url, widget.public_key),
    }


@router.post("/rotate-key", summary="Сгенерировать новый ключ виджета")
async def rotate_widget_key(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Сменить публичный ключ виджета (старый код вставки перестанет работать)."""
    await require_feature(db, current_user.id, "widget_access")
    widget = await get_or_create_widget(db, current_user.id)
    widget.public_key = secrets.token_urlsafe(18)
    await db.commit()
    await db.refresh(widget)

    base_url = str(request.base_url).rstrip("/")
    return {
        "status": "success",
        "public_key": widget.public_key,
        "embed_code": _build_embed_code(base_url, widget.public_key),
    }


# ====================
# Публичные эндпоинты (сам виджет)
# ====================

async def _widget_is_serviceable(db: AsyncSession, widget: WidgetConfig) -> bool:
    """Виджет работает только если включён и у владельца действует тариф с widget_access."""
    if not widget.is_enabled:
        return False
    owner_limits = await get_active_limits(db, widget.user_id)
    return bool(owner_limits.get("widget_access"))


@router.get("/public/{public_key}/config", summary="Публичный конфиг виджета")
async def public_widget_config(
    public_key: str,
    db: AsyncSession = Depends(get_db),
):
    """Публичная (безопасная) конфигурация виджета для отрисовки."""
    widget = await get_widget_by_key(db, public_key)
    if not widget:
        raise HTTPException(status_code=404, detail="Виджет не найден")

    serviceable = await _widget_is_serviceable(db, widget)
    return {
        "enabled": serviceable,
        "title": widget.title,
        "welcome_message": widget.welcome_message,
        "accent_color": widget.accent_color,
    }


@router.post("/public/{public_key}/chat", summary="Сообщение в виджет")
async def public_widget_chat(
    public_key: str,
    payload: WidgetChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Обработать сообщение посетителя и вернуть ответ AI-ассистента."""
    widget = await get_widget_by_key(db, public_key)
    if not widget:
        raise HTTPException(status_code=404, detail="Виджет не найден")

    if not await _widget_is_serviceable(db, widget):
        raise HTTPException(status_code=403, detail="Виджет недоступен")

    # Контекст: собственные товары владельца виджета.
    products = (
        await db.execute(
            select(Product)
            .where(Product.user_id == widget.user_id, Product.is_competitor.is_(False))
            .limit(30)
        )
    ).scalars().all()

    products_context = "\n".join(
        f"- {p.name[:80]} — {int(p.price)} ₽" if p.price else f"- {p.name[:80]}"
        for p in products
    )

    history = []
    for turn in (payload.history or [])[-10:]:
        if isinstance(turn, dict) and turn.get("text"):
            history.append({"role": turn.get("role", "user"), "text": str(turn["text"])[:500]})

    ai_service = get_ai_service()
    reply = await ai_service.widget_assistant_reply(
        store_title=widget.title,
        products_context=products_context,
        history=history,
        message=payload.message,
    )

    return {"reply": reply}


@router.get("/public/{public_key}/widget.js", summary="Loader-скрипт виджета")
async def public_widget_loader(
    public_key: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """JS-скрипт для вставки на сайт: рисует кнопку-лаунчер и iframe с чатом."""
    widget = await get_widget_by_key(db, public_key)
    if not widget:
        raise HTTPException(status_code=404, detail="Виджет не найден")

    base_url = str(request.base_url).rstrip("/")
    frame_url = f"{base_url}/api/v1/widget/public/{public_key}/frame"

    script = _WIDGET_LOADER_JS
    script = script.replace("__FRAME_URL__", frame_url)
    script = script.replace("__COLOR__", widget.accent_color)
    script = script.replace("__TITLE__", widget.title.replace("'", " "))

    return Response(content=script, media_type="application/javascript; charset=utf-8")


@router.get("/public/{public_key}/frame", summary="HTML-фрейм виджета")
async def public_widget_frame(
    public_key: str,
    db: AsyncSession = Depends(get_db),
):
    """HTML-страница чата, которая встраивается в iframe на сайте продавца."""
    widget = await get_widget_by_key(db, public_key)
    if not widget:
        raise HTTPException(status_code=404, detail="Виджет не найден")

    html = _WIDGET_FRAME_HTML
    html = html.replace("__KEY__", public_key)
    html = html.replace("__COLOR__", widget.accent_color)
    html = html.replace("__TITLE__", widget.title)
    html = html.replace("__WELCOME__", widget.welcome_message)

    # Разрешаем встраивание этого фрейма на сторонних сайтах (anti-framing снят в middleware).
    return HTMLResponse(content=html, headers={"Content-Security-Policy": "frame-ancestors *"})


# ====================
# Шаблоны фронтенда виджета
# ====================

_WIDGET_LOADER_JS = """
(function () {
  if (window.__megaSharkWidgetLoaded) return;
  window.__megaSharkWidgetLoaded = true;

  var FRAME_URL = "__FRAME_URL__";
  var COLOR = "__COLOR__";

  // Кнопка-лаунчер.
  var btn = document.createElement("button");
  btn.setAttribute("aria-label", "Открыть чат");
  btn.style.cssText = "position:fixed;right:20px;bottom:20px;width:60px;height:60px;border-radius:50%;border:none;cursor:pointer;z-index:2147483000;box-shadow:0 6px 20px rgba(0,0,0,.25);background:" + COLOR + ";color:#fff;font-size:26px;";
  btn.innerHTML = "&#128172;";

  // Контейнер iframe.
  var frame = document.createElement("iframe");
  frame.src = FRAME_URL;
  frame.title = "__TITLE__";
  frame.style.cssText = "position:fixed;right:20px;bottom:90px;width:370px;height:540px;max-width:calc(100vw - 40px);max-height:calc(100vh - 120px);border:none;border-radius:16px;box-shadow:0 12px 40px rgba(0,0,0,.3);z-index:2147483000;display:none;background:#fff;";

  var open = false;
  btn.addEventListener("click", function () {
    open = !open;
    frame.style.display = open ? "block" : "none";
    btn.innerHTML = open ? "&#10005;" : "&#128172;";
  });

  function mount() {
    document.body.appendChild(frame);
    document.body.appendChild(btn);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
"""

_WIDGET_FRAME_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; display: flex; flex-direction: column; height: 100vh; background: #f8fafc; }
  .header { background: __COLOR__; color: #fff; padding: 14px 16px; font-weight: 600; }
  .messages { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
  .msg { max-width: 85%; padding: 9px 12px; border-radius: 12px; font-size: 14px; line-height: 1.4; white-space: pre-wrap; }
  .bot { background: #fff; border: 1px solid #e2e8f0; align-self: flex-start; }
  .user { background: __COLOR__; color: #fff; align-self: flex-end; }
  .typing { color: #64748b; font-size: 13px; align-self: flex-start; }
  .input { display: flex; gap: 8px; padding: 10px; border-top: 1px solid #e2e8f0; background: #fff; }
  .input input { flex: 1; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 10px; font-size: 14px; outline: none; }
  .input button { background: __COLOR__; color: #fff; border: none; border-radius: 10px; padding: 0 16px; cursor: pointer; font-size: 14px; }
  .input button:disabled { opacity: .5; cursor: default; }
  .powered { text-align: center; font-size: 11px; color: #94a3b8; padding: 4px 0 8px; }
</style>
</head>
<body>
  <div class="header">__TITLE__</div>
  <div class="messages" id="messages"></div>
  <div class="input">
    <input id="text" type="text" placeholder="Напишите сообщение..." autocomplete="off">
    <button id="send">Отправить</button>
  </div>
  <div class="powered">Работает на MegaSharkAI</div>
<script>
  var KEY = "__KEY__";
  var history = [];
  var messagesEl = document.getElementById("messages");
  var inputEl = document.getElementById("text");
  var sendEl = document.getElementById("send");

  function addMessage(text, role) {
    var div = document.createElement("div");
    div.className = "msg " + (role === "user" ? "user" : "bot");
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  addMessage("__WELCOME__", "bot");

  function setBusy(busy) {
    sendEl.disabled = busy;
    inputEl.disabled = busy;
  }

  async function send() {
    var text = inputEl.value.trim();
    if (!text) return;
    addMessage(text, "user");
    history.push({ role: "user", text: text });
    inputEl.value = "";
    setBusy(true);

    var typing = document.createElement("div");
    typing.className = "typing";
    typing.textContent = "печатает...";
    messagesEl.appendChild(typing);
    messagesEl.scrollTop = messagesEl.scrollHeight;

    try {
      var resp = await fetch("/api/v1/widget/public/" + KEY + "/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history: history })
      });
      typing.remove();
      if (!resp.ok) { addMessage("Извините, сервис временно недоступен.", "bot"); return; }
      var data = await resp.json();
      addMessage(data.reply || "...", "bot");
      history.push({ role: "assistant", text: data.reply || "" });
    } catch (e) {
      typing.remove();
      addMessage("Ошибка соединения. Попробуйте позже.", "bot");
    } finally {
      setBusy(false);
      inputEl.focus();
    }
  }

  sendEl.addEventListener("click", send);
  inputEl.addEventListener("keydown", function (e) { if (e.key === "Enter") send(); });
</script>
</body>
</html>
"""
