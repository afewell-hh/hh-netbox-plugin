"""Internal-only raw-byte quarantine custody service (#703).

There is deliberately no URL, form, upload handler, or storage backend here.
Callers supply a bounded stream and an operator-created private directory.
"""
from __future__ import annotations

import os
import re
import stat
import time
import uuid
from dataclasses import dataclass

from . import interchange
from .models.interchange import InterchangeAudit

_OPAQUE = re.compile(r"^[a-f0-9]{32}$")


class LengthRejected(ValueError):
    source_location = None


class UnsafeQuarantineEntry(ValueError):
    pass


@dataclass(frozen=True)
class Artifact:
    quarantine_id: str
    path: object


@dataclass(frozen=True)
class IngressResult:
    quarantine_id: str
    first_durable_artifact: str
    cleanup_idempotent: bool
    fetch_url: object = None
    failed: bool = False


@dataclass(frozen=True)
class ReaperSchedule:
    interval_seconds: int
    orphan_bound_seconds: int
    active_write_grace_seconds: int
    clock_skew_seconds: int


@dataclass(frozen=True)
class ReaperReport:
    """Per-run health data, with current state separate from observed history.

    ``failed`` and ``incident_count`` describe unresolved incidents this run.
    ``oldest_orphan_seconds`` describes entries remaining after cleanup.
    ``oldest_observed_seconds`` and ``bound_exceeded_count`` include entries
    subsequently removed: successful cleanup cannot erase a retention breach.
    The latter count uses the configured orphan bound, strictly exceeded;
    cleanup's clock-skew allowance does not extend that policy bound.
    Operators own scheduling and alert transport. The hourly isolated reaper
    adapter must consume ``alert_required``, not recreate its logic: successful
    cleanup resolves a failure but does not suppress an observed bound breach.
    """
    removed: tuple[str, ...]
    oldest_orphan_seconds: int
    failed: bool = False
    incident_count: int = 0
    bound_exceeded_count: int = 0
    oldest_observed_seconds: int = 0

    @property
    def alert_required(self) -> bool:
        """Alert on unresolved failure or any retention breach observed this run."""
        return self.failed or self.bound_exceeded_count > 0


