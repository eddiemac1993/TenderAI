from io import BytesIO
import re

from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.utils import timezone
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import PageBreak, Paragraph, Spacer, Table, TableStyle

from core.models import SystemSettings
from core.pdf import add_signature, build_pdf_response, letterhead_elements, styles
from documents.models import CompanyDocument
from tenders.services import bid_pack_output_for_task, required_document_types
from .models import BidDocument


ATTACHMENT_ORDER = [
    CompanyDocument.DocumentType.PACRA,
    CompanyDocument.DocumentType.TPIN_CERTIFICATE,
    CompanyDocument.DocumentType.ZRA_TAX_CLEARANCE,
    CompanyDocument.DocumentType.NAPSA,
    CompanyDocument.DocumentType.WORKERS_COMPENSATION,
    CompanyDocument.DocumentType.NCC,
    CompanyDocument.DocumentType.NCC_B,
    CompanyDocument.DocumentType.NCC_R,
    CompanyDocument.DocumentType.NCC_E,
    CompanyDocument.DocumentType.ERB,
    CompanyDocument.DocumentType.EIZ_CERTIFICATE,
    CompanyDocument.DocumentType.ZEMA_LICENSE,
    CompanyDocument.DocumentType.ROADWORTHINESS,
    CompanyDocument.DocumentType.ZPPA_REGISTRATION,
    CompanyDocument.DocumentType.BANK_CONFIRMATION,
    CompanyDocument.DocumentType.AUDITED_FINANCIALS,
    CompanyDocument.DocumentType.DELIVERY_EVIDENCE,
    CompanyDocument.DocumentType.TRAINING_PROGRAMME,
    CompanyDocument.DocumentType.WARRANTY_UNDERTAKING,
    CompanyDocument.DocumentType.PAST_CONTRACT,
    CompanyDocument.DocumentType.COMPANY_PROFILE,
    CompanyDocument.DocumentType.OTHER,
]

QUALIFICATION_FORM_DEFINITIONS = {
    'ELI 1.1': {
        'title': 'Form ELI 1.1 - Bidder Information Sheet',
        'factor': 'Eligibility',
        'headers': ['Field', 'TenderAI filled value'],
        'rows': [
            ('Bidder legal name', 'company.name'),
            ('Country of registration', 'Zambia'),
            ('Year of registration', 'To be completed from PACRA certificate'),
            ('Legal address', 'company.address'),
            ('Authorized representative', 'To be completed'),
            ('TPIN', 'company.tpin'),
            ('Attached evidence', 'PACRA, TPIN, tax clearance, and other eligibility documents'),
        ],
    },
    'ELI 1.2': {
        'title': 'Form ELI 1.2 - Party to JV Information Sheet',
        'factor': 'Eligibility',
        'headers': ['Field', 'TenderAI filled value'],
        'rows': [
            ('JV party legal name', 'Not applicable unless bidding as a JV'),
            ('Country of registration', 'To be completed if JV applies'),
            ('Legal address', 'To be completed if JV applies'),
            ('Authorized representative', 'To be completed if JV applies'),
        ],
    },
    'CON-2': {
        'title': 'Form CON-2 - Historical Contract Non-Performance',
        'factor': 'Historical Contract Non-Performance',
        'headers': ['Year', 'Contract', 'Non-performance details', 'Status'],
        'rows': [('To be completed', 'To be completed', 'None / disclose if applicable', 'To be completed')],
    },
    'CON-3': {
        'title': 'Form CON-3 - Current Contract Commitments / Works in Progress',
        'factor': 'Historical Contract Non-Performance',
        'headers': ['Client', 'Contract description', 'Value', 'Completion date', 'Percent complete'],
        'rows': [('To be completed', 'Current contract / works in progress', '-', '-', '-')],
    },
    'CCC': {
        'title': 'Form CCC - Current Contract Commitments',
        'factor': 'Historical Contract Non-Performance',
        'headers': ['Client', 'Contract', 'Outstanding value', 'Expected completion'],
        'rows': [('To be completed', 'To be completed', '-', '-')],
    },
    'FIN-3.1': {
        'title': 'Form FIN-3.1 - Financial Situation',
        'factor': 'Financial Situation',
        'headers': ['Financial year', 'Total assets', 'Total liabilities', 'Net worth', 'Source document'],
        'rows': [('To be completed', '-', '-', '-', 'Audited accounts / financial statements')],
    },
    'FIN-3.2': {
        'title': 'Form FIN-3.2 - Average Annual Turnover',
        'factor': 'Financial Situation',
        'headers': ['Year', 'Turnover', 'Currency', 'Source document'],
        'rows': [('To be completed', '-', 'ZMW', 'Financial statements')],
    },
    'FIN-3.3': {
        'title': 'Form FIN-3.3 - Financial Resources',
        'factor': 'Financial Situation',
        'headers': ['Source of financing', 'Amount', 'Currency', 'Evidence'],
        'rows': [('Bank / credit facility / cash resources', '-', 'ZMW', 'Attach bank confirmation or proof')],
    },
    'EXP-2.4.1': {
        'title': 'Form EXP-2.4.1 - General Experience',
        'factor': 'Experience',
        'headers': ['Starting month/year', 'Ending month/year', 'Client', 'Contract description', 'Role'],
        'rows': [('To be completed', 'To be completed', 'To be completed', 'Relevant works/supplies/services', 'Contractor')],
    },
    'EXP-2.4.2(a)': {
        'title': 'Form EXP-2.4.2(a) - Specific Experience',
        'factor': 'Experience',
        'headers': ['Contract', 'Client', 'Country', 'Contract value', 'Completion date', 'Similarity'],
        'rows': [('To be completed', 'To be completed', 'Zambia', '-', '-', 'Similar assignment')],
    },
    'EXP-2.4.2(b)': {
        'title': 'Form EXP-2.4.2(b) - Specific Experience in Key Activities',
        'factor': 'Experience',
        'headers': ['Key activity', 'Contract reference', 'Quantity / scope', 'Completion date'],
        'rows': [('To be completed', 'To be completed', '-', '-')],
    },
    'PER-1': {
        'title': 'Form PER-1 - Proposed Personnel',
        'factor': 'Personnel',
        'headers': ['Position', 'Name', 'Qualification', 'Years experience'],
        'rows': [('Project Manager / Supervisor', 'To be completed', 'To be completed', '-')],
    },
    'PER-2': {
        'title': 'Form PER-2 - Resume of Proposed Personnel',
        'factor': 'Personnel',
        'headers': ['Field', 'TenderAI filled value'],
        'rows': [
            ('Position', 'To be completed'),
            ('Name', 'To be completed'),
            ('Date of birth', 'To be completed'),
            ('Professional qualifications', 'To be completed'),
            ('Present employer', 'To be completed'),
            ('Relevant experience', 'To be completed'),
        ],
    },
    'EQU': {
        'title': 'Forms for Equipment',
        'factor': 'Equipment',
        'headers': ['Equipment type', 'Make / model', 'Capacity', 'Owned / leased', 'Availability'],
        'rows': [('To be completed', '-', '-', '-', 'Available for contract')],
    },
    'MFR': {
        'title': 'Manufacturer’s Authorisation',
        'factor': 'Manufacturer Authorisation',
        'headers': ['Field', 'TenderAI filled value'],
        'rows': [
            ('Manufacturer / supplier', 'To be completed where goods require authorisation'),
            ('Tender title', 'tender.title'),
            ('Bidder name', 'company.name'),
            ('Authorised goods', 'To be completed'),
            ('Signature', 'To be completed'),
        ],
    },
}


def build_bid_checklist(bid_pack):
    tender = bid_pack.tender
    itb_rows = ordered_itb_rows(bid_pack)
    if itb_rows:
        checklist = [required_item for _, required_item, _, _ in itb_rows]
    else:
        checklist = [
            'Cover letter',
            'Company profile summary',
            'Price schedule',
            'Priced schedule / bill of quantities',
        ]

    for requirement in tender.requirements.all():
        if not requirement.is_mandatory:
            continue
        if requirement.requirement_type not in {
            requirement.RequirementType.MANDATORY_DOCUMENT,
            requirement.RequirementType.CERTIFICATE,
            requirement.RequirementType.REQUIRED_FORM,
            requirement.RequirementType.BID_SECURITY,
            requirement.RequirementType.SITE_VISIT,
        }:
            continue
        item = str(requirement.description).strip()
        if not is_clean_checklist_item(item):
            continue
        if itb_rows and requirement.requirement_type == requirement.RequirementType.REQUIRED_FORM:
            continue
        if itb_rows and 'bid security' in item.lower() and any('bid security' in existing.lower() for existing in checklist):
            continue
        if item and item not in checklist:
            checklist.append(item)
    return checklist


