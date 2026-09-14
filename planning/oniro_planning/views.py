from datetime import date
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import IntegrityError, transaction
from django.conf import settings
from django.db.models import Q
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from plane.api.middleware.api_authentication import APIKeyAuthentication
from plane.api.rate_limit import ApiKeyRateThrottle, ServiceTokenRateThrottle
from plane.db.models import APIToken, Issue, Project, ProjectMember, Workspace, WorkspaceMember
from .models import Capacity, PlanEvent, PlanSlot, ProjectPlanning


class Conflict(APIException):
    status_code = 409
    default_detail = "Il piano è cambiato. Aggiorna la schermata prima di riprovare."


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields)
        if unknown:
            raise ValidationError({k: "Campo non supportato" for k in unknown})
        return super().to_internal_value(data)


class SlotInput(StrictSerializer):
    id = serializers.UUIDField()
    issue_id = serializers.UUIDField()
    person_id = serializers.UUIDField()
    day = serializers.DateField()
    minutes = serializers.IntegerField(min_value=1, max_value=1440)
    position = serializers.IntegerField(min_value=1, max_value=999, default=1)
    outcome = serializers.CharField(max_length=1000)
    reschedule_from = serializers.UUIDField(required=False)
    source_version = serializers.IntegerField(min_value=1, required=False)


class SlotChange(StrictSerializer):
    version = serializers.IntegerField(min_value=1)
    minutes = serializers.IntegerField(min_value=1, max_value=1440, required=False)
    position = serializers.IntegerField(min_value=1, max_value=999, required=False)
    outcome = serializers.CharField(max_length=1000, required=False)
    status = serializers.ChoiceField(choices=["planned", "working", "blocked", "done", "cancelled"], required=False)
    blocker = serializers.CharField(max_length=1000, allow_blank=True, required=False)


