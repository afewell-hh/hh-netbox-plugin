"""Explicit lane-only evidence harness. Never loaded by the hourly runner.

Unit is measured in a private loopback child process. Container isolation must
additionally come from the host-side lane runner, mounted read-only by CI; a
process inside the web test container cannot certify another container's mounts.
"""
from __future__ import annotations

import dataclasses
import hashlib
import http.client
import json
import os
import re
import socket
import stat
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from .reaper_adapter import HarnessEvidenceMissing, validate_deployment

_REQUIRED = ('accepted_raw', 'oversize_413', 'chunked_411', 'no_listener_spool',
             'uid_isolation', 'mount_isolation', 'no_public_upload_route')


def _code_digest():
    root = Path(__file__).parent
    digest = hashlib.sha256()
    for relative in ('reaper_adapter.py', 'reaper_lane.py', 'secure_ingress.py',
                     'raw_ingress_admission.py', 'reference_listener.py',
                     'management/commands/isolated_ingress_reaper.py'):
        digest.update(relative.encode())
        digest.update((root / relative).read_bytes())
    return digest.hexdigest()


def _fail():
    raise HarnessEvidenceMissing('lane evidence missing or contradicted') from None


@dataclasses.dataclass(frozen=True)
class _Observation:
    observed: bool
    evidence: object


@dataclasses.dataclass(frozen=True)
class _Result:
    observations: dict
    unit_version: str

    def without(self, name):
        return dataclasses.replace(self, observations={k: v for k, v in self.observations.items() if k != name})

    def with_observation(self, name, **changes):
        return dataclasses.replace(self, observations={
            **self.observations, name: dataclasses.replace(self.observations[name], **changes)})


def _container_evidence(uid):
    try:
        if 'HNP_REAPER_CONTAINER_EVIDENCE' in os.environ:
            path = Path(os.environ['HNP_REAPER_CONTAINER_EVIDENCE'])
            if not os.statvfs(path).f_flag & os.ST_RDONLY:
                _fail()
        else:
            # Supported local runner copies fresh host-observed evidence into
            # its explicitly labelled permission-read-only snapshot. This is
            # not a claim of a kernel read-only mount; CI always uses the above.
            path = Path(os.environ['HNP_TEST_LOCAL_CHECKOUT_ROOT']) / 'reaper-container-evidence.json'
            if path.stat().st_mode & 0o222:
                _fail()
        raw = path.read_bytes()
        if len(raw) > 65536:
            _fail()
        data = json.loads(raw)
        if (data['code_sha256'] != _code_digest() or data['uid'] != uid or uid == 0
                or data['q_owner_uid'] != uid or data['q_mode'] != 0o700
                or data['root_readonly'] is not True or data['writable_mounts'] != 2
                or data['forbidden_mounts'] != 0 or data['effective_capabilities'] != 0
                or data['no_new_privileges'] is not True
                or not re.fullmatch('[a-f0-9]{32}', data['run_id'])
                or not 0 <= time.time() - data['observed_at'] <= 3600):
            _fail()
        if data['scheduler'] != {'interval_seconds': 3600, 'real_reap': True,
                                  'first_failure': True, 'missed': True, 'recovery': True,
                                  'bounded': True, 'secret_absent': True}:
            _fail()
        listener = data['listener']
        if (listener['uid'] != uid or listener['admitted'] != 8
                or listener['refused'] != 1 or listener['refused_reached_unit'] is not False
                or listener['q_mounted'] is not False or listener['public_listener'] is not False
                or listener['spool_sentinel_absent'] is not True
                or listener['unit_processes_inspected'] < 3):
            _fail()
        checkout = Path(os.environ.get('HNP_TEST_CHECKOUT_ROOT')
                        or os.environ['HNP_TEST_LOCAL_CHECKOUT_ROOT'])
        digest = hashlib.sha256()
        for relative in ('deployment/reaper/compose.yml', 'deployment/reaper/config.example.json'):
            digest.update(relative.encode())
            digest.update((checkout / relative).read_bytes())
        if digest.hexdigest() != data['reference_sha256']:
            _fail()
        return data
    except (OSError, KeyError, TypeError, ValueError):
        _fail()


