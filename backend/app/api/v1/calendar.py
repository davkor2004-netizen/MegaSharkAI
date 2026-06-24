"""
Эндпоинты для календаря распродаж.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
from io import StringIO
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from loguru import logger
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.models.notification import SaleCalendar
from app.models.user import User

router = APIRouter()

CalendarEventType = Literal["sale", "promotion", "holiday", "deadline", "other"]
RepeatType = Literal["none", "daily", "weekly", "monthly"]


class CalendarEventCreate(BaseModel):
    """Схема для создания события календаря."""

    title: str = Field(..., min_length=2, max_length=255)
    start_date: str
    end_date: str
    marketplace: str | None = Field(default=None, max_length=50)
    event_type: CalendarEventType = "sale"
    discount_percent: float | None = Field(default=None, ge=0, le=100)
    description: str | None = None
    notes: str | None = None
    repeat_type: RepeatType = "none"
    repeat_count: int = Field(default=1, ge=1, le=100)
    repeat_until: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        """Проверяем, что заголовок не пустой после trim."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("Название события не может быть пустым")
        return normalized


class CalendarEventUpdate(BaseModel):
    """Схема для обновления события календаря."""

    title: str | None = Field(default=None, min_length=2, max_length=255)
    start_date: str | None = None
    end_date: str | None = None
    marketplace: str | None = Field(default=None, max_length=50)
    event_type: CalendarEventType | None = None
    discount_percent: float | None = Field(default=None, ge=0, le=100)
    description: str | None = None
    notes: str | None = None

    @field_validator("title")
    @classmethod
    def validate_optional_title(cls, value: str | None) -> str | None:
        """Проверяем заголовок, если он передан в запросе."""
        if value is None:
            return value

        normalized = value.strip()
        if not normalized:
            raise ValueError("Название события не может быть пустым")
        return normalized


def parse_iso_datetime(value: str, field_name: str) -> datetime:
    """Безопасно распарсить ISO-дату и вернуть понятную ошибку при невалидном формате."""
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Неверный формат поля {field_name}. Используйте ISO формат (YYYY-MM-DDTHH:MM:SS)",
        ) from exc


def add_months(source_dt: datetime, months: int) -> datetime:
    """Добавить к дате N месяцев без внешних библиотек."""
    month_index = source_dt.month - 1 + months
    year = source_dt.year + month_index // 12
    month = month_index % 12 + 1

    # Корректируем день месяца, чтобы избежать невалидных дат вроде 31 февраля.
    max_day = [
        31,
        29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ][month - 1]
    day = min(source_dt.day, max_day)

    return source_dt.replace(year=year, month=month, day=day)


def build_occurrences(
    *,
    start_date: datetime,
    end_date: datetime,
    repeat_type: RepeatType,
    repeat_count: int,
    repeat_until: datetime | None,
) -> list[tuple[datetime, datetime]]:
    """
    Сформировать список повторений события.

    - первое событие всегда включается;
    - при repeat_type=none возвращается ровно одно событие;
    - количество защищено лимитом, чтобы не создавать тысячи записей случайно.
    """
    if repeat_type == "none":
        return [(start_date, end_date)]

    occurrences: list[tuple[datetime, datetime]] = []
    current_start = start_date
    current_end = end_date

    for _ in range(repeat_count):
        if repeat_until and current_start > repeat_until:
            break

        occurrences.append((current_start, current_end))

        if repeat_type == "daily":
            current_start += timedelta(days=1)
            current_end += timedelta(days=1)
        elif repeat_type == "weekly":
            current_start += timedelta(weeks=1)
            current_end += timedelta(weeks=1)
        else:  # monthly
            duration = current_end - current_start
            current_start = add_months(current_start, 1)
            current_end = current_start + duration

    if not occurrences:
        raise HTTPException(status_code=400, detail="Не удалось создать повторяющиеся события: проверьте repeat_until")

    return occurrences


def serialize_event(event: SaleCalendar, now: datetime, current_user: User) -> dict:
    """Преобразовать ORM-объект события в API-ответ."""
    is_owned = event.user_id == current_user.id
    is_active = bool(event.start_date and event.end_date and event.start_date <= now <= event.end_date)
    is_upcoming = bool(event.start_date and event.start_date > now)

    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "marketplace": event.marketplace,
        "event_type": event.event_type,
        "start_date": event.start_date.isoformat() if event.start_date else None,
        "end_date": event.end_date.isoformat() if event.end_date else None,
        "is_global": event.is_global,
        "discount_percent": event.discount_percent,
        "notes": event.notes,
        "is_owned": is_owned,
        "can_edit": is_owned and not event.is_global,
        "can_delete": is_owned and not event.is_global,
        "is_active": is_active,
        "is_upcoming": is_upcoming,
        "is_past": not is_active and not is_upcoming,
    }


def parse_optional_date_filter(value: str | None, field_name: str) -> datetime | None:
    """Распарсить дату фильтра, если она передана."""
    if not value:
        return None
    return parse_iso_datetime(value, field_name)