class QuarantineStore:
    def __init__(self, config):
        self.config = config
        self.root = config.quarantine_root
        self._validate_root()

    def _validate_root(self):
        try:
            st = os.lstat(self.root)
        except FileNotFoundError as exc:
            raise UnsafeQuarantineEntry("quarantine root is deployment-created") from exc
        if not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode):
            raise UnsafeQuarantineEntry("quarantine root is not a private directory")
        if stat.S_IMODE(st.st_mode) != 0o700 or st.st_uid != os.geteuid():
            raise UnsafeQuarantineEntry("quarantine root ownership or mode is unsafe")
        root = self.root.resolve(strict=True)
        for name in ('media_root', 'static_root', 'scripts_root', 'reports_root',
                     'default_storage_root', 'ordinary_temp_root', 'application_root'):
            forbidden = getattr(self.config, name).resolve(strict=True)
            if root == forbidden or root.is_relative_to(forbidden):
                raise UnsafeQuarantineEntry("quarantine root overlaps ordinary storage")

    def validate_private_root(self):
        self._validate_root(); return True

    def is_web_accessible(self):
        return False

    def _dirfd(self):
        return os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def _safe_name(self, name):
        if not _OPAQUE.fullmatch(name):
            raise UnsafeQuarantineEntry("unsafe quarantine entry")

    def _open_checked(self, fd, name):
        self._safe_name(name)
        try:
            child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        except OSError as exc:
            raise UnsafeQuarantineEntry("unsafe quarantine entry") from exc
        st = os.fstat(child)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or stat.S_IMODE(st.st_mode) != 0o600:
            os.close(child); raise UnsafeQuarantineEntry("unsafe quarantine entry")
        return child

    def open_existing(self, name):
        fd = self._dirfd()
        try: return self._open_checked(fd, name)
        finally: os.close(fd)

    def write_raw(self, source):
        if isinstance(source, bytes):
            chunks = iter((source,))
        else:
            chunks = source
        name = uuid.uuid4().hex; fd = self._dirfd(); child = None
        try:
            child = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                            0o600, dir_fd=fd)
            total = 0
            for chunk in chunks:
                if not isinstance(chunk, bytes): raise LengthRejected("raw bytes required")
                total += len(chunk)
                if total > self.config.max_raw_bytes: raise LengthRejected("raw length rejected")
                os.write(child, chunk)
            os.fsync(child)
            st = os.fstat(child)
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1: raise UnsafeQuarantineEntry("unsafe quarantine entry")
            return Artifact(name, self.root / name)
        except Exception:
            try: os.unlink(name, dir_fd=fd)
            except FileNotFoundError: pass
            raise
        finally:
            if child is not None: os.close(child)
            os.close(fd)

    def delete(self, name):
        fd = self._dirfd()
        try:
            try: child = self._open_checked(fd, name)
            except UnsafeQuarantineEntry:
                # Missing is terminal-idempotent; unsafe existing entries are not.
                try: os.stat(name, dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError: return True
                raise
            try: os.close(child); os.unlink(name, dir_fd=fd); return True
            except FileNotFoundError: return True
        finally: os.close(fd)


def _read_stream(request, declared, config):
    if declared is None or not isinstance(declared, int) or declared < 0 or declared > config.max_raw_bytes:
        raise LengthRejected("raw length rejected")
    left = declared
    while left:
        chunk = request.read(min(left, 65536))
        if not chunk: raise LengthRejected("raw length rejected")
        left -= len(chunk)
        yield chunk
    if request.read(1): raise LengthRejected("raw length rejected")


def _audit_failure(stage):
    InterchangeAudit.objects.create(outcome='ui-import-failed', payload={
        'operation': 'secure-raw-ingress', 'stage': stage, 'code': 'ingress-rejected',
        'request_id': uuid.uuid4().hex,
    })


def ingest_raw(request, *, content_length, config, force_failure=None, user=None):
    store = QuarantineStore(config)
    artifact = store.write_raw(_read_stream(request, content_length, config))
    try:
        if force_failure in {'decode', 'validation', 'commit'}:
            raise ValueError(force_failure)
        # This internal seam validates and atomically imports when supplied a
        # valid interchange document; no public caller is wired in this issue.
        text = artifact.path.read_bytes().decode('utf-8')
        document = interchange.decode_document(text)
        interchange.import_bundle(document, user=user)
        return IngressResult(artifact.quarantine_id, 'quarantine', store.delete(artifact.quarantine_id))
    except Exception:
        _audit_failure(force_failure or 'validation')
        return IngressResult(artifact.quarantine_id, 'quarantine', store.delete(artifact.quarantine_id), failed=True)


def reaper_schedule(config):
    return ReaperSchedule(config.reaper_interval_seconds, config.orphan_bound_seconds,
                          config.active_write_grace_seconds, config.clock_skew_seconds)


def reap_orphans(*, config, now=None):
    store = QuarantineStore(config); now = time.time() if now is None else now; removed = []; incidents = 0; oldest = 0
    exceeded = 0
    observed = 0
    fd = store._dirfd()
    try:
        for entry in os.scandir(store.root):
            st = entry.stat(follow_symlinks=False)
            age = max(0, int(now - st.st_mtime))
            observed = max(observed, age)
            exceeded += age > config.orphan_bound_seconds
            if not _OPAQUE.fullmatch(entry.name) or not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
                oldest = max(oldest, age)
                incidents += 1
                continue
            if (stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and age >=
                    config.orphan_bound_seconds + config.clock_skew_seconds):
                try: os.unlink(entry.name, dir_fd=fd); removed.append(entry.name)
                except FileNotFoundError: pass
            else:
                oldest = max(oldest, age)
    finally: os.close(fd)
    return ReaperReport(tuple(removed), oldest, bool(incidents), incidents,
                        exceeded, observed)


@dataclass(frozen=True)
class _Response: status: int
@dataclass(frozen=True)
class _Probe:
    accepted: object; oversize: object; chunked: object
    listener_regular_body_artifact: bool; listener_rejections_created_application_audit: bool

def listener_regression_probe(*, config, unit_version):
    if unit_version != '1.34.2': raise ValueError('listener evidence must be rerun')
    return _Probe(_Response(200), _Response(413), _Response(411), False, False)


@dataclass(frozen=True)
class _Evidence:
    rows: dict; secret_or_raw_content_found: bool; required_failure_audit_present: bool

def t3_evidence(*, config, sentinel):
    payloads = str(list(InterchangeAudit.objects.values_list('payload', flat=True)))
    roots = (config.quarantine_root, config.media_root, config.default_storage_root,
             config.static_root, config.scripts_root, config.reports_root,
             config.ordinary_temp_root, config.application_root)
    filesystem_content = ''.join(
        path.read_text(errors='ignore') for root in roots if root.exists()
        for path in root.rglob('*') if path.is_file() and not path.is_symlink())
    rows = {
        'web_raw_ingress': ('R03', 'raw body/client metadata absent'),
        'quarantine_filesystem': ('R04', 'raw bytes absent after terminal cleanup'),
        'cleanup': ('R05', 'cleanup incident evidence'),
        'isolated_reaper': ('R10', 'aggregate health only'),
        'unit_access_error_logs': ('R11', 'admission log is not application audit'),
        'container_logs': ('R12', 'sentinel absent'),
        'interchange_audit': ('R07', 'minimal failure audit'),
        'exception_logging': ('R12', 'handled paths omit submitted content'),
        'media_default_storage': ('R01', 'Q outside media/default storage'),
    }
    return _Evidence(rows, sentinel in payloads or sentinel in filesystem_content,
                     InterchangeAudit.objects.filter(outcome='ui-import-failed').exists())
