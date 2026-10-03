"""Executed inside the reference reaper container by the host evidence runner.

No web service or database calls. Real files and persisted scheduler state are
used, with deterministic timestamps to exercise the approved hourly cadence.
Only a bounded, aggregate record is printed.
"""
import json
import os
from pathlib import Path

from netbox_hedgehog import reaper_adapter as adapter
from netbox_hedgehog.reaper_lane import _code_digest


def run():
    config = adapter._load_config('/etc/hnp-reaper.json')
    adapter._validate_runtime(config, '/reaper-state', '/etc/hnp-reaper.json')
    q = Path('/secure-quarantine')
    state_root = Path('/reaper-state')
    store = adapter._StateStore(state_root)
    scheduler = adapter._Scheduler(config, store)
    assert config.reaper_interval_seconds == 3600
    payload = 'HH709-LANE-PAYLOAD-NEVER-LOG'
    artifact = q / ('d' * 32)
    artifact.write_text(payload)
    artifact.chmod(0o600)
    os.utime(artifact, (100, 100))
    state = scheduler.tick(now=108100)
    assert not artifact.exists()
    assert state.alerting and state.history[-1].bound_exceeded_count == 1
    assert state.history[-1].succeeded
    assert scheduler.tick(now=108101) is None
    assert not scheduler.tick(now=111700).alerting
    unsafe = q / 'unsafe-entry'
    unsafe.write_text(payload)
    assert scheduler.tick(now=115300).alerting
    assert scheduler.health(now=115301).alerting
    unsafe.unlink()
    assert not scheduler.tick(now=118900).alerting
    assert scheduler.health(now=122561).alerting  # first missed cadence + skew
    assert not scheduler.tick(now=122561).alerting
    for index in range(30):
        assert not scheduler.tick(now=126161 + index * 3600).alerting
    raw = (state_root / 'health.json').read_text()
    assert len(json.loads(raw)['history']) == 24
    assert payload not in raw and str(q) not in raw and 'd' * 32 not in raw
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    assert int(status['CapEff'].strip(), 16) == 0
    assert status['NoNewPrivs'].strip() == '1'
    evidence = {
        'code_sha256': _code_digest(), 'uid': os.geteuid(),
        'q_owner_uid': q.stat().st_uid, 'q_mode': q.stat().st_mode & 0o777,
        'root_readonly': bool(os.statvfs('/').f_flag & os.ST_RDONLY),
        'effective_capabilities': int(status['CapEff'].strip(), 16),
        'no_new_privileges': status['NoNewPrivs'].strip() == '1',
        'scheduler': {'interval_seconds': 3600, 'real_reap': True, 'first_failure': True,
                      'missed': True, 'recovery': True, 'bounded': True, 'secret_absent': True},
    }
    # Remove only this probe's safe state file; the real-clock daemon experiment
    # starts with a fresh clock domain. Never enumerate/delete Q as cleanup.
    (state_root / 'health.json').unlink()
    print('HH709_CONTAINER ' + json.dumps(evidence, sort_keys=True))
