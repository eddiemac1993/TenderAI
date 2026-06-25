from django.utils import timezone

from companies.models import Company
from documents.models import CompanyDocument

from .models import TenderMatch, TenderRequirement


DOC_KEYWORDS = {
    'PACRA': CompanyDocument.DocumentType.PACRA,
    'tax clearance': CompanyDocument.DocumentType.ZRA_TAX_CLEARANCE,
    'tpin': CompanyDocument.DocumentType.TPIN_CERTIFICATE,
    'napsa': CompanyDocument.DocumentType.NAPSA,
    'workers compensation': CompanyDocument.DocumentType.WORKERS_COMPENSATION,
    'ncc': CompanyDocument.DocumentType.NCC,
    'erb': CompanyDocument.DocumentType.ERB,
    'energy regulation board': CompanyDocument.DocumentType.ERB,
    'eiz': CompanyDocument.DocumentType.EIZ_CERTIFICATE,
    'engineering institution of zambia': CompanyDocument.DocumentType.EIZ_CERTIFICATE,
    'zppa': CompanyDocument.DocumentType.ZPPA_REGISTRATION,
    'bank': CompanyDocument.DocumentType.BANK_CONFIRMATION,
    'profile': CompanyDocument.DocumentType.COMPANY_PROFILE,
}

KEYWORD_DOC_REQUIREMENTS = {
    'construction': CompanyDocument.DocumentType.NCC,
    'ncc': CompanyDocument.DocumentType.NCC,
    'erb': CompanyDocument.DocumentType.ERB,
    'energy regulation board': CompanyDocument.DocumentType.ERB,
    'eiz': CompanyDocument.DocumentType.EIZ_CERTIFICATE,
    'engineering institution of zambia': CompanyDocument.DocumentType.EIZ_CERTIFICATE,
    'zppa': CompanyDocument.DocumentType.ZPPA_REGISTRATION,
    'tax clearance': CompanyDocument.DocumentType.ZRA_TAX_CLEARANCE,
    'zra': CompanyDocument.DocumentType.ZRA_TAX_CLEARANCE,
    'workers compensation': CompanyDocument.DocumentType.WORKERS_COMPENSATION,
    'napsa': CompanyDocument.DocumentType.NAPSA,
    'similar experience': CompanyDocument.DocumentType.PAST_CONTRACT,
    'past contract': CompanyDocument.DocumentType.PAST_CONTRACT,
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


def calculate_tender_matches(tender):
    today = timezone.localdate()
    required_docs = required_document_types(tender)
    signals = tender_signals(tender)
    matches = []
    for company in Company.objects.prefetch_related('documents', 'business_categories'):
        docs = list(company.documents.all())
        active_types = {doc.document_type for doc in docs if not doc.expiry_date or doc.expiry_date >= today}
        expired_types = {doc.document_type for doc in docs if doc.expiry_date and doc.expiry_date < today}
        missing = sorted(required_docs - active_types - expired_types)
        expired = sorted(required_docs & expired_types)

        score = 35
        if tender.category and company.business_categories.filter(pk=tender.category_id).exists():
            score += 20
        elif tender.category:
            score -= 10
        if required_docs:
            score += int(35 * (len(required_docs - set(missing) - set(expired)) / len(required_docs)))
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