def is_clean_checklist_item(item):
    if not item or len(item) < 3:
        return False
    noisy_markers = ['........', 'error! bookmark', 'section vi.', 'section iii.', 'this section contains']
    lower = item.lower()
    if any(marker in lower for marker in noisy_markers):
        return False
    if lower.startswith('('):
        return False
    if lower.startswith(('information that ', 'evaluation of bids')):
        return False
    if lower in {'and schedules', 'schedules'}:
        return False
    if item.count('.') > 8:
        return False
    return True


def requirements_matrix_rows(bid_pack):
    rows = []
    for requirement in bid_pack.tender.requirements.all():
        if requirement.requirement_type not in {
            requirement.RequirementType.MANDATORY_DOCUMENT,
            requirement.RequirementType.CERTIFICATE,
            requirement.RequirementType.REQUIRED_FORM,
            requirement.RequirementType.BID_SECURITY,
            requirement.RequirementType.SITE_VISIT,
            requirement.RequirementType.EXPERIENCE,
        }:
            continue
        if not is_clean_checklist_item(requirement.description):
            continue
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


def ordered_itb_rows(bid_pack):
    rows = []
    tasks = bid_pack.tender.bid_tasks.filter(title__startswith='ITB ').order_by('sort_order', 'title')
    for task in tasks:
        reference, _, required_item = task.title.partition(':')
        rows.append((
            reference.strip(),
            required_item.strip() or task.title,
            bid_pack_output_for_task(task),
            task.get_status_display(),
        ))
    return rows


def xml_bid_structure_groups(bid_pack):
    groups = []
    group_map = {}
    for item in bid_pack.tender.itb_11_items or []:
        envelope = item.get('envelope') or 'Bid requirements'
        if envelope not in group_map:
            group_map[envelope] = {
                'title': envelope,
                'items': [],
            }
            groups.append(group_map[envelope])
        group_map[envelope]['items'].append(item)
    return groups


def has_xml_bid_structure(bid_pack):
    return bool(xml_bid_structure_groups(bid_pack))


