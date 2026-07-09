import re
import xml.etree.ElementTree as ET
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
    if lower.endswith('.xml'):
        return extract_text_from_c4t_xml(path)
    with open(path, 'r', encoding='utf-8', errors='ignore') as handle:
        return handle.read()


def extract_text_from_c4t_xml(path):
    tree = ET.parse(path)
    root = tree.getroot()
    lines = [
        f'ZPPA C4T XML cftid: {root.attrib.get("cftid", "")}',
        f'Procedure: {root.attrib.get("procedure", "")}',
        f'Evaluation type: {root.attrib.get("eval-type", "")}',
        'Documents Comprising the Bid 11.1 The Bid shall comprise the following:',
    ]
    order = 1
    for envelope in root.findall('envelope'):
        envelope_label = xml_envelope_label(envelope)
        lines.append(f'Envelope: {envelope_label}')
        sections = sorted(envelope.findall('section'), key=lambda item: int(item.attrib.get('pos') or 0))
        for section in sections:
            section_label = xml_node_label(section)
            if not section_label:
                continue
            criteria = []
            for criterion in section.findall('criterion'):
                criterion_label = xml_node_label(criterion)
                if criterion_label:
                    criteria.append(criterion_label)
            mandatory = any(criterion.attrib.get('mandatory') == '1' for criterion in section.findall('criterion'))
            detail = '; '.join(criteria)
            title = section_label if not detail else f'{section_label} - {detail}'
            suffix = ' mandatory' if mandatory else ''
            lines.append(f'({xml_order_letter(order)}) {envelope_label}: {title}{suffix}')
            order += 1
    return '\n'.join(lines)


def xml_node_label(node):
    label = node.find('label')
    if label is None or label.text is None:
        return ''
    return re.sub(r'\s+', ' ', label.text).strip()


def xml_envelope_label(envelope):
    envelope_type = envelope.attrib.get('type', '').strip()
    labels = {
        'proofDocs': 'Proof documents',
        'technical': 'Technical response',
        'commercial': 'Commercial offer',
    }
    return labels.get(envelope_type, envelope_type or envelope.attrib.get('name', 'Envelope'))


def xml_order_letter(index):
    letters = ''
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(97 + remainder) + letters
    return letters


def analyze_tender_document(document_text):
    return {
        'required_documents': extract_required_documents(document_text),
        'ordered_bid_items': extract_ordered_bid_items(document_text),
        'clarification_address': '\n'.join(extract_address_lines(document_text, mode='clarification')),
        'submission_address': '\n'.join(extract_address_lines(document_text, mode='submission')),
        'qualification_forms': extract_qualification_forms(document_text),
        'extracted_form_templates': extract_form_templates(document_text),
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
        'ZEMA License': ['zema', 'zambia environmental management agency'],
        'ZPPA Registration': ['zppa registration', 'public procurement registration'],
        'Bank Confirmation Letter': ['bank confirmation', 'bank statement'],
        'Past Contracts': ['similar experience', 'past contracts', 'reference letters'],
    }
    return [name for name, keywords in checks.items() if any(keyword in text for keyword in keywords)]


def extract_ordered_bid_items(document_text):
    if 'ZPPA C4T XML' in document_text:
        xml_items = ordered_xml_items(document_text)
        if xml_items:
            return xml_items
    patterns = [
        (
            'ITB 11.1',
            r'11\.\s*Documents\s+Comprising\s+the\s+Bid\s+11\.1\s*The\s+Bid\s+shall\s+comprise\s+the\s+following:\s*(?P<body>.*?)(?:\s+11\.2|\n\s*12\.\s*Letter\s+of\s+Bid|\n\s*Section\s+III)',
        ),
        (
            'Documents Comprising the Bid',
            r'Documents\s+Comprising\s+the\s+Bid\s+11\.1\s*The\s+Bid\s+shall\s+comprise\s+the\s+following:\s*(?P<body>.*?)(?:\s+11\.2|Letter\s+of\s+Bid\s+and\s+Schedules|Section\s+III)',
        ),
    ]
    for section, pattern in patterns:
        match = re.search(pattern, document_text, re.I | re.S)
        if not match:
            continue
        items = ordered_letter_items(match.group('body'), section)
        if items:
            return items
    return []


