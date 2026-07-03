import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen

from django.utils import timezone
from django.db.models import Q

from .models import Tender, ZppaScrapeLog


ZPPA_EGP_HOME_URL = 'https://www.zppa.org.zm/epps'


@dataclass
class ScrapedTender:
    listed_date: date | None
    title: str
    url: str
    tender_number: str
    resource_id: str = ''
    procuring_entity: str = ''
    description: str = ''
    published_at: datetime | None = None
    closing_at: datetime | None = None
    submission_method: str = ''
    procurement_method: str = ''
    participation_fee: Decimal | None = None
    bid_security_amount: Decimal | None = None
    detail_rows: list | None = None


class LinkTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._current_href = None
        self._text_parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            attrs_dict = dict(attrs)
            self._current_href = attrs_dict.get('href')
            self._text_parts = []

    def handle_data(self, data):
        if self._current_href:
            self._text_parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self._current_href:
            text = ' '.join(part.strip() for part in self._text_parts if part.strip())
            if text:
                self.links.append((self._current_href, re.sub(r'\s+', ' ', text).strip()))
            self._current_href = None
            self._text_parts = []


class DetailTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        text = re.sub(r'\s+', ' ', unescape(data)).strip()
        if text:
            self.parts.append(text)


class PublicZppaTenderScraper:
    """Reads only the public e-GP landing page tender links."""

    MONTHS = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    }
    DATE_RE = re.compile(r'^(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]{3})\s+(?P<year>\d{2})\s+(?P<title>.+)$')
    TENDER_NUMBER_RE = re.compile(r'\b[A-Z0-9]{2,}(?:/[A-Z0-9.-]+){2,}\b')
    RESOURCE_ID_RE = re.compile(r'resourceId=(\d+)')

    def __init__(self, source_url=ZPPA_EGP_HOME_URL, timeout=20):
        self.source_url = source_url
        self.timeout = timeout

    def fetch_html(self, url=None):
        request = Request(
            url or self.source_url,
            headers={'User-Agent': 'TenderAI public tender importer/1.0'},
        )
        with urlopen(request, timeout=self.timeout) as response:
            return response.read().decode('utf-8', errors='replace'), response.geturl()

    def scrape(self, today_only=False, limit=10):
        html, final_url = self.fetch_html()
        parser = LinkTextParser()
        parser.feed(html)
        tenders = []
        today = timezone.localdate()
        for href, text in parser.links:
            scraped = self.parse_link(text, urljoin(final_url, href))
            if not scraped:
                continue
            if today_only and scraped.listed_date != today:
                continue
            scraped = self.enrich_from_detail_page(scraped)
            tenders.append(scraped)
            if len(tenders) >= limit:
                break
        return tenders

    def parse_link(self, text, url):
        match = self.DATE_RE.match(text)
        if not match:
            return None
        month = self.MONTHS.get(match.group('month').lower())
        if not month:
            return None
        year = 2000 + int(match.group('year'))
        listed_date = date(year, month, int(match.group('day')))
        title = match.group('title').strip()
        if 'tender' not in title.lower():
            return None
        tender_number = self.extract_tender_number(title)
        return ScrapedTender(
            listed_date=listed_date,
            title=title,
            url=url,
            tender_number=tender_number,
            resource_id=self.extract_resource_id(url),
        )

    def extract_tender_number(self, title):
        if title.lower().startswith('tender:') and ':' in title[7:]:
            possible = title.split(':', 2)[1].strip()
            if possible:
                return possible[:120]
        match = self.TENDER_NUMBER_RE.search(title)
        return match.group(0)[:120] if match else ''

    def extract_resource_id(self, url):
        parsed = urlparse(url)
        query_id = parse_qs(parsed.query).get('resourceId', [''])[0]
        if query_id:
            return query_id[:40]
        match = self.RESOURCE_ID_RE.search(url)
        return match.group(1)[:40] if match else ''

    def enrich_from_detail_page(self, tender):
        if 'prepareViewCfTWS.do' not in tender.url:
            return tender
        try:
            html, final_url = self.fetch_html(tender.url)
        except Exception:
            return tender
        values = self.parse_detail_values(html, final_url)
        tender.detail_rows = values.get('_rows', [])
        tender.resource_id = values.get('resource_id') or tender.resource_id
        tender.title = values.get('Title') or tender.title
        tender.tender_number = values.get('Tender Unique ID') or tender.tender_number
        tender.procuring_entity = values.get('Name of Procuring Entity') or tender.procuring_entity
        tender.description = values.get('Description') or tender.description
        tender.published_at = self.parse_zppa_datetime(values.get('Date of Publication/Invitation'))
        tender.closing_at = self.parse_zppa_datetime(values.get('Deadline for Bid Submission'))
        tender.submission_method = values.get('Submission Method Details') or tender.submission_method
        tender.procurement_method = values.get('Procedure') or tender.procurement_method
        tender.participation_fee = self.parse_money(
            values.get('Payment Amount (ZMW)') or values.get('Participation Fee') or values.get('Payment Amount')
        )
        tender.bid_security_amount = self.parse_money(
            values.get('Bid Security Amount') or values.get('Bid Security Amount (ZMW)')
        )
        return tender

    def parse_detail_values(self, html, base_url=None):
        values = self.parse_definition_list_values(html, base_url)
        if values:
            resource_match = re.search(r'var\s+RESOURCE_ID\s*=\s*"(?P<id>\d+)"', html)
            if resource_match:
                values['resource_id'] = resource_match.group('id')
            return values

        parser = DetailTextParser()
        parser.feed(html)
        values = {}
        rows = []
        parts = parser.parts
        for index, part in enumerate(parts[:-1]):
            if part.endswith(':'):
                label = part[:-1]
                value = parts[index + 1]
                values[label] = value
                rows.append({'label': label, 'value': value})
        resource_match = re.search(r'var\s+RESOURCE_ID\s*=\s*"(?P<id>\d+)"', html)
        if resource_match:
            values['resource_id'] = resource_match.group('id')
        values['_rows'] = rows
        return values

    def parse_definition_list_values(self, html, base_url=None):
        values = {}
        rows = []
        pattern = re.compile(r'<dt\b[^>]*>(?P<label>.*?)</dt>\s*<dd\b[^>]*>(?P<value>.*?)</dd>', re.I | re.S)
        for match in pattern.finditer(html):
            label = self.clean_html_text(match.group('label')).rstrip(':')
            value_html = match.group('value')
            value = self.clean_html_text(value_html)
            if not label or not value:
                continue
            row = {'label': label, 'value': value}
            href_match = re.search(r'<a\b[^>]*href=["\'](?P<href>[^"\']+)["\']', value_html, re.I)
            if href_match:
                row['url'] = urljoin(base_url or self.source_url, href_match.group('href'))
            rows.append(row)
            values[label] = value
        values['_rows'] = rows
        return values

    def clean_html_text(self, html):
        text = re.sub(r'<[^>]+>', ' ', html)
        return re.sub(r'\s+', ' ', unescape(text)).strip()

    def parse_zppa_datetime(self, value):
        if not value:
            return None
        try:
            parsed = datetime.strptime(value, '%d/%m/%Y %H:%M:%S')
        except ValueError:
            return None
        return timezone.make_aware(parsed, timezone.get_current_timezone())

    def parse_money(self, value):
        if not value:
            return None
        cleaned = re.sub(r'[^\d.]', '', str(value))
        if not cleaned:
            return None
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None