def table_of_contents(bid_pack=None):
    has_xml = bool(bid_pack and has_xml_bid_structure(bid_pack))
    sections = [
        'Tender Summary',
        'Submission Gaps',
        'XML Structured Bid Response' if has_xml else 'ITB Ordered Bid Checklist',
        'Cover Letter',
        'Form of Bid / Tender Submission Letter',
        'Required Forms',
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
    if bid_pack and bid_pack.tender.requirements.exists():
        sections.append('Attached Company Certificates')
    return sections


def submission_gap_rows(bid_pack):
    return [
        (item['label'], item['status'], item['action'])
        for item in submission_gap_items(bid_pack)
    ]


def submission_gap_items(bid_pack):
    docs = list(bid_pack.company.documents.all())
    required = list(required_document_types(bid_pack.tender))
    if not required:
        required = [
            CompanyDocument.DocumentType.PACRA,
            CompanyDocument.DocumentType.ZRA_TAX_CLEARANCE,
            CompanyDocument.DocumentType.TPIN_CERTIFICATE,
            CompanyDocument.DocumentType.ZPPA_REGISTRATION,
            CompanyDocument.DocumentType.BANK_CONFIRMATION,
            CompanyDocument.DocumentType.COMPANY_PROFILE,
        ]
    items = []
    for doc_type in required:
        matching = [document for document in docs if document.document_type == doc_type]
        label = CompanyDocument.DocumentType(doc_type).label
        if not matching:
            items.append({
                'label': label,
                'status': 'Missing',
                'action': 'Upload this document before final bid submission.',
                'document_type': doc_type,
            })
            continue
        if any(document.is_expired for document in matching):
            items.append({
                'label': label,
                'status': 'Expired',
                'action': 'Renew this document before submission.',
                'document_type': doc_type,
            })
    if not bid_pack.company.tpin:
        items.append({
            'label': 'Company TPIN',
            'status': 'Missing',
            'action': 'Fill in the company TPIN on the company profile.',
            'document_type': '',
        })
    if not bid_pack.company.registration_number:
        items.append({
            'label': 'PACRA registration number',
            'status': 'Missing',
            'action': 'Fill in the company registration number.',
            'document_type': '',
        })
    if not bid_pack.company.address:
        items.append({
            'label': 'Company address',
            'status': 'Missing',
            'action': 'Fill in the company address for letterhead and forms.',
            'document_type': '',
        })
    return items


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
        CompanyDocument.DocumentType.ZEMA_LICENSE,
        CompanyDocument.DocumentType.ROADWORTHINESS,
        CompanyDocument.DocumentType.ZPPA_REGISTRATION,
        CompanyDocument.DocumentType.BANK_CONFIRMATION,
        CompanyDocument.DocumentType.AUDITED_FINANCIALS,
        CompanyDocument.DocumentType.DELIVERY_EVIDENCE,
        CompanyDocument.DocumentType.TRAINING_PROGRAMME,
        CompanyDocument.DocumentType.WARRANTY_UNDERTAKING,
        CompanyDocument.DocumentType.PAST_CONTRACT,
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


def required_form_specs(bid_pack):
    tender = bid_pack.tender
    company = bid_pack.company
    form_text = ' '.join(
        requirement.description.lower()
        for requirement in tender.requirements.filter(requirement_type='REQUIRED_FORM')
    )
    itb_text = ' '.join(row[1].lower() for row in ordered_itb_rows(bid_pack))
    corpus = f'{form_text} {itb_text} {tender.title.lower()}'

    specs = [
        {
            'title': 'Letter of Bid',
            'kind': 'letter_of_bid',
        }
    ]

    if 'bid securing declaration' in corpus or 'bid security' in corpus:
        specs.append({
            'title': 'Bid-Securing Declaration',
            'kind': 'bid_securing_declaration',
        })

    if 'schedule' in corpus or 'bill of quantities' in corpus or 'boq' in corpus:
        specs.append({
            'title': 'Price Schedule / Bill of Quantities',
            'headers': ['Item No.', 'Description', 'Unit', 'Quantity', 'Unit Price', 'Total'],
            'rows': [
                ('1', 'Complete from solicitation BOQ / price schedule', '-', '-', '-', '-'),
                ('2', 'Add additional line items as required', '-', '-', '-', '-'),
            ],
        })

    if 'authorization' in corpus or 'authorizing' in corpus or 'power of attorney' in corpus:
        specs.append({
            'title': 'Signatory Authorization / Power of Attorney',
            'rows': [
                ('Company', company.name),
                ('Tender title', tender.title),
                ('Authorised person', 'To be completed'),
                ('Position', 'To be completed'),
                ('Scope', 'Authority to sign and submit bid documents'),
                ('Director / witness signature', 'To be completed and signed'),
            ],
        })

    if 'experience' in corpus or tender.requirements.filter(description__icontains='Past Contracts').exists():
        specs.append({
            'title': 'Similar Experience Table',
            'headers': ['Client', 'Contract description', 'Year', 'Value', 'Contact person'],
            'rows': [
                ('To be completed', 'Relevant similar contract', '-', '-', '-'),
                ('To be completed', 'Relevant similar contract', '-', '-', '-'),
            ],
        })

    for form in qualification_form_specs(bid_pack):
        if not any(existing.get('title') == form.get('title') for existing in specs):
            specs.append(form)

    unmapped = unmapped_required_items(bid_pack)
    if unmapped:
        specs.append({
            'title': 'Other Required Items Not Yet Mapped',
            'headers': ['Requirement', 'Action'],
            'rows': [(item, 'Confirm where this must be included in the final bid pack.') for item in unmapped],
        })

    return specs


def qualification_form_specs(bid_pack):
    codes = []
    for requirement in bid_pack.tender.requirements.filter(requirement_type='REQUIRED_FORM'):
        text = requirement.description.upper().replace('–', '-')
        for code in QUALIFICATION_FORM_DEFINITIONS:
            if code.upper() in text and code not in codes:
                codes.append(code)
    document = bid_pack.tender.solicitation_documents.order_by('-uploaded_at').first()
    analysis = document.analysis_summary if document else {}
    for form in analysis.get('qualification_forms', []):
        code = form.get('code')
        if code in QUALIFICATION_FORM_DEFINITIONS and code not in codes:
            codes.append(code)
    return [build_qualification_form_spec(bid_pack, code) for code in codes]


def build_qualification_form_spec(bid_pack, code):
    definition = QUALIFICATION_FORM_DEFINITIONS[code]
    return {
        'title': definition['title'],
        'factor': definition['factor'],
        'headers': definition['headers'],
        'rows': [
            tuple(resolve_form_value(bid_pack, value) for value in row)
            for row in definition['rows']
        ],
    }


def resolve_form_value(bid_pack, value):
    if value == 'company.name':
        return bid_pack.company.name
    if value == 'company.address':
        return bid_pack.company.address or '-'
    if value == 'company.tpin':
        return bid_pack.company.tpin or '-'
    if value == 'tender.title':
        return bid_pack.tender.title
    return value


def unmapped_required_items(bid_pack):
    mapped_words = [
        'pacra', 'zra', 'tax', 'napsa', 'workers', 'ncc', 'eiz', 'bank', 'past contract',
        'letter of bid', 'bid securing', 'bid security', 'schedule', 'personnel', 'equipment',
        'eli', 'con-', 'fin-', 'exp-', 'per-', 'manufacturer', 'experience',
    ]
    items = []
    for requirement in bid_pack.tender.requirements.filter(is_mandatory=True):
        text = str(requirement.description).strip()
        lower = text.lower()
        if not is_clean_checklist_item(text):
            continue
        if any(word in lower for word in mapped_words):
            continue
        if text not in items:
            items.append(text)
    return items[:20]


def add_pdf_required_form_tables(elements, bid_pack, style):
    for spec in required_form_specs(bid_pack):
        if spec.get('kind') == 'letter_of_bid':
            elements.append(PageBreak())
        if spec.get('kind') == 'bid_securing_declaration':
            elements.append(PageBreak())
        elements.append(Paragraph(spec['title'], style['Heading3']))
        if spec.get('kind') == 'letter_of_bid':
            add_pdf_letter_of_bid(elements, bid_pack, style)
            elements.append(Spacer(1, 10))
            continue
        if spec.get('kind') == 'bid_securing_declaration':
            add_pdf_bid_securing_declaration(elements, bid_pack, style)
            elements.append(Spacer(1, 10))
            elements.append(PageBreak())
            continue
        if 'headers' in spec:
            rows = [spec['headers'], *spec['rows']]
            col_width = 475 / len(spec['headers'])
            elements.append(Table(rows, colWidths=[col_width] * len(spec['headers']), style=table_style()))
        else:
            rows = [['Field', 'TenderAI filled value']]
            rows.extend([[field, Paragraph(str(value), style['BodyText'])] for field, value in spec['rows']])
            elements.append(Table(rows, colWidths=[150, 325], style=table_style()))
        elements.append(Spacer(1, 10))


def add_docx_required_form_tables(document, bid_pack):
    for spec in required_form_specs(bid_pack):
        if spec.get('kind') == 'letter_of_bid':
            document.add_page_break()
        if spec.get('kind') == 'bid_securing_declaration':
            document.add_page_break()
        document.add_heading(spec['title'], level=2)
        if spec.get('kind') == 'letter_of_bid':
            add_docx_letter_of_bid(document, bid_pack)
            continue
        if spec.get('kind') == 'bid_securing_declaration':
            add_docx_bid_securing_declaration(document, bid_pack)
            document.add_page_break()
            continue
        if 'headers' in spec:
            table = document.add_table(rows=1, cols=len(spec['headers']))
            table.style = 'Table Grid'
            for idx, heading in enumerate(spec['headers']):
                table.rows[0].cells[idx].text = heading
            for row in spec['rows']:
                cells = table.add_row().cells
                for idx, value in enumerate(row):
                    cells[idx].text = str(value)
        else:
            table = document.add_table(rows=1, cols=2)
            table.style = 'Table Grid'
            table.rows[0].cells[0].text = 'Field'
            table.rows[0].cells[1].text = 'TenderAI filled value'
            for field, value in spec['rows']:
                cells = table.add_row().cells
                cells[0].text = str(field)
                cells[1].text = str(value)


def letter_of_bid_context(bid_pack):
    tender = bid_pack.tender
    company = bid_pack.company
    closing_date = tender.closing_at or tender.closing_date or '-'
    return {
        'date': timezone.localdate().strftime('%d/%m/%Y'),
        'bidding_no': tender.tender_number or tender.zppa_resource_id or '-',
        'invitation_no': tender.zppa_resource_id or tender.tender_number or '-',
        'to': tender.procuring_entity or '-',
        'works': tender.title,
        'bid_price': 'To be completed from the priced BOQ / schedule of prices',
        'discounts': 'None, unless stated separately in the priced schedule',
        'validity': 'Confirm from solicitation / ITB 18.1',
        'company': company.name,
        'company_address': company.address or '-',
        'company_tpin': company.tpin or '-',
        'representative': 'To be completed',
        'signatory_capacity': 'Authorised Representative',
        'submission_method': tender.submission_method or '-',
        'closing_date': closing_date,
    }


def letter_of_bid_declarations(context):
    return [
        'We have examined and have no reservations to the Bidding Documents, including Addenda issued in accordance with Instructions to Bidders (ITB) Clause 8.',
        f'We offer to execute in conformity with the Bidding Documents the following Works: {context["works"]}.',
        f'The total price of our Bid, excluding any discounts offered below is: {context["bid_price"]}.',
        f'The discounts offered and the methodology for their application are: {context["discounts"]}.',
        f'Our bid shall be valid for a period of {context["validity"]} days from the date fixed for the bid submission deadline and shall remain binding upon us.',
        'If price adjustment provisions apply, the Table(s) of Adjustment Data shall be considered part of this Bid.',
        'If our bid is accepted, we commit to obtain a performance security in accordance with the Bidding Document.',
        'Our firm, including any subcontractors or suppliers for any part of the Contract, have nationalities from eligible countries.',
        'We, including any subcontractors or suppliers for any part of the contract, do not have any conflict of interest in accordance with ITB 4.3.',
        'We are not participating, as a Bidder or as a subcontractor, in more than one bid in this bidding process, other than alternative offers submitted in accordance with ITB 13.',
        'Our firm, its affiliates or subsidiaries, including any subcontractors or suppliers for any part of the contract, has not been declared ineligible by ZPPA or by a United Nations Security Council decision.',
        'We are not a government owned entity / We are a government owned entity but meet the requirements of ITB 4.5. Delete whichever is not applicable.',
        'We have paid, or will pay, no commissions, gratuities, or fees with respect to the bidding process or execution of the Contract unless disclosed below.',
        'We understand that this bid, together with your written acceptance included in your notification of award, shall constitute a binding contract between us until a formal contract is prepared and executed.',
        'We understand that you are not bound to accept the best-evaluated bid or any other bid that you may receive.',
        f'If awarded the contract, the person named below shall act as Contractor’s Representative: {context["representative"]}.',
    ]


def add_pdf_letter_of_bid(elements, bid_pack, style):
    context = letter_of_bid_context(bid_pack)
    elements.append(Paragraph('The Bidder should prepare this Letter of Bid on company letterhead showing the complete name and address.', style['SmallMuted']))
    elements.append(Spacer(1, 6))
    rows = [
        ['Date', context['date']],
        ['Bidding No.', context['bidding_no']],
        ['Invitation for Bid No.', context['invitation_no']],
        ['To', context['to']],
        ['Bidder', context['company']],
    ]
    elements.append(Table(rows, colWidths=[145, 330], style=table_style()))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph('We, the undersigned, declare that:', style['BodyText']))
    for index, declaration in enumerate(letter_of_bid_declarations(context), start=1):
        letter = chr(96 + index)
        elements.append(Paragraph(f'({letter}) {declaration}', style['BodyText']))
    elements.append(Spacer(1, 8))
    commission_rows = [
        ['Name of Recipient', 'Address', 'Reason', 'Amount'],
        ['None', '-', '-', '-'],
    ]
    elements.append(Table(commission_rows, colWidths=[130, 130, 130, 85], style=table_style()))
    elements.append(Spacer(1, 8))
    signature_rows = [
        ['Name', 'To be completed'],
        ['In the capacity of', context['signatory_capacity']],
        ['Signed', '____________________________'],
        ['Duly authorized to sign the Bid for and on behalf of', context['company']],
        ['Date', context['date']],
    ]
    elements.append(Table(signature_rows, colWidths=[210, 265], style=table_style()))


