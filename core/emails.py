import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse


logger = logging.getLogger(__name__)


def send_welcome_email(user, organization, request=None):
    if not user.email:
        return False

    dashboard_url = _absolute_url(request, reverse('dashboard'))
    context = {
        'user': user,
        'organization': organization,
        'dashboard_url': dashboard_url,
        'app_name': 'TenderAI',
    }
    subject = 'Welcome to TenderAI'
    text_body = render_to_string('emails/welcome_email.txt', context)
    html_body = render_to_string('emails/welcome_email.html', context)
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'TenderAI <no-reply@tenderai.local>')
    try:
        message = EmailMultiAlternatives(subject, text_body, from_email, [user.email])
        message.attach_alternative(html_body, 'text/html')
        message.send(fail_silently=False)
        return True
    except Exception:
        logger.exception('Could not send TenderAI welcome email to user %s', user.pk)
        return False


def _absolute_url(request, path):
    public_url = getattr(settings, 'TENDERAI_PUBLIC_URL', '').strip().rstrip('/')
    if public_url:
        return f'{public_url}{path}'
    if request:
        return request.build_absolute_uri(path)
    return path