def import_public_zppa_tenders(today_only=False, limit=10, write_log=False):
    log = ZppaScrapeLog.objects.create(today_only=today_only, limit=limit) if write_log else None
    scraper = PublicZppaTenderScraper()
    imported = []
    try:
        for item in scraper.scrape(today_only=today_only, limit=limit):
            tender = find_existing_tender(item)
            created = tender is None
            if created:
                tender = Tender()
            tender.title = item.title
            tender.tender_number = item.tender_number
            tender.zppa_resource_id = item.resource_id
            tender.procuring_entity = item.procuring_entity or 'ZPPA e-GP public listing'
            tender.description = item.description
            tender.source = Tender.Source.ZPPA
            tender.closing_date = item.closing_at.date() if item.closing_at else None
            tender.published_at = item.published_at
            tender.closing_at = item.closing_at
            tender.submission_method = item.submission_method
            tender.procurement_method = item.procurement_method
            tender.participation_fee = item.participation_fee
            tender.bid_security_amount = item.bid_security_amount
            tender.zppa_details = item.detail_rows or []
            tender.imported_reference = item.url
            tender.notes = f'Imported from public ZPPA e-GP listing. Listed date: {item.listed_date or "unknown"}.'
            tender.save()
            imported.append((tender, created))
    except Exception as exc:
        if log:
            from django.utils import timezone
            log.status = 'FAILED'
            log.finished_at = timezone.now()
            log.message = str(exc)
            log.save()
        raise
    if log:
        from django.utils import timezone
        log.status = 'SUCCESS'
        log.finished_at = timezone.now()
        log.created_count = sum(1 for _, created in imported if created)
        log.updated_count = len(imported) - log.created_count
        log.message = 'Public ZPPA scrape completed. No login-only pages accessed.'
        log.save()
    return imported