def add_docx_letter_of_bid(document, bid_pack):
    context = letter_of_bid_context(bid_pack)
    document.add_paragraph('The Bidder should prepare this Letter of Bid on company letterhead showing the complete name and address.')
    table = document.add_table(rows=1, cols=2)
    table.style = 'Table Grid'
    table.rows[0].cells[0].text = 'Field'
    table.rows[0].cells[1].text = 'Value'
    for field, value in [
        ('Date', context['date']),
        ('Bidding No.', context['bidding_no']),
        ('Invitation for Bid No.', context['invitation_no']),
        ('To', context['to']),
        ('Bidder', context['company']),
    ]:
        cells = table.add_row().cells
        cells[0].text = field
        cells[1].text = str(value)
    document.add_paragraph('We, the undersigned, declare that:')
    for index, declaration in enumerate(letter_of_bid_declarations(context), start=1):
        letter = chr(96 + index)
        document.add_paragraph(f'({letter}) {declaration}')
    document.add_paragraph('Commissions, gratuities, or fees:')
    commission_table = document.add_table(rows=2, cols=4)
    commission_table.style = 'Table Grid'
    for idx, heading in enumerate(['Name of Recipient', 'Address', 'Reason', 'Amount']):
        commission_table.rows[0].cells[idx].text = heading
    for idx, value in enumerate(['None', '-', '-', '-']):
        commission_table.rows[1].cells[idx].text = value
    signature_table = document.add_table(rows=1, cols=2)
    signature_table.style = 'Table Grid'
    signature_table.rows[0].cells[0].text = 'Name'
    signature_table.rows[0].cells[1].text = 'To be completed'
    for field, value in [
        ('In the capacity of', context['signatory_capacity']),
        ('Signed', '____________________________'),
        ('Duly authorized to sign the Bid for and on behalf of', context['company']),
        ('Date', context['date']),
    ]:
        cells = signature_table.add_row().cells
        cells[0].text = field
        cells[1].text = str(value)


def bid_securing_declaration_context(bid_pack):
    tender = bid_pack.tender
    company = bid_pack.company
    return {
        'date': timezone.localdate().strftime('%d/%m/%Y'),
        'ref_no': tender.tender_number or tender.zppa_resource_id or '-',
        'alternative_no': 'Not applicable',
        'procuring_entity': tender.procuring_entity or '-',
        'bidder': company.name,
        'signatory': 'To be completed',
        'capacity': 'Authorised Representative',
        'signing_date': timezone.localdate().strftime('%d/%m/%Y'),
    }


def bid_securing_declaration_paragraphs(context):
    return [
        '1. We understand that, according to your conditions, bids must be supported by a Bid-Securing Declaration.',
        '2. We accept that we shall be liable to suspension from participating in public procurement in accordance with sections 95 and 96 of the Public Procurement Act No. 8 of 2020 if we are in breach of our obligations under the bid conditions because we:',
        '(a) have withdrawn our Bid during the period of bid validity specified by us in the Bidding Data Sheet; or',
        '(b) having been notified of the acceptance of our Bid by the Procuring Entity during the period of bid validity: (i) fail or refuse to execute the Contract, if required; or (ii) fail or refuse to furnish the Performance Security, in accordance with the Instructions to Bidders.',
        '3. We understand this Bid-Securing Declaration shall expire if we are not the successful Bidder, on the earlier of: (a) our receipt of a copy of your notification of the name of the successful Bidder; or (b) twenty-eight days after the expiration of our Bid.',
        '4. We understand that if we are a Joint Venture, the Bid-Securing Declaration shall be in the name of the Joint Venture that submits the bid. If the Joint Venture has not been legally constituted at the time of bidding, the declaration shall be in the names of all future partners as named in the letter of intent.',
    ]


def add_pdf_bid_securing_declaration(elements, bid_pack, style):
    context = bid_securing_declaration_context(bid_pack)
    title_style = style['Heading2'].clone('BidSecuringTitle')
    title_style.alignment = 1
    elements.append(Paragraph('FORM V', title_style))
    elements.append(Paragraph('Reg 88 (2)', title_style))
    elements.append(Paragraph('BID-SECURING DECLARATION', title_style))
    elements.append(Paragraph('The Bidder shall fill in this Form in accordance with the instructions indicated.', style['SmallMuted']))
    elements.append(Spacer(1, 8))
    rows = [
        ['Date', context['date']],
        ['Ref No.', context['ref_no']],
        ['Alternative No.', context['alternative_no']],
        ['Procuring Entity', context['procuring_entity']],
        ['Bidder', context['bidder']],
    ]
    elements.append(Table(rows, colWidths=[145, 330], style=table_style()))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph('We, the undersigned, declare that:', style['BodyText']))
    for paragraph in bid_securing_declaration_paragraphs(context):
        elements.append(Paragraph(paragraph, style['BodyText']))
    elements.append(Spacer(1, 10))
    signature_rows = [
        ['Signed', '____________________________'],
        ['In the capacity of', context['capacity']],
        ['Name', context['signatory']],
        ['Duly authorised to sign the bid for and on behalf of', context['bidder']],
        ['Dated on', context['signing_date']],
    ]
    elements.append(Table(signature_rows, colWidths=[230, 245], style=table_style()))


def add_docx_bid_securing_declaration(document, bid_pack):
    context = bid_securing_declaration_context(bid_pack)
    document.add_heading('FORM V', level=3)
    document.add_paragraph('Reg 88 (2)')
    document.add_paragraph('BID-SECURING DECLARATION')
    document.add_paragraph('The Bidder shall fill in this Form in accordance with the instructions indicated.')
    table = document.add_table(rows=1, cols=2)
    table.style = 'Table Grid'
    table.rows[0].cells[0].text = 'Field'
    table.rows[0].cells[1].text = 'Value'
    for field, value in [
        ('Date', context['date']),
        ('Ref No.', context['ref_no']),
        ('Alternative No.', context['alternative_no']),
        ('Procuring Entity', context['procuring_entity']),
        ('Bidder', context['bidder']),
    ]:
        cells = table.add_row().cells
        cells[0].text = field
        cells[1].text = str(value)
    document.add_paragraph('We, the undersigned, declare that:')
    for paragraph in bid_securing_declaration_paragraphs(context):
        document.add_paragraph(paragraph)
    signature_table = document.add_table(rows=1, cols=2)
    signature_table.style = 'Table Grid'
    signature_table.rows[0].cells[0].text = 'Signed'
    signature_table.rows[0].cells[1].text = '____________________________'
    for field, value in [
        ('In the capacity of', context['capacity']),
        ('Name', context['signatory']),
        ('Duly authorised to sign the bid for and on behalf of', context['bidder']),
        ('Dated on', context['signing_date']),
    ]:
        cells = signature_table.add_row().cells
        cells[0].text = field
        cells[1].text = str(value)


def price_schedule_rows(bid_pack):
    return []


