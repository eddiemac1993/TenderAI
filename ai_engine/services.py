import re

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
        'NCC': ['ncc', 'national council for construction'],
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
