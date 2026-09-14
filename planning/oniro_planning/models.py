import uuid

from django.conf import settings
from django.db import models


class ProjectPlanning(models.Model):
    project = models.OneToOneField("db.Project", on_delete=models.CASCADE)
    enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)


class PlanSlot(models.Model):
    """A person's daily commitment; never changes the issue's due date."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE)
    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE)
    person = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    day = models.DateField()
    minutes = models.PositiveIntegerField()
    position = models.PositiveIntegerField(default=1)
    outcome = models.CharField(max_length=1000)
    status = models.CharField(max_length=16, default="planned")
    blocker = models.CharField(max_length=1000, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="planning_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="planning_updated")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["day", "person_id", "position", "created_at"]
        constraints = [
            models.CheckConstraint(check=models.Q(minutes__gte=1, minutes__lte=1440), name="planning_minutes_range"),
            models.UniqueConstraint(fields=["workspace", "issue", "person", "day"], condition=~models.Q(status__in=["cancelled", "rescheduled"]), name="planning_unique_daily_commitment"),
        ]
        indexes = [models.Index(fields=["workspace", "day"])]


class Capacity(models.Model):
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE)
    person = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    day = models.DateField()
    minutes = models.PositiveIntegerField()
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["workspace", "person", "day"], name="planning_unique_capacity"),
            models.CheckConstraint(check=models.Q(minutes__lte=1440), name="planning_capacity_range"),
        ]


class PlanEvent(models.Model):
    """Append-only application audit, including superseded commitments."""
    slot = models.ForeignKey(PlanSlot, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    at = models.DateTimeField(auto_now_add=True)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
