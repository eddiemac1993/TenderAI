from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.TENDERAI_REQUIRE_LOGIN:
            return self.get_response(request)
        if request.user.is_authenticated or self.is_public_path(request.path):
            return self.get_response(request)
        return redirect(f'{reverse("login")}?next={request.get_full_path()}')

    def is_public_path(self, path):
        public_prefixes = [
            settings.STATIC_URL,
            settings.MEDIA_URL,
            reverse('login'),
            reverse('logout'),
            '/admin/login/',
        ]
        return any(path.startswith(prefix) for prefix in public_prefixes if prefix)
