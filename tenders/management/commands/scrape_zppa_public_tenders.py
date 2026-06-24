from django.core.management.base import BaseCommand, CommandError

from tenders.zppa_scraper import import_public_zppa_tenders


class Command(BaseCommand):
    help = 'Scrape visible public ZPPA e-GP tender links. Does not access login-only pages.'

    def add_arguments(self, parser):
        parser.add_argument('--today', action='store_true', help='Only import tenders listed today.')
        parser.add_argument('--limit', type=int, default=10, help='Maximum visible tenders to import.')

    def handle(self, *args, **options):
        try:
            imported = import_public_zppa_tenders(
                today_only=options['today'],
                limit=options['limit'],
                write_log=True,
            )
        except Exception as exc:
            raise CommandError(f'Public ZPPA scrape failed: {exc}') from exc
        created_count = sum(1 for _, created in imported if created)
        updated_count = len(imported) - created_count
        self.stdout.write(
            self.style.SUCCESS(
                f'Public ZPPA scrape finished: {created_count} created, {updated_count} updated.'
            )
        )
