"""
CLMStore — PDF Generation Service
Generates invoice and receipt PDFs using reportlab.
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from typing import TYPE_CHECKING

import structlog
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.config.settings import settings

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.payment import Payment

logger = structlog.get_logger()

# Brand colours
CLM_GREEN = colors.HexColor("#1B8C4E")
CLM_DARK = colors.HexColor("#1A1A2E")
CLM_LIGHT = colors.HexColor("#F5F5F5")
CLM_GREY = colors.HexColor("#666666")


def _currency(amount: float) -> str:
    return f"Le {amount:,.0f}"


def _build_header(elements: list, title: str, doc_number: str, date: datetime) -> None:
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "clm_title",
        parent=styles["Heading1"],
        fontSize=22,
        textColor=CLM_GREEN,
        spaceAfter=2,
    )
    sub_style = ParagraphStyle(
        "clm_sub",
        parent=styles["Normal"],
        fontSize=10,
        textColor=CLM_GREY,
    )
    doc_style = ParagraphStyle(
        "clm_doc",
        parent=styles["Normal"],
        fontSize=11,
        textColor=CLM_DARK,
        spaceAfter=2,
    )

    elements.append(Paragraph("CLMStore", title_style))
    elements.append(Paragraph("Food Delivery Marketplace — Sierra Leone", sub_style))
    elements.append(Spacer(1, 8 * mm))

    header_data = [
        [Paragraph(f"<b>{title}</b>", doc_style), Paragraph(f"<b>#{doc_number}</b>", doc_style)],
        ["", Paragraph(f"Date: {date.strftime('%d %B %Y')}", sub_style)],
    ]
    header_table = Table(header_data, colWidths=[100 * mm, 80 * mm])
    header_table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 4 * mm))

    # Divider line
    line = Table([[""]], colWidths=[180 * mm], rowHeights=[1])
    line.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), CLM_GREEN)]))
    elements.append(line)
    elements.append(Spacer(1, 6 * mm))


def _build_parties(elements: list, order: "Order") -> None:
    styles = getSampleStyleSheet()
    label_style = ParagraphStyle("lbl", parent=styles["Normal"], fontSize=9, textColor=CLM_GREY)
    value_style = ParagraphStyle("val", parent=styles["Normal"], fontSize=10, textColor=CLM_DARK)

    customer = getattr(order, "customer", None)
    restaurant = getattr(order, "restaurant", None)
    addr = order.delivery_address_snapshot or {}

    from_block = [
        Paragraph("FROM", label_style),
        Paragraph(f"<b>{restaurant.name if restaurant else 'Restaurant'}</b>", value_style),
        Paragraph(restaurant.address if restaurant and restaurant.address else "", value_style),
        Paragraph("Freetown, Sierra Leone", value_style),
    ]
    to_block = [
        Paragraph("BILL TO", label_style),
        Paragraph(
            f"<b>{customer.first_name} {customer.last_name}</b>" if customer else "<b>Customer</b>",
            value_style,
        ),
        Paragraph(addr.get("address_line", ""), value_style),
        Paragraph(customer.email if customer else "", value_style),
    ]

    party_data = [[from_block, to_block]]
    party_table = Table(party_data, colWidths=[90 * mm, 90 * mm])
    party_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(party_table)
    elements.append(Spacer(1, 8 * mm))


def _build_items_table(elements: list, order: "Order") -> None:
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle("th", parent=styles["Normal"], fontSize=9, textColor=colors.white)
    cell_style = ParagraphStyle("td", parent=styles["Normal"], fontSize=9, textColor=CLM_DARK)

    rows = [[
        Paragraph("Item", header_style),
        Paragraph("Qty", header_style),
        Paragraph("Unit Price", header_style),
        Paragraph("Total", header_style),
    ]]

    for item in (order.items or []):
        rows.append([
            Paragraph(item.name, cell_style),  # name is snapshotted on order items
            Paragraph(str(item.quantity), cell_style),
            Paragraph(_currency(item.unit_price), cell_style),
            Paragraph(_currency(item.unit_price * item.quantity), cell_style),
        ])

    items_table = Table(rows, colWidths=[85 * mm, 20 * mm, 38 * mm, 37 * mm])
    items_table.setStyle(TableStyle([
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), CLM_GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        # Body rows
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CLM_LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CCCCCC")),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 6 * mm))


def _build_totals(elements: list, order: "Order") -> None:
    styles = getSampleStyleSheet()
    label_style = ParagraphStyle("tot_lbl", parent=styles["Normal"], fontSize=9, textColor=CLM_GREY)
    value_style = ParagraphStyle("tot_val", parent=styles["Normal"], fontSize=9, textColor=CLM_DARK)
    total_lbl = ParagraphStyle("grand_lbl", parent=styles["Normal"], fontSize=11, textColor=colors.white)
    total_val = ParagraphStyle("grand_val", parent=styles["Normal"], fontSize=11, textColor=colors.white)

    rows = [
        [Paragraph("Subtotal", label_style), Paragraph(_currency(order.subtotal), value_style)],
        [Paragraph("Delivery Fee", label_style), Paragraph(_currency(order.delivery_fee), value_style)],
        [Paragraph("Service Fee", label_style), Paragraph(_currency(order.service_fee), value_style)],
    ]
    if order.discount_amount and order.discount_amount > 0:
        rows.append([
            Paragraph("Discount", label_style),
            Paragraph(f"- {_currency(order.discount_amount)}", value_style),
        ])
    rows.append([
        Paragraph("<b>TOTAL</b>", total_lbl),
        Paragraph(f"<b>{_currency(order.total_amount)}</b>", total_val),
    ])

    totals_table = Table(rows, colWidths=[130 * mm, 50 * mm])
    style_cmds = [
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.5, CLM_DARK),
        ("BACKGROUND", (0, -1), (-1, -1), CLM_GREEN),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
        ("TOPPADDING", (0, -1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 5),
    ]
    totals_table.setStyle(TableStyle(style_cmds))
    elements.append(totals_table)


def _build_footer(elements: list, order_number: str) -> None:
    styles = getSampleStyleSheet()
    footer_style = ParagraphStyle(
        "footer", parent=styles["Normal"], fontSize=8, textColor=CLM_GREY, alignment=1
    )
    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(
        f"Order Reference: {order_number} | Thank you for choosing CLMStore!",
        footer_style,
    ))
    elements.append(Paragraph(
        "CLMStore | Freetown, Sierra Leone | support@clmstore.sl | +232 76 000 000",
        footer_style,
    ))


def generate_invoice_pdf(order: "Order", invoice_number: str) -> bytes:
    """Generate an invoice PDF and return raw bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    elements: list = []
    _build_header(elements, "TAX INVOICE", invoice_number, datetime.utcnow())
    _build_parties(elements, order)
    _build_items_table(elements, order)
    _build_totals(elements, order)
    _build_footer(elements, order.order_number)

    doc.build(elements)
    return buffer.getvalue()


