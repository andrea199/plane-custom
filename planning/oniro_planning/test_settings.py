"""Isolated test DB and in-memory caches/broker: never production settings."""
import os
from plane.settings.common import *  # noqa: F403,F401

if 'planning-test-db' not in os.environ.get('DATABASE_URL', ''):
    raise RuntimeError('Planner tests require an isolated planning-test-db URL')
SECRET_KEY = 'isolated-planner-tests-only'
DEBUG = True
WEB_URL = 'http://localhost:18080'
REDIS_URL = 'redis://planning-test-redis:6379/0'
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
CELERY_BROKER_URL = 'memory://'
CELERY_TASK_ALWAYS_EAGER = False
CELERY_RESULT_BACKEND = 'cache+memory://'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
