from textwrap import shorten

from django.utils import timezone

from companies.models import Company
from documents.models import CompanyDocument

from .models import BidTask, TenderMatch, TenderRequirement

CORE_READINESS_DOCUMENTS = [
    CompanyDocument.DocumentType.PACRA,
    CompanyDocument.DocumentType.TPIN_CERTIFICATE,
    CompanyDocument.DocumentType.ZRA_TAX_CLEARANCE,
    CompanyDocument.DocumentType.NAPSA,
    CompanyDocument.DocumentType.WORKERS_COMPENSATION,
    CompanyDocument.DocumentType.ZPPA_REGISTRATION,
    CompanyDocument.DocumentType.NCC,
    CompanyDocument.DocumentType.NCC_B,
    CompanyDocument.DocumentType.NCC_R,
    CompanyDocument.DocumentType.NCC_E,
    CompanyDocument.DocumentType.ERB,
    CompanyDocument.DocumentType.EIZ_CERTIFICATE,
    CompanyDocument.DocumentType.ZEMA_LICENSE,
    CompanyDocument.DocumentType.ROADWORTHINESS,
    CompanyDocument.DocumentType.BANK_CONFIRMATION,
    CompanyDocument.DocumentType.AUDITED_FINANCIALS,
    CompanyDocument.DocumentType.DELIVERY_EVIDENCE,
    CompanyDocument.DocumentType.TRAINING_PROGRAMME,
    CompanyDocument.DocumentType.WARRANTY_UNDERTAKING,
    CompanyDocument.DocumentType.COMPANY_PROFILE,
    CompanyDocument.DocumentType.PAST_CONTRACT,
]

STANDARD_BID_TASKS = [
    ('Upload solicitation document', 'Upload the PDF/DOCX solicitation document for analysis.', BidTask.Priority.HIGH),
    ('Run TenderAI analysis', 'Extract requirements, dates, forms, and disqualification risks.', BidTask.Priority.HIGH),
    ('Match companies', 'Compare tender requirements against company readiness.', BidTask.Priority.HIGH),
    ('Confirm selected company', 'Choose the company that will participate in the bid.', BidTask.Priority.HIGH),
    ('Upload missing certificates', 'Attach any required missing certificates before generating the bid pack.', BidTask.Priority.HIGH),
    ('Renew expired certificates', 'Renew any expired documents needed for submission.', BidTask.Priority.HIGH),
    ('Confirm site visit', 'Confirm site visit requirement, date, and attendance proof.', BidTask.Priority.MEDIUM),
    ('Confirm bid security', 'Confirm bid security amount/type or bid securing declaration.', BidTask.Priority.HIGH),
    ('Confirm participation fee', 'Confirm whether participation fee payment is required and attach proof.', BidTask.Priority.MEDIUM),
    ('Complete required forms', 'Complete tender forms, declarations, and schedules.', BidTask.Priority.HIGH),
    ('Generate bid pack', 'Generate the DOCX/PDF bid pack.', BidTask.Priority.MEDIUM),
    ('Review final PDF', 'Review cover page, checklist, certificates, and required sections.', BidTask.Priority.HIGH),
    ('Submit bid', 'Submit the bid using the required method before the deadline.', BidTask.Priority.HIGH),
    ('Mark tender as submitted', 'Update TenderAI status after submission.', BidTask.Priority.LOW),
]


