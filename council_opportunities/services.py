import html
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen

from django.db import IntegrityError
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import CouncilPage, CouncilPost, ScrapeRun

logger = logging.getLogger(__name__)

KEYWORDS = [
    'CDF',
    'Constituency Development Fund',
    'tender',
    'RFQ',
    'request for quotation',
    'procurement',
    'bidding',
    'bid',
    'invitation to bid',
    'empowerment',
    'grant',
    'grants',
    'loan',
    'skills bursary',
    'call for applications',
    'impact story',
    'road maintenance',
    'community projects',
    'process of application',
    'application',
    'cooperative',
    'youth',
    'women',
]

CATEGORY_RULES = [
    (CouncilPost.Category.CDF, ['cdf', 'constituency development fund']),
    (CouncilPost.Category.RFQ, ['rfq', 'request for quotation', 'quotation']),
    (CouncilPost.Category.TENDER, ['tender', 'invitation to bid', 'bidding']),
    (CouncilPost.Category.PROCUREMENT, ['procurement', 'bid']),
    (CouncilPost.Category.BURSARY, ['skills bursary', 'bursary']),
    (CouncilPost.Category.GRANT, ['empowerment', 'grant', 'grants', 'loan', 'cooperative', 'youth', 'women', 'call for applications']),
]

DATE_PATTERNS = [
    r'(?:deadline|closing date|closes|submit by|before)\D{0,30}(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
    r'(?:deadline|closing date|closes|submit by|before)\D{0,30}(\d{4}[/-]\d{1,2}[/-]\d{1,2})',
]


@dataclass
class PublicPostCandidate:
    post_text: str
    post_url: str
    date_posted: datetime | None = None
    attachment_url: str = ''


def matched_keywords(text: str) -> list[str]:
    text_lower = text.lower()
    return [keyword for keyword in KEYWORDS if keyword.lower() in text_lower]


def detect_category(text: str) -> str:
    text_lower = text.lower()
    for category, terms in CATEGORY_RULES:
        if any(term in text_lower for term in terms):
            return category
    return CouncilPost.Category.OTHER


def detect_deadline(text: str):
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        value = match.group(1).replace('/', '-')
        parsed = parse_date(value)
        if parsed:
            return parsed
        for fmt in ('%d-%m-%Y', '%d-%m-%y'):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                pass
    return None


def fetch_public_page_html(url: str, timeout: int = 25) -> str:
    # Public-only scraper: no cookies, no credentials, no browser automation, and no login bypass.
    request = Request(
        url,
        headers={
            'User-Agent': 'TenderAI Council Opportunities/1.0 (+public pages only)',
            'Accept': 'text/html,application/xhtml+xml',
        },
    )
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get('content-type', '')
        if 'text/html' not in content_type:
            raise ValueError(f'Expected public HTML, got {content_type or "unknown content type"}.')
        return response.read().decode('utf-8', errors='replace')


def _clean_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r'<[^>]+>', ' ', value)
    value = re.sub(r'\s+', ' ', value)
    return value.strip()


def _meta_content(page_html: str, name: str) -> str:
    pattern = rf'<meta[^>]+(?:property|name)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']'
    match = re.search(pattern, page_html, flags=re.IGNORECASE)
    return _clean_text(match.group(1)) if match else ''


def _normalise_post_url(page_url: str, raw_url: str) -> str:
    url = html.unescape(raw_url).replace('\\/', '/')
    url = urljoin(page_url, url)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if 'story_fbid' in query and 'id' in query:
        return f'https://www.facebook.com/permalink.php?story_fbid={query["story_fbid"][0]}&id={query["id"][0]}'
    clean = parsed._replace(fragment='')
    return clean.geturl()