async def get_user_event_or_404(db: AsyncSession, event_id: int, current_user: User) -> SaleCalendar:
    """Получить пользовательское событие или выбросить 404 без раскрытия чужих ID."""
    result = await db.execute(
        select(SaleCalendar).where(
            SaleCalendar.id == event_id,
            SaleCalendar.user_id == current_user.id,
            SaleCalendar.is_global.is_(False),
        )
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")

    return event


@router.get(
    "/",
    summary="Список событий календаря",
    description="Получение списка распродаж и акций. Возвращает глобальные события + события текущего пользователя.",
)
async def get_calendar_events(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    marketplace: str | None = Query(default=None, description="Фильтр по маркетплейсу"),
    event_type: CalendarEventType | None = Query(default=None, description="Фильтр по типу события"),
    start_date: str | None = Query(default=None, description="Дата начала фильтра (ISO)"),
    end_date: str | None = Query(default=None, description="Дата окончания фильтра (ISO)"),
    status: Literal["all", "upcoming", "active", "past"] = Query(default="all"),
    include_global: bool = Query(default=True, description="Добавлять ли глобальные события"),
    owned_only: bool = Query(default=False, description="Возвращать только события пользователя"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Получение списка событий календаря с расширенными фильтрами."""
    logger.info(
        f"📅 Запрос событий календаря: user_id={current_user.id}, status={status}, event_type={event_type}, marketplace={marketplace}"
    )
    
    now = datetime.utcnow()
    parsed_start = parse_optional_date_filter(start_date, "start_date")
    parsed_end = parse_optional_date_filter(end_date, "end_date")

    if parsed_start and parsed_end and parsed_start > parsed_end:
        raise HTTPException(status_code=400, detail="start_date не может быть позже end_date")

    visibility_filters = [SaleCalendar.user_id == current_user.id]
    if include_global and not owned_only:
        visibility_filters.append(SaleCalendar.is_global.is_(True))

    query = select(SaleCalendar).where(or_(*visibility_filters))

    if marketplace:
        query = query.where(SaleCalendar.marketplace == marketplace)

    if event_type:
        query = query.where(SaleCalendar.event_type == event_type)

    if parsed_start:
        query = query.where(SaleCalendar.end_date >= parsed_start)

    if parsed_end:
        query = query.where(SaleCalendar.start_date <= parsed_end)

    if status == "upcoming":
        query = query.where(SaleCalendar.start_date > now)
    elif status == "active":
        query = query.where(and_(SaleCalendar.start_date <= now, SaleCalendar.end_date >= now))
    elif status == "past":
        query = query.where(SaleCalendar.end_date < now)

    query = query.order_by(SaleCalendar.start_date).offset(offset).limit(limit)

    result = await db.execute(query)
    events = result.scalars().all()
    
    return [serialize_event(event, now, current_user) for event in events]


@router.post(
    "/",
    summary="Создать событие календаря",
    description="Добавление нового события в календарь. Поддерживает повторяющиеся события.",
)
async def create_calendar_event(
    event_data: CalendarEventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создание нового события (или серии повторяющихся событий)."""
    logger.info(
        f"📅 Создание события: title='{event_data.title}', user_id={current_user.id}, repeat_type={event_data.repeat_type}"
    )

    start = parse_iso_datetime(event_data.start_date, "start_date")
    end = parse_iso_datetime(event_data.end_date, "end_date")

    if start >= end:
        raise HTTPException(status_code=400, detail="Дата начала должна быть раньше даты окончания")

    repeat_until_dt = None
    if event_data.repeat_until:
        repeat_until_dt = parse_iso_datetime(event_data.repeat_until, "repeat_until")

    occurrences = build_occurrences(
        start_date=start,
        end_date=end,
        repeat_type=event_data.repeat_type,
        repeat_count=event_data.repeat_count,
        repeat_until=repeat_until_dt,
    )

    created_events: list[SaleCalendar] = []
    for occurrence_start, occurrence_end in occurrences:
        event = SaleCalendar(
            title=event_data.title,
            description=event_data.description,
            marketplace=event_data.marketplace,
            event_type=event_data.event_type,
            start_date=occurrence_start,
            end_date=occurrence_end,
            is_global=False,
            discount_percent=event_data.discount_percent,
            notes=event_data.notes,
            user_id=current_user.id,
        )
        db.add(event)
        created_events.append(event)

    await db.commit()

    for event in created_events:
        await db.refresh(event)

    return {
        "status": "success",
        "event_ids": [event.id for event in created_events],
        "created_count": len(created_events),
        "message": "Событие(я) создано",
    }


@router.put(
    "/{event_id:int}",
    summary="Обновить событие",
    description="Обновление события календаря. Только владелец может редактировать своё событие.",
)
async def update_calendar_event(
    event_id: int,
    payload: CalendarEventUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить одно пользовательское событие календаря."""
    logger.info(f"✏️ Обновление события {event_id}, user_id={current_user.id}")

    event = await get_user_event_or_404(db, event_id, current_user)

    new_start = parse_iso_datetime(payload.start_date, "start_date") if payload.start_date else event.start_date
    new_end = parse_iso_datetime(payload.end_date, "end_date") if payload.end_date else event.end_date

    if new_start >= new_end:
        raise HTTPException(status_code=400, detail="Дата начала должна быть раньше даты окончания")

    if payload.title is not None:
        event.title = payload.title
    if payload.description is not None:
        event.description = payload.description
    if payload.marketplace is not None:
        event.marketplace = payload.marketplace
    if payload.event_type is not None:
        event.event_type = payload.event_type
    if payload.discount_percent is not None:
        event.discount_percent = payload.discount_percent
    if payload.notes is not None:
        event.notes = payload.notes

    event.start_date = new_start
    event.end_date = new_end

    await db.commit()
    await db.refresh(event)

    return {
        "status": "success",
        "message": "Событие обновлено",
        "event": serialize_event(event, datetime.utcnow(), current_user),
    }


@router.delete(
    "/{event_id:int}",
    status_code=204,
    summary="Удалить событие",
    description="Удаление события из календаря. Только владелец может удалить своё событие.",
)
async def delete_calendar_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Удаление события текущего пользователя."""
    logger.info(f"🗑️ Удаление события {event_id}, user_id={current_user.id}")

    event = await get_user_event_or_404(db, event_id, current_user)

    await db.execute(delete(SaleCalendar).where(SaleCalendar.id == event.id))
    await db.commit()

    return None


@router.get(
    "/upcoming",
    summary="Ближайшие события",
    description="Получение ближайших распродаж (по умолчанию 30 дней). Глобальные + события пользователя.",
)
async def get_upcoming_events(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365),
    marketplace: str | None = Query(default=None),
    event_type: CalendarEventType | None = Query(default=None),
    limit: int = Query(20, ge=1, le=200),
):
    """Получение ближайших событий."""
    logger.info(f"📅 Запрос ближайших событий ({days} дней): user_id={current_user.id}")

    now = datetime.utcnow()
    future = now + timedelta(days=days)

    query = (
        select(SaleCalendar)
        .where(or_(SaleCalendar.is_global.is_(True), SaleCalendar.user_id == current_user.id))
        .where(SaleCalendar.start_date >= now)
        .where(SaleCalendar.start_date <= future)
    )

    if marketplace:
        query = query.where(SaleCalendar.marketplace == marketplace)

    if event_type:
        query = query.where(SaleCalendar.event_type == event_type)

    query = query.order_by(SaleCalendar.start_date).limit(limit)

    result = await db.execute(query)
    events = result.scalars().all()

    return [
        {
            **serialize_event(event, now, current_user),
            "days_until": (event.start_date - now).days if event.start_date else 0,
        }
        for event in events
    ]


@router.get(
    "/export/csv",
    summary="Экспорт календаря в CSV",
    description="Экспортирует события текущего пользователя и глобальные события в CSV.",
)
async def export_calendar_csv(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Экспорт событий календаря в CSV без внешних библиотек."""
    query = (
        select(SaleCalendar)
        .where(or_(SaleCalendar.is_global.is_(True), SaleCalendar.user_id == current_user.id))
        .order_by(SaleCalendar.start_date)
    )
    result = await db.execute(query)
    events = result.scalars().all()

    csv_buffer = StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow([
        "id",
        "title",
        "marketplace",
        "event_type",
        "start_date",
        "end_date",
        "discount_percent",
        "description",
        "notes",
        "is_global",
    ])

    for event in events:
        writer.writerow([
            event.id,
            event.title,
            event.marketplace,
            event.event_type,
            event.start_date.isoformat() if event.start_date else "",
            event.end_date.isoformat() if event.end_date else "",
            event.discount_percent if event.discount_percent is not None else "",
            event.description or "",
            event.notes or "",
            event.is_global,
        ])

    return Response(
        content=csv_buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=calendar_events.csv"},
    )


def escape_ics_text(value: str | None) -> str:
    """Экранирование спецсимволов для текста iCalendar."""
    if not value:
        return ""
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


@router.get(
    "/export/ics",
    summary="Экспорт календаря в ICS",
    description="Экспортирует события календаря в формате iCalendar (ICS).",
)
async def export_calendar_ics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Экспорт событий календаря в ICS-файл без сторонних зависимостей."""
    query = (
        select(SaleCalendar)
        .where(or_(SaleCalendar.is_global.is_(True), SaleCalendar.user_id == current_user.id))
        .order_by(SaleCalendar.start_date)
    )
    result = await db.execute(query)
    events = result.scalars().all()

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//MegaSharkAI//Calendar//RU",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    for event in events:
        if not event.start_date or not event.end_date:
            continue

        start = event.start_date.strftime("%Y%m%dT%H%M%SZ")
        end = event.end_date.strftime("%Y%m%dT%H%M%SZ")
        uid = f"calendar-event-{event.id}@megashark.ai"

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{timestamp}",
            f"DTSTART:{start}",
            f"DTEND:{end}",
            f"SUMMARY:{escape_ics_text(event.title)}",
            f"DESCRIPTION:{escape_ics_text(event.description)}",
            f"CATEGORIES:{escape_ics_text(event.event_type)}",
            f"LOCATION:{escape_ics_text(event.marketplace)}",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")

    return Response(
        content="\r\n".join(lines),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=calendar_events.ics"},
    )
