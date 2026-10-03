"""Opt-in isolated Unix listener; not the generic NetBox listener.

No TCP port is opened. The private admission socket is the only ingress to
this profile; the Unit socket/control live in its unshared private tmpfs.
The existing NetBox WSGI application has no upload route. Wiring a public
caller or a new upload application remains outside this adapter's scope.
"""
import argparse
import asyncio
import http.client
import json
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess

from .raw_ingress_admission import AdmissionGate, ListenerPolicy


def unit_configuration(policy, socket_path, application_path, module):
    return {
        'settings': {'http': policy.unit_http_settings()},
        'listeners': {f'unix:{socket_path}': {'pass': 'applications/raw-capability'}},
        # No process cap: body concurrency is controlled before Unit.
        'applications': {'raw-capability': {
            'type': 'python', 'path': str(application_path), 'module': module,
            'callable': 'application'}},
    }


async def serve(policy, runtime, *, application_path='/opt/netbox/netbox', module='netbox.wsgi'):
    runtime = Path(runtime)
    info = runtime.lstat()
    if (os.geteuid() == 0 or not runtime.is_absolute()
            or runtime.resolve(strict=True) != runtime or info.st_uid != os.geteuid()
            or not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700
            or any(runtime.iterdir())):
        raise ValueError('unsafe isolated listener runtime')
    # An empty private ephemeral mount makes startup exclusive/fail-closed.
    # No repair, stale socket deletion, or persistent raw body directory.
    state = runtime / 'state'
    state.mkdir(mode=0o700)
    control, backend, front = (runtime / name for name in ('control.sock', 'unit.sock', 'admission.sock'))
    version = subprocess.run(['unitd', '--version'], capture_output=True, text=True, check=True)
    if 'unit version: 1.34.2' not in version.stderr:
        raise ValueError('unsupported isolated Unit version')
    unit = subprocess.Popen(['unitd', '--no-daemon', '--control', f'unix:{control}',
        '--state', str(state), '--tmp', str(runtime), '--pid', str(runtime / 'unit.pid'),
        '--log', '/dev/stderr'], env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
        stdout=subprocess.DEVNULL)
    try:
        for _ in range(100):
            if control.exists():
                break
            if unit.poll() is not None:
                raise ValueError('isolated Unit startup failed')
            await asyncio.sleep(.05)
        connection = http.client.HTTPConnection('localhost', timeout=5)
        connection.sock = socket.socket(socket.AF_UNIX)
        connection.sock.settimeout(5)
        connection.sock.connect(str(control))
        connection.request('PUT', '/config', json.dumps(unit_configuration(
            policy, backend, application_path, module)))
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError('isolated Unit configuration rejected')
        response.read()
        connection.close()
        gate = AdmissionGate(policy, str(backend))
        server = await asyncio.start_unix_server(gate.connected, str(front), limit=8192)
        async with server:
            while unit.poll() is None:
                await asyncio.sleep(.25)
            raise ValueError('isolated Unit stopped')
    finally:
        if unit.poll() is None:
            unit.terminate()
        unit.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--runtime', default='/run/hnp-listener')
    args = parser.parse_args()
    with open(args.config, 'rb') as stream:
        encoded = stream.read(65537)
    if len(encoded) > 65536:
        raise ValueError('invalid isolated listener configuration')
    data = json.loads(encoded)
    if data['unit_route_cap_bytes'] != data['max_raw_bytes']:
        raise ValueError('isolated listener cap mismatch')
    policy = ListenerPolicy(data['unit_route_cap_bytes'], data['body_buffer_size'],
                            data['max_concurrent_bodies'], data['capacity_budget_bytes'])
    async def run():
        task = asyncio.current_task()
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, task.cancel)
        await serve(policy, args.runtime)
    try:
        asyncio.run(run())
    except asyncio.CancelledError:
        pass


if __name__ == '__main__':
    main()
