"""
Printable/downloadable receipt generation for the ``payments`` app
(CPMAS-21, BRD 5.19: "Generates printable/downloadable receipts for
recorded payments").

Kept separate from services.py: this is presentation (rendering a
Receipt to bytes), not business logic -- nothing here reads or writes
the database, it only formats an already-fetched Receipt instance.
"""
import io

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from .models import Receipt


def render_receipt_pdf(receipt: Receipt) -> bytes:
    """
    Render a single Receipt as a one-page PDF, matching the field list
    BRD 5.19 specifies: Receipt number, Payment, Client/supplier, Date,
    Amount, Payment method, Reference. (Currency is out of scope for
    this version -- see ReceiptSerializer's docstring.)
    """
    buffer = io.BytesIO()
    doc = canvas.Canvas(buffer, pagesize=letter)
    page_width, _ = letter

    left_margin = 1 * inch
    y = 10 * inch

    doc.setFont('Helvetica-Bold', 18)
    doc.drawString(left_margin, y, "Payment Receipt")
    y -= 0.4 * inch

    doc.setFont('Helvetica', 10)
    doc.drawString(left_margin, y, f"Receipt #: {receipt.receipt_number}")
    y -= 0.3 * inch

    party_name = None
    payment = receipt.payment
    if payment.client_id:
        party_name = payment.client.name
    elif payment.supplier_id:
        party_name = payment.supplier.name

    rows = [
        ("Date", receipt.receipt_date.isoformat()),
        ("Payment #", payment.payment_number),
        ("Client / Supplier", party_name or "-"),
        ("Payment method", payment.payment_method),
        ("Reference", receipt.reference or "-"),
    ]
    for label, value in rows:
        doc.drawString(left_margin, y, f"{label}: {value}")
        y -= 0.3 * inch

    y -= 0.2 * inch
    doc.setFont('Helvetica-Bold', 14)
    doc.drawString(left_margin, y, f"Amount: {receipt.amount}")

    doc.showPage()
    doc.save()
    return buffer.getvalue()
