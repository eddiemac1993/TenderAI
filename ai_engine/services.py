import re
from textwrap import shorten

from docx import Document as DocxDocument
from pypdf import PdfReader

from .models import SolicitationDocument, TenderAnalysisRun
from tenders.models import TenderRequirement


class PlaceholderTenderAnalysisService:
    """Replace this class with an OpenAI-backed extractor when API access is configured."""

    DEFAULT_REQUIREMENTS = [
        (TenderRequirement.RequirementType.MANDATORY_DOCUMENT, 'Valid PACRA company registration document'),
        (TenderRequirement.RequirementType.MANDATORY_DOCUMENT, 'Valid ZRA Tax Clearance certificate'),
        (TenderRequirement.RequirementType.CERTIFICATE, 'Valid ZPPA registration certificate where applicable'),
        (TenderRequirement.RequirementType.BID_SECURITY, 'Confirm whether bid security is required and record the amount'),
        (TenderRequirement.RequirementType.SITE_VISIT, 'Confirm whether a site visit is mandatory'),
        (TenderRequirement.RequirementType.EVALUATION, 'Capture evaluation criteria from the solicitation document'),
    ]

    def analyze_tender(self, tender):
        created = 0
        for requirement_type, description in self.DEFAULT_REQUIREMENTS:
            _, was_created = TenderRequirement.objects.get_or_create(
                tender=tender,
                requirement_type=requirement_type,
                description=description,
                defaults={'is_mandatory': requirement_type != TenderRequirement.RequirementType.EVALUATION},
            )
            created += int(was_created)
        TenderAnalysisRun.objects.create(
            tender=tender,
            raw_output={'requirements_created': created, 'provider': 'placeholder'},
        )
        return created


def extract_text_from_file(path):
    lower = path.lower()
    if lower.endswith('.pdf'):
        reader = PdfReader(path)
        return '\n'.join(page.extract_text() or '' for page in reader.pages)
    if lower.endswith('.docx'):
        document = DocxDocument(path)
        return '\n'.join(paragraph.text for paragraph in document.paragraphs)
    with open(path, 'r', encoding='utf-8', errors='ignore') as handle:
        return handle.read()


def analyze_tender_document(document_text):
    return {
        'required_documents': extract_required_documents(document_text),
        'dates': extract_dates(document_text),
        'evaluation_criteria': extract_evaluation_criteria(document_text),
        'forms_required': extract_forms_required(document_text),
        'bid_security_required': 'bid security' in document_text.lower() or 'bid securing declaration' in document_text.lower(),
        'site_visit_required': 'site visit' in document_text.lower() or 'mandatory visit' in document_text.lower(),
    }


def extract_required_documents(document_text):
    text = document_text.lower()
    checks = {
        'PACRA': ['pacra', 'certificate of incorporation'],
        'ZRA Tax Clearance': ['tax clearance', 'zra'],
        'TPIN Certificate': ['tpin'],
        'NAPSA': ['napsa'],
        'Workers Compensation': ['workers compensation'],
        'NCC B': ['ncc b', 'ncc-b'],
        'NCC R': ['ncc r', 'ncc-r'],
        'NCC E': ['ncc e', 'ncc-e'],
        'NCC': ['ncc', 'national council for construction'],
        'ERB Registration / Licence': ['erb', 'energy regulation board'],
        'EIZ Certificate': ['eiz', 'engineering institution of zambia'],
        'ZPPA Registration': ['zppa registration', 'public procurement registration'],
        'Bank Confirmation Letter': ['bank confirmation', 'bank statement'],
        'Past Contracts': ['similar experience', 'past contracts', 'reference letters'],
    }
    return [name for name, keywords in checks.items() if any(keyword in text for keyword in keywords)]


