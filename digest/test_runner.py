"""Linux runner tests; SMTP and Docker are mocked, so no messages are sent."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

if os.name == 'nt':
    raise unittest.SkipTest('Server runner uses Linux file locks')

import runner
from digest import DigestError


class RunnerTests(unittest.TestCase):
    def test_smtp_library_errors_are_not_exposed(self):
        with patch.object(runner.subprocess, 'run', return_value=Mock(returncode=1, stdout='', stderr='SECRET')):
            with self.assertRaises(DigestError) as caught:
                runner.plane_shell('source')
        self.assertNotIn('SECRET', str(caught.exception))

    def test_error_notice_sent_at_most_once_per_day(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'config.json').write_text(json.dumps({'manager_id': 'andrea', 'recipients': [{'id': 'andrea', 'email': 'andrea.detry@oniro.tech'}]}))
            with patch.object(runner, 'HOME', root), patch.object(runner, 'plane_shell') as send:
                runner.notify_failure('Errore lettura')
                runner.notify_failure('Errore lettura')
                self.assertEqual(send.call_count, 1)

    def test_uncertain_notice_is_not_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'config.json').write_text(json.dumps({'manager_id': 'andrea', 'recipients': [{'id': 'andrea', 'email': 'andrea.detry@oniro.tech'}]}))
            with patch.object(runner, 'HOME', root), patch.object(runner, 'plane_shell', side_effect=DigestError('timeout')) as send:
                with self.assertRaises(DigestError):
                    runner.notify_failure('Errore lettura')
                runner.notify_failure('Errore lettura')
                self.assertEqual(send.call_count, 1)


if __name__ == '__main__':
    unittest.main()
