"""Run only inside the disposable isolated-listener reference container."""
import http.client
import json
import os
from pathlib import Path
import socket
import stat
import time


def run():
    root = Path('/run/hnp-listener')
    for _ in range(100):
        if (root / 'admission.sock').exists():
            break
        time.sleep(.05)
    def control(path):
        connection = http.client.HTTPConnection('localhost', timeout=5)
        connection.sock = socket.socket(socket.AF_UNIX)
        connection.sock.settimeout(5)
        connection.sock.connect(str(root / 'control.sock'))
        connection.request('GET', path)
        response = connection.getresponse()
        assert response.status == 200
        value = json.loads(response.read())
        connection.close()
        return value
    config = control('/config')
    assert config['settings']['http'] == {'max_body_size': 10485760, 'body_buffer_size': 10485760}
    assert list(config['listeners']) == ['unix:/run/hnp-listener/unit.sock']
    assert 'processes' not in config['applications']['raw-capability']
    assert os.geteuid() == 999
    assert not Path('/secure-quarantine').exists()
    clients = []
    sentinel = b'HH709-GENERATED-CONTAINER-PROBE'
    baseline = control('/status')['requests']['total']
    def connect():
        client = socket.socket(socket.AF_UNIX)
        client.settimeout(5)
        client.connect(str(root / 'admission.sock'))
        return client
    try:
        for _ in range(8):
            client = connect()
            clients.append(client)
            client.sendall(b'POST /raw-ingress HTTP/1.1\r\nContent-Length: 10485760\r\n\r\n'
                           + sentinel + b'x' * (65536 - len(sentinel)))
        for _ in range(100):
            if control('/status')['requests']['total'] == baseline + 8:
                break
            time.sleep(.05)
        assert control('/status')['requests']['total'] == baseline + 8
        with connect() as ninth:
            response = http.client.HTTPResponse(ninth)
            response.begin()
            assert response.status == 503
            response.read()
        assert control('/status')['requests']['total'] == baseline + 8
        device = root.stat().st_dev
        rows = {}
        inspected = 0
        for process in Path('/proc').iterdir():
            if not process.name.isdigit():
                continue
            try:
                if not (process / 'cmdline').read_bytes().startswith((b'unit:', b'unitd')):
                    continue
                inspected += 1
                for fd in (process / 'fd').iterdir():
                    try:
                        info = fd.stat()
                        if stat.S_ISREG(info.st_mode) and info.st_dev == device:
                            with fd.open('rb') as stream:
                                found = sentinel in os.pread(stream.fileno(), 65536, 0)
                            rows[(info.st_dev, info.st_ino)] = dict(
                                st_dev=info.st_dev, st_nlink=info.st_nlink,
                                byte_count=info.st_size, sentinel_found=found)
                            assert not found
                            assert info.st_nlink != 0
                    except FileNotFoundError:
                        continue
            except FileNotFoundError:
                continue
        assert inspected >= 3
        print(json.dumps(dict(uid=os.geteuid(), admitted=8, refused=1,
            refused_reached_unit=False, unit_processes_inspected=inspected,
            temp_st_dev=device, filesystem_descriptors=list(rows.values()),
            spool_sentinel_absent=True, q_mounted=False, public_listener=False)))
    finally:
        for client in clients:
            client.close()


if __name__ == '__main__':
    run()