def extract_dates(document_text):
    return re.findall(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?\b', document_text)


def extract_evaluation_criteria(document_text):
    lines = candidate_lines(document_text, ['evaluation', 'criteria', 'responsive', 'score', 'points'])
    return lines[:20]


def extract_forms_required(document_text):
    lines = candidate_lines(document_text, ['form of bid', 'bid form', 'power of attorney', 'declaration', 'schedule', 'undertaking'])
    return lines[:20]


def candidate_lines(document_text, keywords):
    lines = []
    for line in document_text.splitlines():
        clean = re.sub(r'\s+', ' ', line).strip()
        if len(clean) < 4:
            continue
        lower = clean.lower()
        if any(keyword in lower for keyword in keywords):
            lines.append(clean[:300])
    return lines


def answer_tender_question(tender, question):
    document = tender.solicitation_documents.order_by('-uploaded_at').first()
    if not document or not document.extracted_text.strip():
        return (
            'Please upload a solicitation document first. Once the PDF or DOCX is uploaded, '
            'I can read the extracted text and guide you on required documents, dates, forms, '
            'evaluation criteria, bid security, site visit, and next steps.'
        ), document

    question_lower = question.lower()
    text = document.extracted_text
    analysis = document.analysis_summary or analyze_tender_document(text)
    answer_parts = []

    if any(word in question_lower for word in ['next', 'do', 'steps', 'prepare', 'checklist']):
        answer_parts.append(build_next_steps_answer(tender, analysis))
    if any(word in question_lower for word in ['document', 'certificate', 'requirement', 'required']):
        answer_parts.append(build_required_documents_answer(analysis))
    if any(word in question_lower for word in ['date', 'deadline', 'closing', 'opening', 'clarification', 'site visit']):
        answer_parts.append(build_dates_answer(tender, analysis, text))
    if any(word in question_lower for word in ['evaluation', 'criteria', 'score', 'responsive']):
        answer_parts.append(build_list_answer('Evaluation criteria found', analysis.get('evaluation_criteria', [])))
    if any(word in question_lower for word in ['form', 'forms', 'letter', 'declaration', 'power of attorney']):
        answer_parts.append(build_list_answer('Forms and declarations found', analysis.get('forms_required', [])))
    if any(word in question_lower for word in ['security', 'bid bond', 'bid securing']):
        answer_parts.append(build_bid_security_answer(analysis, text))

    if not answer_parts:
        relevant_lines = find_relevant_lines(text, question)
        if relevant_lines:
            answer_parts.append(build_list_answer('Most relevant lines I found', relevant_lines[:8]))
        else:
            answer_parts.append(build_next_steps_answer(tender, analysis))
            answer_parts.append(
                'I could not find an exact phrase match for your question, so I summarized the strongest bid actions from the uploaded solicitation.'
            )

    answer_parts.append(
        'Note: this is rule-based analysis from the uploaded document text. Please confirm against the original solicitation before submission.'
    )
    return '\n\n'.join(part for part in answer_parts if part), document


def build_next_steps_answer(tender, analysis):
    steps = []
    required_documents = analysis.get('required_documents', [])
    if required_documents:
        steps.append('Confirm these documents are valid and not expired: ' + ', '.join(required_documents) + '.')
    if analysis.get('bid_security_required'):
        steps.append('Prepare the required bid security or bid securing declaration.')
    if analysis.get('site_visit_required') or tender.site_visit_date:
        steps.append('Confirm whether the site visit is mandatory and record attendance evidence.')
    if analysis.get('forms_required'):
        steps.append('Complete the required forms/declarations listed in the solicitation.')
    if tender.closing_at or tender.closing_date:
        deadline = tender.closing_at or tender.closing_date
        steps.append(f'Work backwards from the submission deadline: {deadline}.')
    steps.append('Generate a bid pack, then review the cover letter, checklist, price schedule, company profile, and certificate attachments.')
    return build_list_answer('Recommended next steps', steps)


def build_required_documents_answer(analysis):
    documents = analysis.get('required_documents', [])
    if not documents:
        return 'Required documents: I did not detect clear certificate names yet. Check the solicitation manually for a mandatory requirements table.'
    return build_list_answer('Required documents detected', documents)


def build_dates_answer(tender, analysis, document_text):
    dates = []
    if tender.closing_at:
        dates.append(f'Closing deadline from tender record: {tender.closing_at}')
    elif tender.closing_date:
        dates.append(f'Closing date from tender record: {tender.closing_date}')
    if tender.site_visit_date:
        dates.append(f'Site visit date from tender record: {tender.site_visit_date}')
    dates.extend(analysis.get('dates', [])[:12])
    if not dates:
        dates = candidate_lines(document_text, ['deadline', 'closing', 'opening', 'clarification', 'site visit'])[:8]
    return build_list_answer('Dates and deadline signals', dates)


def build_bid_security_answer(analysis, document_text):
    lines = candidate_lines(document_text, ['bid security', 'bid securing', 'bid bond', 'security amount', 'declaration'])[:8]
    if analysis.get('bid_security_required'):
        return build_list_answer('Bid security appears to be required or mentioned', lines or ['Confirm the amount/type in the solicitation.'])
    return 'Bid security: I did not detect a clear bid security requirement, but please confirm in the solicitation document.'


def build_list_answer(title, items):
    if not items:
        return f'{title}: none clearly detected.'
    lines = [f'{title}:']
    for item in items:
        lines.append(f'- {shorten(str(item), width=260, placeholder="...")}')
    return '\n'.join(lines)


def find_relevant_lines(document_text, question):
    terms = [term for term in re.findall(r'[a-zA-Z][a-zA-Z0-9-]{2,}', question.lower()) if term not in STOP_WORDS]
    if not terms:
        return []
    scored = []
    for line in document_text.splitlines():
        clean = re.sub(r'\s+', ' ', line).strip()
        if len(clean) < 4:
            continue
        lower = clean.lower()
        score = sum(1 for term in terms if term in lower)
        if score:
            scored.append((score, clean[:300]))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [line for _, line in scored]


STOP_WORDS = {
    'what', 'when', 'where', 'which', 'with', 'that', 'this', 'from', 'have',
    'need', 'should', 'could', 'would', 'about', 'after', 'before', 'tender',
    'solicitation', 'document', 'please', 'give', 'show',
}


def process_solicitation_document(solicitation_document):
    text = extract_text_from_file(solicitation_document.file.path)
    analysis = analyze_tender_document(text)
    solicitation_document.extracted_text = text
    solicitation_document.analysis_summary = analysis
    solicitation_document.save(update_fields=['extracted_text', 'analysis_summary'])
    create_requirements_from_analysis(solicitation_document.tender, analysis)
    TenderAnalysisRun.objects.create(
        tender=solicitation_document.tender,
        source_file=solicitation_document.file,
        raw_output=analysis,
        status='RULE_BASED_COMPLETE',
    )
    return analysis


def create_requirements_from_analysis(tender, analysis):
    for document in analysis.get('required_documents', []):
        TenderRequirement.objects.get_or_create(
            tender=tender,
            requirement_type=TenderRequirement.RequirementType.MANDATORY_DOCUMENT,
            description=document,
            defaults={'is_mandatory': True},
        )
    for criteria in analysis.get('evaluation_criteria', [])[:5]:
        TenderRequirement.objects.get_or_create(
            tender=tender,
            requirement_type=TenderRequirement.RequirementType.EVALUATION,
            description=criteria,
            defaults={'is_mandatory': False},
        )
    for form in analysis.get('forms_required', [])[:5]:
        TenderRequirement.objects.get_or_create(
            tender=tender,
            requirement_type=TenderRequirement.RequirementType.REQUIRED_FORM,
            description=form,
            defaults={'is_mandatory': True},
        )
