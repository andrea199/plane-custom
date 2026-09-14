from django.urls import path
from plane.urls import urlpatterns as plane_patterns
from .preview import enter
urlpatterns = [path('preview/start/', enter)] + plane_patterns
