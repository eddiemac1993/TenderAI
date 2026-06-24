"""
PythonAnywhere WSGI template for TenderAI.

Copy this into the WSGI configuration file shown on the PythonAnywhere Web tab.
Change YOUR_USERNAME below to your PythonAnywhere username.
"""

import os
import sys


USERNAME = 'YOUR_USERNAME'
PROJECT_PATH = f'/home/{USERNAME}/TenderAI'

if PROJECT_PATH not in sys.path:
    sys.path.insert(0, PROJECT_PATH)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tenderai.settings')
os.environ.setdefault('DJANGO_SECRET_KEY', 'change-this-on-pythonanywhere')
os.environ.setdefault('DJANGO_DEBUG', '0')
os.environ.setdefault('DJANGO_ALLOWED_HOSTS', f'{USERNAME}.pythonanywhere.com')
os.environ.setdefault('DJANGO_CSRF_TRUSTED_ORIGINS', f'https://{USERNAME}.pythonanywhere.com')
os.environ.setdefault('TENDERAI_REQUIRE_LOGIN', '1')
os.environ.setdefault('DJANGO_SECURE_SSL_REDIRECT', '0')
os.environ.setdefault('DJANGO_SESSION_COOKIE_SECURE', '1')
os.environ.setdefault('DJANGO_CSRF_COOKIE_SECURE', '1')

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
