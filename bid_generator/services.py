from io import BytesIO

from django.core.files.base import ContentFile
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from core.models import SystemSettings
from core.pdf import add_signature, build_pdf_response, letterhead_elements, styles
from documents.models import CompanyDocument


def build_bid_checklist(bid_pack):
    tender = bid_pack.tender
    requirements = list(tender.requirements.all())
    checklist = [
        'Cover letter',
        'Company profile summary',
        'Price schedule',
        'Signed quotation',
    ]
    checklist.extend(requirement.description for requirement in requirements if requirement.is_mandatory)
    return checklist


def company_document_checklist(company):
    today_docs = company.documents.all()
    required = [
        CompanyDocument.DocumentType.PACRA,
        CompanyDocument.DocumentType.ZRA_TAX_CLEARANCE,
        CompanyDocument.DocumentType.TPIN_CERTIFICATE,
        CompanyDocument.DocumentType.NAPSA,
        CompanyDocument.DocumentType.WORKERS_COMPENSATION,
        CompanyDocument.DocumentType.ZPPA_REGISTRATION,
        CompanyDocument.DocumentType.COMPANY_PROFILE,
    ]
    rows = []
    for doc_type in required:
        docs = [doc for doc in today_docs if doc.document_type == doc_type]
        status = 'Missing'
        if docs:
            status = 'Available'
            if any(doc.is_expired for doc in docs):
                status = 'Expired'
        rows.append((CompanyDocument.DocumentType(doc_type).label, status))
    return rows


def price_schedule_rows(bid_pack):
    if not bid_pack.quotation:
        return []
    return [
        (item.description, item.quantity, item.unit_price, item.line_total)
        for item in bid_pack.quotation.items.all()
    ]


def generate_bid_pack_pdf(bid_pack):
    style = styles()
    settings = SystemSettings.load()
    currency = settings.default_currency or 'ZMW'
    elements = letterhead_elements(bid_pack.company, 'Bid Pack')
    elements.append(Paragraph(f'<b>Tender:</b> {bid_pack.tender.title}', style['BodyText']))
    elements.append(Paragraph(f'<b>Procuring Entity:</b> {bid_pack.tender.procuring_entity}', style['BodyText']))
    elements.append(Paragraph(f'<b>Closing:</b> {bid_pack.tender.closing_at or bid_pack.tender.closing_date or "-"}', style['BodyText']))
    elements.append(Spacer(1, 12))

    sections = build_bid_sections(bid_pack)
    for title, lines in sections:
        elements.append(Paragraph(title, style['SectionTitle']))
        for line in lines:
            elements.append(Paragraph(str(line), style['BodyText']))
        elements.append(Spacer(1, 6))

    if bid_pack.quotation:
        elements.append(Paragraph('Price Schedule', style['SectionTitle']))
        rows = [['Description', 'Qty', 'Unit', 'Total']]
        for description, qty, unit, total in price_schedule_rows(bid_pack):
            rows.append([Paragraph(description, style['BodyText']), str(qty), f'{currency} {unit:,.2f}', f'{currency} {total:,.2f}'])
        rows.append(['', '', 'Grand total', f'{currency} {bid_pack.quotation.total:,.2f}'])
        elements.append(Table(rows, colWidths=[230, 55, 95, 95], style=table_style()))

    elements.append(Paragraph('Company Document Checklist', style['SectionTitle']))
    elements.append(Table([['Document', 'Status'], *company_document_checklist(bid_pack.company)], colWidths=[260, 160], style=table_style()))
    add_signature(elements, label='Authorised signatory')
    return build_pdf_response(elements, f'Bid Pack - {bid_pack.tender.title}')