class _UnixConnection(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__('localhost', timeout=5)
        self.path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(str(self.path))


def _unit_probe(root, cap, app_file):
    """Real Unit 1.34.2: includes an in-flight raw body and open/deleted FDs."""
    version = subprocess.run(['unitd', '--version'], capture_output=True, text=True, check=True)
    match = re.search(r'unit version: (\d+\.\d+\.\d+)', version.stderr)
    if match is None or match[1] != '1.34.2' or os.geteuid() == 0:
        _fail()
    state, temporary = root / 'unit-state', root / 'body-temp'
    state.mkdir(); temporary.mkdir()
    control = root / 'control.sock'
    # A private loopback listener, never a published Docker/host upload route.
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    log = root / 'unit.log'
    process = subprocess.Popen(['unitd', '--no-daemon', '--control', f'unix:{control}',
                                '--pid', str(root / 'unit.pid'), '--log', str(log),
                                '--state', str(state), '--tmp', str(temporary)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    try:
        for _ in range(100):
            if control.exists():
                break
            if process.poll() is not None:
                _fail()
            time.sleep(.05)
        config = {
            'settings': {'http': {'max_body_size': cap, 'body_buffer_size': cap,
                                  'body_temp_path': str(temporary)}},
            'listeners': {f'127.0.0.1:{port}': {'pass': 'applications/probe'}},
            'applications': {'probe': {'type': 'python', 'path': str(app_file.parent),
                                       'module': app_file.stem, 'callable': 'application',
                                       'processes': 1}},
        }
        connection = _UnixConnection(control)
        connection.request('PUT', '/config', json.dumps(config))
        response = connection.getresponse()
        if response.status != 200:
            _fail()
        response.read(); connection.close()

        def request(body):
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
            conn.request('POST', '/no-upload-route', body=body)
            reply = conn.getresponse()
            status = reply.status
            accepted = reply.getheader('X-Lane-Bytes')
            reply.read(); conn.close()
            return status, accepted

        if request(b'x') != (404, '1'):
            _fail()

        def snapshot():
            # Observe all children owned by this Unit tree, including router
            # descriptors whose files have already been unlinked.
            pids = {process.pid}
            for _ in range(4):
                for pid in tuple(pids):
                    children = Path(f'/proc/{pid}/task/{pid}/children').read_text()
                    pids.update(int(value) for value in children.split())
            regular = set()
            memory_probe = os.memfd_create('hh709-memory-device', os.MFD_CLOEXEC)
            try:
                memory_device = os.fstat(memory_probe).st_dev
            finally:
                os.close(memory_probe)
            routers = 0
            for pid in pids:
                command = Path(f'/proc/{pid}/cmdline').read_bytes()
                routers += b'unit: router' in command
                for fd in Path(f'/proc/{pid}/fd').iterdir():
                    try:
                        info = fd.stat()
                        target = os.readlink(fd)
                    except FileNotFoundError:
                        continue
                    if stat.S_ISREG(info.st_mode) and target != str(log):
                        # Kernel-created anonymous transport is not a durable
                        # spool. Identify it by both memfd name and a measured
                        # memfd device, never by nlink==0 alone (disk spools
                        # also have zero links).
                        if (target.startswith('/memfd:') and info.st_dev == memory_device
                                and info.st_nlink == 0):
                            continue
                        regular.add((info.st_dev, info.st_ino, info.st_nlink))
            if routers < 1:
                _fail()
            return regular, {p.name for p in temporary.iterdir()}, routers

        before, files, routers = snapshot()
        sentinel = b'HH709-UNIT-BODY-SENTINEL'
        with socket.create_connection(('127.0.0.1', port), timeout=10) as client:
            client.sendall(f'POST /no-upload-route HTTP/1.1\r\nHost: localhost\r\nContent-Length: {cap}\r\nConnection: close\r\n\r\n'.encode())
            first = sentinel + b'x' * (65536 - len(sentinel))
            client.sendall(first)
            for _ in range(5):
                time.sleep(.05)
                current, current_files, _ = snapshot()
                if current - before or current_files != files:
                    _fail()
            remaining = cap - len(first)
            while remaining:
                chunk = b'x' * min(65536, remaining)
                client.sendall(chunk)
                remaining -= len(chunk)
            response = http.client.HTTPResponse(client)
            response.begin()
            if response.status != 404 or response.getheader('X-Lane-Bytes') != str(cap):
                _fail()
            response.read()
        oversized = socket.create_connection(('127.0.0.1', port), timeout=5)
        try:
            oversized.sendall(f'POST /no-upload-route HTTP/1.1\r\nHost: localhost\r\nContent-Length: {cap + 1}\r\nConnection: close\r\n\r\n'.encode())
            response = http.client.HTTPResponse(oversized); response.begin()
            if response.status != 413:
                _fail()
            response.read()
        finally:
            oversized.close()
        with socket.create_connection(('127.0.0.1', port), timeout=5) as client:
            client.sendall(b'POST /no-upload-route HTTP/1.1\r\nHost: localhost\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n1\r\nx\r\n0\r\n\r\n')
            response = http.client.HTTPResponse(client); response.begin()
            if response.status != 411:
                _fail()
            response.read()
        after, after_files, _ = snapshot()
        if after - before or after_files != files or sentinel in log.read_bytes():
            _fail()
        return {'accepted_status': 404, 'accepted_bytes': cap, 'oversize_status': 413,
                'chunked_status': 411, 'router_processes_inspected': routers,
                'new_regular_descriptors': 0, 'body_temp_changes': 0,
                'inflight_samples': 5, 'log_sentinel_absent': True}
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=5)


class _LaneHarness:
    is_lane_only = True
    exposes_public_upload = False
    pinned_unit_version = '1.34.2'
    required_observations = _REQUIRED

    def __init__(self, config, *, artifact_dir):
        validate_deployment(config)
        self.config = config
        self.unit_route_cap_bytes = config.unit_route_cap_bytes
        self.root = Path(artifact_dir)
        self._files = ()
        self._expected = None

    def render(self):
        if self._files:
            return self._files
        run = uuid.uuid4().hex
        spec = self.root / f'{run}.json'
        app = self.root / f'probe_{run}.py'
        spec.write_text(json.dumps({'lane_only': True, 'unit_version': self.pinned_unit_version,
                                    'cap': self.unit_route_cap_bytes, 'uid': self.config.reaper_uid}))
        app.write_text('def application(environ, start_response):\n'
                       '    remaining = int(environ.get("CONTENT_LENGTH") or 0)\n'
                       '    total = 0\n'
                       '    while remaining:\n'
                       '        block = environ["wsgi.input"].read(min(remaining, 65536))\n'
                       '        if not block: break\n'
                       '        remaining -= len(block)\n'
                       '        total += len(block)\n'
                       '    start_response("404 Not Found", [("X-Lane-Bytes", str(total))])\n'
                       '    return [b"no public upload route"]\n')
        self._files = (spec, app)
        return self._files

    def _hash(self):
        try:
            return hashlib.sha256(b''.join(path.read_bytes() for path in self._files)).hexdigest()
        except OSError:
            _fail()

    def observe(self):
        if not self._files:
            _fail()
        external = _container_evidence(self.config.reaper_uid)
        with tempfile.TemporaryDirectory(prefix='hh709-unit-') as temp:
            try:
                unit = _unit_probe(Path(temp), self.unit_route_cap_bytes, self._files[1])
            except (OSError, ValueError, subprocess.SubprocessError):
                _fail()
        common = {'run_id': external['run_id'], 'artifacts_sha256': self._hash(),
                  'code_sha256': _code_digest()}
        observations = {name: _Observation(True, {**common, 'measurement': unit if name not in
                         ('uid_isolation', 'mount_isolation') else external}) for name in _REQUIRED}
        result = _Result(observations, self.pinned_unit_version)
        self._expected = json.dumps(dataclasses.asdict(result), sort_keys=True)
        self._observed_hash = self._hash()
        print('HH709_ADAPTER unit=1.34.2 uid=999 container_mounts=verified '
              'accepted=404 oversize=413 chunked=411 inflight_samples=5 '
              'new_body_files=0 new_regular_fds=0 scheduler=verified result=PASS', flush=True)
        return result

    def verify(self, result):
        try:
            if (not self._expected or self._hash() != self._observed_hash
                    or json.dumps(dataclasses.asdict(result), sort_keys=True) != self._expected):
                _fail()
        except (ValueError, TypeError, AttributeError):
            _fail()