QUALIFICATION_FORM_PATTERNS = [
    ('ELI 1.1', 'Bidder Information Sheet', 'Eligibility', ['form eli', 'eli 1.1', 'bidder information sheet']),
    ('ELI 1.2', 'Party to JV Information Sheet', 'Eligibility', ['eli 1.2', 'party to jv information sheet']),
    ('CON-2', 'Historical Contract Non-Performance', 'Historical Contract Non-Performance', ['con-2', 'con – 2', 'historical contract non-performance']),
    ('CON-3', 'Current Contract Commitments / Works in Progress', 'Historical Contract Non-Performance', ['con-3', 'con – 3', 'current contract commitments', 'works in progress']),
    ('CCC', 'Current Contract Commitments', 'Historical Contract Non-Performance', ['form ccc', 'ccc']),
    ('FIN-3.1', 'Financial Situation', 'Financial Situation', ['fin-3.1', 'fin – 3.1', 'financial situation']),
    ('FIN-3.2', 'Average Annual Turnover', 'Financial Situation', ['fin-3.2', 'fin – 3.2', 'average annual turnover']),
    ('FIN-3.3', 'Financial Resources', 'Financial Situation', ['fin-3.3', 'fin – 3.3', 'financial resources']),
    ('EXP-2.4.1', 'General Experience', 'Experience', ['exp-2.4.1', 'exp – 2.4.1', 'general experience']),
    ('EXP-2.4.2(a)', 'Specific Experience', 'Experience', ['exp-2.4.2(a)', 'exp – 2.4.2(a)', 'specific experience']),
    ('EXP-2.4.2(b)', 'Specific Experience in Key Activities', 'Experience', ['exp-2.4.2(b)', 'exp – 2.4.2(b)', 'specific experience in key activities']),
    ('PER-1', 'Proposed Personnel', 'Personnel', ['per-1', 'per – 1', 'proposed personnel', 'forms for personnel']),
    ('PER-2', 'Resume of Proposed Personnel', 'Personnel', ['per-2', 'per – 2', 'resume of proposed personnel']),
    ('EQU', 'Equipment', 'Equipment', ['equipment form', 'forms for equipment', 'form equ', 'equipment']),
    ('MFR', 'Manufacturer’s Authorisation', 'Manufacturer Authorisation', ['manufacturer', 'manufacturer’s authorisation', "manufacturer's authorisation", 'manufacturer authorization']),
]


def extract_qualification_forms(document_text):
    text = re.sub(r'\s+', ' ', document_text).lower()
    found = []
    for code, title, factor, patterns in QUALIFICATION_FORM_PATTERNS:
        if any(pattern.lower() in text for pattern in patterns):
            found.append({
                'code': code,
                'title': title,
                'factor': factor,
                'source': 'Section III qualification / Section IV forms',
            })
    return found


