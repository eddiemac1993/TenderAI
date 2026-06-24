from django.core.management.base import BaseCommand

from companies.models import Company


CORE_COMPANIES = [
    'The CMM Chronos Limited',
    'Solid Connections Zambia Limited',
    'Universal General Supplies Limited',
    'Raised Right Investments Limited',
]


class Command(BaseCommand):
    help = 'Create the core TenderAI company profiles if they do not already exist.'

    def handle(self, *args, **options):
        created = 0
        for name in CORE_COMPANIES:
            _, was_created = Company.objects.get_or_create(name=name)
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f'Seeded {created} new core company profile(s).'))
