from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from core.models import SystemSettings
from core.pdf import add_signature, build_pdf_response, letterhead_elements, styles


def commercial_document_pdf(document, title):
    style = styles()
    settings = SystemSettings.load()
    currency = settings.default_currency or 'ZMW'
    elements = letterhead_elements(document.company, title)
    meta = [
        ['Document number', document.number],
        ['Date', document.date.strftime('%d/%m/%Y')],
        ['Customer', document.customer_name],
        ['Customer TPIN', document.customer_tpin or '-'],
        ['Customer address', document.customer_address or '-'],
    ]
    if hasattr(document, 'validity_period_days'):
        meta.append(['Validity', f'{document.validity_period_days} days'])
    if hasattr(document, 'due_date'):
        meta.append(['Due date', document.due_date.strftime('%d/%m/%Y') if document.due_date else '-'])
    elements.append(Table(meta, colWidths=[120, 340], style=table_style()))
    elements.append(Spacer(1, 12))

    rows = [['Description', 'Qty', 'Unit price', 'Total']]
    for item in document.items.all():
        rows.append([
            Paragraph(item.description, style['BodyText']),
            f'{item.quantity}',
            f'{currency} {item.unit_price:,.2f}',
            f'{currency} {item.line_total:,.2f}',
        ])
    rows.extend([
        ['', '', 'Subtotal', f'{currency} {document.subtotal:,.2f}'],
        ['', '', f'Tax ({document.get_tax_type_display()})', f'{currency} {document.tax_amount:,.2f}'],
        ['', '', 'Total', f'{currency} {document.total:,.2f}'],
    ])
    elements.append(Table(rows, colWidths=[230, 55, 95, 95], style=table_style(header=True)))
    if document.company.bank_details.exists():
        bank = document.company.bank_details.first()
        elements.append(Paragraph('Bank details', style['SectionTitle']))
        elements.append(Paragraph(
            f'{bank.bank_name} | {bank.branch or "-"} | {bank.account_name} | {bank.account_number} | SWIFT: {bank.swift_code or "-"}',
            style['BodyText'],
        ))
    if document.notes:
        elements.append(Paragraph('Notes', style['SectionTitle']))
        elements.append(Paragraph(document.notes, style['BodyText']))
    add_signature(elements)
    return build_pdf_response(elements, title)


def pdf_http_response(document, title, filename):
    response = HttpResponse(commercial_document_pdf(document, title), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def table_style(header=False):
    commands = [
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d9e2ec')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
    ]
    if header:
        commands.extend([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#edf4f3')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (-2, -3), (-1, -1), 'Helvetica-Bold'),
        ])
    return TableStyle(commands)
