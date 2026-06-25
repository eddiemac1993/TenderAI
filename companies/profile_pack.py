from io import BytesIO

from django.utils.text import slugify
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph, Spacer

from core.pdf import build_pdf_response, letterhead_elements, styles
from documents.models import CompanyDocument


CERTIFICATE_TYPES = {
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
    CompanyDocument.DocumentType.BANK_CONFIRMATION,
}


def build_company_profile_pack(company):
    writer = PdfWriter()
    skipped = []
    profile_document = latest_profile_document(company)

    if profile_document and is_pdf(profile_document):
        append_document_pdf(writer, profile_document)
    else:
        append_pdf_bytes(writer, generated_company_profile_summary(company, profile_document))
        if profile_document:
            skipped.append(f'{profile_document.get_document_type_display()} is not a PDF: {profile_document.file.name}')

    for document in certificate_documents(company):
        if is_pdf(document):
            append_pdf_bytes(writer, document_divider_pdf(document))
            append_document_pdf(writer, document)
        else:
            skipped.append(f'{document.get_document_type_display()} is not a PDF: {document.file.name}')

    if skipped:
        append_pdf_bytes(writer, skipped_documents_pdf(company, skipped))

    buffer = BytesIO()
    writer.write(buffer)
    buffer.seek(0)
    filename = f'{slugify(company.name) or "company"}-profile-pack.pdf'
    return buffer, filename


def latest_profile_document(company):
    return (
        company.documents
        .filter(document_type=CompanyDocument.DocumentType.COMPANY_PROFILE)
        .order_by('-uploaded_at', '-id')
        .first()
    )


def certificate_documents(company):
    return (
        company.documents
        .filter(document_type__in=CERTIFICATE_TYPES)
        .exclude(file='')
        .order_by('document_type', '-expiry_date', '-uploaded_at')
    )


def is_pdf(document):
    return bool(document.file and document.file.name.lower().endswith('.pdf'))


def append_document_pdf(writer, company_document):
    with company_document.file.open('rb') as handle:
        reader = PdfReader(handle)
        for page in reader.pages:
            writer.add_page(page)


def append_pdf_bytes(writer, pdf_bytes):
    reader = PdfReader(BytesIO(pdf_bytes))
    for page in reader.pages:
        writer.add_page(page)


def generated_company_profile_summary(company, profile_document=None):
    style = styles()
    elements = letterhead_elements(company, 'Company Profile')
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(company.profile_summary or f'{company.name} is a registered supplier/contractor.', style['BodyText']))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f'<b>TPIN:</b> {company.tpin or "-"}', style['BodyText']))
    elements.append(Paragraph(f'<b>PACRA Registration:</b> {company.registration_number or "-"}', style['BodyText']))
    elements.append(Paragraph(f'<b>Email:</b> {company.email or "-"}', style['BodyText']))
    elements.append(Paragraph(f'<b>Phone:</b> {company.phone or "-"}', style['BodyText']))
    elements.append(Paragraph(f'<b>Address:</b> {company.address or "-"}', style['BodyText']))
    if profile_document:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f'Uploaded company profile file: {profile_document.file.name}', style['SmallMuted']))
    return build_pdf_response(elements, f'Company Profile - {company.name}')


def document_divider_pdf(company_document):
    style = styles()
    title_style = style['Title'].clone('DocumentDividerTitle')
    title_style.alignment = 1
    title_style.fontSize = 28
    title_style.leading = 34
    elements = [
        Spacer(1, A4[1] * 0.36),
        Paragraph(f'<b>{company_document.get_document_type_display()}</b>', title_style),
    ]
    return build_pdf_response(elements, f'Attachment - {company_document.get_document_type_display()}')


def skipped_documents_pdf(company, skipped):
    style = styles()
    elements = letterhead_elements(company, 'Documents Not Attached')
    elements.append(Paragraph('These uploaded documents were not attached because they are not PDF files:', style['BodyText']))
    for item in skipped:
        elements.append(Paragraph(f'- {item}', style['BodyText']))
    return build_pdf_response(elements, f'Skipped Documents - {company.name}')