def generate_bid_pack_docx(bid_pack):
    from docx import Document

    settings = SystemSettings.load()
    currency = settings.default_currency or 'ZMW'
    document = Document()
    document.add_heading(bid_pack.company.name, 0)
    document.add_paragraph(f'TPIN: {bid_pack.company.tpin or "-"}')
    document.add_paragraph(f'Address: {bid_pack.company.address or "-"}')
    document.add_paragraph(f'Email: {bid_pack.company.email or "-"} | Phone: {bid_pack.company.phone or "-"}')
    document.add_heading('Bid Pack', level=1)
    document.add_paragraph(f'Tender: {bid_pack.tender.title}')
    document.add_paragraph(f'Procuring Entity: {bid_pack.tender.procuring_entity}')
    document.add_paragraph(f'Tender Unique ID: {bid_pack.tender.tender_number or "-"}')

    for title, lines in build_bid_sections(bid_pack):
        document.add_heading(title, level=2)
        for line in lines:
            document.add_paragraph(str(line), style='List Bullet' if title.endswith('Checklist') else None)

    document.add_heading('Price Schedule', level=2)
    table = document.add_table(rows=1, cols=4)
    table.style = 'Table Grid'
    for idx, heading in enumerate(['Description', 'Qty', 'Unit', 'Total']):
        table.rows[0].cells[idx].text = heading
    for description, qty, unit, total in price_schedule_rows(bid_pack):
        cells = table.add_row().cells
        cells[0].text = str(description)
        cells[1].text = str(qty)
        cells[2].text = f'{currency} {unit:,.2f}'
        cells[3].text = f'{currency} {total:,.2f}'

    document.add_heading('Company Document Checklist', level=2)
    checklist_table = document.add_table(rows=1, cols=2)
    checklist_table.style = 'Table Grid'
    checklist_table.rows[0].cells[0].text = 'Document'
    checklist_table.rows[0].cells[1].text = 'Status'
    for name, status in company_document_checklist(bid_pack.company):
        cells = checklist_table.add_row().cells
        cells[0].text = name
        cells[1].text = status

    document.add_paragraph('\nAuthorised signatory: ________________________')
    document.add_paragraph(f'Prepared by: {settings.default_prepared_by_name or "________________________"}')
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def build_bid_sections(bid_pack):
    tender = bid_pack.tender
    company = bid_pack.company
    return [
        ('Cover Letter', [
            f'We submit our bid for {tender.title}.',
            f'{company.name} confirms interest and availability to perform the required works/services/supplies.',
        ]),
        ('Form of Bid / Tender Submission Letter', [
            f'We, {company.name}, offer to execute the tender in accordance with the solicitation requirements.',
            'We confirm that our bid remains valid for the required validity period.',
        ]),
        ('Bid Checklist', build_bid_checklist(bid_pack)),
        ('Company Profile Summary', [
            company.profile_summary or f'{company.name} is a registered supplier/contractor.',
            f'TPIN: {company.tpin or "-"}',
            f'PACRA Registration: {company.registration_number or "-"}',
        ]),
        ('Similar Experience Table', [
            'Past contract | Client | Year | Value | Contact person',
            'To be completed with relevant past contracts before submission.',
        ]),
        ('Litigation Declaration Placeholder', [
            'We declare that litigation history will be disclosed truthfully before bid submission.',
        ]),
        ('Power of Attorney Placeholder', [
            'Attach signed power of attorney or board authorisation for the bid signatory where required.',
        ]),
        ('Delivery Period Confirmation', [
            'We confirm delivery/service execution within the period stated in the tender or final contract.',
        ]),
        ('Warranty / Undertaking Letter', [
            'We undertake to provide warranty, support, and compliance commitments where applicable.',
        ]),
    ]


def save_generated_files(bid_pack):
    pdf_bytes = generate_bid_pack_pdf(bid_pack)
    docx_bytes = generate_bid_pack_docx(bid_pack)
    safe_id = bid_pack.pk or 'new'
    bid_pack.generated_pdf.save(f'bid-pack-{safe_id}.pdf', ContentFile(pdf_bytes), save=False)
    bid_pack.generated_docx.save(f'bid-pack-{safe_id}.docx', ContentFile(docx_bytes), save=False)
    bid_pack.save(update_fields=['generated_pdf', 'generated_docx'])


def table_style():
    return TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d9e2ec')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#edf4f3')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
    ])
