"""
Management command to load DIET reference data (seed data).

This command is idempotent - safe to run multiple times.
It uses update_or_create to avoid duplicating records.

Usage:
    docker compose exec netbox python manage.py load_diet_reference_data

Reference:
    - Issue #85 (DIET-001): Database Models & Migrations – Reference Data Layer
    - PRD Issue #83: Breakout option specifications
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from netbox_hedgehog.models.topology_planning import BreakoutOption


class Command(BaseCommand):
    help = 'Load DIET reference data (BreakoutOption seed data)'

    def handle(self, *args, **options):
        """Load seed data for DIET reference data models"""

        self.stdout.write(self.style.WARNING('Loading DIET reference data...'))

        # Load BreakoutOption seed data
        breakout_count = self.load_breakout_options()

        self.stdout.write(self.style.SUCCESS(
            f'\nSuccessfully loaded DIET reference data:'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'  - BreakoutOption: {breakout_count} records created/updated'
        ))

    @transaction.atomic
    def load_breakout_options(self):
        """
        Load BreakoutOption seed data.

        Based on PRD Issue #83, Appendix: Reference Data: Pre-populated Values.

        Returns:
            int: Number of BreakoutOption records created/updated
        """

        # Breakout configurations from PRD #83
        # Format: (breakout_id, from_speed, logical_ports, logical_speed, optic_type)
        breakout_data = [
            # 800G breakouts (QSFP-DD)
            ('1x800g', 800, 1, 800, 'QSFP-DD'),
            ('2x400g', 800, 2, 400, 'QSFP-DD'),
            ('4x200g', 800, 4, 200, 'QSFP-DD'),
            ('8x100g', 800, 8, 100, 'QSFP-DD'),

            # 400G breakouts (QSFP-DD)
            ('1x400g', 400, 1, 400, 'QSFP-DD'),
            ('2x200g', 400, 2, 200, 'QSFP-DD'),
            ('4x100g', 400, 4, 100, 'QSFP-DD'),

            # 100G breakouts (QSFP28)
            ('1x100g', 100, 1, 100, 'QSFP28'),
            ('1x40g', 100, 1, 40, 'QSFP28'),
            ('4x25g', 100, 4, 25, 'QSFP28'),
            ('4x10g', 100, 4, 10, 'QSFP28'),
            ('2x50g', 100, 2, 50, 'QSFP28'),

            # 1G (RJ45 / SFP)
            ('1x1g', 1, 1, 1, 'RJ45'),

            # 10G (SFP+)
            ('1x10g', 10, 1, 10, 'SFP+'),
        ]

        created_count = 0
        updated_count = 0

        for breakout_id, from_speed, logical_ports, logical_speed, optic_type in breakout_data:
            breakout, created = BreakoutOption.objects.update_or_create(
                breakout_id=breakout_id,
                defaults={
                    'from_speed': from_speed,
                    'logical_ports': logical_ports,
                    'logical_speed': logical_speed,
                    'optic_type': optic_type,
                }
            )

            if created:
                created_count += 1
                self.stdout.write(f'  Created: {breakout}')
            else:
                updated_count += 1
                self.stdout.write(f'  Updated: {breakout}')

        total_count = created_count + updated_count

        if created_count > 0:
            self.stdout.write(self.style.SUCCESS(
                f'\nBreakoutOption: {created_count} created, {updated_count} updated'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f'\nBreakoutOption: All {updated_count} records already exist (updated)'
            ))

        return total_count
