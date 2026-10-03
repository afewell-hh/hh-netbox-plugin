"""Isolated reaper configuration, scheduling and bounded aggregate health.

No request handler or Script entry point is registered. Filesystem preflight
never repairs operator configuration. Runtime mount verification is additional
to the declarative validation, not a substitute for it.
"""
from __future__ import annotations

import os
import json
import fcntl
import stat
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace


class DeploymentRejected(ValueError):
    """Fixed, non-sensitive preflight failure."""


class HarnessEvidenceMissing(ValueError):
    """A lane observation cannot be substantiated."""


_DEFAULTS = dict(max_raw_bytes=10485760, active_write_grace_seconds=300,
                 clock_skew_seconds=60, reaper_interval_seconds=3600,
                 orphan_bound_seconds=86400, body_buffer_size=10485760,
                 max_concurrent_bodies=8, capacity_budget_bytes=83886080)
_FORBIDDEN = ('media', 'static', 'scripts', 'reports', 'default_storage', 'ordinary_temp')


def _reject():
    raise DeploymentRejected('reaper deployment rejected') from None


def validate_deployment(config):
    """Read-only validation of paths, identity and the declared mount contract."""
    try:
        if any(type(getattr(config, name)) is not int or getattr(config, name) <= 0
               for name in _DEFAULTS if name != 'clock_skew_seconds'):
            _reject()
        if type(config.clock_skew_seconds) is not int or config.clock_skew_seconds < 0:
            _reject()
        if config.max_raw_bytes != config.unit_route_cap_bytes:
            _reject()
        from .raw_ingress_admission import ListenerPolicy
        ListenerPolicy(config.unit_route_cap_bytes, config.body_buffer_size,
                       config.max_concurrent_bodies, config.capacity_budget_bytes)
        if (config.orphan_bound_seconds - config.reaper_interval_seconds
                - config.clock_skew_seconds <= config.active_write_grace_seconds):
            _reject()
        if (type(config.reaper_uid) is not int or config.reaper_uid <= 0
                or config.web_uid != config.reaper_uid
                or config.reaper_uid != os.geteuid()):
            _reject()
        root = Path(config.quarantine_root)
        resolved = root.resolve(strict=True)
        if not root.is_absolute() or root != resolved:
            _reject()
        info = root.lstat()
        if (not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700
                or info.st_uid != config.reaper_uid):
            _reject()
        if (config.quarantine_mount_is_dedicated is not True
                or config.exposes_public_upload is not False
                or tuple(config.reaper_mounts) != (str(root),)):
            _reject()
        if set(config.forbidden_roots) != set(_FORBIDDEN):
            _reject()
        for value in config.forbidden_roots.values():
            forbidden = Path(value).resolve(strict=True)
            if root.is_relative_to(forbidden) or forbidden.is_relative_to(root):
                _reject()
    except (OSError, AttributeError, TypeError, ValueError):
        _reject()
    return True


class AdapterSpec:
    """Declarative spec, validated without mutating its deployment."""
    web_service_name = 'netbox'
    reaper_service_name = 'ingress-reaper'

    def __init__(self, config):
        validate_deployment(config)
        self.reaper_uid = config.reaper_uid
        self.quarantine_owner_uid = Path(config.quarantine_root).lstat().st_uid
        self.reaper_mount_points = tuple(config.reaper_mounts)


@dataclass(frozen=True)
class RunOutcome:
    started_at: int
    succeeded: bool


@dataclass(frozen=True)
class _Record:
    started_at: int
    succeeded: bool
    alerting: bool
    removed_count: int = 0
    oldest_orphan_seconds: int = 0
    incident_count: int = 0
    bound_exceeded_count: int = 0
    oldest_observed_seconds: int = 0


@dataclass(frozen=True)
class _Run:
    state: str
    alerting: bool
    record: _Record


@dataclass(frozen=True)
class _Health:
    alerting: bool
    seconds_since_success: int
    history: tuple[_Record, ...]
    history_limit: int


def _number(value):
    if type(value) is not int or value < 0:
        raise ValueError('invalid aggregate value')
    return value


def _record(outcome, report=None):
    if type(outcome.succeeded) is not bool:
        raise ValueError('invalid run outcome')
    args = dict(started_at=_number(outcome.started_at), succeeded=outcome.succeeded,
                alerting=not outcome.succeeded)
    if report is not None:
        # This property is the policy boundary. Never re-derive it from fields.
        alert = report.alert_required
        if type(alert) is not bool:
            raise ValueError('invalid report verdict')
        args['alerting'] |= alert
        args['removed_count'] = len(report.removed)
        for field in ('oldest_orphan_seconds', 'incident_count',
                      'bound_exceeded_count', 'oldest_observed_seconds'):
            args[field] = _number(getattr(report, field))
    return _Record(**args)


