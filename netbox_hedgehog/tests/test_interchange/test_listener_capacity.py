"""#709: admission belongs before Unit, not inside its application workers."""
import asyncio
import tempfile
import json
import subprocess
import sys
from pathlib import Path
from unittest import TestCase


class ListenerCapacityTests(TestCase):
    def test_real_unit_declared_length_spool_and_admission_matrix(self):
        probe = Path(__file__).with_name('unit_body_spool_probe.py')
        def run(*arguments):
            result = subprocess.run([sys.executable, '-m',
                                    'netbox_hedgehog.tests.test_interchange.unit_body_spool_probe',
                                    *arguments], cwd=probe.parents[3],
                                    capture_output=True, text=True, timeout=40)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        unsafe = run('--buffer-size', '1048576')
        self.assertGreater(unsafe['deleted_spool_inode_count'], 0)
        self.assertTrue(unsafe['request_sentinel_in_spool'])
        self.assertEqual(unsafe['spool_bytes'], 65536)
        self.assertTrue(any(row['st_dev'] == unsafe['temporary_st_dev']
                            and row['st_nlink'] == 0 and row['byte_count'] == 65536
                            for row in unsafe['regular_descriptors']))
        small = run('--buffer-size', '1048576', '--declared-size', '524288')
        protected = run('--buffer-size', '10485760', '--admission')
        for clean in (small, protected):
            self.assertEqual(clean['sent_bytes'], unsafe['sent_bytes'])
            self.assertEqual(clean['spool_inode_count'], 0)
            self.assertFalse(clean['request_sentinel_in_spool'])
        self.assertEqual(protected['declared_bytes'], 10485760)
        self.assertEqual(protected['admitted_bodies'], 8)
        self.assertEqual(protected['ninth_status'], 503)
        self.assertIs(protected['ninth_reached_unit'], False)
        print('HH709_ADMISSION unit=1.34.2 admitted=8 refused=1 '
              'refused_reached_unit=false inflight_disk_spools=0 '
              'declared_length_positive_control=PASS result=PASS', flush=True)

    def test_capacity_configuration(self):
        from netbox_hedgehog.raw_ingress_admission import ListenerPolicy
        policy = ListenerPolicy()
        self.assertEqual(policy.unit_http_settings(), {
            'max_body_size': 10485760, 'body_buffer_size': 10485760})
        self.assertEqual(policy.max_concurrent_bodies, 8)
        self.assertEqual(policy.capacity_budget_bytes, 83886080)
        for changes in ({'body_buffer_size': 10485759},
                        {'max_concurrent_bodies': 0},
                        {'max_concurrent_bodies': -1},
                        {'max_concurrent_bodies': True},
                        {'capacity_budget_bytes': 83886079}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                ListenerPolicy(**changes)
        custom = ListenerPolicy(max_body_size=1024, body_buffer_size=2048,
                                max_concurrent_bodies=2, capacity_budget_bytes=4096)
        self.assertEqual(custom.unit_http_settings()['body_buffer_size'], 2048)

    def test_eight_held_bodies_ninth_refused_without_upstream_admission(self):
        asyncio.run(self._capacity())

    async def _capacity(self):
        from netbox_hedgehog.raw_ingress_admission import AdmissionGate, ListenerPolicy
        with tempfile.TemporaryDirectory() as directory:
            upstream_path = str(Path(directory) / 'unit.sock')
            connections = []
            writers = []
            readers = []
            async def upstream(reader, writer):
                connections.append(writer)
                try:
                    await reader.readuntil(b'\r\n\r\n')
                    await reader.readexactly(1024)
                    writer.write(b'HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
                    await writer.drain()
                except asyncio.IncompleteReadError:
                    pass
                finally:
                    writer.close()
                    await writer.wait_closed()
            server = await asyncio.start_unix_server(upstream, upstream_path)
            gate = AdmissionGate(ListenerPolicy(max_body_size=1024,
                body_buffer_size=1024, capacity_budget_bytes=8192), upstream_path)
            front = await asyncio.start_unix_server(gate.connected, str(Path(directory) / 'gate.sock'))
            try:
                for _ in range(8):
                    reader, writer = await asyncio.open_unix_connection(str(Path(directory) / 'gate.sock'))
                    writers.append(writer)
                    readers.append(reader)
                    writer.write(b'POST /raw-ingress HTTP/1.1\r\nContent-Length: 1024\r\n\r\nx')
                    await writer.drain()
                for _ in range(100):
                    if len(connections) == 8:
                        break
                    await asyncio.sleep(.01)
                self.assertEqual(len(connections), 8)
                reader, writer = await asyncio.open_unix_connection(str(Path(directory) / 'gate.sock'))
                writers.append(writer)
                # The ninth is refused without even sending headers/body:
                # there is no ninth user-space body prefetch buffer.
                response = await asyncio.wait_for(reader.read(), 2)
                self.assertTrue(response.startswith(b'HTTP/1.1 503 '), response)
                self.assertEqual(len(connections), 8)
                self.assertEqual(gate.active_bodies, 8)
                # Completion releases exactly one slot. A permanently full
                # gate would satisfy refusal but is not a working controller.
                writers[0].write(b'x' * 1023)
                await writers[0].drain()
                completed = await asyncio.wait_for(readers[0].read(), 2)
                self.assertTrue(completed.startswith(b'HTTP/1.1 404 '))
                reader, writer = await asyncio.open_unix_connection(str(Path(directory) / 'gate.sock'))
                writers.append(writer)
                writer.write(b'POST /raw-ingress HTTP/1.1\r\nContent-Length: 1024\r\n\r\nx')
                await writer.drain()
                for _ in range(100):
                    if len(connections) == 9:
                        break
                    await asyncio.sleep(.01)
                self.assertEqual(len(connections), 9)
                self.assertEqual(gate.active_bodies, 8)
            finally:
                for writer in writers + connections:
                    writer.close()
                front.close()
                server.close()
                await front.wait_closed()
                await server.wait_closed()
                await asyncio.sleep(.05)
