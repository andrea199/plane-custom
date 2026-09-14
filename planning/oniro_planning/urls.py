from django.urls import path
from .views import Bootstrap, Capacities, Projects, Slots, WorkItems

urlpatterns = [
    path("bootstrap/", Bootstrap.as_view()),
    path("projects/<uuid:project_id>/", Projects.as_view()),
    path("work-items/", WorkItems.as_view()),
    path("slots/", Slots.as_view()),
    path("slots/<uuid:slot_id>/", Slots.as_view()),
    path("capacities/", Capacities.as_view()),
]