def _service_config(config):
    # The merged service expects these root names. The adapter rejects both
    # overlap directions before invoking it; no service semantics are changed.
    values = {name: getattr(config, name) for name in _DEFAULTS}
    values['quarantine_root'] = Path(config.quarantine_root)
    for name, value in config.forbidden_roots.items():
        values[name + '_root'] = Path(value)
    values['application_root'] = Path(__file__).resolve().parent
    return SimpleNamespace(**values)


_UNSUPPLIED = object()


def run_scheduled_reap(config, *, report=_UNSUPPLIED, missed=False, now=None):
    validate_deployment(config)
    now = int(time.time()) if now is None else _number(now)
    if missed:
        return _Run('missed', True, _record(RunOutcome(now, False)))
    if report is _UNSUPPLIED:
        from .secure_ingress import reap_orphans
        try:
            report = reap_orphans(config=_service_config(config), now=now)
        except Exception:
            # Never propagate filesystem names or a submitted exception string.
            return _Run('failed', True, _record(RunOutcome(now, False)))
    if report is None:
        return _Run('failed', True, _record(RunOutcome(now, False)))
    record = _record(RunOutcome(now, True), report)
    return _Run('completed', record.alerting, record)


def health_state(config, *, now, last_success_at, runs, last_report=None,
                 history_limit=24, previous=None):
    if type(history_limit) is not int or not 1 <= history_limit <= 128:
        raise ValueError('invalid history capacity')
    now = _number(now)
    unknown = last_success_at is None
    elapsed = 0 if unknown else now - _number(last_success_at)
    records = tuple(_record(run, last_report) for run in runs)
    history = (() if previous is None else tuple(previous.history)) + records
    history = history[-history_limit:]
    latest_bad = bool(history and (not history[-1].succeeded or history[-1].alerting))
    alert = (unknown or elapsed < 0 or
             elapsed > config.reaper_interval_seconds + config.clock_skew_seconds or latest_bad)
    return _Health(bool(alert), max(0, elapsed), history, history_limit)


def lane_harness_spec(config, *, artifact_dir):
    # Deferred import keeps operational reaping independent of lane tooling.
    from .reaper_lane import _LaneHarness as LaneHarness
    return LaneHarness(config, artifact_dir=artifact_dir)