def find_existing_tender(item):
    query = Q(imported_reference=item.url)
    if item.resource_id:
        query |= Q(zppa_resource_id=item.resource_id)
    if item.tender_number:
        query |= Q(tender_number=item.tender_number)
    return Tender.objects.filter(query).order_by('-zppa_resource_id', 'id').first()


def zppa_detail_value(rows, *labels):
    wanted = {label.lower().strip(':') for label in labels}
    for row in rows or []:
        label = str(row.get('label', '')).lower().strip(':')
        if label in wanted:
            return row.get('value', '')
    return ''


def parse_zppa_money(value):
    return PublicZppaTenderScraper().parse_money(value)


def payment_amount_from_detail_rows(rows):
    return parse_zppa_money(zppa_detail_value(
        rows,
        'Payment Amount (ZMW)',
        'Payment Amount',
        'Participation Fee',
    ))


def bid_security_amount_from_detail_rows(rows):
    return parse_zppa_money(zppa_detail_value(
        rows,
        'Bid Security Amount',
        'Bid Security Amount (ZMW)',
    ))


def import_public_zppa_tender_from_url(url):
    scraper = PublicZppaTenderScraper(source_url=url)
    resource_id = scraper.extract_resource_id(url)
    if not resource_id:
        raise ValueError('This URL does not contain a ZPPA resourceId.')

    scraped = ScrapedTender(
        listed_date=None,
        title='ZPPA tender',
        url=url,
        tender_number='',
        resource_id=resource_id,
    )
    scraped = scraper.enrich_from_detail_page(scraped)
    tender = find_existing_tender(scraped)
    created = tender is None
    if created:
        tender = Tender()
    tender.title = scraped.title
    tender.tender_number = scraped.tender_number
    tender.zppa_resource_id = scraped.resource_id or resource_id
    tender.procuring_entity = scraped.procuring_entity or 'ZPPA e-GP public tender'
    tender.description = scraped.description
    tender.source = Tender.Source.ZPPA
    tender.closing_date = scraped.closing_at.date() if scraped.closing_at else tender.closing_date
    tender.published_at = scraped.published_at or tender.published_at
    tender.closing_at = scraped.closing_at or tender.closing_at
    tender.submission_method = scraped.submission_method
    tender.procurement_method = scraped.procurement_method
    tender.participation_fee = scraped.participation_fee
    tender.bid_security_amount = scraped.bid_security_amount
    tender.zppa_details = scraped.detail_rows or tender.zppa_details or []
    tender.imported_reference = url
    tender.notes = 'Imported from a public ZPPA tender URL. No login-only pages accessed.'
    tender.save()
    return tender, created
