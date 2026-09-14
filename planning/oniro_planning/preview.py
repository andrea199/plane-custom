"""Demo entry point, imported exclusively by the isolated preview settings."""
from django.conf import settings
from django.contrib.auth import login
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from plane.db.models import User

def enter(request):
    if not getattr(settings, 'ONIRO_PLANNING_PREVIEW', False):
        return HttpResponseForbidden()
    login(request, User.objects.get(email='andrea@preview.example.test'), backend='django.contrib.auth.backends.ModelBackend')
    return redirect('/oniro-demo/planning/')