DOC_KEYWORDS = {
    'PACRA': CompanyDocument.DocumentType.PACRA,
    'tax clearance': CompanyDocument.DocumentType.ZRA_TAX_CLEARANCE,
    'tpin': CompanyDocument.DocumentType.TPIN_CERTIFICATE,
    'napsa': CompanyDocument.DocumentType.NAPSA,
    'workers compensation': CompanyDocument.DocumentType.WORKERS_COMPENSATION,
    'ncc b': CompanyDocument.DocumentType.NCC_B,
    'ncc-b': CompanyDocument.DocumentType.NCC_B,
    'ncc r': CompanyDocument.DocumentType.NCC_R,
    'ncc-r': CompanyDocument.DocumentType.NCC_R,
    'ncc e': CompanyDocument.DocumentType.NCC_E,
    'ncc-e': CompanyDocument.DocumentType.NCC_E,
    'ncc': CompanyDocument.DocumentType.NCC,
    'erb': CompanyDocument.DocumentType.ERB,
    'energy regulation board': CompanyDocument.DocumentType.ERB,
    'eiz': CompanyDocument.DocumentType.EIZ_CERTIFICATE,
    'engineering institution of zambia': CompanyDocument.DocumentType.EIZ_CERTIFICATE,
    'zema': CompanyDocument.DocumentType.ZEMA_LICENSE,
    'environmental compliance': CompanyDocument.DocumentType.ZEMA_LICENSE,
    'environmental and social': CompanyDocument.DocumentType.ZEMA_LICENSE,
    'roadworthiness': CompanyDocument.DocumentType.ROADWORTHINESS,
    'road worthy': CompanyDocument.DocumentType.ROADWORTHINESS,
    'audited financial': CompanyDocument.DocumentType.AUDITED_FINANCIALS,
    'financial statements': CompanyDocument.DocumentType.AUDITED_FINANCIALS,
    'delivery notes': CompanyDocument.DocumentType.DELIVERY_EVIDENCE,
    'award letters': CompanyDocument.DocumentType.DELIVERY_EVIDENCE,
    'training programme': CompanyDocument.DocumentType.TRAINING_PROGRAMME,
    'warranty': CompanyDocument.DocumentType.WARRANTY_UNDERTAKING,
    'undertaking': CompanyDocument.DocumentType.WARRANTY_UNDERTAKING,
    'zppa': CompanyDocument.DocumentType.ZPPA_REGISTRATION,
    'bank': CompanyDocument.DocumentType.BANK_CONFIRMATION,
    'profile': CompanyDocument.DocumentType.COMPANY_PROFILE,
}

KEYWORD_DOC_REQUIREMENTS = {
    'construction': CompanyDocument.DocumentType.NCC,
    'ncc b': CompanyDocument.DocumentType.NCC_B,
    'ncc-b': CompanyDocument.DocumentType.NCC_B,
    'ncc r': CompanyDocument.DocumentType.NCC_R,
    'ncc-r': CompanyDocument.DocumentType.NCC_R,
    'ncc e': CompanyDocument.DocumentType.NCC_E,
    'ncc-e': CompanyDocument.DocumentType.NCC_E,
    'ncc': CompanyDocument.DocumentType.NCC,
    'erb': CompanyDocument.DocumentType.ERB,
    'energy regulation board': CompanyDocument.DocumentType.ERB,
    'eiz': CompanyDocument.DocumentType.EIZ_CERTIFICATE,
    'engineering institution of zambia': CompanyDocument.DocumentType.EIZ_CERTIFICATE,
    'zema': CompanyDocument.DocumentType.ZEMA_LICENSE,
    'zambia environmental management agency': CompanyDocument.DocumentType.ZEMA_LICENSE,
    'environmental compliance': CompanyDocument.DocumentType.ZEMA_LICENSE,
    'environmental and social': CompanyDocument.DocumentType.ZEMA_LICENSE,
    'roadworthiness': CompanyDocument.DocumentType.ROADWORTHINESS,
    'vehicle compliance': CompanyDocument.DocumentType.ROADWORTHINESS,
    'audited financial': CompanyDocument.DocumentType.AUDITED_FINANCIALS,
    'financial statements': CompanyDocument.DocumentType.AUDITED_FINANCIALS,
    'average annual turnover': CompanyDocument.DocumentType.AUDITED_FINANCIALS,
    'financial resources': CompanyDocument.DocumentType.BANK_CONFIRMATION,
    'delivery notes': CompanyDocument.DocumentType.DELIVERY_EVIDENCE,
    'lpo': CompanyDocument.DocumentType.DELIVERY_EVIDENCE,
    'grn': CompanyDocument.DocumentType.DELIVERY_EVIDENCE,
    'award letters': CompanyDocument.DocumentType.DELIVERY_EVIDENCE,
    'technical capacity building': CompanyDocument.DocumentType.TRAINING_PROGRAMME,
    'training programme': CompanyDocument.DocumentType.TRAINING_PROGRAMME,
    'machine orientation': CompanyDocument.DocumentType.TRAINING_PROGRAMME,
    'warranty': CompanyDocument.DocumentType.WARRANTY_UNDERTAKING,
    'undertaking': CompanyDocument.DocumentType.WARRANTY_UNDERTAKING,
    'zppa': CompanyDocument.DocumentType.ZPPA_REGISTRATION,
    'tax clearance': CompanyDocument.DocumentType.ZRA_TAX_CLEARANCE,
    'zra': CompanyDocument.DocumentType.ZRA_TAX_CLEARANCE,
    'workers compensation': CompanyDocument.DocumentType.WORKERS_COMPENSATION,
    'napsa': CompanyDocument.DocumentType.NAPSA,
    'similar experience': CompanyDocument.DocumentType.PAST_CONTRACT,
    'past contract': CompanyDocument.DocumentType.PAST_CONTRACT,
}