def extract_public_post_candidates(page_url: str, page_html: str) -> list[PublicPostCandidate]:
    if re.search(r'log in to facebook|you must log in|login_required', page_html, re.IGNORECASE):
        raise ValueError('Facebook returned a login-required page; TenderAI will not bypass authentication.')

    # Facebook public HTML changes often, so extraction is intentionally conservative and failure-safe.
    description = _meta_content(page_html, 'og:description')
    title = _meta_content(page_html, 'og:title')
    image_url = _meta_content(page_html, 'og:image')
    fallback_text = _clean_text(' '.join(part for part in [title, description] if part))

    post_urls = set()
    for pattern in (
        r'href=["\']([^"\']*(?:/posts/|permalink\.php|story_fbid=|/photos/|/videos/|/reel/)[^"\']*)["\']',
        r'"url":"([^"]*(?:/posts/|permalink\.php|story_fbid=|/photos/|/videos/|/reel/)[^"]*)"',
    ):
        for match in re.finditer(pattern, page_html, flags=re.IGNORECASE):
            post_urls.add(_normalise_post_url(page_url, match.group(1)))

    candidates = []
    for post_url in sorted(post_urls):
        index = page_html.find(post_url)
        snippet = fallback_text
        if index > -1:
            snippet = _clean_text(page_html[max(0, index - 700): index + 700]) or fallback_text
        candidates.append(PublicPostCandidate(post_text=snippet, post_url=post_url, attachment_url=image_url))

    if not candidates and fallback_text:
        candidates.append(PublicPostCandidate(post_text=fallback_text, post_url=page_url, attachment_url=image_url))
    return candidates


def save_matching_candidates(page: CouncilPage, candidates: Iterable[PublicPostCandidate]) -> tuple[int, int, int]:
    found = created = updated = 0
    for candidate in candidates:
        keywords = matched_keywords(candidate.post_text)
        if not keywords:
            continue
        found += 1
        defaults = {
            'post_text': candidate.post_text,
            'date_posted': candidate.date_posted,
            'date_scraped': timezone.now(),
            'matched_keywords': keywords,
            'category': detect_category(candidate.post_text),
            'detected_deadline': detect_deadline(candidate.post_text),
            'attachment_url': candidate.attachment_url,
        }
        try:
            _, was_created = CouncilPost.objects.update_or_create(
                post_url=candidate.post_url,
                defaults={'council_page': page, **defaults},
            )
        except IntegrityError:
            logger.exception('Could not save council post %s', candidate.post_url)
            continue
        created += int(was_created)
        updated += int(not was_created)
    return found, created, updated


def import_public_post_url(page: CouncilPage, post_url: str, pasted_text: str = '') -> tuple[bool, CouncilPost | None, list[str]]:
    image_url = ''
    text = _clean_text(pasted_text)
    if not text:
        page_html = fetch_public_page_html(post_url)
        description = _meta_content(page_html, 'og:description')
        title = _meta_content(page_html, 'og:title')
        image_url = _meta_content(page_html, 'og:image')
        text = _clean_text(' '.join(part for part in [title, description] if part))
        if not text:
            text = _clean_text(page_html[:3000])

    keywords = matched_keywords(text)
    if not keywords:
        return False, None, []

    post, created = CouncilPost.objects.update_or_create(
        post_url=_normalise_post_url(post_url, post_url),
        defaults={
            'council_page': page,
            'post_text': text,
            'date_posted': None,
            'date_scraped': timezone.now(),
            'matched_keywords': keywords,
            'category': detect_category(text),
            'detected_deadline': detect_deadline(text),
            'attachment_url': image_url,
        },
    )
    return created, post, keywords


def scrape_council_pages(limit: int | None = None, page_id: int | None = None) -> ScrapeRun:
    run = ScrapeRun.objects.create(status=ScrapeRun.Status.STARTED)
    pages = CouncilPage.objects.filter(is_active=True).exclude(facebook_url='')
    if page_id:
        pages = pages.filter(id=page_id)
    if limit:
        pages = pages[:limit]

    errors = []
    for page in pages:
        run.pages_checked += 1
        try:
            page_html = fetch_public_page_html(page.facebook_url)
            candidates = extract_public_post_candidates(page.facebook_url, page_html)
            found, created, updated = save_matching_candidates(page, candidates)
            run.posts_found += found
            run.posts_created += created
            run.posts_updated += updated
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            message = f'{page.name}: {exc}'
            errors.append(message)
            logger.warning('Council scrape failed for %s: %s', page.facebook_url, exc)
        except Exception as exc:
            message = f'{page.name}: unexpected error: {exc}'
            errors.append(message)
            logger.exception('Unexpected council scrape failure for %s', page.facebook_url)

    run.finished_at = timezone.now()
    if errors and run.posts_found:
        run.status = ScrapeRun.Status.PARTIAL
    elif errors:
        run.status = ScrapeRun.Status.FAILED
    else:
        run.status = ScrapeRun.Status.SUCCESS
    run.message = '\n'.join(errors) if errors else 'Council public post scrape completed.'
    run.save()
    return run
