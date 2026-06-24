import csv
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from companies.models import BusinessCategory
from tenders.models import Tender


class Command(BaseCommand):
    help = 'Import public ZPPA tender rows from a CSV file. This command does not scrape protected pages.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path')

    def handle(self, *args, **options):
        path = options['csv_path']
        imported = 0
        try:
            with open(path, newline='', encoding='utf-8-sig') as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    category = None
                    if row.get('category'):
                        category, _ = BusinessCategory.objects.get_or_create(name=row['category'].strip())
                    closing_date = None
                    if row.get('closing_date'):
                        closing_date = datetime.strptime(row['closing_date'], '%Y-%m-%d').date()
                    Tender.objects.update_or_create(
                        tender_number=row.get('tender_number', '').strip(),
                        title=row['title'].strip(),
                        defaults={
                            'procuring_entity': row.get('procuring_entity', '').strip(),
                            'source': Tender.Source.ZPPA,
                            'category': category,
                            'closing_date': closing_date,
                            'submission_method': row.get('submission_method', '').strip(),
                            'imported_reference': row.get('source_url_or_reference', '').strip(),
                        },
                    )
                    imported += 1
        except FileNotFoundError as exc:
            raise CommandError(f'CSV file not found: {path}') from exc
        self.stdout.write(self.style.SUCCESS(f'Imported or updated {imported} ZPPA tender row(s).'))