NCC_ALTERNATE_TYPES = {
    CompanyDocument.DocumentType.NCC,
    CompanyDocument.DocumentType.NCC_B,
    CompanyDocument.DocumentType.NCC_R,
    CompanyDocument.DocumentType.NCC_E,
}


def required_document_types(tender):
    required = set()
    corpus = ' '.join([
        tender.title or '',
        tender.description or '',
        tender.procurement_method or '',
        tender.submission_method or '',
        ' '.join(f"{row.get('label', '')} {row.get('value', '')}" for row in (tender.zppa_details or [])),
    ]).lower()
    for keyword, doc_type in KEYWORD_DOC_REQUIREMENTS.items():
        if keyword in corpus:
            required.add(doc_type)
    for requirement in tender.requirements.all():
        text = requirement.description.lower()
        if requirement.requirement_type in {
            TenderRequirement.RequirementType.MANDATORY_DOCUMENT,
            TenderRequirement.RequirementType.CERTIFICATE,
        }:
            for keyword, doc_type in DOC_KEYWORDS.items():
                if keyword in text:
                    required.add(doc_type)
    return required


def tender_signals(tender):
    corpus = ' '.join([
        tender.title or '',
        tender.description or '',
        ' '.join(f"{row.get('label', '')} {row.get('value', '')}" for row in (tender.zppa_details or [])),
    ]).lower()
    return {
        'bid_security': 'bid security' in corpus or 'bid securing declaration' in corpus,
        'site_visit': 'site visit' in corpus or 'mandatory visit' in corpus,
        'construction': 'construction' in corpus or 'ncc' in corpus,
        'similar_experience': 'similar experience' in corpus or 'past contract' in corpus,
    }


def calculate_tender_matches(tender, organization=None):
    today = timezone.localdate()
    required_docs = required_document_types(tender)
    signals = tender_signals(tender)
    matches = []
    companies = Company.objects.prefetch_related('documents', 'business_categories')
    if organization:
        companies = companies.filter(organization=organization)
    for company in companies:
        docs = list(company.documents.all())
        active_types = {doc.document_type for doc in docs if not doc.expiry_date or doc.expiry_date >= today}
        expired_types = {doc.document_type for doc in docs if doc.expiry_date and doc.expiry_date < today}
        effective_active_types = set(active_types)
        if active_types & NCC_ALTERNATE_TYPES:
            effective_active_types.add(CompanyDocument.DocumentType.NCC)
        missing = sorted(required_docs - active_types - expired_types)
        if CompanyDocument.DocumentType.NCC in required_docs and effective_active_types & NCC_ALTERNATE_TYPES:
            missing = [doc_type for doc_type in missing if doc_type != CompanyDocument.DocumentType.NCC]
        expired = sorted(required_docs & expired_types)

        score = 35
        if tender.category and company.business_categories.filter(pk=tender.category_id).exists():
            score += 20
        elif tender.category:
            score -= 10
        if required_docs:
            met_docs = required_docs - set(missing) - set(expired)
            if CompanyDocument.DocumentType.NCC in required_docs and effective_active_types & NCC_ALTERNATE_TYPES:
                met_docs.add(CompanyDocument.DocumentType.NCC)
            score += int(35 * (len(met_docs) / len(required_docs)))
        else:
            score += 10
        if signals['bid_security']:
            score -= 5
        if signals['site_visit']:
            score -= 5
        if signals['similar_experience'] and CompanyDocument.DocumentType.PAST_CONTRACT not in active_types:
            score -= 10
        score -= len(expired) * 5
        score = max(0, min(100, score))

        action_bits = []
        if missing:
            action_bits.append('Upload missing required documents.')
        if expired:
            action_bits.append('Renew expired documents.')
        if signals['bid_security']:
            action_bits.append('Confirm bid security or bid securing declaration.')
        if signals['site_visit']:
            action_bits.append('Check site visit date and attendance requirement.')
        if signals['similar_experience'] and CompanyDocument.DocumentType.PAST_CONTRACT not in active_types:
            action_bits.append('Attach similar past contracts.')
        if action_bits:
            action = ' '.join(action_bits)
        elif score >= 80:
            action = 'Strong candidate for this bid.'
        else:
            action = 'Review category fit and tender requirements manually.'

        match, _ = TenderMatch.objects.update_or_create(
            tender=tender,
            company=company,
            defaults={
                'score': score,
                'missing_documents': ', '.join(missing),
                'expired_documents': ', '.join(expired),
                'recommended_action': action,
            },
        )
        matches.append(match)
    return sorted(matches, key=lambda item: item.score, reverse=True)


