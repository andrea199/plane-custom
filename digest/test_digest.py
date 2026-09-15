import datetime as dt
import tempfile
import unittest
from zoneinfo import ZoneInfo
from pathlib import Path
from unittest.mock import Mock

from digest import DigestError, Ledger, Plane, collect, due_now, normalize, render, summarize, validate_recipients

TODAY = dt.date(2026, 9, 15)
CONFIG = {'base_url': 'https://plane.example', 'workspace': 'oniro', 'api_key': 'test',
          'manager_id': 'andrea', 'recipients': [
              {'id': 'luca', 'name': 'Luca', 'email': 'luca.cervone@oniro.tech'},
              {'id': 'andrea', 'name': 'Andrea', 'email': 'andrea.detry@oniro.tech'}]}
PROJECT = {'id': 'p', 'identifier': 'PROJ', 'name': 'Progetto'}


def row(**kwargs):
    return {'id': 'task', 'sequence_id': 1, 'name': 'Task', 'state': {'name': 'In corso', 'group': 'started'},
            'assignees': ['luca'], 'priority': 'high', **kwargs}


def task(**kwargs):
    return normalize(row(**kwargs), PROJECT, CONFIG)


class DigestTests(unittest.TestCase):
    def test_completed_archived_and_draft_are_inactive(self):
        self.assertFalse(task(state={'name': 'Fatto', 'group': 'completed'})['active'])
        self.assertFalse(task(archived_at='2026-09-01')['active'])
        self.assertFalse(task(is_draft=True)['active'])

    def test_unknown_state_aborts(self):
        with self.assertRaises(DigestError):
            task(state='state-id-not-expanded')

    def test_invalid_date_aborts(self):
        with self.assertRaises(DigestError):
            task(start_date='yesterday')

    def test_future_start_never_becomes_today_goal(self):
        result = summarize([task(start_date='2026-09-16', priority='urgent')], 'luca', {'p': {'luca'}}, TODAY)
        self.assertEqual(result['focus'], [])

    def test_months_old_deadline_needs_review_not_a_daily_commitment(self):
        result = summarize([task(target_date='2026-05-10', priority='urgent')], 'luca', {'p': {'luca'}}, TODAY)
        self.assertEqual(result['focus'], [])
        self.assertEqual(len(result['stale']), 1)
        self.assertEqual(result['deadlines'], [])

    def test_blocked_is_not_a_suggested_goal(self):
        t = task(target_date='2026-09-14')
        t['blockers'] = ['Dipendenza aperta']
        result = summarize([t], 'luca', {'p': {'luca'}}, TODAY)
        self.assertEqual(result['focus'], [])
        self.assertEqual(len(result['deadlines']), 1)
        self.assertEqual(len(result['blocked']), 1)

    def test_no_personal_access_no_email_content(self):
        result = summarize([task()], 'luca', {'p': {'andrea'}}, TODAY)
        self.assertEqual(result['active'], 0)

    def test_undated_low_priority_backlog_not_invented_as_goal(self):
        result = summarize([task(state={'name': 'Backlog', 'group': 'backlog'}, priority='low')], 'luca', {'p': {'luca'}}, TODAY)
        self.assertEqual(result['focus'], [])

    def test_overdue_then_today_then_in_progress_and_three_max(self):
        rows = [task(id='ongoing'), task(id='today', target_date='2026-09-15'),
                task(id='late', target_date='2026-09-01'), task(id='extra')]
        result = summarize(rows, 'luca', {'p': {'luca'}}, TODAY)
        self.assertEqual([t['id'] for t in result['focus']][:2], ['late', 'today'])
        self.assertEqual(len(result['focus']), 3)

    def test_email_escapes_html_and_personal_has_no_other_people(self):
        rows = [task(name='<script>alert(1)</script>'), task(id='private', name='PRIVATE-ANDREA', assignees=['andrea'])]
        messages = render(CONFIG, rows, {'p': {'luca', 'andrea'}}, {'projects': 1, 'skipped_projects': 0, 'unassigned': 0}, TODAY)
        self.assertNotIn('<script>', messages[0]['html'])
        self.assertIn('&lt;script&gt;', messages[0]['html'])
        self.assertNotIn('PRIVATE-ANDREA', messages[0]['text'])
        self.assertIn('QUADRO DEL TEAM', messages[1]['text'])
        self.assertNotIn('QUADRO DEL TEAM', messages[0]['text'])

    def test_fail_closed_on_missing_recipient_or_external_address(self):
        with self.assertRaises(DigestError):
            validate_recipients(CONFIG, {'luca'})
        wrong = {**CONFIG, 'recipients': [{'id': 'andrea', 'email': 'andrea@example.com'}]}
        with self.assertRaises(DigestError):
            validate_recipients(wrong, {'andrea'})

    def test_collect_all_pages(self):
        client = Plane(CONFIG)
        client.get = Mock(side_effect=[{'results': [1], 'next_page_results': True, 'next_cursor': 'a'},
                                       {'results': [2], 'next_page_results': False}])
        self.assertEqual(client.all('projects/'), [1, 2])

    def test_broken_pagination_refuses_partial_result(self):
        client = Plane(CONFIG)
        client.get = Mock(return_value={'results': [1], 'next_page_results': True, 'next_cursor': 'a'})
        with self.assertRaises(DigestError):
            client.all('projects/')

    def test_ambiguous_pagination_refuses_partial_result(self):
        client = Plane(CONFIG)
        client.get = Mock(return_value={'results': [1]})
        with self.assertRaises(DigestError):
            client.all('projects/')

    def test_empty_cursor_is_not_sent_to_installed_api(self):
        client = Plane(CONFIG)
        response = Mock()
        response.read.return_value = b'[]'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=None)
        client.opener.open = Mock(return_value=response)
        client.get('projects/', {'per_page': 100, 'cursor': ''})
        request = client.opener.open.call_args.args[0]
        self.assertNotIn('cursor=', request.full_url)
        self.assertEqual(request.method, 'GET')

    def test_completed_dependency_does_not_block_but_unknown_does(self):
        api = Mock()
        api.all.side_effect = [[{'id': 'luca'}, {'id': 'andrea'}], [PROJECT], [{'id': 'luca'}, {'id': 'andrea'}],
                               [row(), row(id='done', state={'name': 'Fatto', 'group': 'completed'})]]
        api.get.return_value = {'blocked_by': [{'issue_id': 'done'}, {'issue_id': 'unread'}]}
        tasks, _, _ = collect(api, CONFIG)
        self.assertEqual(tasks[0]['blockers'], ['Dipendenza da verificare (fuori dai progetti letti)'])

    def test_ledger_prevents_duplicate_and_uncertain_retries(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'state.sqlite3')
            self.assertTrue(ledger.reserve('2026-09-15', 'luca'))
            self.assertFalse(ledger.reserve('2026-09-15', 'luca'))
            ledger.finish('2026-09-15', 'luca', 'uncertain')
            self.assertFalse(ledger.reserve('2026-09-15', 'luca'))
            self.assertTrue(ledger.reserve('2026-09-16', 'luca'))
            ledger.db.close()

    def test_weekday_and_delivery_window(self):
        self.assertTrue(due_now(dt.datetime(2026, 9, 15, 8, 30)))
        self.assertFalse(due_now(dt.datetime(2026, 9, 15, 8, 29)))
        self.assertFalse(due_now(dt.datetime(2026, 9, 15, 9, 30)))
        self.assertFalse(due_now(dt.datetime(2026, 9, 19, 8, 30)))

    def test_rome_schedule_tracks_summer_and_winter_time(self):
        rome = ZoneInfo('Europe/Rome')
        summer = dt.datetime(2026, 9, 15, 6, 30, tzinfo=dt.timezone.utc).astimezone(rome)
        winter = dt.datetime(2026, 11, 16, 7, 30, tzinfo=dt.timezone.utc).astimezone(rome)
        self.assertTrue(due_now(summer))
        self.assertTrue(due_now(winter))


if __name__ == '__main__':
    unittest.main()