def generate_bid_pack_pdf(bid_pack):
    style = styles()
    settings = SystemSettings.load()
    currency = settings.default_currency or 'ZMW'
    elements = []
    add_pdf_cover_page(elements, bid_pack)
    elements.append(PageBreak())
    add_pdf_table_of_contents(elements, bid_pack)
    elements.append(PageBreak())

    sections = build_bid_sections(bid_pack)
    for number, (title, lines) in enumerate(sections, start=1):
        if number > 1 and title in {
            'Cover Letter',
            'Bid Checklist',
            'Company Document Checklist',
            'Similar Experience Table',
        }:
            elements.append(PageBreak())
        elements.append(Paragraph(f'{number}. {title}', style['SectionTitle']))
        for line in lines:
            elements.append(Paragraph(str(line), style['BodyText']))
        elements.append(Spacer(1, 6))

        if title == 'ITB Ordered Bid Checklist':
            itb_rows = ordered_itb_rows(bid_pack)
            if itb_rows:
                rows = [['ITB Ref', 'Required Item', 'TenderAI Output', 'Status']]
                rows.extend([
                    [reference, Paragraph(required_item, style['BodyText']), Paragraph(output, style['BodyText']), status]
                    for reference, required_item, output, status in itb_rows
                ])
                elements.append(Table(rows, colWidths=[62, 190, 160, 65], style=table_style()))
            else:
                rows = [['Type', 'Requirement', 'Mandatory', 'Action']]
                rows.extend([
                    [kind, Paragraph(description, style['BodyText']), mandatory, action]
                    for kind, description, mandatory, action in requirements_matrix_rows(bid_pack)
                ])
                elements.append(Table(rows, colWidths=[95, 215, 65, 100], style=table_style()))
            elements.append(Spacer(1, 6))

        if title == 'XML Structured Bid Response':
            add_pdf_xml_bid_structure(elements, bid_pack, style, include_heading=False)

        if title == 'Submission Gaps':
            rows = [['Item', 'Status', 'Recommended action']]
            gap_rows = submission_gap_rows(bid_pack)
            if gap_rows:
                rows.extend([[item, status, Paragraph(action, style['BodyText'])] for item, status, action in gap_rows])
            else:
                rows.append(['No critical gaps detected', 'Ready', 'Continue final review before submission.'])
            elements.append(Table(rows, colWidths=[165, 80, 230], style=table_style()))
            elements.append(Spacer(1, 6))

        if title == 'Required Forms':
            add_pdf_required_form_tables(elements, bid_pack, style)

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
    add_docx_table_of_contents(document, bid_pack)
    document.add_page_break()

    for number, (title, lines) in enumerate(build_bid_sections(bid_pack), start=1):
        document.add_heading(f'{number}. {title}', level=1)
        for line in lines:
            document.add_paragraph(docx_safe_text(line), style='List Bullet' if title.endswith('Checklist') else None)

        if title == 'ITB Ordered Bid Checklist':
            table = document.add_table(rows=1, cols=4)
            table.style = 'Table Grid'
            headings = ['ITB Ref', 'Required Item', 'TenderAI Output', 'Status'] if ordered_itb_rows(bid_pack) else ['Type', 'Requirement', 'Mandatory', 'Action']
            for idx, heading in enumerate(headings):
                table.rows[0].cells[idx].text = heading
            row_source = ordered_itb_rows(bid_pack) or requirements_matrix_rows(bid_pack)
            for first, second, third, fourth in row_source:
                cells = table.add_row().cells
                cells[0].text = docx_safe_text(first)
                cells[1].text = docx_safe_text(second)
                cells[2].text = docx_safe_text(third)
                cells[3].text = docx_safe_text(fourth)

        if title == 'XML Structured Bid Response':
            add_docx_xml_bid_structure(document, bid_pack, include_heading=False)

        if title == 'Submission Gaps':
            gap_table = document.add_table(rows=1, cols=3)
            gap_table.style = 'Table Grid'
            for idx, heading in enumerate(['Item', 'Status', 'Recommended action']):
                gap_table.rows[0].cells[idx].text = heading
            rows = submission_gap_rows(bid_pack) or [('No critical gaps detected', 'Ready', 'Continue final review before submission.')]
            for item, status, action in rows:
                cells = gap_table.add_row().cells
                cells[0].text = docx_safe_text(item)
                cells[1].text = docx_safe_text(status)
                cells[2].text = docx_safe_text(action)

        if title == 'Required Forms':
            add_docx_required_form_tables(document, bid_pack)

        if title == 'Company Document Checklist':
            checklist_table = document.add_table(rows=1, cols=2)
            checklist_table.style = 'Table Grid'
            checklist_table.rows[0].cells[0].text = 'Document'
            checklist_table.rows[0].cells[1].text = 'Status'
            for name, status in company_document_checklist(bid_pack.company):
                cells = checklist_table.add_row().cells
                cells[0].text = docx_safe_text(name)
                cells[1].text = docx_safe_text(status)

    document.add_paragraph('\nAuthorised signatory: ________________________')
    document.add_paragraph(f'Prepared by: {settings.default_prepared_by_name or "________________________"}')
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def add_pdf_xml_bid_structure(elements, bid_pack, style, include_heading=True):
    if include_heading:
        elements.append(Paragraph('XML Structured Bid Response', style['Heading1']))
    elements.append(Paragraph(
        'This section follows the Tender Structure XML from ZPPA. Complete and attach the items below in the same envelope order.',
        style['BodyText'],
    ))
    elements.append(Spacer(1, 8))
    for group in xml_bid_structure_groups(bid_pack):
        elements.append(Paragraph(group['title'], style['Heading2']))
        rows = [['No.', 'Requirement', 'Mandatory', 'Expected response / attachment']]
        for item in group['items']:
            response_items = item.get('response_items') or []
            if response_items:
                response = '<br/>'.join(f'• {value}' for value in response_items)
            else:
                response = item.get('response') or 'To be completed / attached'
            rows.append([
                str(item.get('order') or ''),
                Paragraph(item.get('requirement') or item.get('title') or '-', style['BodyText']),
                'Yes' if item.get('mandatory') else 'No',
                Paragraph(response, style['BodyText']),
            ])
        elements.append(Table(rows, colWidths=[36, 165, 62, 212], style=table_style()))
        elements.append(Spacer(1, 10))


def add_docx_xml_bid_structure(document, bid_pack, include_heading=True):
    if include_heading:
        document.add_heading('XML Structured Bid Response', level=1)
    document.add_paragraph(
        'This section follows the Tender Structure XML from ZPPA. Complete and attach the items below in the same envelope order.'
    )
    for group in xml_bid_structure_groups(bid_pack):
        document.add_heading(group['title'], level=2)
        table = document.add_table(rows=1, cols=4)
        table.style = 'Table Grid'
        for idx, heading in enumerate(['No.', 'Requirement', 'Mandatory', 'Expected response / attachment']):
            table.rows[0].cells[idx].text = heading
        for item in group['items']:
            cells = table.add_row().cells
            cells[0].text = docx_safe_text(item.get('order') or '')
            cells[1].text = docx_safe_text(item.get('requirement') or item.get('title') or '-')
            cells[2].text = 'Yes' if item.get('mandatory') else 'No'
            response_items = item.get('response_items') or []
            if response_items:
                cells[3].text = ''
                for response in response_items:
                    cells[3].add_paragraph(docx_safe_text(response), style='List Bullet')
            else:
                cells[3].text = docx_safe_text(item.get('response') or 'To be completed / attached')


def docx_safe_text(value):
    text = str(value or '')
    return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', text)


def add_pdf_cover_page(elements, bid_pack):
    if is_raised_right(bid_pack.company):
        add_raised_right_pdf_cover_page(elements, bid_pack)
        return

    style = styles()
    company = bid_pack.company
    tender = bid_pack.tender
    elements.extend(letterhead_elements(company, 'Bid Submission Pack'))
    elements.append(Spacer(1, 30))
    elements.append(Paragraph(f'<b>Tender:</b> {tender.title}', style['Heading2']))
    elements.append(Paragraph(f'<b>Procuring Entity:</b> {tender.procuring_entity}', style['BodyText']))
    elements.append(Paragraph(f'<b>Tender Number:</b> {tender.tender_number or "-"}', style['BodyText']))
    elements.append(Paragraph(f'<b>Tender Unique ID:</b> {tender.tender_number or "-"}', style['BodyText']))
    elements.append(Paragraph(f'<b>ZPPA Resource ID:</b> {tender.zppa_resource_id or "-"}', style['BodyText']))
    elements.append(Paragraph(f'<b>Procurement Method:</b> {tender.procurement_method or "-"}', style['BodyText']))
    elements.append(Paragraph(f'<b>Submission Method:</b> {tender.submission_method or "-"}', style['BodyText']))
    elements.append(Paragraph(f'<b>Closing Date:</b> {tender.closing_at or tender.closing_date or "-"}', style['BodyText']))
    elements.append(Spacer(1, 26))
    elements.append(Paragraph(f'<b>Submitted by:</b> {company.name}', style['BodyText']))
    elements.append(Paragraph(f'<b>TPIN:</b> {company.tpin or "-"}', style['BodyText']))
    elements.append(Paragraph(f'<b>Address:</b> {company.address or "-"}', style['BodyText']))
    elements.append(Paragraph(f'<b>Email / Phone:</b> {company.email or "-"} / {company.phone or "-"}', style['BodyText']))


def is_raised_right(company):
    return company.name.strip().lower() == 'raised right investments limited'