def document_type_label(document_type):
    try:
        return CompanyDocument.DocumentType(document_type).label
    except ValueError:
        return str(document_type).replace('_', ' ').title()


def split_document_type_values(value):
    if not value:
        return []
    return [item.strip() for item in value.split(',') if item.strip()]


def readable_document_list(value):
    return [document_type_label(item) for item in split_document_type_values(value)]


def company_readiness(company, required_types=None):
    today = timezone.localdate()
    required_types = list(required_types or CORE_READINESS_DOCUMENTS)
    rows = []
    for doc_type in required_types:
        docs = list(company.documents.filter(document_type=doc_type).order_by('-expiry_date', '-uploaded_at'))
        active_docs = [doc for doc in docs if not doc.expiry_date or doc.expiry_date >= today]
        expired_docs = [doc for doc in docs if doc.expiry_date and doc.expiry_date < today]
        if active_docs:
            status = 'Ready'
            badge = 'success'
            detail = active_docs[0].expiry_date or 'No expiry'
        elif expired_docs:
            status = 'Expired'
            badge = 'danger'
            detail = expired_docs[0].expiry_date
        else:
            status = 'Missing'
            badge = 'warning'
            detail = 'Upload needed'
        rows.append({
            'type': doc_type,
            'label': document_type_label(doc_type),
            'status': status,
            'badge': badge,
            'detail': detail,
        })
    ready_count = sum(1 for row in rows if row['status'] == 'Ready')
    return {
        'rows': rows,
        'ready_count': ready_count,
        'total_count': len(rows),
        'score': int((ready_count / len(rows)) * 100) if rows else 0,
    }


def company_profile_gaps(company):
    checks = [
        ('TPIN', company.tpin),
        ('PACRA registration number', company.registration_number),
        ('Phone', company.phone),
        ('Email', company.email),
        ('Address', company.address),
        ('Profile summary', company.profile_summary),
    ]
    return [label for label, value in checks if not value]


def tender_decision(match, tender=None):
    tender = tender or match.tender
    missing = readable_document_list(match.missing_documents)
    expired = readable_document_list(match.expired_documents)
    signals = tender_signals(tender)
    blockers = []
    warnings = []

    if missing:
        blockers.append(f'Missing required documents: {", ".join(missing)}.')
    if expired:
        blockers.append(f'Expired required documents: {", ".join(expired)}.')
    if signals['site_visit'] or tender.site_visit_date:
        warnings.append('Confirm site visit attendance and proof before submission.')
    if signals['bid_security'] or tender.bid_security_amount:
        warnings.append('Confirm bid security or bid securing declaration before pricing the bid.')
    if tender.participation_fee:
        warnings.append(f'Participation fee is recorded as ZMW {tender.participation_fee}.')

    if match.score >= 80 and not blockers:
        recommendation = 'Bid'
        tone = 'success'
        next_step = 'Start preparing the bid pack and review the solicitation requirements line by line.'
    elif match.score >= 55:
        recommendation = 'Prepare after fixing documents'
        tone = 'warning'
        next_step = 'Fix the missing or expired items first, then generate the bid pack.'
    else:
        recommendation = 'Do not bid yet'
        tone = 'danger'
        next_step = 'Use this company only after improving document readiness or choose a better matched company.'

    return {
        'match': match,
        'recommendation': recommendation,
        'tone': tone,
        'next_step': next_step,
        'missing': missing,
        'expired': expired,
        'warnings': warnings,
        'blockers': blockers,
    }


