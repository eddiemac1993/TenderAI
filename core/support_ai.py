import re


SUPPORT_TOPICS = [
    {
        'keywords': ['zppa url', 'find by url', 'resourceid', 'resource id', 'paste url'],
        'answer': (
            'Open Tenders, click Find by ZPPA URL, paste the public ZPPA tender link, and submit. '
            'TenderAI will import the tender, fetch public documents/XML where available, then open the tender workspace.'
        ),
    },
    {
        'keywords': ['scrape', 'scraping', 'scrape today', 'zppa'],
        'answer': (
            'Use Tenders > Scrape today when running locally. PythonAnywhere free accounts may block ZPPA outbound access, '
            'so online scraping can fail with a 403 tunnel error. For protected or paid ZPPA documents, download them manually and upload them to the tender.'
        ),
    },
    {
        'keywords': ['solicitation', 'upload document', 'xml', 'tender structure', 'analyze'],
        'answer': (
            'Open the tender detail page and use Upload solicitation / Ask AI. You can upload PDF, DOCX, XML, or TXT. '
            'TenderAI extracts requirements, ITB 11.1 items, addresses, dates, and document evidence from the file.'
        ),
    },
    {
        'keywords': ['bid document', 'generate bid', 'bid pack', 'combined pdf', 'cover page'],
        'answer': (
            'Open a tender, click Generate bid documents, choose the company, then review the generated bid pack. '
            'TenderAI follows the XML structure where available, creates separate documents, and can combine them into one PDF.'
        ),
    },
    {
        'keywords': ['missing document', 'certificate', 'zra', 'pacra', 'napsa', 'zema', 'erb', 'roadworthiness'],
        'answer': (
            'Open the tender detail page and check the XML evidence checklist. Missing or expired items have Upload buttons that preselect the company and document type.'
        ),
    },
    {
        'keywords': ['company profile', 'generate profile', 'profile document'],
        'answer': (
            'Upload the company head profile as a Company Profile document, then open the company and use Generate Profile. '
            'TenderAI starts with the profile document and attaches uploaded certificates.'
        ),
    },
    {
        'keywords': ['match', 'which company', 'participate', 'bid or not'],
        'answer': (
            'Open the tender and use Should we bid? TenderAI compares the tender requirements against company categories, certificates, expired documents, and past contracts.'
        ),
    },
    {
        'keywords': ['council', 'cdf', 'facebook', 'grant', 'bursary'],
        'answer': (
            'Use Council Opportunities to view public council posts. Add or update council Facebook URLs from the council source list/admin, then run the council scraper.'
        ),
    },
    {
        'keywords': ['update app', 'github pull', 'new version'],
        'answer': (
            'When updates are available, use the Update link in the navigation. It runs the safe local update process, then you may need to restart TenderAI.'
        ),
    },
    {
        'keywords': ['admin', 'password', 'superuser'],
        'answer': (
            'Open Admin from the navigation and sign in with your Django superuser. From admin you can manage companies, documents, tenders, council pages, and support chats.'
        ),
    },
]


def normalize_question(question):
    return re.sub(r'\s+', ' ', str(question or '').lower()).strip()


def answer_support_question(question):
    normalized = normalize_question(question)
    if not normalized:
        return 'Please type your question about using TenderAI.', 20

    scored = []
    for topic in SUPPORT_TOPICS:
        score = sum(1 for keyword in topic['keywords'] if keyword in normalized)
        if score:
            scored.append((score, topic['answer']))
    if scored:
        score, answer = max(scored, key=lambda item: item[0])
        confidence = min(95, 60 + score * 12)
        return answer, confidence

    return (
        'I am not fully sure from that wording yet. Try asking about a specific part, for example: importing a ZPPA URL, '
        'uploading solicitation documents, generating bid documents, matching companies, or uploading certificates. '
        'This question has been saved so the admin can clarify it if needed.'
    ), 35