class _StateStore:
    """One bounded atomic JSON document in a pre-created private state mount.

    Only aggregate records enter this store. No pickle, report repr, artifact
    names, caller metadata, exception text, or DB history is persisted.
    """
    def __init__(self, root):
        self.root = Path(root)
        try:
            info = self.root.lstat()
            if (not self.root.is_absolute() or self.root.resolve(strict=True) != self.root
                    or not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700
                    or info.st_uid != os.geteuid() or os.geteuid() == 0):
                _reject()
        except OSError:
            _reject()

    def _fd(self):
        return os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    @staticmethod
    def _validate(data):
        if type(data) is not dict or set(data) != {'version', 'last_success_at', 'next_due_at',
                                                  'in_progress', 'history', 'history_limit'}:
            _reject()
        if type(data['version']) is not int or data['version'] != 1:
            _reject()
        for key in ('last_success_at', 'next_due_at'):
            if data[key] is not None:
                _number(data[key])
        if type(data['in_progress']) is not bool:
            _reject()
        limit = data['history_limit']
        if type(limit) is not int or not 1 <= limit <= 128:
            _reject()
        if type(data['history']) is not list or len(data['history']) > limit:
            _reject()
        for record in data['history']:
            if type(record) is not dict or set(record) != set(_Record.__dataclass_fields__):
                _reject()
            for key, value in record.items():
                if key in ('succeeded', 'alerting'):
                    if type(value) is not bool:
                        _reject()
                else:
                    _number(value)
        return data

    def load(self):
        directory = self._fd()
        try:
            try:
                os.stat('health.pending', dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                # An interrupted atomic write is unresolved, never clean.
                # Leave the bounded artifact for operator inspection/recovery.
                _reject()
            try:
                fd = os.open('health.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=directory)
            except FileNotFoundError:
                return None
            with os.fdopen(fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                        or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600
                        or info.st_size > 65536):
                    _reject()
                raw = stream.read(65537)
            if len(raw) > 65536:
                _reject()
            return self._validate(json.loads(raw))
        except (OSError, ValueError, TypeError, KeyError):
            _reject()
        finally:
            os.close(directory)

    def save(self, data):
        self._validate(data)
        raw = json.dumps(data, separators=(',', ':'), sort_keys=True).encode()
        if len(raw) > 65536:
            _reject()
        directory = self._fd()
        name = 'health.pending'
        created = False
        try:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory)
            created = True
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, 'health.json', src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
        except OSError:
            _reject()
        finally:
            try:
                if created:
                    os.unlink(name, dir_fd=directory)
            except FileNotFoundError:
                pass
            os.close(directory)

    def lock(self):
        """Single runner lock; kernel releases it on abrupt process death."""
        directory = self._fd()
        try:
            fd = os.open('runner.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                         0o600, dir_fd=directory)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid():
                    _reject()
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return fd
            except (OSError, DeploymentRejected):
                os.close(fd)
                _reject()
        finally:
            os.close(directory)


class _Scheduler:
    """Injectable clock-driven scheduler; no sleeping is required to test time."""
    def __init__(self, config, store, *, history_limit=24):
        validate_deployment(config)
        if type(history_limit) is not int or not 1 <= history_limit <= 128:
            _reject()
        self.config, self.store, self.limit = config, store, history_limit

    def _data(self):
        return self.store.load() or dict(version=1, last_success_at=None, next_due_at=None,
                                         in_progress=False, history=[], history_limit=self.limit)

    def health(self, *, now):
        data = self._data()
        previous = _Health(False, 0, tuple(_Record(**row) for row in data['history']), self.limit)
        result = health_state(self.config, now=now, last_success_at=data['last_success_at'],
                              runs=(), previous=previous, history_limit=self.limit)
        if data['in_progress']:
            return _Health(True, result.seconds_since_success, result.history, result.history_limit)
        return result

    def tick(self, *, now):
        now = _number(now)
        data = self._data()
        if (not data['in_progress'] and data['next_due_at'] is not None
                and now < data['next_due_at']):
            return None
        data['in_progress'] = True
        self.store.save(data)
        result = run_scheduled_reap(self.config, now=now)
        data['in_progress'] = False
        data['next_due_at'] = now + self.config.reaper_interval_seconds
        if result.record.succeeded:
            data['last_success_at'] = now
        data['history_limit'] = self.limit
        data['history'] = (data['history'] + [asdict(result.record)])[-self.limit:]
        self.store.save(data)
        return self.health(now=now)


def _load_config(path):
    """Strict bounded operator configuration; never print its contents."""
    try:
        with open(path, 'rb') as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            _reject()
        data = json.loads(raw)
        required = {'quarantine_root', 'web_uid', 'reaper_uid', 'forbidden_roots',
                    'unit_route_cap_bytes'}
        optional = set(_DEFAULTS) | {'reaper_mounts', 'quarantine_mount_is_dedicated',
                                   'exposes_public_upload'}
        if type(data) is not dict or not required <= data.keys() or data.keys() - required - optional:
            _reject()
        values = {**_DEFAULTS, **data}
        values['quarantine_root'] = Path(values['quarantine_root'])
        values['forbidden_roots'] = {key: Path(value) for key, value in values['forbidden_roots'].items()}
        values.setdefault('reaper_mounts', (str(values['quarantine_root']),))
        values.setdefault('quarantine_mount_is_dedicated', True)
        values.setdefault('exposes_public_upload', False)
        config = SimpleNamespace(**values)
        validate_deployment(config)
        return config
    except (OSError, ValueError, TypeError, AttributeError):
        _reject()


def _validate_runtime(config, state_dir, config_file):
    """Inspect this execution namespace, not just the declared Q-only spec."""
    validate_deployment(config)
    state_dir, config_file = Path(state_dir), Path(config_file)
    _StateStore(state_dir)  # ownership/mode only; no file is written
    q = Path(config.quarantine_root)
    if (state_dir == q or state_dir.is_relative_to(q) or q.is_relative_to(state_dir)
            or not os.statvfs('/').f_flag & os.ST_RDONLY):
        _reject()
    allowed = {str(q): False, str(state_dir): False, str(config_file): True,
               '/opt/netbox/netbox/netbox_hedgehog': True, '/etc/netbox/config': True}
    seen = set()
    try:
        with open('/proc/self/mountinfo', encoding='utf-8') as stream:
            for line in stream:
                fields = line.split()
                mount = fields[4]
                if (mount == '/' or mount in ('/etc/hosts', '/etc/hostname', '/etc/resolv.conf')
                        or mount == '/proc' or mount.startswith('/proc/')
                        or mount == '/sys' or mount.startswith('/sys/')
                        or mount == '/dev' or mount.startswith('/dev/')):
                    continue
                if mount not in allowed:
                    _reject()
                readonly = 'ro' in fields[5].split(',')
                if readonly != allowed[mount]:
                    _reject()
                seen.add(mount)
    except (OSError, IndexError):
        _reject()
    if not {str(q), str(state_dir), str(config_file)} <= seen:
        _reject()
    return True