FORM_TEMPLATE_PATTERNS = [
    ('LETTER_OF_BID', 'Letter of Bid', ['letter of bid', 'bid submission form', 'form of bid']),
    ('BID_SECURING_DECLARATION', 'Bid-Securing Declaration', ['bid-securing declaration', 'bid securing declaration']),
    ('ELI 1.1', 'Bidder Information Sheet', ['form eli 1.1', 'eli 1.1', 'bidder information sheet']),
    ('ELI 1.2', 'Party to JV Information Sheet', ['form eli 1.2', 'eli 1.2', 'party to jv information sheet']),
    ('CON-2', 'Historical Contract Non-Performance', ['form con-2', 'con-2', 'historical contract non-performance']),
    ('CON-3', 'Current Contract Commitments', ['form con-3', 'con-3', 'current contract commitments']),
    ('FIN-3.1', 'Financial Situation', ['form fin-3.1', 'fin-3.1', 'financial situation']),
    ('FIN-3.2', 'Average Annual Turnover', ['form fin-3.2', 'fin-3.2', 'average annual turnover']),
    ('FIN-3.3', 'Financial Resources', ['form fin-3.3', 'fin-3.3', 'financial resources']),
    ('EXP-2.4.1', 'General Experience', ['form exp-2.4.1', 'exp-2.4.1', 'general experience']),
    ('EXP-2.4.2(a)', 'Specific Experience', ['form exp-2.4.2(a)', 'exp-2.4.2(a)', 'specific experience']),
    ('EXP-2.4.2(b)', 'Specific Experience in Key Activities', ['form exp-2.4.2(b)', 'exp-2.4.2(b)', 'key activities']),
    ('PER-1', 'Proposed Personnel', ['form per-1', 'per-1', 'proposed personnel']),
    ('PER-2', 'Resume of Proposed Personnel', ['form per-2', 'per-2', 'resume of proposed personnel']),
    ('EQU', 'Equipment Form', ['form equ', 'equipment form', 'forms for equipment']),
    ('MFR', 'Manufacturer Authorisation', ['manufacturer authorisation', 'manufacturer authorization']),
]


def extract_form_templates(document_text):
    lines = [re.sub(r'\s+', ' ', line).strip() for line in document_text.splitlines()]
    lines = [line for line in lines if line]
    templates = []
    used_codes = set()
    for code, title, patterns in FORM_TEMPLATE_PATTERNS:
        index = find_form_heading_index(lines, patterns)
        if index is None or code in used_codes:
            continue
        section_lines = collect_form_section(lines, index)
        if len(section_lines) < 2:
            continue
        templates.append({
            'code': code,
            'title': title,
            'heading': section_lines[0],
            'source': 'Uploaded solicitation document',
            'lines': section_lines[:45],
            'fields': extract_form_fields_from_lines(section_lines),
            'rows': extract_form_rows_from_lines(section_lines),
        })
        used_codes.add(code)
    return templates


def find_form_heading_index(lines, patterns):
    for index, line in enumerate(lines):
        lower = line.lower()
        if any(pattern in lower for pattern in patterns):
            return index
    return None


def collect_form_section(lines, start_index):
    section = []
    for line in lines[start_index:start_index + 80]:
        lower = line.lower()
        if len(section) > 8 and is_new_major_section(lower):
            break
        section.append(line)
        if len(section) >= 45:
            break
    return section


def is_new_major_section(lower_line):
    markers = [
        'section v.', 'section vi.', 'section vii.', 'section iv.',
        'qualification criteria', 'schedule of requirements', 'general conditions',
    ]
    if any(marker in lower_line for marker in markers):
        return True
    return bool(re.match(r'^(form\s+)?(?:eli|con|fin|exp|per)[\s-]*\d', lower_line))


def extract_form_fields_from_lines(lines):
    fields = []
    field_patterns = [
        r'^(?P<label>[A-Z][A-Za-z0-9 /\-,().]{2,55})\s*[:]\s*(?P<value>.*)$',
        r'^(?P<label>Date|Name|Address|Country|Tender|Bidder|Signature|Position|Title|Email|Telephone)\b\s*(?P<value>.*)$',
    ]
    for line in lines:
        for pattern in field_patterns:
            match = re.match(pattern, line)
            if not match:
                continue
            label = match.group('label').strip(' :')
            if label.lower() in {'form', 'section'}:
                continue
            if label not in fields:
                fields.append(label)
            break
    return fields[:24]


def extract_form_rows_from_lines(lines):
    rows = []
    for line in lines:
        if not re.search(r'\s{2,}|\t|\|', line):
            continue
        parts = [part.strip() for part in re.split(r'\s{2,}|\t|\|', line) if part.strip()]
        if len(parts) >= 2:
            rows.append(parts[:6])
    return rows[:18]


