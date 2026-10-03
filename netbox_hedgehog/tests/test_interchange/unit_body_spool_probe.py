"""Standalone, non-root Unit in-flight spool diagnostic; prints no body/path.

Run in the disposable pinned NetBox image, NOT against the shared listener.
The buffer/declaration options exercise both approved and deliberately unsafe
controls in a disposable listener, never the shared listener.
"""
import argparse
import http.client
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import tempfile
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--buffer-size', type=int)
    parser.add_argument('--declared-size', type=int, default=10485760)
    parser.add_argument('--sent-size', type=int, default=65536)
    parser.add_argument('--admission', action='store_true')
    args = parser.parse_args()
    assert 64 <= args.sent_size < args.declared_size <= 10485760
    assert os.geteuid() != 0
    version = subprocess.run(['unitd', '--version'], capture_output=True, text=True, check=True)
    assert 'unit version: 1.34.2' in version.stderr
    with tempfile.TemporaryDirectory(prefix='hh709-spool-probe-') as temporary:
        root = Path(temporary)
        for name in ('state', 'body-temp'):
            (root / name).mkdir()
        (root / 'app.py').write_text(
            'def application(environ, start_response):\n'
            '    left = int(environ.get("CONTENT_LENGTH") or 0)\n'
            '    while left:\n'
            '        block = environ["wsgi.input"].read(min(left, 65536))\n'
            '        if not block: break\n'
            '        left -= len(block)\n'
            '    start_response("404 Not Found", [])\n'
            '    return [b"no upload route"]\n')
        with socket.socket() as reserved:
            reserved.bind(('127.0.0.1', 0))
            port = reserved.getsockname()[1]
        control = root / 'control.sock'
        unit_socket = root / 'unit.sock'
        gate_socket = root / 'admission.sock'
        gate = None
        held = []
        process = subprocess.Popen(
            ['unitd', '--no-daemon', '--control', f'unix:{control}',
             '--state', str(root / 'state'), '--tmp', str(root / 'body-temp'),
             '--pid', str(root / 'unit.pid'), '--log', str(root / 'unit.log')],
            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                if control.exists(): break
                assert process.poll() is None
                time.sleep(.05)
            settings = {'max_body_size': 10485760}
            if args.buffer_size is not None:
                settings['body_buffer_size'] = args.buffer_size
            listener = f'unix:{unit_socket}' if args.admission else f'127.0.0.1:{port}'
            config = {'settings': {'http': settings},
                      'listeners': {listener: {'pass': 'applications/probe'}},
                      'applications': {'probe': {'type': 'python', 'path': str(root),
                                                'module': 'app', 'processes': 1}}}
            if args.admission:
                from netbox_hedgehog.raw_ingress_admission import ListenerPolicy
                from netbox_hedgehog.reference_listener import unit_configuration
                config = unit_configuration(ListenerPolicy(), unit_socket, root, 'app')
            connection = http.client.HTTPConnection('localhost')
            connection.sock = socket.socket(socket.AF_UNIX)
            connection.sock.connect(str(control))
            connection.request('PUT', '/config', json.dumps(config))
            response = connection.getresponse()
            assert response.status == 200
            response.read(); connection.close()
            if args.admission:
                assert args.buffer_size == 10485760
                policy = root / 'listener.json'
                policy.write_text(json.dumps({'unit_route_cap_bytes': 10485760,
                    'body_buffer_size': args.buffer_size, 'max_concurrent_bodies': 8,
                    'capacity_budget_bytes': 83886080}))
                gate = subprocess.Popen([sys.executable, '-m', 'netbox_hedgehog.raw_ingress_admission',
                    '--config', str(policy), '--socket', str(gate_socket),
                    '--upstream-socket', str(unit_socket)], stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE)
                for _ in range(100):
                    if gate_socket.exists(): break
                    assert gate.poll() is None, 'admission process failed'
                    time.sleep(.05)
            warmup = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
            if args.admission:
                warmup.sock = socket.socket(socket.AF_UNIX)
                warmup.sock.settimeout(10)
                warmup.sock.connect(str(gate_socket))
            warmup.request('POST', '/raw-ingress' if args.admission else '/no-upload-route', b'x')
            response = warmup.getresponse()
            assert response.status == 404
            response.read(); warmup.close()
            sentinel = b'HH709-ONLY-GENERATED-PROBE-BYTES'
            def connect():
                if args.admission:
                    client = socket.socket(socket.AF_UNIX)
                    client.settimeout(10)
                    client.connect(str(gate_socket))
                    return client
                return socket.create_connection(('127.0.0.1', port), timeout=10)

            def send_partial(client):
                route = b'/raw-ingress' if args.admission else b'/no-upload-route'
                client.sendall(b'POST ' + route + b' HTTP/1.1\r\nHost: localhost\r\n'
                               + f'Content-Length: {args.declared_size}\r\nConnection: close\r\n\r\n'.encode())
                client.sendall(sentinel + b'x' * (args.sent_size - len(sentinel)))

            def unit_requests():
                connection = http.client.HTTPConnection('localhost')
                connection.sock = socket.socket(socket.AF_UNIX)
                connection.sock.connect(str(control))
                connection.request('GET', '/status')
                reply = connection.getresponse()
                assert reply.status == 200
                status = json.loads(reply.read())
                connection.close()
                return status['requests']['total']

            with connect() as client:
                baseline = unit_requests()
                send_partial(client)
                ninth_status = None
                if args.admission:
                    for _ in range(7):
                        extra = connect()
                        held.append(extra)
                        send_partial(extra)
                    for _ in range(100):
                        if unit_requests() == baseline + 8: break
                        time.sleep(.05)
                    assert unit_requests() == baseline + 8
                    with connect() as ninth:
                        rejected = http.client.HTTPResponse(ninth)
                        rejected.begin()
                        ninth_status = rejected.status
                        assert ninth_status == 503
                        rejected.read()
                    assert unit_requests() == baseline + 8, 'refused body reached Unit'
                time.sleep(.25)
                pids = {process.pid}
                for _ in range(4):
                    for pid in tuple(pids):
                        pids.update(map(int, Path(f'/proc/{pid}/task/{pid}/children').read_text().split()))
                found = set()
                contains_sentinel = False
                sizes = []
                descriptors = {}
                temporary_device = (root / 'body-temp').stat().st_dev
                for pid in pids:
                    for fd in Path(f'/proc/{pid}/fd').iterdir():
                        try:
                            info = fd.stat()
                            target = os.readlink(fd)
                            # Inspect disk-backed open/deleted files, not only
                            # visible names. Unit transport memfds have a
                            # different device; report them separately below.
                            if stat.S_ISREG(info.st_mode):
                                descriptors[(info.st_dev, info.st_ino)] = {
                                    'st_dev': info.st_dev, 'st_nlink': info.st_nlink,
                                    'byte_count': info.st_size,
                                    'temp_filesystem': info.st_dev == temporary_device,
                                    'deleted': info.st_nlink == 0}
                            if (stat.S_ISREG(info.st_mode)
                                    and info.st_dev == temporary_device
                                    and (info.st_nlink == 0 or target.startswith(str(root / 'body-temp')))):
                                with fd.open('rb') as stream:
                                    contains_sentinel |= sentinel in os.pread(stream.fileno(), 65536, 0)
                                found.add((info.st_dev, info.st_ino, info.st_nlink))
                                sizes.append(info.st_size)
                        except FileNotFoundError:
                            continue
                print(json.dumps({'unit': '1.34.2', 'uid': os.geteuid(),
                                  'cap': 10485760, 'body_buffer_size': args.buffer_size,
                                  'declared_bytes': args.declared_size,
                                  'admitted_bodies': 8 if args.admission else 1,
                                  'ninth_status': ninth_status,
                                  'ninth_reached_unit': False if args.admission else None,
                                  'sent_bytes': args.sent_size, 'unit_processes_inspected': len(pids),
                                  'temporary_st_dev': temporary_device,
                                  'regular_descriptors': list(descriptors.values()),
                                  'directory_entry_count': len(list((root / 'body-temp').iterdir())),
                                  'spool_inode_count': len(found),
                                  'deleted_spool_inode_count': sum(item[2] == 0 for item in found),
                                  'spool_bytes': max(sizes, default=0),
                                  'request_sentinel_in_spool': contains_sentinel}, sort_keys=True))
        finally:
            for client in held:
                client.close()
            if gate is not None:
                gate.terminate()
                gate.wait(timeout=10)
            process.terminate()
            process.wait(timeout=10)


if __name__ == '__main__':
    main()
