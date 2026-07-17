from django.contrib.auth.signals import user_logged_out
from django.dispatch import receiver

from .models import UserProfile


@receiver(user_logged_out)
def clear_active_session_on_logout(sender, request, user, **kwargs):
    if not user:
        return
    UserProfile.objects.filter(user=user, active_session_key=request.session.session_key or '').update(
        active_session_key='',
        active_session_started_at=None,
    )
