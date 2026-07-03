from django.conf import settings
from django.db import migrations


def seed_default_organization(apps, schema_editor):
    Organization = apps.get_model('core', 'Organization')
    UserProfile = apps.get_model('core', 'UserProfile')
    User = apps.get_model('auth', 'User')
    Company = apps.get_model('companies', 'Company')
    SupportChatSession = apps.get_model('core', 'SupportChatSession')

    organization, _ = Organization.objects.get_or_create(
        name='TenderAI Owner',
        defaults={'active': True},
    )
    Company.objects.filter(organization__isnull=True).update(organization=organization)
    SupportChatSession.objects.filter(organization__isnull=True).update(organization=organization)
    for user in User.objects.filter(is_superuser=True):
        UserProfile.objects.get_or_create(
            user=user,
            defaults={'organization': organization, 'role': 'ORG_ADMIN'},
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0003_organization_supportchatsession_organization_and_more'),
        ('companies', '0002_company_organization_alter_company_name_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_default_organization, noop_reverse),
    ]