def validated(cls, data):
    serializer = cls(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def as_date(value):
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValidationError("Data richiesta nel formato YYYY-MM-DD")


def as_uuid(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        raise ValidationError("Identificativo non valido")


def integer(value, default, maximum):
    try:
        result = int(value if value is not None else default)
        if result < 0 or result > maximum:
            raise ValueError()
        return result
    except (TypeError, ValueError):
        raise ValidationError("Parametro numerico non valido")


def name(user):
    return (f"{user.first_name or ''} {user.last_name or ''}".strip() or user.display_name or str(user.id))


def issue_data(issue):
    return {"id": str(issue.id), "project_id": str(issue.project_id), "project": issue.project.name,
            "identifier": f"{issue.project.identifier}-{issue.sequence_id}", "name": issue.name,
            "priority": issue.priority, "state": issue.state.name if issue.state else None,
            "state_group": issue.state.group if issue.state else None,
            "target_date": str(issue.target_date) if issue.target_date else None,
            "parent_id": str(issue.parent_id) if issue.parent_id else None,
            "assignee_ids": [str(x.id) for x in issue.assignees.all()]}


def slot_data(slot):
    return {"id": str(slot.id), "issue": issue_data(slot.issue), "person_id": str(slot.person_id),
            "day": str(slot.day), "minutes": slot.minutes, "position": slot.position,
            "outcome": slot.outcome, "status": slot.status, "blocker": slot.blocker,
            "version": slot.version, "updated_at": slot.updated_at.isoformat()}


def audit(slot, user, before=None):
    PlanEvent.objects.create(slot=slot, actor=user, before=before or {}, after=slot_data(slot))


class PlanningView(APIView):
    authentication_classes = [APIKeyAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_throttles(self):
        token = self.request.headers.get("X-Api-Key")
        if not token:
            return []
        if APIToken.objects.filter(token=token, is_service=True).exists():
            return [ServiceTokenRateThrottle()]
        return [ApiKeyRateThrottle()]

    def context(self, request, slug):
        workspace = get_object_or_404(Workspace, slug=slug, deleted_at__isnull=True)
        membership = WorkspaceMember.objects.filter(workspace=workspace, member=request.user,
                                                    is_active=True, deleted_at__isnull=True).first()
        if not membership or membership.role < 15:
            raise PermissionDenied("La pianificazione richiede il ruolo membro o amministratore.")
        projects = Project.objects.filter(workspace=workspace, archived_at__isnull=True, deleted_at__isnull=True,
                                          is_hidden=False, id__in=ProjectMember.objects.filter(
                                              workspace=workspace, member=request.user, role__gte=15, is_active=True,
                                              deleted_at__isnull=True).values("project_id"))
        return workspace, membership.role == 20, projects

    def person(self, request, workspace, project, person_id, admin):
        if not admin and person_id != request.user.id:
            raise PermissionDenied("Puoi pianificare soltanto la tua giornata.")
        if not WorkspaceMember.objects.filter(workspace=workspace, member_id=person_id, role__gte=15,
                                              is_active=True, deleted_at__isnull=True).exists():
            raise ValidationError("La persona non è un membro attivo del workspace.")
        if not ProjectMember.objects.filter(project=project, member_id=person_id, role__gte=15,
                                            is_active=True, deleted_at__isnull=True).exists():
            raise ValidationError("La persona deve essere un membro del progetto.")

    def slots(self, workspace, projects):
        return PlanSlot.objects.filter(workspace=workspace, issue__project__in=projects,
                                       issue__deleted_at__isnull=True).select_related("issue__project", "issue__state").prefetch_related("issue__assignees")


class Bootstrap(PlanningView):
    def get(self, request, slug):
        ws, admin, projects = self.context(request, slug)
        try:
            user_zone = ZoneInfo(request.user.user_timezone or 'Europe/Rome')
        except (ZoneInfoNotFoundError, ValueError):
            user_zone = ZoneInfo('Europe/Rome')
        enabled = set(ProjectPlanning.objects.filter(project__in=projects, enabled=True).values_list("project_id", flat=True))
        project_members = ProjectMember.objects.filter(project__in=projects, role__gte=15, is_active=True,
                                                       deleted_at__isnull=True).values_list("project_id", "member_id")
        grouped = {}
        for project, member in project_members:
            grouped.setdefault(str(project), []).append(str(member))
        members = WorkspaceMember.objects.filter(workspace=ws, role__gte=15, is_active=True,
                                                  deleted_at__isnull=True).select_related("member")
        return Response({"user_id": str(request.user.id), "can_manage_team": admin,
                         "preview": getattr(settings, 'ONIRO_PLANNING_PREVIEW', False),
                         "csrf_token": get_token(request._request), "today": timezone.localdate(timezone=user_zone).isoformat(),
                         "projects": [{"id": str(p.id), "name": p.name, "identifier": p.identifier,
                                       "enabled": p.id in enabled, "member_ids": grouped.get(str(p.id), [])} for p in projects.order_by("name")],
                         "members": [{"id": str(m.member_id), "name": name(m.member)} for m in members]})


class Projects(PlanningView):
    def patch(self, request, slug, project_id):
        ws, admin, projects = self.context(request, slug)
        if not admin:
            raise PermissionDenied()
        project = get_object_or_404(projects, pk=project_id)
        if set(request.data) != {"enabled"} or type(request.data["enabled"]) is not bool:
            raise ValidationError("Specificare enabled: true oppure false.")
        ProjectPlanning.objects.update_or_create(project=project, defaults={"enabled": request.data["enabled"]})
        return Response({"project_id": str(project_id), "enabled": request.data["enabled"]})


class WorkItems(PlanningView):
    def get(self, request, slug):
        ws, admin, projects = self.context(request, slug)
        projects = projects.filter(projectplanning__enabled=True)
        qp = request.query_params
        if qp.get("project_id"):
            projects = projects.filter(id=as_uuid(qp["project_id"]))
        issues = Issue.objects.filter(workspace=ws, project__in=projects, archived_at__isnull=True,
                                      deleted_at__isnull=True, is_draft=False).exclude(state__group__in=["completed", "cancelled"])
        if qp.get("query"):
            issues = issues.filter(name__icontains=qp["query"][:200])
        if qp.get("person_id"):
            issues = issues.filter(assignees__id=as_uuid(qp["person_id"]))
        offset, limit = integer(qp.get("offset"), 0, 100000), max(1, integer(qp.get("limit"), 60, 100))
        issues = issues.distinct().order_by("project__name", "sequence_id")
        count = issues.count()
        rows = issues.select_related("project", "state").prefetch_related("assignees")[offset:offset + limit]
        return Response({"results": [issue_data(i) for i in rows], "total": count,
                         "next_offset": offset + limit if offset + limit < count else None})


class Slots(PlanningView):
    def get(self, request, slug, slot_id=None):
        ws, admin, projects = self.context(request, slug)
        slots = self.slots(ws, projects)
        if slot_id:
            return Response(slot_data(get_object_or_404(slots, pk=slot_id)))
        qp = request.query_params
        start, end = as_date(qp.get("from")), as_date(qp.get("to"))
        if end < start or (end - start).days > 31:
            raise ValidationError("Intervallo massimo di 32 giorni.")
        if qp.get("carryover") == "true":
            slots = slots.filter(day__lt=start).exclude(status__in=["done", "cancelled", "rescheduled"]).exclude(issue__state__group__in=["completed", "cancelled"])
        else:
            slots = slots.filter(day__range=(start, end))
        if qp.get("person_id"):
            slots = slots.filter(person_id=as_uuid(qp["person_id"]))
        offset, limit = integer(qp.get("offset"), 0, 100000), max(1, integer(qp.get("limit"), 100, 200))
        count = slots.count()
        return Response({"retrieved_at": timezone.now().isoformat(), "results": [slot_data(s) for s in slots[offset:offset + limit]],
                         "total": count, "next_offset": offset + limit if offset + limit < count else None})

    def post(self, request, slug):
        ws, admin, projects = self.context(request, slug)
        data = validated(SlotInput, request.data)
        issue = get_object_or_404(Issue.objects.select_related("project", "state"), pk=data["issue_id"],
                                  workspace=ws, project__in=projects, archived_at__isnull=True, deleted_at__isnull=True, is_draft=False)
        self.person(request, ws, issue.project, data["person_id"], admin)
        if not ProjectPlanning.objects.filter(project=issue.project, enabled=True).exists():
            raise ValidationError("Il progetto non è abilitato alla pianificazione.")
        if issue.state and issue.state.group in ["completed", "cancelled"]:
            raise ValidationError("Questa task è già conclusa o annullata.")
        original = data.pop("reschedule_from", None)
        source_version = data.pop("source_version", None)
        try:
            with transaction.atomic():
                # Lock the workspace row to serialize creates/capacity updates, including missing rows.
                Workspace.objects.select_for_update().get(pk=ws.pk)
                existing = PlanSlot.objects.filter(pk=data["id"]).first()
                if existing:
                    if existing.workspace_id != ws.id or any(getattr(existing, k) != v for k, v in data.items()):
                        raise Conflict("Identificativo già usato con un contenuto diverso.")
                    return Response(slot_data(existing))
                if original:
                    source = get_object_or_404(self.slots(ws, projects).select_for_update(of=("self",)), pk=original)
                    self.person(request, ws, source.issue.project, source.person_id, admin)
                    if source.version != source_version or source.status in ["done", "cancelled", "rescheduled"]:
                        raise Conflict()
                    if source.issue_id != issue.id or source.person_id != data["person_id"] or source.day == data["day"]:
                        raise ValidationError("La ripianificazione conserva task e persona e richiede un giorno diverso.")
                    before = slot_data(source)
                    source.status, source.version, source.updated_by = "rescheduled", source.version + 1, request.user
                    source.save()
                    audit(source, request.user, before)
                slot = PlanSlot.objects.create(workspace=ws, created_by=request.user, updated_by=request.user, **data)
                audit(slot, request.user)
                return Response(slot_data(slot), status=201)
        except IntegrityError:
            raise Conflict("Questa task è già pianificata per la persona e il giorno selezionati.")

    def patch(self, request, slug, slot_id):
        ws, admin, projects = self.context(request, slug)
        data = validated(SlotChange, request.data)
        try:
            with transaction.atomic():
                slot = get_object_or_404(self.slots(ws, projects).select_for_update(of=("self",)), pk=slot_id)
                self.person(request, ws, slot.issue.project, slot.person_id, admin)
                if slot.version != data.pop("version"):
                    raise Conflict()
                if slot.status == "rescheduled":
                    raise ValidationError("Il piano è stato spostato: aprire il nuovo impegno.")
                if data.get("status", slot.status) == "blocked" and not data.get("blocker", slot.blocker).strip():
                    raise ValidationError("Indicare cosa impedisce di procedere.")
                before = slot_data(slot)
                for key, value in data.items():
                    setattr(slot, key, value)
                slot.version += 1
                slot.updated_by = request.user
                slot.save()
                audit(slot, request.user, before)
                return Response(slot_data(slot))
        except IntegrityError:
            raise Conflict("Esiste già un impegno attivo per questa task, persona e giorno.")


class Capacities(PlanningView):
    def get(self, request, slug):
        ws, admin, projects = self.context(request, slug)
        start, end = as_date(request.query_params.get("from")), as_date(request.query_params.get("to"))
        if end < start or (end - start).days > 31:
            raise ValidationError("Intervallo massimo di 32 giorni.")
        rows = Capacity.objects.filter(workspace=ws, day__range=(start, end))
        return Response({"results": [{"person_id": str(c.person_id), "day": str(c.day), "minutes": c.minutes, "version": c.version} for c in rows]})

    def put(self, request, slug):
        ws, admin, projects = self.context(request, slug)
        class Input(StrictSerializer):
            person_id = serializers.UUIDField()
            day = serializers.DateField()
            minutes = serializers.IntegerField(min_value=0, max_value=1440)
            version = serializers.IntegerField(min_value=0)
        data = validated(Input, request.data)
        if not admin and data["person_id"] != request.user.id:
            raise PermissionDenied()
        if not WorkspaceMember.objects.filter(workspace=ws, member_id=data["person_id"], role__gte=15,
                                              is_active=True, deleted_at__isnull=True).exists():
            raise ValidationError("Membro non valido.")
        with transaction.atomic():
            Workspace.objects.select_for_update().get(pk=ws.pk)
            obj = Capacity.objects.filter(workspace=ws, person_id=data["person_id"], day=data["day"]).first()
            if (obj.version if obj else 0) != data["version"]:
                raise Conflict()
            if obj:
                obj.minutes, obj.version = data["minutes"], obj.version + 1
                obj.save()
            else:
                obj = Capacity.objects.create(workspace=ws, **{k: v for k, v in data.items() if k != "version"})
        return Response({"person_id": str(obj.person_id), "day": str(obj.day), "minutes": obj.minutes, "version": obj.version})

    patch = put
