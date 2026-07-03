from django.core.management.base import BaseCommand

from council_opportunities.models import CouncilPage


COUNCIL_SOURCES = [
    ('Lusaka City Council', 'Lusaka', 'Lusaka Province'),
    ('Chongwe Municipal Council', 'Chongwe', 'Lusaka Province'),
    ('Chilanga Town Council', 'Chilanga', 'Lusaka Province'),
    ('Kafue Town Council', 'Kafue', 'Lusaka Province'),
    ('Luangwa Town Council', 'Luangwa', 'Lusaka Province'),
    ('Rufunsa Town Council', 'Rufunsa', 'Lusaka Province'),
    ('Ndola City Council', 'Ndola', 'Copperbelt Province'),
    ('Kitwe City Council', 'Kitwe', 'Copperbelt Province'),
    ('Chingola Municipal Council', 'Chingola', 'Copperbelt Province'),
    ('Mufulira Municipal Council', 'Mufulira', 'Copperbelt Province'),
    ('Luanshya Municipal Council', 'Luanshya', 'Copperbelt Province'),
    ('Kalulushi Municipal Council', 'Kalulushi', 'Copperbelt Province'),
    ('Chililabombwe Municipal Council', 'Chililabombwe', 'Copperbelt Province'),
    ('Lufwanyama Town Council', 'Lufwanyama', 'Copperbelt Province'),
    ('Masaiti Town Council', 'Masaiti', 'Copperbelt Province'),
    ('Mpongwe Town Council', 'Mpongwe', 'Copperbelt Province'),
    ('Kabwe Municipal Council', 'Kabwe', 'Central Province'),
    ('Kapiri Mposhi Town Council', 'Kapiri Mposhi', 'Central Province'),
    ('Mkushi Town Council', 'Mkushi', 'Central Province'),
    ('Serenje Town Council', 'Serenje', 'Central Province'),
    ('Chibombo Town Council', 'Chibombo', 'Central Province'),
    ('Chisamba Town Council', 'Chisamba', 'Central Province'),
    ('Mumbwa Town Council', 'Mumbwa', 'Central Province'),
    ('Ngabwe Town Council', 'Ngabwe', 'Central Province'),
    ('Luano Town Council', 'Luano', 'Central Province'),
    ('Shibuyunji Town Council', 'Shibuyunji', 'Central Province'),
    ('Livingstone City Council', 'Livingstone', 'Southern Province'),
    ('Choma Municipal Council', 'Choma', 'Southern Province'),
    ('Mazabuka Municipal Council', 'Mazabuka', 'Southern Province'),
    ('Monze Town Council', 'Monze', 'Southern Province'),
    ('Kalomo Town Council', 'Kalomo', 'Southern Province'),
    ('Namwala Town Council', 'Namwala', 'Southern Province'),
    ('Kazungula Town Council', 'Kazungula', 'Southern Province'),
    ('Siavonga Town Council', 'Siavonga', 'Southern Province'),
    ('Zimba Town Council', 'Zimba', 'Southern Province'),
    ('Pemba Town Council', 'Pemba', 'Southern Province'),
    ('Gwembe Town Council', 'Gwembe', 'Southern Province'),
    ('Sinazongwe Town Council', 'Sinazongwe', 'Southern Province'),
    ('Chipata City Council', 'Chipata', 'Eastern Province'),
    ('Katete Town Council', 'Katete', 'Eastern Province'),
    ('Petauke Town Council', 'Petauke', 'Eastern Province'),
    ('Lundazi Town Council', 'Lundazi', 'Eastern Province'),
    ('Chadiza Town Council', 'Chadiza', 'Eastern Province'),
    ('Vubwi Town Council', 'Vubwi', 'Eastern Province'),
    ('Sinda Town Council', 'Sinda', 'Eastern Province'),
    ('Mambwe Town Council', 'Mambwe', 'Eastern Province'),
    ('Nyimba Town Council', 'Nyimba', 'Eastern Province'),
    ('Chipangali Town Council', 'Chipangali', 'Eastern Province'),
    ('Kasenengwa Town Council', 'Kasenengwa', 'Eastern Province'),
    ('Lumezi Town Council', 'Lumezi', 'Eastern Province'),
    ('Kasama Municipal Council', 'Kasama', 'Northern Province'),
    ('Mbala Town Council', 'Mbala', 'Northern Province'),
    ('Mpulungu Town Council', 'Mpulungu', 'Northern Province'),
    ('Mporokoso Town Council', 'Mporokoso', 'Northern Province'),
    ('Luwingu Town Council', 'Luwingu', 'Northern Province'),
    ('Chilubi Town Council', 'Chilubi', 'Northern Province'),
    ('Nsama Town Council', 'Nsama', 'Northern Province'),
    ('Lunte Town Council', 'Lunte', 'Northern Province'),
    ('Senga Hill Town Council', 'Senga Hill', 'Northern Province'),
    ('Lupososhi Town Council', 'Lupososhi', 'Northern Province'),
    ('Mansa Municipal Council', 'Mansa', 'Luapula Province'),
    ('Kawambwa Town Council', 'Kawambwa', 'Luapula Province'),
    ('Samfya Town Council', 'Samfya', 'Luapula Province'),
    ('Nchelenge Town Council', 'Nchelenge', 'Luapula Province'),
    ('Mwense Town Council', 'Mwense', 'Luapula Province'),
    ('Chembe Town Council', 'Chembe', 'Luapula Province'),
    ('Chiengi Town Council', 'Chiengi', 'Luapula Province'),
    ('Milenge Town Council', 'Milenge', 'Luapula Province'),
    ('Lunga Town Council', 'Lunga', 'Luapula Province'),
    ('Chinsali Town Council', 'Chinsali', 'Muchinga Province'),
    ('Mpika Town Council', 'Mpika', 'Muchinga Province'),
    ('Nakonde Town Council', 'Nakonde', 'Muchinga Province'),
    ('Isoka Town Council', 'Isoka', 'Muchinga Province'),
    ('Mafinga Town Council', 'Mafinga', 'Muchinga Province'),
    ("Shiwang'andu Town Council", "Shiwang'andu", 'Muchinga Province'),
    ('Lavushimanda Town Council', 'Lavushimanda', 'Muchinga Province'),
    ('Kanchibiya Town Council', 'Kanchibiya', 'Muchinga Province'),
    ('Solwezi Municipal Council', 'Solwezi', 'North-Western Province'),
    ('Kasempa Town Council', 'Kasempa', 'North-Western Province'),
    ('Mwinilunga Town Council', 'Mwinilunga', 'North-Western Province'),
    ('Zambezi Town Council', 'Zambezi', 'North-Western Province'),
    ('Kabompo Town Council', 'Kabompo', 'North-Western Province'),
    ('Chavuma Town Council', 'Chavuma', 'North-Western Province'),
    ('Manyinga Town Council', 'Manyinga', 'North-Western Province'),
    ('Ikelenge Town Council', 'Ikelenge', 'North-Western Province'),
    ('Mushindamo Town Council', 'Mushindamo', 'North-Western Province'),
    ('Kalumbila Town Council', 'Kalumbila', 'North-Western Province'),
    ('Mongu Municipal Council', 'Mongu', 'Western Province'),
    ('Senanga Town Council', 'Senanga', 'Western Province'),
    ('Kaoma Town Council', 'Kaoma', 'Western Province'),
    ('Kalabo Town Council', 'Kalabo', 'Western Province'),
    ('Sesheke Town Council', 'Sesheke', 'Western Province'),
    ("Shang'ombo Town Council", "Shang'ombo", 'Western Province'),
    ('Sikongo Town Council', 'Sikongo', 'Western Province'),
    ('Sioma Town Council', 'Sioma', 'Western Province'),
    ('Nalolo Town Council', 'Nalolo', 'Western Province'),
    ('Limulunga Town Council', 'Limulunga', 'Western Province'),
    ('Luampa Town Council', 'Luampa', 'Western Province'),
    ('Mitete Town Council', 'Mitete', 'Western Province'),
    ('Nkeyema Town Council', 'Nkeyema', 'Western Province'),
    ('Mwandi Town Council', 'Mwandi', 'Western Province'),
]


class Command(BaseCommand):
    help = 'Seed CouncilPage records for Zambian local authorities. Facebook URLs are left blank until administrators add official public pages.'

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for name, district, province in COUNCIL_SOURCES:
            page = CouncilPage.objects.filter(name=name, province=province).first()
            if page:
                changed = False
                if page.district != district:
                    page.district = district
                    changed = True
                if changed:
                    page.save(update_fields=['district', 'updated_at'])
                    updated_count += 1
                continue

            CouncilPage.objects.create(
                name=name,
                district=district,
                province=province,
                facebook_url='',
                is_active=True,
            )
            created_count += 1

        total = len(COUNCIL_SOURCES)
        self.stdout.write(
            self.style.SUCCESS(
                f'Seeded council sources: {created_count} created, {updated_count} updated, {total} listed.'
            )
        )
