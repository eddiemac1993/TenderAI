from django.core.management.base import BaseCommand

from council_opportunities.services import scrape_council_pages


class Command(BaseCommand):
    help = 'Scrape active public council Facebook pages for CDF, tender, RFQ, procurement, grant, and bursary opportunities.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, help='Maximum number of active council pages to check.')
        parser.add_argument('--page-id', type=int, help='Scrape one CouncilPage by database ID.')

    def handle(self, *args, **options):
        run = scrape_council_pages(limit=options.get('limit'), page_id=options.get('page_id'))
        self.stdout.write(
            self.style.SUCCESS(
                f'{run.status}: checked {run.pages_checked} page(s), '
                f'found {run.posts_found}, created {run.posts_created}, updated {run.posts_updated}.'
            )
        )
        if run.message:
            self.stdout.write(run.message)
