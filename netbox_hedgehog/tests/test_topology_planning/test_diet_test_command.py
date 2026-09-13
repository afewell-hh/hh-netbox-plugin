"""Regression coverage for the supported local DIET test command (DIET-652)."""

import os
import stat
import subprocess
import tempfile
from pathlib import Path

from django.test import SimpleTestCase


REPO_ROOT = Path(__file__).resolve().parents[3]
COMMAND = REPO_ROOT / 'netbox_hedgehog' / 'scripts' / 'run_diet_tests.sh'
RUNNER = 'netbox_hedgehog.tests.runner.DietTestRunner'


class DietTestCommandTestCase(SimpleTestCase):
    """The wrapper must always explicitly select the test-only guard runner."""

    def _run_command(self, *arguments):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            fake_docker = temp / 'docker'
            fake_docker.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n', encoding='utf-8')
            fake_docker.chmod(fake_docker.stat().st_mode | stat.S_IXUSR)

            environment = os.environ.copy()
            environment['NETBOX_DOCKER_DIR'] = temp_dir
            environment['PATH'] = f'{temp_dir}{os.pathsep}{environment["PATH"]}'
            return subprocess.run(
                [str(COMMAND), *arguments],
                check=False,
                capture_output=True,
                encoding='utf-8',
                env=environment,
            )

    def test_invokes_manage_test_with_the_diet_test_runner(self):
        result = self._run_command('example.diet_test', '--keepdb')

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                'compose',
                'exec',
                '-T',
                'netbox',
                'python',
                '-u',
                'manage.py',
                'test',
                'example.diet_test',
                '--keepdb',
                f'--testrunner={RUNNER}',
            ],
        )

    def test_rejects_an_attempt_to_replace_the_test_runner(self):
        result = self._run_command('example.diet_test', '--testrunner=other.Runner')

        self.assertEqual(result.returncode, 2)
        self.assertIn('do not pass --testrunner', result.stderr)
        self.assertEqual(result.stdout, '')
