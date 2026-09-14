from .test_settings import *
ONIRO_PLANNING_PREVIEW = True
ROOT_URLCONF = 'oniro_planning.preview_urls'
ALLOWED_HOSTS = ['plane-aziendaa.tail490d68.ts.net', 'planning-preview-web', 'localhost', '127.0.0.1']
SESSION_COOKIE_NAME = 'oniro_planning_preview_session'
CSRF_COOKIE_NAME = 'oniro_planning_preview_csrf'
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_DOMAIN = None
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
CSRF_TRUSTED_ORIGINS = ['https://plane-aziendaa.tail490d68.ts.net:9443']
