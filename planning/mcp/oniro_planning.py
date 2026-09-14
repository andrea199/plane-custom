"""Compact daily planning tools for the existing ONIRO MCP transport."""
from oniro_write import ID, obj, validate_schema

DATE = {'type':'string','format':'date'}
TEXT = {'type':'string','minLength':1,'maxLength':1000}
MINUTES = {'type':'integer','minimum':1,'maximum':1440}
VERSION = {'type':'integer','minimum':1}
RANGE = {'from':DATE,'to':DATE}
PAGING = {'offset':{'type':'integer','minimum':0,'maximum':100000}, 'limit':{'type':'integer','minimum':1,'maximum':100}}
STATUS = {'type':'string','enum':['planned','working','blocked','done','cancelled']}

def build_planning_tools():
    def tool(name, description, fields, required=(), write=False):
        return {'name':name,'description':description,'inputSchema':obj(fields,required),
                'annotations':{'readOnlyHint':not write,'destructiveHint':write,'idempotentHint':not write,'openWorldHint':True}}
    return [
        tool('get_planning_context','Read people, project membership and enabled agenda projects. Prefer this and list_daily_plan over a full workspace scan for daily scheduling.',{}),
        tool('list_daily_plan','Read daily commitments in an inclusive date range of at most 32 days; follow next_offset. carryover=true returns unfinished commitments BEFORE from. Task deadlines and planned execution days are separate.',{**RANGE,**PAGING,'person_id':ID,'carryover':{'type':'boolean'}},['from','to']),
        tool('get_daily_commitment','Read one commitment and its current version before editing.',{'slot_id':ID},['slot_id']),
        tool('list_planning_work_items','Search unfinished tasks from enabled projects. Results are paginated on the server. Resolve task and person IDs before planning.',{**PAGING,'project_id':ID,'person_id':ID,'query':{'type':'string','maxLength':200}}),
        tool('list_daily_capacity','Read declared availability for people in a date range, maximum 32 days. Missing availability is unknown; zero means unavailable.',RANGE,['from','to']),
        tool('create_daily_commitment','Create an authorized daily commitment. Supply a new UUID id; reuse it with IDENTICAL arguments to verify an uncertain creation. Does not alter task deadlines or assignees. To move an existing commitment, also pass reschedule_from and source_version; task and person must stay the same.',
             {'id':ID,'issue_id':ID,'person_id':ID,'day':DATE,'minutes':MINUTES,'position':{'type':'integer','minimum':1,'maximum':999},'outcome':TEXT,'reschedule_from':ID,'source_version':VERSION},['id','issue_id','person_id','day','minutes','outcome'],True),
        tool('update_daily_commitment','Change an authorized daily commitment using the exact version from a fresh read. done means the daily outcome is done; it does not close the task. A stale version rejects the entire change. blocked requires a blocker explanation.',
             {'slot_id':ID,'version':VERSION,'changes':obj({'minutes':MINUTES,'position':{'type':'integer','minimum':1,'maximum':999},'outcome':TEXT,'status':STATUS,'blocker':{'type':'string','maxLength':1000}},min_properties=1)},['slot_id','version','changes'],True),
        tool('set_daily_capacity','Set explicitly requested availability in minutes. Read capacity first and pass its version, or 0 only if no record exists. Zero minutes means unavailable.',
             {'person_id':ID,'day':DATE,'minutes':{'type':'integer','minimum':0,'maximum':1440},'version':{'type':'integer','minimum':0}},['person_id','day','minutes','version'],True),
        tool('set_project_planning_enabled','Administrator: explicitly include or exclude a project from selecting NEW commitments. Existing history is retained. Do not enable draft projects without user direction.',
             {'project_id':ID,'enabled':{'type':'boolean'}},['project_id','enabled'],True),
    ]

PLANNING_NAMES={t['name'] for t in build_planning_tools()}

def invoke_planning(plane,name,args):
    schema=next(t['inputSchema'] for t in build_planning_tools() if t['name']==name)
    validate_schema(args,schema,'arguments')
    if name=='get_planning_context':
        result=plane.request('GET','planning/bootstrap/')
        result.pop('csrf_token',None)
        return result
    if name=='get_daily_commitment':
        return plane.request('GET','planning/slots/'+args['slot_id']+'/')
    if name in ('list_daily_plan','list_planning_work_items','list_daily_capacity'):
        route={'list_daily_plan':'slots/','list_planning_work_items':'work-items/','list_daily_capacity':'capacities/'}[name]
        params=dict(args)
        if 'carryover' in params:params['carryover']='true' if params['carryover'] else 'false'
        return plane.request('GET','planning/'+route,params=params)
    if name=='create_daily_commitment':
        if ('reschedule_from' in args)!=('source_version' in args):
            raise ValueError('Rescheduling requires both reschedule_from and source_version.')
        return plane.request('POST','planning/slots/',data=args)
    if name=='update_daily_commitment':
        return plane.request('PATCH','planning/slots/'+args['slot_id']+'/',data={'version':args['version'],**args['changes']})
    if name=='set_daily_capacity':
        return plane.request('PATCH','planning/capacities/',data=args)
    if name=='set_project_planning_enabled':
        return plane.request('PATCH','planning/projects/'+args['project_id']+'/',data={'enabled':args['enabled']})
    raise ValueError('Unknown planning tool')