def generate_receipt_pdf(order: "Order", receipt_number: str, payment: "Payment") -> bytes:
    """Generate a payment receipt PDF and return raw bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    label_style = ParagraphStyle("rl", parent=styles["Normal"], fontSize=9, textColor=CLM_GREY)
    value_style = ParagraphStyle("rv", parent=styles["Normal"], fontSize=10, textColor=CLM_DARK)

    elements: list = []
    _build_header(elements, "PAYMENT RECEIPT", receipt_number, datetime.utcnow())
    _build_parties(elements, order)
    _build_items_table(elements, order)
    _build_totals(elements, order)

    # Payment details block
    elements.append(Spacer(1, 8 * mm))
    pay_rows = [
        [Paragraph("Payment Method", label_style), Paragraph(str(payment.provider.value).replace("_", " ").title(), value_style)],
        [Paragraph("Transaction ID", label_style), Paragraph(payment.provider_ref or "—", value_style)],
        [Paragraph("Payment Status", label_style), Paragraph("PAID", ParagraphStyle("paid", parent=styles["Normal"], fontSize=10, textColor=CLM_GREEN))],
        [Paragraph("Amount Paid", label_style), Paragraph(f"<b>{_currency(payment.amount)}</b>", value_style)],
    ]
    pay_table = Table(pay_rows, colWidths=[60 * mm, 120 * mm])
    pay_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.HexColor("#EEEEEE")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(pay_table)

    _build_footer(elements, order.order_number)
    doc.build(elements)
    return buffer.getvalue()


async def save_pdf(pdf_bytes: bytes, filename: str, subfolder: str = "invoices") -> str:
    """
    Saves PDF bytes to local disk or S3 and returns the public URL.
    """
    import aiofiles

    if settings.USE_S3:
        import boto3
        from botocore.exceptions import ClientError
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            endpoint_url=settings.S3_ENDPOINT_URL,
            region_name=settings.S3_REGION,
        )
        key = f"{subfolder}/{filename}"
        try:
            s3.put_object(
                Bucket=settings.S3_BUCKET,
                Key=key,
                Body=pdf_bytes,
                ContentType="application/pdf",
                ACL="public-read",
            )
            return f"{settings.CDN_BASE_URL}/{key}"
        except ClientError as e:
            logger.error("pdf_s3_upload_failed", error=str(e))
            raise

    # Local disk storage
    local_dir = os.path.join(settings.UPLOAD_DIR, subfolder)
    os.makedirs(local_dir, exist_ok=True)
    local_path = os.path.join(local_dir, filename)
    async with aiofiles.open(local_path, "wb") as f:
        await f.write(pdf_bytes)
    return f"/static/uploads/{subfolder}/{filename}"
