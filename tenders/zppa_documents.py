import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen

from django.core.files.base import ContentFile

from ai_engine.models import SolicitationDocument
from ai_engine.services import process_solicitation_document


ZPPA_BASE_URL = 'https://eprocure.zppa.org.zm/epps/'
MAX_PUBLIC_DOCUMENT_BYTES = 60 * 1024 * 1024


@dataclass
class PublicZppaDocument:
    document_id: str
    filename: str
    description: str


class PublicZppaDocumentFetcher:
    """Fetches only public ZPPA tender documents exposed through anonymous download URLs."""

    ROW_RE = re.compile(r'<tr\b[^>]*>(?P<row>.*?)</tr>', re.I | re.S)
    CELL_RE = re.compile(r'<td\b[^>]*>(?P<cell>.*?)</td>', re.I | re.S)
    DOC_RE = re.compile(
        r'downloadDocForAnonymous\([\'"](?P<id>\d+)[\'"]\).*?>(?P<name>.*?)</a>',
        re.I | re.S,
    )

    def __init__(self, timeout=30):
        self.timeout = timeout

    def fetch_for_tender(self, tender):
        resource_id = self.resource_id_for_tender(tender)
        if not resource_id:
            raise ValueError('Tender has no ZPPA resource ID.')

        documents = self.list_documents(resource_id)
        if not documents:
            raise ValueError('No public downloadable ZPPA documents were found.')

        chosen = self.choose_solicitation_document(documents)
        file_bytes, filename = self.download_document(resource_id, chosen)
        solicitation = SolicitationDocument(tender=tender)
        solicitation.file.save(filename, ContentFile(file_bytes), save=True)
        analysis = process_solicitation_document(solicitation)
        return solicitation, chosen, analysis

    def fetch_all_for_tender(self, tender):
        resource_id = self.resource_id_for_tender(tender)
        if not resource_id:
            raise ValueError('Tender has no ZPPA resource ID.')

        documents = self.list_documents(resource_id)
        if not documents:
            raise ValueError('No public downloadable ZPPA documents were found.')

        supported = [doc for doc in documents if self.is_supported_filename(doc.filename)]
        if not supported:
            raise ValueError('Public ZPPA documents were found, but none were PDF, DOCX, or XML files.')

        fetched = []
        skipped = []
        for public_document in supported:
            try:
                file_bytes, filename = self.download_document(resource_id, public_document)
            except Exception as exc:
                skipped.append(f'{public_document.filename}: {exc}')
                continue
            solicitation = SolicitationDocument(tender=tender)
            solicitation.file.save(filename, ContentFile(file_bytes), save=True)
            analysis = process_solicitation_document(solicitation)
            fetched.append((solicitation, public_document, analysis))
        if not fetched and skipped:
            raise ValueError('No public documents could be downloaded. ' + ' | '.join(skipped[:3]))
        return fetched, skipped

    def resource_id_for_tender(self, tender):
        if tender.zppa_resource_id:
            return tender.zppa_resource_id
        if tender.imported_reference:
            query = parse_qs(urlparse(tender.imported_reference).query)
            return query.get('resourceId', [''])[0]
        return ''

    def list_documents(self, resource_id):
        url = urljoin(ZPPA_BASE_URL, f'cft/listContractDocuments.do?resourceId={resource_id}')
        html, _ = self.fetch_text(url)
        documents = []
        for row_match in self.ROW_RE.finditer(html):
            row_html = row_match.group('row')
            doc_match = self.DOC_RE.search(row_html)
            if not doc_match:
                continue
            cells = [self.clean_html(cell.group('cell')) for cell in self.CELL_RE.finditer(row_html)]
            documents.append(PublicZppaDocument(
                document_id=doc_match.group('id'),
                filename=self.clean_html(doc_match.group('name')),
                description=cells[1] if len(cells) > 1 else '',
            ))
        return documents

    def choose_solicitation_document(self, documents):
        preferred_words = ['solicitation', 'bidding document', 'tender document']
        supported = [
            doc for doc in documents
            if self.is_supported_filename(doc.filename) and not doc.filename.lower().endswith('.xml')
        ]
        for doc in supported:
            haystack = f'{doc.description} {doc.filename}'.lower()
            if any(word in haystack for word in preferred_words):
                return doc
        if supported:
            return supported[0]
        xml_docs = [doc for doc in documents if doc.filename.lower().endswith('.xml')]
        if xml_docs:
            return xml_docs[0]
        raise ValueError('Public ZPPA documents were found, but none were PDF, DOCX, or XML files.')

    def download_document(self, resource_id, document):
        url = urljoin(
            ZPPA_BASE_URL,
            f'cft/downloadContractDocument.do?documentId={document.document_id}&resourceId={resource_id}',
        )
        request = Request(url, headers={'User-Agent': 'TenderAI public document fetcher/1.0'})
        with urlopen(request, timeout=self.timeout) as response:
            content_type = response.headers.get('content-type', '').lower()
            content_disposition = response.headers.get('content-disposition', '')
            file_bytes = response.read(MAX_PUBLIC_DOCUMENT_BYTES + 1)
        if len(file_bytes) > MAX_PUBLIC_DOCUMENT_BYTES:
            raise ValueError('Public ZPPA document is larger than TenderAI download limit.')
        if not self.is_supported_response(content_type, document.filename, file_bytes):
            raise ValueError('ZPPA did not return a supported PDF, DOCX, or XML file. It may require payment or login.')
        filename = self.filename_from_headers(content_disposition) or document.filename
        return file_bytes, self.safe_filename(filename)

    def fetch_text(self, url):
        request = Request(url, headers={'User-Agent': 'TenderAI public document fetcher/1.0'})
        with urlopen(request, timeout=self.timeout) as response:
            return response.read().decode('utf-8', errors='replace'), response.geturl()

    def is_supported_response(self, content_type, filename, file_bytes):
        lower_name = filename.lower()
        if file_bytes.startswith(b'%PDF'):
            return True
        if file_bytes.startswith(b'PK') and lower_name.endswith('.docx'):
            return True
        if lower_name.endswith('.xml') and file_bytes.lstrip().startswith(b'<'):
            return True
        return (
            'pdf' in content_type
            or (
                'word' in content_type
                and lower_name.endswith('.docx')
            )
            or 'xml' in content_type
            or self.is_supported_filename(filename)
        )

    def is_supported_filename(self, filename):
        return filename.lower().endswith(('.pdf', '.docx', '.xml'))

    def filename_from_headers(self, content_disposition):
        match = re.search(r'filename="?([^";]+)"?', content_disposition or '', re.I)
        return match.group(1) if match else ''

    def safe_filename(self, filename):
        filename = unescape(filename or 'zppa-solicitation-document.pdf').strip()
        filename = re.sub(r'[\\/:*?"<>|]+', '-', filename)
        filename = re.sub(r'\s+', ' ', filename)
        return filename[:180]

    def clean_html(self, html):
        text = re.sub(r'<[^>]+>', ' ', html)
        return re.sub(r'\s+', ' ', unescape(text)).strip()
