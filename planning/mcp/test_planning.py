import unittest
from unittest.mock import Mock
from oniro_planning import invoke_planning

ID='11111111-1111-4111-8111-111111111111'
class PlanningTransportTests(unittest.TestCase):
    def setUp(self):
        self.plane=Mock();self.plane.request.return_value={'results':[]}
    def test_context_never_returns_csrf(self):
        self.plane.request.return_value={'csrf_token':'private','members':[]}
        self.assertNotIn('csrf_token',invoke_planning(self.plane,'get_planning_context',{}))
    def test_pagination_and_boolean_pass_through(self):
        invoke_planning(self.plane,'list_daily_plan',{'from':'2026-09-14','to':'2026-09-14','carryover':True,'offset':100,'limit':20})
        self.assertEqual(self.plane.request.call_args.kwargs['params']['carryover'],'true')
        self.assertEqual(self.plane.request.call_args.kwargs['params']['offset'],100)
    def test_version_is_mandatory(self):
        with self.assertRaises(ValueError):invoke_planning(self.plane,'update_daily_commitment',{'slot_id':ID,'changes':{'minutes':30}})
        self.plane.request.assert_not_called()
    def test_id_cannot_escape_api_path(self):
        with self.assertRaises(ValueError):invoke_planning(self.plane,'get_daily_commitment',{'slot_id':'../../projects/'})
        self.plane.request.assert_not_called()
    def test_updates_cannot_change_execution_day(self):
        with self.assertRaises(ValueError):invoke_planning(self.plane,'update_daily_commitment',{'slot_id':ID,'version':1,'changes':{'day':'2026-09-15'}})
        self.plane.request.assert_not_called()
    def test_transport_preserves_version(self):
        invoke_planning(self.plane,'update_daily_commitment',{'slot_id':ID,'version':7,'changes':{'minutes':30}})
        self.plane.request.assert_called_once_with('PATCH','planning/slots/'+ID+'/',data={'version':7,'minutes':30})
    def test_capacity_zero_allowed(self):
        args={'person_id':ID,'day':'2026-09-14','minutes':0,'version':0}
        invoke_planning(self.plane,'set_daily_capacity',args)
        self.plane.request.assert_called_once_with('PATCH','planning/capacities/',data=args)
    def test_uncertain_writes_are_not_retried(self):
        self.plane.request.side_effect=RuntimeError('Connection lost')
        with self.assertRaises(RuntimeError):invoke_planning(self.plane,'set_project_planning_enabled',{'project_id':ID,'enabled':True})
        self.assertEqual(self.plane.request.call_count,1)
if __name__=='__main__':unittest.main()
