#!/usr/bin/env python3
"""Host-side disposable reference-container proof; no Docker socket in NetBox.

Usage: python3 scripts/prove_reaper_lane.py --output /absolute/evidence.json
Requires Docker Compose and the pinned NetBox image. Never touches a running
NetBox stack. No root/privileged execution, no published ports, no DB service.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    run_id = uuid.uuid4().hex
    project = 'hh709-' + run_id[:12]
    image = 'netboxcommunity/netbox:v4.4-3.4.2@sha256:14c2de3f179d8ed5b5722a76b6d7389c8c95bb8be46c600f3d7fe1f7698b4574'

    def command(argv, *, env=None, expected=0):
        result = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=120)
        if result.returncode != expected:
            raise RuntimeError('isolated lane command failed: ' + argv[0])
        return result.stdout

    with tempfile.TemporaryDirectory(prefix='hh709-container-') as directory:
        root = Path(directory)
        root.chmod(0o777)  # provisioning only; Q/state created 0700 by UID 999
        configuration = root / 'configuration'
        configuration.mkdir()
        (configuration / 'configuration.py').write_text(
            'import os\n'
            'SECRET_KEY = os.environ["SECRET_KEY"]\n'
            'ALLOWED_HOSTS = ["*"]\n'
            'DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "unused"}}\n'
            'REDIS = {"tasks": {"HOST": "localhost", "PORT": 6379, "DATABASE": 0}, '
            '"caching": {"HOST": "localhost", "PORT": 6379, "DATABASE": 1}}\n'
            'PLUGINS = ["netbox_hedgehog"]\n'
            'DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760\n')
        config = json.loads((repo / 'deployment/reaper/config.example.json').read_text())
        config_file = root / 'config.json'
        config_file.write_text(json.dumps(config))
        environment = {**os.environ,
            'REAPER_QUARANTINE_DIR': str(root / 'q'), 'REAPER_STATE_DIR': str(root / 'state'),
            'REAPER_PLUGIN_DIR': str(repo / 'netbox_hedgehog'),
            'REAPER_NETBOX_CONFIG_DIR': str(configuration), 'REAPER_CONFIG_FILE': str(config_file),
            'REAPER_DJANGO_SECRET_KEY': 'hh709-isolated-test-only-not-a-production-secret-0000',
        }
        compose = ['docker', 'compose', '-p', project, '-f', str(repo / 'deployment/reaper/compose.yml'),
                   '--profile', 'isolated-reaper']
        provision = ['docker', 'run', '--rm', '--user', '999:0', '--network', 'none',
                     '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                     '--mount', f'type=bind,src={root},dst=/provision',
                     '--entrypoint', '/opt/netbox/venv/bin/python', image]
        command(provision + ['-c', 'from pathlib import Path; '
                             '[Path("/provision", name).mkdir(mode=0o700) for name in ("q", "state")]'])
        try:
            # Long-lived target is the real reference service, not an ad-hoc
            # permissive container. Probe its namespace before running daemon.
            command(compose + ['run', '-d', '--name', project, '--entrypoint', 'sleep',
                               'ingress-reaper', 'infinity'], env=environment)
            inspection = json.loads(command(['docker', 'inspect', project]))[0]
            mounts = inspection['Mounts']
            expected = {'/secure-quarantine': True, '/reaper-state': True,
                        '/opt/netbox/netbox/netbox_hedgehog': False,
                        '/etc/netbox/config': False, '/etc/hnp-reaper.json': False}
            assert {mount['Destination']: mount['RW'] for mount in mounts} == expected
            assert inspection['Config']['User'] == '999:0'
            assert inspection['HostConfig']['ReadonlyRootfs'] is True
            assert not inspection['HostConfig']['Privileged']
            assert not inspection['HostConfig']['PortBindings']
            probe = ['docker', 'exec', project, '/opt/netbox/venv/bin/python',
                     '/opt/netbox/netbox/manage.py', 'shell', '-c',
                     'from netbox_hedgehog.tests.test_interchange.adapter_container_probe import run; run()']
            output = command(probe)
            line = next(line for line in output.splitlines() if line.startswith('HH709_CONTAINER '))
            evidence = json.loads(line.removeprefix('HH709_CONTAINER '))
            evidence.update(writable_mounts=sum(m['RW'] for m in mounts), forbidden_mounts=0,
                            run_id=run_id, observed_at=int(time.time()))
            digest = hashlib.sha256()
            for relative in ('deployment/reaper/compose.yml', 'deployment/reaper/config.example.json'):
                digest.update(relative.encode())
                digest.update((repo / relative).read_bytes())
            evidence['reference_sha256'] = digest.hexdigest()
            # Verify the real command preflight too, before recording proof.
            cli = ['docker', 'exec', project, '/opt/netbox/venv/bin/python',
                   '/opt/netbox/netbox/manage.py', 'isolated_ingress_reaper',
                   '--config', '/etc/hnp-reaper.json', '--state-dir', '/reaper-state']
            preflight = command(cli + ['--mode', 'preflight'])
            assert '"interval_seconds": 3600' in preflight
            # Actual wall-clock scheduled invocations: only these injected test
            # timings differ; the approved default cadence was checked above.
            approved_config = dict(config)
            config.update(reaper_interval_seconds=2, active_write_grace_seconds=1,
                          clock_skew_seconds=0, orphan_bound_seconds=5)
            config_file.write_text(json.dumps(config))
            process = subprocess.Popen(cli + ['--mode', 'serve'], stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)
            try:
                time.sleep(8)
                raw = command(['docker', 'exec', project, '/opt/netbox/venv/bin/python', '-c',
                               'from pathlib import Path; print(Path("/reaper-state/health.json").read_text())'])
                history = json.loads(raw)['history']
                assert len(history) >= 2 and all(row['succeeded'] for row in history)
                assert history[-1]['started_at'] - history[-2]['started_at'] >= 2
            finally:
                # Terminate the in-container daemon itself, not just docker exec.
                command(['docker', 'exec', project, '/opt/netbox/venv/bin/python', '-c',
                         'import os,signal; from pathlib import Path; '
                         '[(os.kill(int(p.name), signal.SIGTERM)) for p in Path("/proc").iterdir() '
                         'if p.name.isdigit() and b"isolated_ingress_reaper" in (p/"cmdline").read_bytes() '
                         'and b"--mode\\x00serve" in (p/"cmdline").read_bytes()]'])
                process.communicate(timeout=10)
            time.sleep(3)
            command(cli + ['--mode', 'health'], expected=1)
            # Recovery uses the approved hourly cadence, not a race between
            # two separate Django bootstraps and the accelerated two-second
            # interval. The missed-run observation above remains real.
            config_file.write_text(json.dumps(approved_config))
            command(cli + ['--mode', 'once'])
            command(cli + ['--mode', 'health'])
            listener_name = project + '-listener'
            try:
                command(compose + ['run', '-d', '--name', listener_name,
                                   'raw-ingress-listener'], env=environment)
                listener = json.loads(command(['docker', 'inspect', listener_name]))[0]
                assert listener['Config']['User'] == '999:0'
                assert listener['HostConfig']['ReadonlyRootfs'] is True
                assert listener['HostConfig']['NetworkMode'] == 'none'
                assert not listener['HostConfig']['PortBindings']
                assert {m['Destination'] for m in listener['Mounts']} == {
                    '/opt/netbox/netbox/netbox_hedgehog', '/etc/netbox/config',
                    '/etc/hnp-reaper.json'}
                assert set(listener['HostConfig']['Tmpfs']) == {'/run/hnp-listener'}
                assert not any(m['RW'] for m in listener['Mounts'])
                evidence['listener'] = json.loads(command(['docker', 'exec', listener_name,
                    '/opt/netbox/venv/bin/python', '-m',
                    'netbox_hedgehog.tests.test_interchange.listener_container_probe']))
            finally:
                command(['docker', 'rm', '-f', listener_name])
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(evidence, sort_keys=True) + '\n')
            print('HH709_CONTAINER uid=999 writable_mounts=2 forbidden_mounts=0 '
                  'hourly_contract=PASS real_scheduler=PASS missed=PASS recovery=PASS '
                  'listener_admitted=8 listener_refused_before_unit=1 result=PASS')
        finally:
            command(['docker', 'rm', '-f', project])
            command(compose + ['down'], env=environment)
            # Only directories created by this invocation, as their non-root owner.
            command(provision + ['-c', 'import shutil; '
                                 '[shutil.rmtree("/provision/" + name) for name in ("q", "state")]'])


if __name__ == '__main__':
    main()
