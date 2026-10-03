"""Standalone, non-root Unit in-flight spool diagnostic; prints no body/path.

Run in the disposable pinned NetBox image, NOT against the shared listener.
The --buffer-size option is experimental evidence, not approved configuration.
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
import tempfile
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--buffer-size', type=int)
    args = parser.parse_args()
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
            config = {'settings': {'http': settings},
                      'listeners': {f'127.0.0.1:{port}': {'pass': 'applications/probe'}},
                      'applications': {'probe': {'type': 'python', 'path': str(root),
                                                'module': 'app', 'processes': 1}}}
            connection = http.client.HTTPConnection('localhost')
            connection.sock = socket.socket(socket.AF_UNIX)
            connection.sock.connect(str(control))
            connection.request('PUT', '/config', json.dumps(config))
            response = connection.getresponse()
            assert response.status == 200
            response.read(); connection.close()
            warmup = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
            warmup.request('POST', '/no-upload-route', b'x')
            response = warmup.getresponse()
            assert response.status == 404
            response.read(); warmup.close()
            sentinel = b'HH709-ONLY-GENERATED-PROBE-BYTES'
            with socket.create_connection(('127.0.0.1', port), timeout=10) as client:
                client.sendall(b'POST /no-upload-route HTTP/1.1\r\nHost: localhost\r\n'
                               b'Content-Length: 10485760\r\nConnection: close\r\n\r\n')
                client.sendall(sentinel + b'x' * (65536 - len(sentinel)))
                time.sleep(.25)
                pids = {process.pid}
                for _ in range(4):
                    for pid in tuple(pids):
                        pids.update(map(int, Path(f'/proc/{pid}/task/{pid}/children').read_text().split()))
                found = set()
                contains_sentinel = False
                sizes = []
                for pid in pids:
                    for fd in Path(f'/proc/{pid}/fd').iterdir():
                        try:
                            info = fd.stat()
                            target = os.readlink(fd)
                            if stat.S_ISREG(info.st_mode) and target.startswith(str(root / 'body-temp')):
                                with fd.open('rb') as stream:
                                    contains_sentinel |= sentinel in os.pread(stream.fileno(), 65536, 0)
                                found.add((info.st_dev, info.st_ino, info.st_nlink))
                                sizes.append(info.st_size)
                        except FileNotFoundError:
                            continue
                print(json.dumps({'unit': '1.34.2', 'uid': os.geteuid(),
                                  'cap': 10485760, 'body_buffer_size': args.buffer_size,
                                  'sent_bytes': 65536, 'unit_processes_inspected': len(pids),
                                  'directory_entry_count': len(list((root / 'body-temp').iterdir())),
                                  'spool_inode_count': len(found),
                                  'deleted_spool_inode_count': sum(item[2] == 0 for item in found),
                                  'spool_bytes': max(sizes, default=0),
                                  'request_sentinel_in_spool': contains_sentinel}, sort_keys=True))
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == '__main__':
    main()
