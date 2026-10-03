"""Dedicated non-root container runner; no RQ/Script registration."""
import json
import os
import time

from django.core.management.base import BaseCommand, CommandError

from netbox_hedgehog import reaper_adapter as adapter


class Command(BaseCommand):
    help = 'Run the isolated hourly quarantine reaper or inspect its bounded health state.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--config', required=True)
        parser.add_argument('--state-dir', required=True)
        parser.add_argument('--mode', choices=('preflight', 'once', 'serve', 'health'), default='serve')

    def handle(self, *args, **options):
        lock = None
        try:
            config = adapter._load_config(options['config'])
            adapter._validate_runtime(config, options['state_dir'], options['config'])
            store = adapter._StateStore(options['state_dir'])
            scheduler = adapter._Scheduler(config, store)
            mode = options['mode']
            if mode == 'preflight':
                self.stdout.write(json.dumps({'preflight': 'passed', 'uid': os.geteuid(),
                                              'interval_seconds': config.reaper_interval_seconds}))
                return
            if mode == 'health':
                health = scheduler.health(now=int(time.time()))
                self.stdout.write(json.dumps({'alerting': health.alerting,
                                              'seconds_since_success': health.seconds_since_success}))
                if health.alerting:
                    raise CommandError('reaper health alert', returncode=1)
                return
            lock = store.lock()
            while True:
                now = int(time.time())
                health = scheduler.tick(now=now)
                if health is not None:
                    # Deliberate field allow-list; never stringify a report/config.
                    record = health.history[-1]
                    self.stdout.write(json.dumps({
                        'event': 'reaper-run', 'alerting': health.alerting,
                        'succeeded': record.succeeded, 'removed_count': record.removed_count,
                        'incident_count': record.incident_count,
                        'bound_exceeded_count': record.bound_exceeded_count,
                        'oldest_orphan_seconds': record.oldest_orphan_seconds,
                        'oldest_observed_seconds': record.oldest_observed_seconds,
                    }, sort_keys=True))
                    self.stdout.flush()
                if mode == 'once':
                    return
                # Monotonic sleep avoids busy-looping; persisted wall-clock
                # completion drives external health even if this process stops.
                delay = max(1, scheduler._data()['next_due_at'] - int(time.time()))
                time.sleep(min(delay, config.reaper_interval_seconds))
        except (OSError, ValueError, TypeError):
            raise CommandError('isolated reaper rejected or failed', returncode=1) from None
        finally:
            if lock is not None:
                os.close(lock)