def tender_decisions(tender, matches=None):
    matches = matches if matches is not None else calculate_tender_matches(tender)
    return [tender_decision(match, tender) for match in matches]


GENERATABLE_REQUIREMENT_KEYWORDS = [
    'bid declaration',
    'bid securing declaration',
    'bid submission form',
    'letter of bid',
    'power of attorney',
    'letter of authorization',
    'authorisation',
    'validity',
    'delivery period',
    'payment terms',
    'programme',
    'schedule',
    'technical specification',
    'technical response',
    'equipment',
    'personnel',
    'experience',
    'boq',
    'bill of quantities',
]

EXTERNAL_ACTION_KEYWORDS = [
    'line of credit',
    'bank statement',
    'site visit',
    'site visit certificate',
    'tax clearance',
    'napsa',
    'workers compensation',
    'ncc',
]


def tender_workspace_tree(tender, xml_items, company=None):
    today = timezone.localdate()
    company_documents = []
    if company:
        company_documents = list(company.documents.all())
    group_map = {}
    groups = []
    total_items = 0
    completed_items = 0
    mandatory_total = 0
    mandatory_completed = 0

    for item in xml_items or []:
        envelope = item.get('envelope') or 'Bid requirements'
        if envelope not in group_map:
            group_map[envelope] = {
                'name': envelope,
                'items': [],
                'total': 0,
                'completed': 0,
                'percent': 0,
            }
            groups.append(group_map[envelope])

        row = tender_workspace_requirement_row(item, company_documents, today, bool(company))
        group_map[envelope]['items'].append(row)
        group_map[envelope]['total'] += 1
        total_items += 1
        if row['is_complete']:
            group_map[envelope]['completed'] += 1
            completed_items += 1
        if row['mandatory']:
            mandatory_total += 1
            if row['is_complete']:
                mandatory_completed += 1

    for group in groups:
        group['percent'] = int((group['completed'] / group['total']) * 100) if group['total'] else 0

    overall_percent = int((completed_items / total_items) * 100) if total_items else 0
    return {
        'groups': groups,
        'total': total_items,
        'completed': completed_items,
        'percent': overall_percent,
        'mandatory_total': mandatory_total,
        'mandatory_completed': mandatory_completed,
        'has_company': bool(company),
        'company': company,
    }


def tender_workspace_requirement_row(item, company_documents, today, has_company):
    text = ' '.join([
        str(item.get('requirement') or ''),
        str(item.get('title') or ''),
        str(item.get('response') or ''),
        ' '.join(str(line) for line in item.get('response_items') or []),
    ])
    normalized = text.lower()
    doc_type = document_type_for_requirement_text(normalized)
    matched_document = None
    if doc_type:
        matched_document = best_company_document_for_type(company_documents, doc_type, today)

    if not has_company:
        status = 'Company not selected'
        badge = 'secondary'
        next_step = 'Select a company to check whether this item is available, expired, or missing.'
        is_complete = False
    elif matched_document:
        if matched_document.expiry_date and matched_document.expiry_date < today:
            status = 'Expired'
            badge = 'danger'
            next_step = 'Upload a valid current copy before submission.'
            is_complete = False
        else:
            status = 'Available'
            badge = 'success'
            next_step = 'Use this uploaded company document and confirm it matches the tender wording.'
            is_complete = True
    elif doc_type:
        status = 'Document missing'
        badge = 'warning'
        next_step = f'Upload {CompanyDocument.DocumentType(doc_type).label} under the selected company.'
        is_complete = False
    elif any(keyword in normalized for keyword in EXTERNAL_ACTION_KEYWORDS):
        status = 'External action required'
        badge = 'danger'
        next_step = 'Obtain this evidence from the bank, authority, procuring entity, or site visit officer.'
        is_complete = False
    elif any(keyword in normalized for keyword in GENERATABLE_REQUIREMENT_KEYWORDS):
        status = 'Draft required'
        badge = 'info'
        next_step = 'TenderAI can generate a draft, but it must be reviewed, signed, stamped, or completed.'
        is_complete = False
    else:
        status = 'Information required'
        badge = 'secondary'
        next_step = 'Review the XML instruction and decide whether to upload evidence or prepare a response.'
        is_complete = False

    return {
        'order': item.get('order'),
        'reference': item.get('reference') or item.get('parent_reference') or '',
        'name': item.get('requirement') or item.get('title') or 'Bid requirement',
        'instruction_lines': item.get('response_items') or ([item.get('response')] if item.get('response') else []),
        'mandatory': bool(item.get('mandatory')),
        'status': status,
        'badge': badge,
        'next_step': next_step,
        'document_type': doc_type,
        'matched_document': matched_document,
        'is_complete': is_complete,
    }


