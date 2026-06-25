from io import BytesIO

from django.core.files.base import ContentFile
from django.http import HttpResponse
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.platypus import PageBreak, Paragraph, Spacer, Table, TableStyle

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


def requirements_matrix_rows(bid_pack):
    rows = []
    for requirement in bid_pack.tender.requirements.all():
        rows.append((
            requirement.get_requirement_type_display(),
            requirement.description,
            'Yes' if requirement.is_mandatory else 'No',
            'To confirm / attach',
        ))
    if not rows:
        rows.append((
            'General',
            'No solicitation requirements have been extracted yet. Upload/analyse the solicitation document before final submission.',
            'Yes',
            'Pending analysis',
        ))
    return rows


def table_of_contents():
    return [
        'Tender Summary',
        'Solicitation Requirements Matrix',
        'Cover Letter',
        'Form of Bid / Tender Submission Letter',
        'Bid Checklist',
        'Company Profile Summary',
        'Price Schedule',
        'Company Document Checklist',
        'Similar Experience Table',
        'Litigation Declaration',
        'Power of Attorney',
        'Delivery Period Confirmation',
        'Warranty / Undertaking Letter',
        'Signature Section',
    ]


def company_document_checklist(company):
    today_docs = company.documents.all()
    required = [
        CompanyDocument.DocumentType.PACRA,
        CompanyDocument.DocumentType.ZRA_TAX_CLEARANCE,
        CompanyDocument.DocumentType.TPIN_CERTIFICATE,
        CompanyDocument.DocumentType.NAPSA,
        CompanyDocument.DocumentType.WORKERS_COMPENSATION,
        CompanyDocument.DocumentType.NCC,
        CompanyDocument.DocumentType.NCC_B,
        CompanyDocument.DocumentType.NCC_R,
        CompanyDocument.DocumentType.NCC_E,
        CompanyDocument.DocumentType.ERB,
        CompanyDocument.DocumentType.EIZ_CERTIFICATE,
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
    elements = []
    add_pdf_cover_page(elements, bid_pack)
    elements.append(PageBreak())
    add_pdf_table_of_contents(elements)
    elements.append(PageBreak())

    sections = build_bid_sections(bid_pack)
    for number, (title, lines) in enumerate(sections, start=1):
        elements.append(Paragraph(f'{number}. {title}', style['SectionTitle']))
        for line in lines:
            elements.append(Paragraph(str(line), style['BodyText']))
        elements.append(Spacer(1, 6))

        if title == 'Solicitation Requirements Matrix':
            rows = [['Type', 'Requirement', 'Mandatory', 'Action']]
            rows.extend([
                [kind, Paragraph(description, style['BodyText']), mandatory, action]
                for kind, description, mandatory, action in requirements_matrix_rows(bid_pack)
            ])
            elements.append(Table(rows, colWidths=[95, 215, 65, 100], style=table_style()))
            elements.append(Spacer(1, 6))

        if title == 'Price Schedule' and bid_pack.quotation:
            rows = [['Description', 'Qty', 'Unit', 'Total']]
            for description, qty, unit, total in price_schedule_rows(bid_pack):
                rows.append([Paragraph(description, style['BodyText']), str(qty), f'{currency} {unit:,.2f}', f'{currency} {total:,.2f}'])
            rows.append(['', '', 'Grand total', f'{currency} {bid_pack.quotation.total:,.2f}'])
            elements.append(Table(rows, colWidths=[230, 55, 95, 95], style=table_style()))
            elements.append(Spacer(1, 6))

        if title == 'Company Document Checklist':
            elements.append(Table([['Document', 'Status'], *company_document_checklist(bid_pack.company)], colWidths=[260, 160], style=table_style()))
            elements.append(Spacer(1, 6))

    add_signature(elements, label='Authorised signatory')
    main_pdf = build_pdf_response(elements, f'Bid Pack - {bid_pack.tender.title}')
    return append_company_certificate_pdfs(main_pdf, bid_pack)


def generate_bid_pack_docx(bid_pack):
    from docx import Document

    settings = SystemSettings.load()
    currency = settings.default_currency or 'ZMW'
    document = Document()
    add_docx_cover_page(document, bid_pack)
    document.add_page_break()
    add_docx_table_of_contents(document)
    document.add_page_break()

    for number, (title, lines) in enumerate(build_bid_sections(bid_pack), start=1):
        document.add_heading(f'{number}. {title}', level=1)
        for line in lines:
            document.add_paragraph(str(line), style='List Bullet' if title.endswith('Checklist') else None)

        if title == 'Solicitation Requirements Matrix':
            table = document.add_table(rows=1, cols=4)
            table.style = 'Table Grid'
            for idx, heading in enumerate(['Type', 'Requirement', 'Mandatory', 'Action']):
                table.rows[0].cells[idx].text = heading
            for kind, description, mandatory, action in requirements_matrix_rows(bid_pack):
                cells = table.add_row().cells
                cells[0].text = kind
                cells[1].text = description
                cells[2].text = mandatory
                cells[3].text = action

        if title == 'Price Schedule' and bid_pack.quotation:
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

        if title == 'Company Document Checklist':
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


def add_pdf_cover_page(elements, bid_pack):
    style = styles()
    company = bid_pack.company
    tender = bid_pack.tender
    elements.extend(letterhead_elements(company, 'Bid Submission Pack'))
    elements.append(Spacer(1, 30))
    elements.append(Paragraph(f'<b>Tender:</b> {tender.title}', style['Heading2']))
    elements.append(Paragraph(f'<b>Procuring Entity:</b> {tender.procuring_entity}', style['BodyText']))
    elements.append(Paragraph(f'<b>Tender Unique ID:</b> {tender.tender_number or "-"}', style['BodyText']))
    elements.append(Paragraph(f'<b>ZPPA Resource ID:</b> {tender.zppa_resource_id or "-"}', style['BodyText']))
    elements.append(Paragraph(f'<b>Closing Date:</b> {tender.closing_at or tender.closing_date or "-"}', style['BodyText']))
    elements.append(Spacer(1, 26))
    elements.append(Paragraph(f'<b>Submitted by:</b> {company.name}', style['BodyText']))
    elements.append(Paragraph(f'<b>TPIN:</b> {company.tpin or "-"}', style['BodyText']))
    elements.append(Paragraph(f'<b>Address:</b> {company.address or "-"}', style['BodyText']))
    elements.append(Paragraph(f'<b>Email / Phone:</b> {company.email or "-"} / {company.phone or "-"}', style['BodyText']))


def add_pdf_table_of_contents(elements):
    style = styles()
    elements.append(Paragraph('Table of Contents', style['Heading1']))
    rows = [['No.', 'Section']]
    rows.extend([[str(index), title] for index, title in enumerate(table_of_contents(), start=1)])
    elements.append(Table(rows, colWidths=[45, 390], style=table_style()))


def append_company_certificate_pdfs(main_pdf, bid_pack):
    pdf_documents = [
        document for document in bid_pack.company.documents.all()
        if document.file and document.file.name.lower().endswith('.pdf')
    ]
    if not pdf_documents:
        return main_pdf

    writer = PdfWriter()
    append_pdf_bytes(writer, main_pdf)
    for document in pdf_documents:
        try:
            divider = certificate_divider_pdf(document)
            append_pdf_bytes(writer, divider)
            with document.file.open('rb') as handle:
                reader = PdfReader(handle)
                for page in reader.pages:
                    writer.add_page(page)
        except Exception:
            continue

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def append_pdf_bytes(writer, pdf_bytes):
    reader = PdfReader(BytesIO(pdf_bytes))
    for page in reader.pages:
        writer.add_page(page)


def certificate_divider_pdf(company_document):
    style = styles()
    elements = [
        Paragraph('Company Certificate Attachment', style['Heading1']),
        Spacer(1, 18),
        Paragraph(f'<b>Document:</b> {company_document.get_document_type_display()}', style['BodyText']),
        Paragraph(f'<b>Title:</b> {company_document.title}', style['BodyText']),
        Paragraph(f'<b>Issue Date:</b> {company_document.issue_date or "-"}', style['BodyText']),
        Paragraph(f'<b>Expiry Date:</b> {company_document.expiry_date or "No expiry"}', style['BodyText']),
    ]
    return build_pdf_response(elements, f'Attachment - {company_document.title}')


def add_docx_cover_page(document, bid_pack):
    company = bid_pack.company
    tender = bid_pack.tender
    document.add_heading('Bid Submission Pack', 0)
    document.add_paragraph(f'Tender: {tender.title}')
    document.add_paragraph(f'Procuring Entity: {tender.procuring_entity}')
    document.add_paragraph(f'Tender Unique ID: {tender.tender_number or "-"}')
    document.add_paragraph(f'ZPPA Resource ID: {tender.zppa_resource_id or "-"}')
    document.add_paragraph(f'Closing Date: {tender.closing_at or tender.closing_date or "-"}')
    document.add_paragraph('')
    document.add_heading('Submitted by', level=1)
    document.add_paragraph(company.name)
    document.add_paragraph(f'TPIN: {company.tpin or "-"}')
    document.add_paragraph(f'Address: {company.address or "-"}')
    document.add_paragraph(f'Email: {company.email or "-"}')
    document.add_paragraph(f'Phone: {company.phone or "-"}')


def add_docx_table_of_contents(document):
    document.add_heading('Table of Contents', level=1)
    for index, title in enumerate(table_of_contents(), start=1):
        document.add_paragraph(f'{index}. {title}')


def build_bid_sections(bid_pack):
    tender = bid_pack.tender
    company = bid_pack.company
    return [
        ('Tender Summary', [
            f'Tender title: {tender.title}',
            f'Procuring entity: {tender.procuring_entity}',
            f'Tender number / unique ID: {tender.tender_number or "-"}',
            f'Procurement method: {tender.procurement_method or "-"}',
            f'Submission method: {tender.submission_method or "-"}',
            f'Bid security: {tender.bid_security_amount or "To confirm from solicitation document"}',
            f'Participation fee: {tender.participation_fee or "-"}',
            f'Closing date: {tender.closing_at or tender.closing_date or "-"}',
        ]),
        ('Solicitation Requirements Matrix', [
            'The requirements below are generated from the tender requirements captured for this solicitation document.',
        ]),
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
        ('Price Schedule', [
            'Attach the priced quotation or bill of quantities for this bid.'
            if not bid_pack.quotation
            else 'The attached price schedule is generated from the linked quotation.',
        ]),
        ('Company Document Checklist', [
            'Confirm that each mandatory company document is attached and valid at submission date.',
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
