import uuid
from datetime import date

from django.test import TestCase
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from plane.db.models import User, Workspace, WorkspaceMember, Project, ProjectMember, Issue, State, APIToken
from .models import ProjectPlanning, PlanSlot, PlanEvent, Capacity


class PlanningTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create(email='admin@example.test', username='planner-admin', first_name='Admin')
        self.member = User.objects.create(email='member@example.test', username='planner-member', first_name='Member')
        self.outsider = User.objects.create(email='outsider@example.test', username='planner-outsider')
        self.ws = Workspace.objects.create(name='Planning test', slug='planning-test', owner=self.admin)
        for user, role in [(self.admin,20),(self.member,15),(self.outsider,15)]:
            WorkspaceMember.objects.create(workspace=self.ws, member=user, role=role, is_active=True)
        self.project = Project.objects.create(workspace=self.ws, name='Project', identifier='PLAN')
        for user in [self.admin, self.member]:
            ProjectMember.objects.create(workspace=self.ws, project=self.project, member=user, role=20 if user==self.admin else 15, is_active=True)
        self.state = State.objects.create(workspace=self.ws, project=self.project, name='Ready', group='unstarted')
        self.issue = Issue.objects.create(workspace=self.ws, project=self.project, name='Deliver result', state=self.state, target_date=date(2026,10,1))
        ProjectPlanning.objects.create(project=self.project, enabled=True)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.url = '/api/workspaces/planning-test/planning/'

    def payload(self, **kwargs):
        return dict(id=str(uuid.uuid4()), issue_id=str(self.issue.id), person_id=str(self.member.id), day='2026-09-14', minutes=120, position=1, outcome='Report ready', **kwargs)

    def create(self, payload=None):
        response=self.client.post(self.url+'slots/', payload or self.payload(), format='json')
        self.assertEqual(response.status_code,201,response.data)
        return response.data

    def test_create_keeps_task_due_date_and_assignments(self):
        row=self.create();self.issue.refresh_from_db()
        self.assertEqual(str(self.issue.target_date),'2026-10-01')
        self.assertEqual(self.issue.assignees.count(),0)
        self.assertEqual(PlanEvent.objects.count(),1)
        self.assertEqual(row['minutes'],120)

    def test_post_idempotency_and_content_conflict(self):
        data=self.payload();self.create(data)
        self.assertEqual(self.client.post(self.url+'slots/',data,format='json').status_code,200)
        data['minutes']=60
        self.assertEqual(self.client.post(self.url+'slots/',data,format='json').status_code,409)
        self.assertEqual(PlanSlot.objects.count(),1)

    def test_duplicate_daily_slot_rejected(self):
        self.create()
        self.assertEqual(self.client.post(self.url+'slots/',self.payload(),format='json').status_code,409)

    def test_version_conflict_preserves_first_edit(self):
        row=self.create();url=self.url+'slots/'+row['id']+'/'
        self.assertEqual(self.client.patch(url,{'version':1,'minutes':30},format='json').status_code,200)
        self.assertEqual(self.client.patch(url,{'version':1,'minutes':90},format='json').status_code,409)
        self.assertEqual(PlanSlot.objects.get().minutes,30)
        self.assertEqual(PlanEvent.objects.count(),2)

    def test_member_cannot_change_others(self):
        data=self.payload();data['person_id']=str(self.admin.id);row=self.create(data)
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.patch(self.url+'slots/'+row['id']+'/',{'version':1,'minutes':60},format='json').status_code,403)
        self.assertEqual(self.client.post(self.url+'slots/',data,format='json').status_code,403)

    def test_project_membership_is_required_for_reader(self):
        row=self.create();self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(self.url+'slots/'+row['id']+'/').status_code,404)
        response=self.client.get(self.url+'slots/?from=2026-09-14&to=2026-09-14')
        self.assertEqual(response.data['results'],[])
        self.assertEqual(self.client.get(self.url+'bootstrap/').data['projects'],[])

    def test_person_must_belong_to_project(self):
        data=self.payload();data['person_id']=str(self.outsider.id)
        self.assertEqual(self.client.post(self.url+'slots/',data,format='json').status_code,400)

    def test_disabled_project_excluded(self):
        ProjectPlanning.objects.update(enabled=False)
        self.assertEqual(self.client.get(self.url+'work-items/').data['results'],[])
        self.assertEqual(self.client.post(self.url+'slots/',self.payload(),format='json').status_code,400)

    def test_reschedule_preserves_previous_commitment(self):
        old=self.create();data=self.payload();data.update(day='2026-09-15',reschedule_from=old['id'],source_version=1)
        self.create(data)
        self.assertEqual(PlanSlot.objects.get(pk=old['id']).status,'rescheduled')
        self.assertEqual(PlanSlot.objects.count(),2)
        self.assertEqual(PlanEvent.objects.count(),3)

    def test_blocker_required_and_fields_validated(self):
        row=self.create();url=self.url+'slots/'+row['id']+'/'
        for data in [{'version':1,'status':'blocked'},{'version':1,'minutes':0},{'version':1,'person_id':str(self.admin.id)},{'version':1,'day':'2026-09-16'}]:
            self.assertEqual(self.client.patch(url,data,format='json').status_code,400)

    def test_capacity_zero_and_conflict(self):
        data={'person_id':str(self.member.id),'day':'2026-09-14','minutes':0,'version':0}
        self.assertEqual(self.client.patch(self.url+'capacities/',data,format='json').status_code,200)
        self.assertEqual(self.client.patch(self.url+'capacities/',data,format='json').status_code,409)
        self.assertEqual(Capacity.objects.get().minutes,0)

    def test_guest_and_unauthenticated_denied(self):
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(self.url+'bootstrap/').status_code,[401,403])
        WorkspaceMember.objects.filter(member=self.member).update(role=5)
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.get(self.url+'bootstrap/').status_code,403)

    def test_date_range_and_pagination(self):
        self.create()
        self.assertEqual(self.client.get(self.url+'slots/?from=bad&to=2026-09-14').status_code,400)
        self.assertEqual(self.client.get(self.url+'slots/?from=2026-01-01&to=2026-12-31').status_code,400)
        response=self.client.get(self.url+'slots/?from=2026-09-14&to=2026-09-14&limit=1')
        self.assertEqual(response.data['total'],1)
        self.assertIsNone(response.data['next_offset'])

    def test_session_csrf_enforced(self):
        client=APIClient(enforce_csrf_checks=True)
        client.force_login(self.admin)
        response=client.post(self.url+'slots/',self.payload(),format='json')
        self.assertEqual(response.status_code,403)

    def test_api_token_and_shared_route(self):
        key='planner-test-token-'+str(uuid.uuid4())
        APIToken.objects.create(user=self.admin,token=key,label='Planner test',is_active=True)
        client=APIClient();client.credentials(HTTP_X_API_KEY=key)
        response=client.get('/api/v1/workspaces/planning-test/planning/bootstrap/')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['user_id'],str(self.admin.id))

    def test_failed_reschedule_rolls_back_source_and_audit(self):
        old=self.create();data=self.payload();data['day']='2026-09-15';self.create(data)
        data=self.payload();data.update(day='2026-09-15',reschedule_from=old['id'],source_version=1)
        self.assertEqual(self.client.post(self.url+'slots/',data,format='json').status_code,409)
        self.assertEqual(PlanSlot.objects.get(pk=old['id']).status,'planned')
        self.assertEqual(PlanEvent.objects.count(),2)

    def test_authenticated_session_can_write_with_bootstrap_csrf(self):
        client=APIClient(enforce_csrf_checks=True);client.force_login(self.admin)
        boot=client.get(self.url+'bootstrap/')
        response=client.post(self.url+'slots/',self.payload(),format='json',HTTP_X_CSRFTOKEN=boot.data['csrf_token'])
        self.assertEqual(response.status_code,201,response.data)

    def test_closed_and_archived_tasks_excluded(self):
        self.issue.archived_at=timezone.now();self.issue.save()
        self.assertEqual(self.client.get(self.url+'work-items/').data['results'],[])
        self.assertEqual(self.client.post(self.url+'slots/',self.payload(),format='json').status_code,404)
        self.issue.archived_at=None;self.issue.save();self.state.group='completed';self.state.save()
        self.assertEqual(self.client.get(self.url+'work-items/').data['results'],[])
        self.assertEqual(self.client.post(self.url+'slots/',self.payload(),format='json').status_code,400)

    def test_canonical_comment_endpoint_used_by_planner(self):
        url=f'/api/workspaces/{self.ws.slug}/projects/{self.project.id}/issues/{self.issue.id}/comments/'
        response=self.client.post(url,{'comment_html':'<p>Planning test comment</p>'},format='json')
        self.assertEqual(response.status_code,201,response.data)
        response=self.client.get(url)
        self.assertEqual(response.status_code,200,response.data)
        self.assertIn('Planning test comment',str(response.data))