def document_type_for_requirement_text(normalized_text):
    for keyword, doc_type in KEYWORD_DOC_REQUIREMENTS.items():
        if keyword in normalized_text:
            return doc_type
    for keyword, doc_type in DOC_KEYWORDS.items():
        if keyword in normalized_text:
            return doc_type
    return None


def best_company_document_for_type(company_documents, doc_type, today):
    matching = [document for document in company_documents if document.document_type == doc_type]
    if doc_type == CompanyDocument.DocumentType.NCC:
        matching.extend(document for document in company_documents if document.document_type in NCC_ALTERNATE_TYPES)
    active = [document for document in matching if not document.expiry_date or document.expiry_date >= today]
    if active:
        return sorted(active, key=lambda document: document.expiry_date or today, reverse=True)[0]
    expired = [document for document in matching if document.expiry_date and document.expiry_date < today]
    if expired:
        return sorted(expired, key=lambda document: document.expiry_date, reverse=True)[0]
    return None


def ensure_bid_tasks(tender):
    deadline = tender.deadline_date
    for index, (title, description, priority) in enumerate(STANDARD_BID_TASKS, start=1):
        BidTask.objects.get_or_create(
            tender=tender,
            title=title,
            defaults={
                'description': description,
                'priority': priority,
                'due_date': deadline,
                'sort_order': index * 10,
            },
        )
    return tender.bid_tasks.all()


