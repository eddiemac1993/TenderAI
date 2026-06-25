import re

from docx import Document as DocxDocument
from pypdf import PdfReader


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
    corpus = '\n'.join(extract_text_from_company_document(doc) for doc in company.documents.all())
    updates = {}
    if not company.tpin:
        tpin = find_tpin(corpus)
        if tpin:
            updates['tpin'] = tpin
    if not company.registration_number:
        registration = find_registration_number(corpus)
        if registration:
            updates['registration_number'] = registration
    if not company.email:
        email = find_email(corpus)
        if email:
            updates['email'] = email
    if not company.phone:
        phone = find_phone(corpus)
        if phone:
            updates['phone'] = phone

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
        r'\b(?:pacra|company|business|incorporation|registration)\s*(?:number|no\.?|#)?\D{0,30}([A-Z0-9][A-Z0-9/\-]{3,30})',
        r'\b([0-9]{6,}/[0-9]{1,}|[A-Z]{2,}[0-9][A-Z0-9/\-]{3,})\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip(' .,:;')
            if not value.isdigit() or len(value) >= 6:
                return value
    return ''


def find_email(text):
    match = re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', text)
    return match.group(0) if match else ''


def find_phone(text):
    match = re.search(r'(?:\+?260|0)\s?\d{2}\s?\d{3}\s?\d{4}', text)
    return re.sub(r'\s+', ' ', match.group(0)).strip() if match else ''
