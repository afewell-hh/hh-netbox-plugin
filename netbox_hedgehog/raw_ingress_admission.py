"""Private reference capability, never registered as a NetBox/public route.

The sole admission owner must precede the isolated Unit Unix listener. Multiple
owners or a bypass listener invalidate the capacity claim. This is not a Unit
application-process limit and does not intercept unrelated NetBox traffic.
"""
from __future__ import annotations

import asyncio
import argparse
import fcntl
import json
import os
from pathlib import Path
import stat
from dataclasses import dataclass


@dataclass(frozen=True)
class ListenerPolicy:
    max_body_size: int = 10485760
    body_buffer_size: int = 10485760
    max_concurrent_bodies: int = 8
    capacity_budget_bytes: int = 83886080

    def __post_init__(self):
        values = (self.max_body_size, self.body_buffer_size,
                  self.max_concurrent_bodies, self.capacity_budget_bytes)
        if (any(type(value) is not int or value <= 0 for value in values)
                or self.body_buffer_size < self.max_body_size
                or self.body_buffer_size * self.max_concurrent_bodies > self.capacity_budget_bytes):
            raise ValueError('invalid isolated listener capacity')

    def unit_http_settings(self):
        return {'max_body_size': self.max_body_size,
                'body_buffer_size': self.body_buffer_size}


class AdmissionGate:
    """Single-event-loop admission before opening a Unit request connection.

Only the internal raw capability is accepted. No multipart, transfer encoding,
connection reuse, request logging or filesystem/body persistence is provided.
503 is an internal harness response, not a public API response contract.
The budget covers body buffering, not connection/HTTP/process overhead.
"""
    def __init__(self, policy, upstream_socket, *, timeout_seconds=60):
        if not isinstance(policy, ListenerPolicy) or timeout_seconds <= 0:
            raise ValueError('invalid isolated admission configuration')
        self.policy = policy
        self.upstream_socket = upstream_socket
        self.timeout_seconds = timeout_seconds
        self.active_bodies = 0

    def connected(self, reader, writer):
        # Synchronous connection callback: do not prefetch request/body bytes
        # into a StreamReader while waiting to decide admission. This endpoint
        # is exclusively the raw capability, not unrelated NetBox traffic.
        writer.transport.pause_reading()
        asyncio.create_task(self.handle(reader, writer))

    async def handle(self, reader, writer):
        admitted = False
        upstream = None
        try:
            async with asyncio.timeout(self.timeout_seconds):
                if self.active_bodies >= self.policy.max_concurrent_bodies:
                    await self._reject(writer, 503)
                    return
                self.active_bodies += 1
                admitted = True
                writer.transport.resume_reading()
                # Read bounded headers only. Never forward client-supplied
                # headers: this internal contract deliberately has no framing
                # ambiguity, credentials, filename or logging metadata.
                header = await reader.readuntil(b'\r\n\r\n')
                if len(header) > 8192:
                    await self._reject(writer, 400)
                    return
                lines = header[:-4].split(b'\r\n')
                if lines.pop(0) != b'POST /raw-ingress HTTP/1.1':
                    await self._reject(writer, 404)
                    return
                lengths = []
                for line in lines:
                    name, separator, value = line.partition(b':')
                    if not separator or name.lower() not in (b'host', b'content-length', b'connection', b'accept-encoding'):
                        await self._reject(writer, 400)
                        return
                    if name.lower() == b'content-length':
                        lengths.append(value.strip())
                if len(lengths) != 1 or not lengths[0].isdigit() or len(lengths[0]) > 20:
                    await self._reject(writer, 411)
                    return
                length = int(lengths[0])
                if length > self.policy.max_body_size:
                    await self._reject(writer, 413)
                    return
                response, upstream = await asyncio.open_unix_connection(self.upstream_socket)
                upstream.write(b'POST /raw-ingress HTTP/1.1\r\nHost: isolated\r\n'
                               + f'Content-Length: {length}\r\nConnection: close\r\n\r\n'.encode('ascii'))
                await upstream.drain()
                while length:
                    block = await reader.read(min(length, 65536))
                    if not block:
                        return
                    upstream.write(block)
                    await upstream.drain()
                    length -= len(block)
                while block := await response.read(65536):
                    writer.write(block)
                    await writer.drain()
        except (OSError, TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            # Deliberately no exception/body/header rendering or logging.
            pass
        finally:
            if upstream is not None:
                upstream.close()
                try:
                    await upstream.wait_closed()
                except OSError:
                    pass
            if admitted:
                self.active_bodies -= 1
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    @staticmethod
    async def _reject(writer, status):
        writer.write(f'HTTP/1.1 {status} Rejected\r\nContent-Length: 0\r\nConnection: close\r\n\r\n'.encode('ascii'))
        await writer.drain()


def main():
    """Reference-only Unix endpoint; no TCP bind or public route registration."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--socket', required=True)
    parser.add_argument('--upstream-socket', required=True)
    args = parser.parse_args()
    with open(args.config, 'rb') as stream:
        encoded = stream.read(65537)
    if len(encoded) > 65536:
        raise ValueError('invalid isolated listener configuration')
    config = json.loads(encoded)
    policy = ListenerPolicy(config['unit_route_cap_bytes'], config['body_buffer_size'],
                            config['max_concurrent_bodies'], config['capacity_budget_bytes'])
    path = Path(args.socket)
    info = path.parent.lstat()
    if (os.geteuid() == 0 or not path.is_absolute()
            or path.parent.resolve(strict=True) != path.parent
            or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700 or path.exists() or path.is_symlink()):
        raise ValueError('unsafe isolated admission endpoint')
    # Retain lock for the entire owner lifetime, including startup. A second
    # worker must fail rather than silently double the configured capacity.
    descriptor = os.open(path.parent / 'admission.lock',
                         os.O_CREAT | os.O_NOFOLLOW | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        async def serve():
            gate = AdmissionGate(policy, args.upstream_socket)
            server = await asyncio.start_unix_server(gate.connected, str(path), limit=8192)
            async with server:
                await server.serve_forever()
        asyncio.run(serve())
    finally:
        os.close(descriptor)


if __name__ == '__main__':
    main()
