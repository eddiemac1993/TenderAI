from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import SystemSettings


def build_pdf_response(elements, title):
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=title,
    )
    document.build(elements)
    return buffer.getvalue()


def styles():
    base = getSampleStyleSheet()
    base.add(ParagraphStyle(name='SmallMuted', parent=base['BodyText'], fontSize=8, textColor=colors.grey))
    base.add(ParagraphStyle(name='SectionTitle', parent=base['Heading2'], fontSize=12, spaceBefore=10, spaceAfter=6))
    return base


def letterhead_elements(company, document_title):
    settings = SystemSettings.load()
    style = styles()
    elements = []
    if settings.letterhead:
        try:
            elements.append(Image(settings.letterhead.path, width=170 * mm, height=28 * mm, kind='proportional'))
            elements.append(Spacer(1, 6))
        except Exception:
            pass
    elements.append(Paragraph(f'<b>{company.name}</b>', style['Title']))
    details = [
        f'TPIN: {company.tpin or "-"}',
        company.address or '',
        company.email or '',
        company.phone or '',
    ]
    elements.append(Paragraph(' | '.join([item for item in details if item]), style['SmallMuted']))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f'<b>{document_title}</b>', style['Heading1']))
    return elements


def add_signature(elements, label='Prepared by'):
    settings = SystemSettings.load()
    style = styles()
    elements.append(Spacer(1, 24))
    elements.append(Paragraph(f'{label}: {settings.default_prepared_by_name or "________________________"}', style['BodyText']))
    if settings.signature:
        try:
            elements.append(Image(settings.signature.path, width=45 * mm, height=18 * mm, kind='proportional'))
        except Exception:
            pass
    elements.append(Paragraph('Signature: ________________________', style['BodyText']))
