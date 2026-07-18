import json

from django.core.management.base import BaseCommand, CommandError

from tenders.zppa_scraper import PublicZppaTenderScraper


class Command(BaseCommand):
    help = 'Scrape public ZPPA tender links and export them to JSON for upload into a hosted TenderAI instance.'

    def add_arguments(self, parser):
        parser.add_argument('output_path')
        parser.add_argument('--today', action='store_true', help='Only export tenders listed today.')
        parser.add_argument('--limit', type=int, default=200, help='Maximum open/not-yet-closed visible tenders to export.')
        parser.add_argument('--include-closed', action='store_true', help='Also export tenders whose ZPPA closing deadline has already passed.')

    def handle(self, *args, **options):
        scraper = PublicZppaTenderScraper()
        try:
            items = scraper.scrape(
                today_only=options['today'],
                limit=options['limit'],
                include_closed=options['include_closed'],
            )
        except Exception as exc:
            raise CommandError(f'Public ZPPA export failed: {exc}') from exc
        payload = [
            {
                'listed_date': item.listed_date.isoformat() if item.listed_date else None,
                'title': item.title,
                'url': item.url,
                'tender_number': item.tender_number,
                'resource_id': item.resource_id,
                'procuring_entity': item.procuring_entity,
                'description': item.description,
                'published_at': item.published_at.isoformat() if item.published_at else None,
                'closing_at': item.closing_at.isoformat() if item.closing_at else None,
                'submission_method': item.submission_method,
                'procurement_method': item.procurement_method,
                'detail_rows': item.detail_rows or [],
            }
            for item in items
        ]
        with open(options['output_path'], 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, indent=2)
        self.stdout.write(self.style.SUCCESS(f'Exported {len(payload)} ZPPA tender row(s) to {options["output_path"]}.'))
