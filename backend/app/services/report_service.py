"""
Сервис генерации отчётов по товарам и конкурентам.

Поддерживает два формата:
- XLSX (openpyxl) — выгрузка таблицы товаров.
- PDF (weasyprint) — сводный отчёт с ключевыми метриками.
"""

import io
from datetime import datetime
from typing import Any

from app.core.datetime_utils import utcnow

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product


async def build_report_data(db: AsyncSession, user_id) -> dict[str, Any]:
    """Собрать данные для отчёта: товары пользователя и агрегаты."""
    products = (
        await db.execute(
            select(Product)
            .where(Product.user_id == user_id)
            .order_by(Product.is_competitor, Product.name)
        )
    ).scalars().all()

    own = [p for p in products if not p.is_competitor]
    competitors = [p for p in products if p.is_competitor]

    def avg_price(items: list[Product]) -> float:
        prices = [float(p.price) for p in items if p.price and p.price > 0]
        return round(sum(prices) / len(prices), 2) if prices else 0.0

    return {
        "generated_at": utcnow(),
        "products": products,
        "own_count": len(own),
        "competitor_count": len(competitors),
        "own_avg_price": avg_price(own),
        "competitor_avg_price": avg_price(competitors),
    }


def generate_xlsx(report: dict[str, Any]) -> bytes:
    """Сформировать XLSX-файл с таблицей товаров."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Товары"

    headers = [
        "Тип", "Название", "Бренд", "Категория", "Маркетплейс",
        "Цена", "Старая цена", "Скидка %", "Рейтинг", "Отзывы",
    ]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for product in report["products"]:
        sheet.append([
            "Конкурент" if product.is_competitor else "Свой",
            product.name,
            product.brand or "",
            product.category or "",
            product.marketplace,
            product.price or 0,
            product.old_price or "",
            product.discount or "",
            product.rating or "",
            product.reviews_count or 0,
        ])

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _report_html(report: dict[str, Any]) -> str:
    """HTML-шаблон сводного отчёта для PDF."""
    generated = report["generated_at"].strftime("%d.%m.%Y %H:%M")
    rows = "".join(
        f"<tr><td>{'Конкурент' if p.is_competitor else 'Свой'}</td>"
        f"<td>{(p.name or '')[:60]}</td><td>{p.marketplace}</td>"
        f"<td style='text-align:right'>{int(p.price) if p.price else '—'} ₽</td></tr>"
        for p in report["products"][:200]
    )
    return f"""
    <html>
    <head><meta charset="utf-8">
    <style>
        body {{ font-family: 'DejaVu Sans', Arial, sans-serif; color: #1e293b; font-size: 12px; }}
        h1 {{ font-size: 20px; }}
        .metrics {{ margin: 16px 0; }}
        .metric {{ display: inline-block; margin-right: 24px; }}
        .metric .value {{ font-size: 18px; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
        th, td {{ border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; }}
        th {{ background: #f1f5f9; }}
    </style></head>
    <body>
        <h1>Отчёт по товарам и конкурентам</h1>
        <p>Сформировано: {generated}</p>
        <div class="metrics">
            <div class="metric"><div class="value">{report['own_count']}</div>Своих товаров</div>
            <div class="metric"><div class="value">{report['competitor_count']}</div>Конкурентов</div>
            <div class="metric"><div class="value">{int(report['own_avg_price'])} ₽</div>Средняя своя цена</div>
            <div class="metric"><div class="value">{int(report['competitor_avg_price'])} ₽</div>Средняя цена конкурентов</div>
        </div>
        <table>
            <thead><tr><th>Тип</th><th>Название</th><th>Маркетплейс</th><th>Цена</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </body>
    </html>
    """


def generate_pdf(report: dict[str, Any]) -> bytes:
    """Сформировать PDF-отчёт через weasyprint."""
    from weasyprint import HTML

    html = _report_html(report)
    return HTML(string=html).write_pdf()


async def generate_competitor_report(
    db: AsyncSession,
    user_id,
    fmt: str = "xlsx",
) -> tuple[bytes, str, str]:
    """
    Сгенерировать отчёт пользователя в выбранном формате.

    Returns:
        (содержимое_файла, имя_файла, media_type)
    """
    report = await build_report_data(db, user_id)
    timestamp = utcnow().strftime("%Y%m%d_%H%M%S")

    if fmt == "pdf":
        content = generate_pdf(report)
        return content, f"megashark_report_{timestamp}.pdf", "application/pdf"

    content = generate_xlsx(report)
    return (
        content,
        f"megashark_report_{timestamp}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
