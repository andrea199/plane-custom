"""Create clearly fictitious demonstration data in the isolated DB only."""
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from plane.db.models import User, Workspace, WorkspaceMember, Project, ProjectMember, State, Issue
from oniro_planning.models import ProjectPlanning, PlanSlot, Capacity

assert settings.ONIRO_PLANNING_PREVIEW
assert settings.DATABASES['default']['HOST'] == 'planning-test-db'
people = []
for name in ['Andrea', 'Luca', 'Riccardo', 'Antonio']:
    user, _ = User.objects.get_or_create(email=name.lower()+'@preview.example.test', defaults={'username':'preview-'+name.lower(), 'first_name':name, 'user_timezone':'Europe/Rome'})
    people.append(user)
ws, _ = Workspace.objects.get_or_create(slug='oniro-demo', defaults={'name':'ONIRO — DATI DI ESEMPIO', 'owner':people[0]})
for user in people:
    WorkspaceMember.objects.get_or_create(workspace=ws, member=user, defaults={'role':20 if user==people[0] else 15, 'is_active':True})
project, _ = Project.objects.get_or_create(workspace=ws, identifier='DEMO', defaults={'name':'Progetto dimostrativo'})
for user in people:
    ProjectMember.objects.get_or_create(workspace=ws, project=project, member=user, defaults={'role':20 if user==people[0] else 15, 'is_active':True})
ready, _ = State.objects.get_or_create(workspace=ws, project=project, name='Da fare', defaults={'group':'unstarted'})
ProjectPlanning.objects.update_or_create(project=project, defaults={'enabled':True})
today = timezone.localdate()
names = ['Definire le priorità della settimana', 'Preparare il modello per il prototipo', 'Verificare il risultato della prova', 'Preparare materiali e attrezzatura']
for index, user in enumerate(people):
    issue, _ = Issue.objects.get_or_create(workspace=ws, project=project, name=names[index], defaults={'state':ready, 'priority':['high','urgent','medium','high'][index], 'target_date':today+timedelta(days=3)})
    issue.assignees.add(user, through_defaults={'workspace':ws, 'project':project})
    PlanSlot.objects.get_or_create(workspace=ws, issue=issue, person=user, day=today, defaults={'minutes':[60,150,90,120][index], 'outcome':['Elenco delle tre priorità condiviso','Modello pronto per la verifica','Risultati annotati nella task','Postazione pronta per la lavorazione'][index], 'created_by':people[0], 'updated_by':people[0]})
    Capacity.objects.get_or_create(workspace=ws, person=user, day=today, defaults={'minutes':360})
print('Demo ready: 4 fictional people and commitments; production untouched.')