def ensure_analysis_bid_tasks(tender, analysis):
    deadline = tender.deadline_date
    created = 0

    task_specs = []
    ordered_bid_text = ''
    for item in analysis.get('ordered_bid_items', [])[:30]:
        reference = item.get('reference') or f'Bid item {item.get("order", "")}'.strip()
        title = item.get('title') or ''
        if not title:
            continue
        ordered_bid_text += f' {title.lower()}'
        task_specs.append((
            f'{reference}: {shorten(str(title), width=120, placeholder="...")}',
            'Prepare this item in the same order it appears in the ITB Documents Comprising the Bid table.',
            BidTask.Priority.HIGH,
            200 + int(item.get('order') or 0),
        ))

    for document in analysis.get('required_documents', [])[:20]:
        if str(document).lower() in ordered_bid_text:
            continue
        task_specs.append((
            f'Attach required document: {shorten(str(document), width=90, placeholder="...")}',
            'Upload or confirm this required company document is valid, readable, and not expired.',
            BidTask.Priority.HIGH,
            210,
        ))

    for form in analysis.get('forms_required', [])[:15]:
        if str(form).lower() in ordered_bid_text:
            continue
        task_specs.append((
            f'Complete form: {shorten(str(form), width=100, placeholder="...")}',
            'Complete, sign, stamp, and include this form/declaration in the bid pack.',
            BidTask.Priority.HIGH,
            310,
        ))

    for form in analysis.get('qualification_forms', [])[:25]:
        title = f'{form.get("code", "").strip()}: {form.get("title", "").strip()}'.strip(': ')
        if not title:
            continue
        task_specs.append((
            f'Complete qualification form: {shorten(title, width=110, placeholder="...")}',
            f'Complete this form from the qualification factor: {form.get("factor", "Qualification")}.',
            BidTask.Priority.HIGH,
            500 + len(task_specs),
        ))

    for criterion in analysis.get('evaluation_criteria', [])[:8]:
        task_specs.append((
            f'Review evaluation item: {shorten(str(criterion), width=100, placeholder="...")}',
            'Confirm the bid response gives evidence for this evaluation or responsiveness requirement.',
            BidTask.Priority.MEDIUM,
            410,
        ))

    if analysis.get('bid_security_required'):
        task_specs.append((
            'Prepare bid security or bid securing declaration',
            'Confirm the exact type, amount, validity period, wording, and attachment required by the solicitation.',
            BidTask.Priority.HIGH,
            120,
        ))

    if analysis.get('site_visit_required') or tender.site_visit_date:
        task_specs.append((
            'Confirm site visit requirement',
            'Check whether the site visit is mandatory and attach attendance/proof if required.',
            BidTask.Priority.HIGH,
            130,
        ))

    if analysis.get('dates'):
        task_specs.append((
            'Review solicitation dates and deadlines',
            'Check closing date, clarification deadline, bid opening date, site visit date, and any payment deadlines.',
            BidTask.Priority.HIGH,
            100,
        ))

    if analysis.get('clarification_address') or analysis.get('submission_address'):
        task_specs.append((
            'Confirm clarification and submission address',
            'Review the ITB/BDS address block and confirm where questions, physical submission, or online submission must go.',
            BidTask.Priority.HIGH,
            115,
        ))

    for offset, (title, description, priority, base_order) in enumerate(task_specs):
        task, was_created = BidTask.objects.get_or_create(
            tender=tender,
            title=title,
            defaults={
                'description': description,
                'priority': priority,
                'due_date': deadline,
                'sort_order': base_order + offset,
            },
        )
        if not was_created:
            fields = []
            if task.sort_order != base_order + offset:
                task.sort_order = base_order + offset
                fields.append('sort_order')
            if task.description != description:
                task.description = description
                fields.append('description')
            if task.priority != priority:
                task.priority = priority
                fields.append('priority')
            if deadline and task.due_date != deadline:
                task.due_date = deadline
                fields.append('due_date')
            if fields:
                fields.append('updated_at')
                task.save(update_fields=fields)
        created += int(was_created)
    return created


def bid_pack_output_for_task(task):
    title = task.title.lower()
    if 'letter of bid' in title:
        return 'Form of Bid / Tender Submission Letter'
    if 'bill of quantities' in title or 'priced' in title or 'schedule' in title:
        return 'Price schedule / BOQ section'
    if 'bid security' in title:
        return 'Bid security declaration or bank guarantee attachment'
    if 'alternative bids' in title:
        return 'Alternative bid confirmation, if permitted'
    if 'signatory' in title or 'authorizing' in title or 'authorization' in title:
        return 'Power of attorney / board authorization'
    if 'qualification' in title or 'documentary evidence' in title:
        return 'Company certificates, profile, and experience attachments'
    if 'technical proposal' in title:
        return 'Technical proposal / methodology / delivery plan'
    if 'bds' in title:
        return 'Extra BDS-required documents'
    return 'Manual bid pack attachment'


def bid_task_progress(tender):
    tasks = list(ensure_bid_tasks(tender))
    itb_tasks = [task for task in tasks if task.title.startswith('ITB ')]
    other_tasks = [task for task in tasks if not task.title.startswith('ITB ')]
    itb_items = [
        {
            'task': task,
            'output': bid_pack_output_for_task(task),
        }
        for task in itb_tasks
    ]
    total = len(tasks)
    done = sum(1 for task in tasks if task.status == BidTask.Status.DONE)
    blocked = sum(1 for task in tasks if task.status == BidTask.Status.BLOCKED)
    pending = total - done - blocked
    return {
        'tasks': tasks,
        'itb_tasks': itb_tasks,
        'itb_items': itb_items,
        'other_tasks': other_tasks,
        'total': total,
        'done': done,
        'blocked': blocked,
        'pending': pending,
        'percent': int((done / total) * 100) if total else 0,
    }