def ordered_letter_items(section_text, section_name):
    normalized = re.sub(r'\s+', ' ', section_text)
    item_matches = list(re.finditer(r'\(([a-z])\)\s*', normalized, re.I))
    items = []
    for index, item_match in enumerate(item_matches):
        start = item_match.end()
        end = item_matches[index + 1].start() if index + 1 < len(item_matches) else len(normalized)
        text = normalized[start:end].strip(' ;,.')
        text = re.sub(r'\s+', ' ', text)
        if len(text) < 4:
            continue
        items.append({
            'order': index + 1,
            'reference': f'{section_name}({item_match.group(1).lower()})',
            'title': shorten(text, width=180, placeholder='...'),
            'envelope': section_name,
            'requirement': shorten(text, width=180, placeholder='...'),
            'response': '',
            'mandatory': False,
        })
    return items[:30]


def ordered_xml_items(document_text):
    items = []
    current_envelope = ''
    item_pattern = re.compile(r'^\((?P<letter>[a-z]+)\)\s+(?P<envelope>[^:]+):\s+(?P<title>.+)$', re.I)
    for line in document_text.splitlines():
        clean = re.sub(r'\s+', ' ', line).strip()
        if not clean:
            continue
        if clean.startswith('Envelope:'):
            current_envelope = clean.split(':', 1)[1].strip()
            continue
        match = item_pattern.match(clean)
        if not match:
            continue
        envelope = match.group('envelope').strip() or current_envelope or 'Bid requirement'
        title = match.group('title').strip()
        mandatory = bool(re.search(r'\bmandatory\b$', title, re.I))
        title = re.sub(r'\s+mandatory$', '', title, flags=re.I).strip()
        requirement, response = split_xml_requirement(title)
        response_items = split_xml_response_items(response)
        order = len(items) + 1
        items.append({
            'order': order,
            'reference': f'XML {match.group("letter").lower()}',
            'envelope': envelope,
            'requirement': requirement,
            'response': response,
            'response_items': response_items,
            'mandatory': mandatory,
            'title': title,
        })
    return items[:80]


def split_xml_requirement(title):
    if ' - ' not in title:
        return title.strip(), ''
    requirement, response = title.split(' - ', 1)
    return requirement.strip(), response.strip()


def split_xml_response_items(response):
    response = re.sub(r'\s+', ' ', response or '').strip()
    if not response:
        return []
    parts = re.split(r';\s*(?=(?:Attach|Provide|Indicate|Submit|Complete|Signed?|Valid|Availability|Evidence|Documentary|Warranty|Delivery|\([ivx]+\)|[A-Z][a-z]+)\b)', response)
    cleaned = []
    for part in parts:
        item = part.strip(' ;')
        if not item:
            continue
        cleaned.append(item)
    if len(cleaned) == 1 and len(cleaned[0]) > 180:
        cleaned = [item.strip(' ;') for item in response.split(';') if item.strip(' ;')]
    return cleaned[:30]


