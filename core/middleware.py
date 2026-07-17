from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse

from .tenancy import path_allowed_for_limited_user, user_has_full_access, user_profile


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.TENDERAI_REQUIRE_LOGIN:
            return self.get_response(request)
        if request.user.is_authenticated:
            session_response = self.enforce_single_session(request)
            if session_response:
                return session_response
            if not self.user_can_access_path(request):
                messages.warning(
                    request,
                    'This feature is locked on limited access. Admin must grant full access days or mark the user as Pro.',
                )
                return redirect('dashboard')
            return self.get_response(request)
        if self.is_public_path(request.path):
            return self.get_response(request)
        return redirect(f'{reverse("login")}?next={request.get_full_path()}')

    def is_public_path(self, path):
        public_prefixes = [
            settings.STATIC_URL,
            settings.MEDIA_URL,
            reverse('login'),
            reverse('register'),
            reverse('logout'),
            '/admin/login/',
        ]
        return any(path.startswith(prefix) for prefix in public_prefixes if prefix)

    def enforce_single_session(self, request):
        if request.user.is_superuser:
            return None
        profile = user_profile(request.user)
        if not profile or profile.is_pro:
            return None
        current_key = request.session.session_key
        if not current_key:
            return None
        if profile.active_session_key and profile.active_session_key != current_key:
            logout(request)
            messages.error(request, 'This account is already logged in on another device.')
            return redirect('login')
        if not profile.active_session_key:
            profile.active_session_key = current_key
            profile.save(update_fields=['active_session_key'])
        return None

    def user_can_access_path(self, request):
        if request.user.is_superuser:
            return True
        if user_has_full_access(request.user):
            return True
        return path_allowed_for_limited_user(request.path)
