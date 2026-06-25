import re

from docx import Document as DocxDocument
from pypdf import PdfReader

from .models import CompanyDocument


def extract_text_from_company_document(document):
    parts = [document.title or '', document.notes or '']
    path = document.file.path if document.file else ''
    try:
        lower = path.lower()
        if lower.endswith('.pdf'):
            reader = PdfReader(path)
            parts.extend(page.extract_text() or '' for page in reader.pages)
        elif lower.endswith('.docx'):
            docx = DocxDocument(path)
            parts.extend(paragraph.text for paragraph in docx.paragraphs)
    except Exception:
        pass
    return '\n'.join(parts)


def sync_company_profile_from_documents(company):
    documents = list(company.documents.all())
    corpus = '\n'.join(extract_text_from_company_document(doc) for doc in documents)
    pacra_corpus = '\n'.join(
        extract_text_from_company_document(doc)
        for doc in documents
        if doc.document_type == CompanyDocument.DocumentType.PACRA
    )
    updates = {}
    if not company.tpin:
        tpin = find_tpin(corpus)
        if tpin:
            updates['tpin'] = tpin
    if not company.registration_number:
        registration = find_registration_number(pacra_corpus)
        if registration:
            updates['registration_number'] = registration

    for field, value in updates.items():
        setattr(company, field, value)
    if updates:
        company.save(update_fields=list(updates))
    return updates


def find_tpin(text):
    match = re.search(r'\b(?:tpin|taxpayer identification number)\D{0,30}(\d{10})\b', text, re.IGNORECASE)
    if match:
        return match.group(1)
    return ''


def find_registration_number(text):
    patterns = [
        r'\b(?:company|business|pacra)\s+registration\s+(?:number|no\.?)\D{0,20}([A-Z0-9][A-Z0-9/\-]{4,30})',
        r'\b(?:incorporation|certificate)\s+(?:number|no\.?)\D{0,20}([A-Z0-9][A-Z0-9/\-]{4,30})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip(' .,:;')
            if any(char.isdigit() for char in value):
                return value
    return ''