def add_raised_right_pdf_cover_page(elements, bid_pack):
    style = styles()
    title_style = style['Title'].clone('RaisedRightCoverTitle')
    title_style.alignment = 1
    title_style.fontSize = 14
    title_style.leading = 18
    title_style.spaceAfter = 0

    label_style = style['BodyText'].clone('RaisedRightCoverLabel')
    label_style.alignment = 1
    label_style.fontName = 'Helvetica-Bold'
    label_style.fontSize = 12
    label_style.leading = 16

    body_style = style['BodyText'].clone('RaisedRightCoverBody')
    body_style.alignment = 1
    body_style.fontSize = 12
    body_style.leading = 18

    detail_style = style['BodyText'].clone('RaisedRightCoverDetail')
    detail_style.alignment = 1
    detail_style.fontSize = 9
    detail_style.leading = 12

    submitted_to = bid_pack.tender.procuring_entity or ''
    tender = bid_pack.tender
    elements.append(Spacer(1, 24))
    elements.append(Paragraph('<b>TENDER</b>', title_style))
    elements.append(Spacer(1, 38))
    elements.append(Paragraph(tender.title, body_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f'<b>Tender Number / Unique ID:</b> {tender.tender_number or "-"}', detail_style))
    elements.append(Paragraph(f'<b>ZPPA Resource ID:</b> {tender.zppa_resource_id or "-"}', detail_style))
    elements.append(Paragraph(f'<b>Procurement Method:</b> {tender.procurement_method or "-"}', detail_style))
    elements.append(Paragraph(f'<b>Submission Method:</b> {tender.submission_method or "-"}', detail_style))
    elements.append(Paragraph(f'<b>Closing Date:</b> {tender.closing_at or tender.closing_date or "-"}', detail_style))
    elements.append(Spacer(1, 54))
    elements.append(Paragraph('<b>SUBMITTED TO:</b>', label_style))
    if submitted_to:
        elements.append(Spacer(1, 14))
        elements.append(Paragraph(submitted_to, body_style))
    elements.append(Spacer(1, 118 if submitted_to else 146))
    elements.append(Paragraph('<b>SUBMITTED BY:</b>', label_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph('Raised Right Investments Ltd', body_style))
    elements.append(Paragraph('Plot No. 31C, Avondale, Off Great East Road', body_style))
    elements.append(Paragraph('Lusaka, Zambia', body_style))
    elements.append(Paragraph('Email: raisedright.zm@gmail.com', body_style))


def add_pdf_table_of_contents(elements, bid_pack):
    style = styles()
    elements.append(Paragraph('Table of Contents', style['Heading1']))
    rows = [['No.', 'Section']]
    rows.extend([[str(index), title] for index, title in enumerate(table_of_contents(bid_pack), start=1)])
    elements.append(Table(rows, colWidths=[45, 390], style=table_style()))


def append_company_certificate_pdfs(main_pdf, bid_pack):
    pdf_documents = ordered_certificate_documents(bid_pack)
    if not pdf_documents:
        return main_pdf

    writer = PdfWriter()
    append_pdf_bytes(writer, main_pdf)
    append_pdf_bytes(writer, attachment_index_pdf(bid_pack, pdf_documents))
    for index, document in enumerate(pdf_documents, start=1):
        try:
            divider = certificate_divider_pdf(document, index)
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


def ordered_certificate_documents(bid_pack):
    documents = [
        document for document in bid_pack.company.documents.all()
        if document.file and document.file.name.lower().endswith('.pdf')
    ]
    required_types = list(required_document_types(bid_pack.tender))

    def order_key(document):
        try:
            required_index = required_types.index(document.document_type)
        except ValueError:
            required_index = 100
        try:
            base_index = ATTACHMENT_ORDER.index(document.document_type)
        except ValueError:
            base_index = 999
        expiry = document.expiry_date or document.issue_date
        return (required_index, base_index, document.is_expired, expiry or '', document.title.lower())

    return sorted(documents, key=order_key)


def regeneration_status(bid_pack):
    if not bid_pack.generated_pdf or not bid_pack.generated_docx:
        return {
            'needed': True,
            'reason': 'PDF/DOCX files have not been generated yet.',
            'latest_change': None,
        }
    if not bid_pack.generated_at:
        return {
            'needed': True,
            'reason': 'This bid pack was generated before TenderAI started tracking generation dates.',
            'latest_change': None,
        }

    latest_document = bid_pack.company.documents.order_by('-uploaded_at').first()
    latest_task = bid_pack.tender.bid_tasks.order_by('-updated_at').first()
    candidates = []
    if latest_document:
        candidates.append((latest_document.uploaded_at, f'Company document updated: {latest_document.get_document_type_display()}'))
    if latest_task:
        candidates.append((latest_task.updated_at, f'Bid task updated: {latest_task.title}'))
    if bid_pack.tender.updated_at:
        candidates.append((bid_pack.tender.updated_at, 'Tender details were updated.'))

    if not candidates:
        return {'needed': False, 'reason': 'Generated files are current.', 'latest_change': None}

    latest_change, reason = max(candidates, key=lambda item: item[0])
    return {
        'needed': latest_change > bid_pack.generated_at,
        'reason': reason if latest_change > bid_pack.generated_at else 'Generated files are current.',
        'latest_change': latest_change,
    }


def attachment_index_pdf(bid_pack, documents):
    style = styles()
    elements = [
        Paragraph('Attached Company Certificates', style['Heading1']),
        Paragraph(
            'The following company documents are attached after this index in the order TenderAI recommends for bid review.',
            style['BodyText'],
        ),
        Spacer(1, 10),
    ]
    rows = [['No.', 'Document', 'Title', 'Expiry', 'Status']]
    rows.extend([
        [
            str(index),
            document.get_document_type_display(),
            document.title or document.get_document_type_display(),
            document.expiry_date or '-',
            document.status_label,
        ]
        for index, document in enumerate(documents, start=1)
    ])
    elements.append(Table(rows, colWidths=[35, 150, 165, 70, 70], style=table_style()))
    return build_pdf_response(elements, f'Attachment Index - {bid_pack.company.name}')


def append_pdf_bytes(writer, pdf_bytes):
    reader = PdfReader(BytesIO(pdf_bytes))
    for page in reader.pages:
        writer.add_page(page)


def certificate_divider_pdf(company_document, index=None):
    style = styles()
    title_style = style['Title']
    title_style.alignment = 1
    title_style.fontSize = 28
    title_style.leading = 34
    label = f'Attachment {index}' if index else 'Attachment'
    elements = [
        Spacer(1, A4[1] * 0.32),
        Paragraph(f'<b>{label}</b>', style['Heading1']),
        Spacer(1, 18),
        Paragraph(f'<b>{company_document.get_document_type_display()}</b>', title_style),
        Spacer(1, 14),
        Paragraph(f'Title: {company_document.title or company_document.get_document_type_display()}', style['BodyText']),
        Paragraph(f'Expiry: {company_document.expiry_date or "-"}', style['BodyText']),
        Paragraph(f'Status: {company_document.status_label}', style['BodyText']),
    ]
    return build_pdf_response(elements, f'Attachment - {company_document.title}')


def add_docx_cover_page(document, bid_pack):
    company = bid_pack.company
    tender = bid_pack.tender
    document.add_heading('Bid Submission Pack', 0)
    document.add_paragraph(f'Tender: {tender.title}')
    document.add_paragraph(f'Procuring Entity: {tender.procuring_entity}')
    document.add_paragraph(f'Tender Number / Unique ID: {tender.tender_number or "-"}')
    document.add_paragraph(f'ZPPA Resource ID: {tender.zppa_resource_id or "-"}')
    document.add_paragraph(f'Procurement Method: {tender.procurement_method or "-"}')
    document.add_paragraph(f'Submission Method: {tender.submission_method or "-"}')
    document.add_paragraph(f'Closing Date: {tender.closing_at or tender.closing_date or "-"}')
    document.add_paragraph('')
    document.add_heading('Submitted by', level=1)
    document.add_paragraph(company.name)
    document.add_paragraph(f'TPIN: {company.tpin or "-"}')
    document.add_paragraph(f'Address: {company.address or "-"}')
    document.add_paragraph(f'Email: {company.email or "-"}')
    document.add_paragraph(f'Phone: {company.phone or "-"}')


def add_docx_table_of_contents(document, bid_pack):
    document.add_heading('Table of Contents', level=1)
    for index, title in enumerate(table_of_contents(bid_pack), start=1):
        document.add_paragraph(f'{index}. {title}')


def build_bid_sections(bid_pack):
    tender = bid_pack.tender
    company = bid_pack.company
    sections = [
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
        ('Submission Gaps', [
            'Fix the following missing or expired items before treating this bid pack as ready for submission.',
        ]),
    ]
    if has_xml_bid_structure(bid_pack):
        sections.append((
            'XML Structured Bid Response',
            ['The response structure below follows the Tender Structure XML envelope order from ZPPA.'],
        ))
    else:
        sections.append((
            'ITB Ordered Bid Checklist',
            ['The checklist below follows the order captured from the solicitation ITB Documents Comprising the Bid table.'],
        ))
    sections.extend([
        ('Cover Letter', [
            f'We submit our bid for {tender.title}.',
            f'{company.name} confirms interest and availability to perform the required works/services/supplies.',
        ]),
        ('Form of Bid / Tender Submission Letter', [
            f'We, {company.name}, offer to execute the tender in accordance with the solicitation requirements.',
            'We confirm that our bid remains valid for the required validity period.',
        ]),
        ('Required Forms', [
            'TenderAI has prepared draft form tables using the tender and company information available. Review and complete any fields marked for confirmation before submission.',
        ]),
        ('Bid Checklist', build_bid_checklist(bid_pack)),
        ('Company Profile Summary', [
            company.profile_summary or f'{company.name} is a registered supplier/contractor.',
            f'TPIN: {company.tpin or "-"}',
            f'PACRA Registration: {company.registration_number or "-"}',
        ]),
        ('Price Schedule', [
            'Attach or complete the tender price schedule, bill of quantities, or financial offer required by the solicitation document.',
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
    ])
    return sections


def save_generated_files(bid_pack):
    pdf_bytes = generate_bid_pack_pdf(bid_pack)
    docx_bytes = generate_bid_pack_docx(bid_pack)
    safe_id = bid_pack.pk or 'new'
    bid_pack.generated_pdf.save(f'bid-pack-{safe_id}.pdf', ContentFile(pdf_bytes), save=False)
    bid_pack.generated_docx.save(f'bid-pack-{safe_id}.docx', ContentFile(docx_bytes), save=False)
    bid_pack.generated_at = timezone.now()
    bid_pack.save(update_fields=['generated_pdf', 'generated_docx', 'generated_at'])


def generate_xml_bid_documents(bid_pack):
    BidDocument.objects.filter(bid_pack=bid_pack).delete()
    created = []
    for group in xml_bid_structure_groups(bid_pack):
        for item in group['items']:
            bid_document = BidDocument.objects.create(
                bid_pack=bid_pack,
                envelope=group['title'],
                requirement=item.get('requirement') or item.get('title') or 'Bid requirement',
                expected_response='\n'.join(item.get('response_items') or [item.get('response', '')]).strip(),
                order=int(item.get('order') or len(created) + 1),
                mandatory=bool(item.get('mandatory')),
                matched_company_document=match_company_document_for_xml_item(bid_pack, item),
            )
            pdf_bytes = generate_single_bid_document_pdf(bid_document)
            bid_document.generated_pdf.save(
                f'{safe_slug(bid_document.order)}-{safe_slug(bid_document.requirement)}.pdf',
                ContentFile(pdf_bytes),
                save=False,
            )
            bid_document.generated_at = timezone.now()
            bid_document.save(update_fields=['generated_pdf', 'generated_at'])
            created.append(bid_document)
    return created


def generate_single_bid_document_pdf(bid_document):
    style = styles()
    elements = []
    bid_pack = bid_document.bid_pack
    company = bid_pack.company
    tender = bid_pack.tender

    elements.extend(letterhead_elements(company, f'Bid Document {bid_document.order}: {bid_document.requirement}'))
    elements.append(Spacer(1, 8))
    rows = [
        ['Tender', tender.title],
        ['Procuring Entity', tender.procuring_entity],
        ['Company', company.name],
        ['Envelope', bid_document.envelope or '-'],
        ['Mandatory', 'Yes' if bid_document.mandatory else 'No'],
    ]
    elements.append(Table(rows, colWidths=[130, 345], style=table_style()))
    elements.append(Spacer(1, 10))
    add_pdf_xml_preparation_checklist(elements, bid_document, style)
    elements.append(Spacer(1, 10))

    lower = bid_document.requirement.lower()
    if 'bid declaration' in lower or 'bid securing' in lower or 'bid security' in lower:
        add_pdf_bid_securing_declaration(elements, bid_pack, style)
    elif 'bid submission form' in lower or 'letter of bid' in lower:
        add_pdf_letter_of_bid(elements, bid_pack, style)
    elif 'power of attorney' in lower:
        add_pdf_placeholder_form(elements, bid_document, 'Power of Attorney / Signatory Authorisation', style)
    elif 'litigation' in lower:
        add_pdf_placeholder_form(elements, bid_document, 'Litigation Status Declaration', style)
    elif bid_document.matched_company_document:
        add_pdf_certificate_reference(elements, bid_document, style)
    else:
        add_pdf_placeholder_form(elements, bid_document, 'Tender Requirement Response', style)

    add_signature(elements, label='Authorised signatory')
    pdf = build_pdf_response(elements, bid_document.requirement)
    return append_matched_certificate_pdf(pdf, bid_document)


def add_pdf_xml_preparation_checklist(elements, bid_document, style):
    elements.append(Paragraph('XML Requirement Checklist', style['Heading2']))
    response_items = bid_document.expected_response_lines
    if not response_items:
        response_items = ['Complete or attach the response required by this XML item.']

    rows = [['No.', 'What must be prepared / attached', 'TenderAI match', 'Action']]
    for index, item in enumerate(response_items, start=1):
        item_text = f'{bid_document.requirement} {item}'
        matched = match_company_document_for_text(bid_document.bid_pack, item_text)
        expected_type = expected_document_type_for_text(item_text)
        if matched:
            match_text = f'{matched.get_document_type_display()} - {matched.title}'
            action = 'Attached from company documents'
        elif looks_like_attachment_request(item):
            match_text = expected_type.label if expected_type else 'Not found'
            action = 'Upload this document type or attach manually'
        else:
            match_text = 'Manual response'
            action = 'Fill in / confirm'
        rows.append([
            str(index),
            Paragraph(item, style['BodyText']),
            Paragraph(match_text, style['BodyText']),
            Paragraph(action, style['BodyText']),
        ])
    elements.append(Table(rows, colWidths=[30, 210, 140, 95], style=table_style()))

    missing = [
        item for item in response_items
        if looks_like_attachment_request(item) and not match_company_document_for_text(bid_document.bid_pack, f'{bid_document.requirement} {item}')
    ]
    if missing:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph('Manual action still needed:', style['Heading3']))
        for item in missing:
            elements.append(Paragraph(f'- {item}', style['BodyText']))


def looks_like_attachment_request(text):
    return any(word in text.lower() for word in ['attach', 'certificate', 'evidence', 'documentary', 'compliance', 'printout', 'status'])


def expected_document_type_for_text(text):
    text = normalize_match_text(text)
    for document_type, keywords in DOCUMENT_MATCH_RULES:
        if any(keyword in text for keyword in keywords):
            return document_type
    return None


def xml_required_document_evidence(tender):
    evidence = {}
    manual_items = []
    for item in tender.itb_11_items or []:
        response_items = item.get('response_items') or []
        if not response_items and item.get('response'):
            response_items = [item.get('response')]
        if not response_items:
            response_items = [item.get('requirement') or item.get('title') or '']
        for response_item in response_items:
            text = f"{item.get('requirement', '')} {response_item}"
            if not looks_like_attachment_request(text):
                continue
            document_type = expected_document_type_for_text(text)
            if document_type:
                bucket = evidence.setdefault(document_type, {
                    'document_type': document_type,
                    'label': document_type.label,
                    'examples': [],
                    'count': 0,
                })
                bucket['count'] += 1
                if response_item and len(bucket['examples']) < 3:
                    bucket['examples'].append(response_item)
            elif response_item:
                manual_items.append(response_item)
    return {
        'typed': list(evidence.values()),
        'manual_items': manual_items[:8],
        'manual_count': len(manual_items),
    }


def document_gap_rows_for_company(tender, company):
    rows = []
    for item in xml_required_document_evidence(tender)['typed']:
        docs = list(company.documents.filter(document_type=item['document_type']).order_by('-expiry_date', '-uploaded_at'))
        active = [document for document in docs if not document.is_expired]
        expired = [document for document in docs if document.is_expired]
        if active:
            status = 'Ready'
            badge = 'success'
            action = 'Ready for attachment'
            document = active[0]
        elif expired:
            status = 'Expired'
            badge = 'danger'
            action = 'Renew or upload a current copy'
            document = expired[0]
        else:
            status = 'Missing'
            badge = 'warning'
            action = 'Upload this document'
            document = None
        rows.append({
            **item,
            'status': status,
            'badge': badge,
            'action': action,
            'document': document,
        })
    return rows


def add_pdf_placeholder_form(elements, bid_document, title, style):
    elements.append(Paragraph(title, style['Heading2']))
    elements.append(Paragraph('Requirement / instruction:', style['Heading3']))
    elements.append(Paragraph(bid_document.requirement, style['BodyText']))
    if bid_document.expected_response:
        elements.append(Spacer(1, 6))
        elements.append(Paragraph('Expected response / attachments:', style['Heading3']))
        for line in bid_document.expected_response_lines:
            elements.append(Paragraph(f'- {line}', style['BodyText']))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph('Response:', style['Heading3']))
    elements.append(Paragraph('To be completed, signed, stamped, or attached as required by the solicitation document.', style['BodyText']))


def add_pdf_certificate_reference(elements, bid_document, style):
    document = bid_document.matched_company_document
    elements.append(Paragraph('Company certificate attachment', style['Heading2']))
    elements.append(Paragraph(
        f'TenderAI matched this requirement to the uploaded company document: {document.get_document_type_display()} - {document.title}.',
        style['BodyText'],
    ))
    rows = [
        ['Document type', document.get_document_type_display()],
        ['Title', document.title],
        ['Issue date', document.issue_date or '-'],
        ['Expiry date', document.expiry_date or '-'],
        ['Status', document.status_label],
    ]
    elements.append(Table(rows, colWidths=[130, 345], style=table_style()))


def match_company_document_for_xml_item(bid_pack, item):
    text = ' '.join([
        str(item.get('requirement', '')),
        str(item.get('response', '')),
        ' '.join(item.get('response_items') or []),
    ]).lower()
    return match_company_document_for_text(bid_pack, text)


DOCUMENT_MATCH_RULES = [
    (CompanyDocument.DocumentType.PACRA, [
        'pacra', 'certificate of incorporation', 'incorporation certificate',
        'schedule of directors', 'pacra printout', 'company registration',
    ]),
    (CompanyDocument.DocumentType.ZRA_TAX_CLEARANCE, [
        'tax clearance', 'zra tax', 'zra clearance', 'valid zra',
    ]),
    (CompanyDocument.DocumentType.TPIN_CERTIFICATE, ['tpin']),
    (CompanyDocument.DocumentType.NAPSA, ['napsa', 'pensions schemes authority']),
    (CompanyDocument.DocumentType.WORKERS_COMPENSATION, [
        'workers compensation', 'worker compensation', 'compensation fund',
        'workers compensation fund control board', 'wcfc',
    ]),
    (CompanyDocument.DocumentType.NCC_B, ['ncc b', 'ncc-b']),
    (CompanyDocument.DocumentType.NCC_R, ['ncc r', 'ncc-r']),
    (CompanyDocument.DocumentType.NCC_E, ['ncc e', 'ncc-e']),
    (CompanyDocument.DocumentType.NCC, ['ncc', 'national council for construction']),
    (CompanyDocument.DocumentType.ERB, [
        'erb', 'energy regulation board', 'erb rating', 'b+ or better',
    ]),
    (CompanyDocument.DocumentType.EIZ_CERTIFICATE, [
        'eiz', 'engineering institution of zambia', 'engineering institution',
    ]),
    (CompanyDocument.DocumentType.ROADWORTHINESS, [
        'roadworthiness', 'road worthy', 'vehicle compliance',
        'occupant safety', 'airbags', 'abs', 'seat belts', 'crash-test',
        'vehicle does not pose environmental',
    ]),
    (CompanyDocument.DocumentType.ZEMA_LICENSE, [
        'zema', 'zambia environmental management agency',
        'environmental compliance', 'environmental and social',
        'environmental certificate', 'environmental licence',
    ]),
    (CompanyDocument.DocumentType.ZPPA_REGISTRATION, [
        'zppa registration', 'public procurement registration',
    ]),
    (CompanyDocument.DocumentType.BANK_CONFIRMATION, [
        'bank confirmation', 'bank letter', 'financial resources',
        'liquid assets', 'credit line', 'bank statement',
    ]),
    (CompanyDocument.DocumentType.AUDITED_FINANCIALS, [
        'audited financial', 'financial statements', 'average annual turnover',
        'annual turnover', 'balance sheet', 'income statement',
    ]),
    (CompanyDocument.DocumentType.DELIVERY_EVIDENCE, [
        'delivery notes', 'delivery note', 'lpo', 'local purchase order',
        'grn', 'goods received note', 'award letters', 'award letter',
        'executed similar assignments', 'government of zambia',
    ]),
    (CompanyDocument.DocumentType.TRAINING_PROGRAMME, [
        'training programme', 'training program', 'technical capacity building',
        'capacity building', 'machine orientation', 'operator orientation',
    ]),
    (CompanyDocument.DocumentType.WARRANTY_UNDERTAKING, [
        'warranty', 'undertaking', 'delivery period', 'warranty period',
    ]),
    (CompanyDocument.DocumentType.PAST_CONTRACT, [
        'similar experience', 'past contract', 'traceable references',
        'reference letters', 'specific experience', 'general experience',
        'contracts that have been successfully executed',
    ]),
    (CompanyDocument.DocumentType.COMPANY_PROFILE, ['company profile']),
]


def normalize_match_text(value):
    return re.sub(r'\s+', ' ', str(value or '').replace('_', ' ').lower()).strip()


def document_match_text(document):
    filename = document.file.name if document.file else ''
    return normalize_match_text(' '.join([
        document.document_type,
        document.get_document_type_display(),
        document.title,
        document.notes,
        filename,
    ]))


def rank_document(document, score):
    expiry_rank = 0 if not document.is_expired else -3
    has_file_rank = 1 if document.file else 0
    expiry = document.expiry_date or document.issue_date
    date_rank = expiry.toordinal() if expiry else 0
    upload_rank = document.uploaded_at.timestamp() if document.uploaded_at else 0
    return (score + expiry_rank + has_file_rank, date_rank, upload_rank)


def best_document_for_type(company, document_type):
    docs = list(company.documents.filter(document_type=document_type))
    if not docs:
        return None
    return max(docs, key=lambda document: rank_document(document, 10))


def best_document_by_keywords(company, keywords):
    candidates = []
    for document in company.documents.all():
        haystack = document_match_text(document)
        score = sum(2 for keyword in keywords if keyword in haystack)
        if document.document_type == CompanyDocument.DocumentType.OTHER and score:
            score += 1
        if score:
            candidates.append((rank_document(document, score), document))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def match_company_document_for_text(bid_pack, text):
    text = normalize_match_text(text)
    for document_type, keywords in DOCUMENT_MATCH_RULES:
        if any(keyword in text for keyword in keywords):
            exact_match = best_document_for_type(bid_pack.company, document_type)
            if exact_match:
                return exact_match
            fallback_match = best_document_by_keywords(bid_pack.company, keywords)
            if fallback_match:
                return fallback_match
    return None


def append_matched_certificate_pdf(main_pdf, bid_document):
    document = bid_document.matched_company_document
    if not document or not document.file or not document.file.name.lower().endswith('.pdf'):
        return main_pdf
    writer = PdfWriter()
    append_pdf_bytes(writer, main_pdf)
    try:
        with document.file.open('rb') as handle:
            reader = PdfReader(handle)
            for page in reader.pages:
                writer.add_page(page)
    except Exception:
        return main_pdf
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def generate_combined_bid_documents_pdf(bid_pack):
    if not bid_pack.bid_documents.exists():
        generate_xml_bid_documents(bid_pack)
    writer = PdfWriter()
    for bid_document in bid_pack.bid_documents.order_by('order'):
        if not bid_document.generated_pdf:
            continue
        try:
            with bid_document.generated_pdf.open('rb') as handle:
                reader = PdfReader(handle)
                for page in reader.pages:
                    writer.add_page(page)
        except Exception:
            continue
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def safe_slug(value):
    text = re.sub(r'[^a-zA-Z0-9]+', '-', str(value)).strip('-').lower()
    return text[:70] or 'document'


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