def extract_dates(document_text):
    return re.findall(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?\b', document_text)


def extract_evaluation_criteria(document_text):
    lines = candidate_lines(document_text, ['evaluation', 'criteria', 'responsive', 'score', 'points'])
    return lines[:20]


def extract_forms_required(document_text):
    lines = candidate_lines(document_text, ['form of bid', 'bid form', 'bid submission form', 'power of attorney', 'declaration', 'schedule', 'undertaking'])
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
    if any(word in question_lower for word in ['address', 'submit', 'submission', 'clarification', 'where', 'attention', 'street', 'email', 'mail']):
        answer_parts.append(build_address_answer(text))
    if 'itb 11.1' in question_lower or '11.1' in question_lower or 'documents comprising the bid' in question_lower:
        answer_parts.append(build_itb_11_answer(analysis, text))
    if any(word in question_lower for word in ['evaluation', 'criteria', 'score', 'responsive']):
        answer_parts.append(build_list_answer('Evaluation criteria found', analysis.get('evaluation_criteria', [])))
    if any(word in question_lower for word in ['form', 'forms', 'letter', 'declaration', 'power of attorney']):
        answer_parts.append(build_list_answer('Forms and declarations found', analysis.get('forms_required', [])))
    if any(word in question_lower for word in ['security', 'bid bond', 'bid securing']):
        answer_parts.append(build_bid_security_answer(analysis, text))
    if any(word in question_lower for word in ['disqualify', 'disqualification', 'reject', 'responsive', 'risk']):
        answer_parts.append(build_disqualification_answer(tender, analysis, text))

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


def build_address_answer(document_text):
    lines = extract_address_lines(document_text)
    if not lines:
        lines = candidate_lines(document_text, ['address', 'attention', 'street address', 'city', 'telephone', 'electronic mail', 'submit', 'submission'])[:10]
    if not lines:
        return 'Address: I did not detect a clear clarification or submission address block. Search the solicitation for "For clarification", "Submission", "Attention", "Street Address", or "Electronic mail address".'
    return build_list_answer('Address / submission signals found', lines)


def build_itb_11_answer(analysis, document_text):
    items = analysis.get('ordered_bid_items') or extract_ordered_bid_items(document_text)
    if not items:
        lines = candidate_lines(document_text, ['itb 11.1', 'documents comprising the bid', 'bid shall comprise', 'letter of bid'])[:12]
        if lines:
            return build_list_answer('ITB 11.1 related lines found', lines)
        return 'ITB 11.1: I could not detect the ordered "Documents Comprising the Bid" list. Please check the solicitation section titled ITB 11.1 or Documents Comprising the Bid.'
    readable = []
    for item in items:
        if isinstance(item, dict):
            label = item.get('label') or item.get('letter') or '-'
            text = item.get('text') or item.get('description') or item
            readable.append(f'{label}: {text}')
        else:
            readable.append(item)
    return build_list_answer('ITB 11.1 documents comprising the bid, in order', readable)


def build_bid_security_answer(analysis, document_text):
    lines = candidate_lines(document_text, ['bid security', 'bid securing', 'bid bond', 'security amount', 'declaration'])[:8]
    if analysis.get('bid_security_required'):
        return build_list_answer('Bid security appears to be required or mentioned', lines or ['Confirm the amount/type in the solicitation.'])
    return 'Bid security: I did not detect a clear bid security requirement, but please confirm in the solicitation document.'


def build_disqualification_answer(tender, analysis, document_text):
    risks = []
    required_documents = analysis.get('required_documents', [])
    if required_documents:
        risks.append('Missing, expired, or incorrectly named mandatory documents: ' + ', '.join(required_documents) + '.')
    if analysis.get('bid_security_required'):
        risks.append('Wrong bid security type, missing bid securing declaration, or incorrect amount/validity.')
    if analysis.get('site_visit_required') or tender.site_visit_date:
        risks.append('Missing a mandatory site visit or failing to attach attendance proof.')
    if analysis.get('forms_required'):
        risks.append('Unsigned, incomplete, or wrongly completed forms/declarations.')
    lines = candidate_lines(document_text, ['non-responsive', 'responsive', 'disqual', 'reject', 'mandatory', 'shall submit'])[:8]
    risks.extend(lines)
    if not risks:
        risks = [
            'I did not detect a clear disqualification section. Review all clauses using words like mandatory, shall, must, non-responsive, reject, and disqualify.'
        ]
    return build_list_answer('Likely disqualification risks', risks)


def extract_address_lines(document_text, mode='any'):
    if mode == 'clarification':
        patterns = [
            r'For\s+Clarification\s+of\s+bid\s+purposes\s+only.*?(?=\n\s*(?:Section|ITB|BDS|For\s+submission|Submission|Deadline|[0-9]+\.)|\Z)',
        ]
    elif mode == 'submission':
        patterns = [
            r'(?:For\s+submission\s+of\s+bids|address\s+for\s+submission|Bid\s+submission\s+address).*?(?=\n\s*(?:Section|ITB|BDS|Deadline|[0-9]+\.)|\Z)',
        ]
    else:
        patterns = [
            r'For\s+Clarification\s+of\s+bid\s+purposes\s+only.*?(?=\n\s*(?:Section|ITB|BDS|For\s+submission|Submission|Deadline|[0-9]+\.)|\Z)',
            r'(?:For\s+submission\s+of\s+bids|address\s+for\s+submission|Bid\s+submission\s+address|The\s+Procuring\s+Entity[^\n]{0,80}address\s+is).*?(?=\n\s*(?:Section|ITB|BDS|Deadline|[0-9]+\.)|\Z)',
        ]
    blocks = []
    for pattern in patterns:
        match = re.search(pattern, document_text, flags=re.I | re.S)
        if match:
            blocks.append(match.group(0))
    if not blocks:
        return []
    lines = []
    for block in blocks:
        for line in block.splitlines():
            clean = re.sub(r'\s+', ' ', line).strip()
            clean_lower = clean.lower()
            if clean_lower.startswith('the procuring entity') and any('procuring entity' in item.lower() for item in lines):
                continue
            if clean and len(clean) > 2 and clean_lower not in {item.lower() for item in lines}:
                lines.append(clean)
    return lines[:14]


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
    from tenders.services import ensure_analysis_bid_tasks

    create_requirements_from_analysis(solicitation_document.tender, analysis)
    analysis['bid_tasks_created'] = ensure_analysis_bid_tasks(solicitation_document.tender, analysis)
    solicitation_document.extracted_text = text
    solicitation_document.analysis_summary = analysis
    solicitation_document.save(update_fields=['extracted_text', 'analysis_summary'])
    update_tender_from_analysis(solicitation_document.tender, analysis)
    TenderAnalysisRun.objects.create(
        tender=solicitation_document.tender,
        source_file=solicitation_document.file,
        raw_output=analysis,
        status='RULE_BASED_COMPLETE',
    )
    return analysis


def update_tender_from_analysis(tender, analysis):
    fields = []
    clarification_address = analysis.get('clarification_address', '').strip()
    submission_address = analysis.get('submission_address', '').strip()
    itb_11_items = analysis.get('ordered_bid_items') or []

    if clarification_address and tender.clarification_address != clarification_address:
        tender.clarification_address = clarification_address
        fields.append('clarification_address')
    if submission_address and tender.submission_address != submission_address:
        tender.submission_address = submission_address
        fields.append('submission_address')
    if itb_11_items and tender.itb_11_items != itb_11_items:
        tender.itb_11_items = itb_11_items
        fields.append('itb_11_items')
    if fields:
        fields.append('updated_at')
        tender.save(update_fields=fields)


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
    for form in analysis.get('qualification_forms', []):
        TenderRequirement.objects.get_or_create(
            tender=tender,
            requirement_type=TenderRequirement.RequirementType.REQUIRED_FORM,
            description=f'{form["code"]}: {form["title"]}',
            defaults={'is_mandatory': True},
        )
    for item in analysis.get('ordered_bid_items', [])[:40]:
        title = item.get('title', '') if isinstance(item, dict) else str(item)
        if not title:
            continue
        requirement_type = TenderRequirement.RequirementType.OTHER
        lower = title.lower()
        if any(word in lower for word in ['certificate', 'license', 'registration', 'attachment', 'pacra', 'napsa', 'tax clearance']):
            requirement_type = TenderRequirement.RequirementType.MANDATORY_DOCUMENT
        elif any(word in lower for word in ['bid submission form', 'power of attorney', 'declaration']):
            requirement_type = TenderRequirement.RequirementType.REQUIRED_FORM
        elif any(word in lower for word in ['experience', 'reference', 'technical', 'fuel', 'diesel', 'petrol', 'station']):
            requirement_type = TenderRequirement.RequirementType.EVALUATION
        TenderRequirement.objects.get_or_create(
            tender=tender,
            requirement_type=requirement_type,
            description=title,
            defaults={'is_mandatory': True},
        )
