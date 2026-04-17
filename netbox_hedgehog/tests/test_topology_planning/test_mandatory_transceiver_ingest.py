"""
GREEN regression tests for #469 — mandatory transceiver enforcement in YAML ingest.

After GREEN, all YAML case files used here are fully annotated with transceiver_module_type.
These tests verify that:
  - Annotated case files apply successfully (positive path / regression guard)
  - Ingest enforcement correctly validates transceiver presence before DB writes
  - The SH and 128GPU cases apply cleanly end-to-end

Acceptance cases:
  A10 — apply_diet_test_case --case training_xoc64_1xopg64_mesh_conv_sh
        (fully annotated after GREEN) → succeeds; all 7 zones + 14 connections
        have non-null transceiver_module_type
  A10b — apply_diet_test_case --case ux_case_128gpu_odd_ports
        (fully annotated after GREEN) → succeeds; all 15 zones + 26 connections
        have non-null transceiver_module_type

Ingest positive-path tests (parse-layer regression guards):
  IG4 — training_xoc64_1xopg64_mesh_conv_sh: fully annotated case applies cleanly
        (no false-positive errors for zones/connections with transceiver set)
  IG5 — ux_case_128gpu_odd_ports: fully annotated case applies cleanly
        (all 15 zones + 26 connections accepted without errors)
"""

from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from netbox_hedgehog.models.topology_planning import (
    PlanServerConnection,
    SwitchPortZone,
    TopologyPlan,
)

# Exact error messages from the spec (used to detect false-positive errors)
_ZONE_INGEST_MSG = 'transceiver_module_type is required for every switch port zone.'
_CONN_INGEST_MSG = 'transceiver_module_type is required for every server connection.'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _apply_case(case_id, extra_args=None, load_reference=False):
    """
    Run apply_diet_test_case for a given case ID.
    Returns (stdout, stderr, exception_or_None).
    """
    stdout = StringIO()
    stderr = StringIO()
    exc = None
    args = ['apply_diet_test_case', '--case', case_id]
    if extra_args:
        args += extra_args
    if load_reference:
        call_command('load_diet_reference_data', stdout=StringIO(), stderr=StringIO())
    try:
        call_command(*args[0:1], *args[1:], stdout=stdout, stderr=stderr)
    except CommandError as e:
        exc = e
    return stdout.getvalue(), stderr.getvalue(), exc


# ---------------------------------------------------------------------------
# Group IG — ingest parse-layer positive-path regression tests
# ---------------------------------------------------------------------------

class MandatoryTransceiverIngestParseTestCase(TestCase):
    """
    IG4–IG5: Positive-path regression guards for the ingest parser.

    These tests verify that fully-annotated case files apply without
    false-positive transceiver-missing errors. They are the primary
    regression guard for the required-check code path after GREEN.
    """

    def test_ig4_case_with_transceivers_set_does_not_produce_ingest_error(self):
        """
        IG4: training_xoc64_1xopg64_mesh_conv_sh is fully annotated after GREEN.
        The case must apply without any transceiver-missing errors.
        """
        stdout, _, exc = _apply_case(
            'training_xoc64_1xopg64_mesh_conv_sh',
            extra_args=['--clean', '--prune'],
            load_reference=True,
        )
        if exc is not None:
            error_text = str(exc)
            has_zone_error = _ZONE_INGEST_MSG in error_text
            has_conn_error = _CONN_INGEST_MSG in error_text
            if has_zone_error or has_conn_error:
                self.fail(
                    f'Fully-annotated XOC-64 SH case must not produce '
                    f'transceiver-missing errors; got: {error_text[:400]}'
                )

    def test_ig5_128gpu_case_applies_cleanly_with_all_transceivers(self):
        """
        IG5: ux_case_128gpu_odd_ports is fully annotated after GREEN.
        All 15 zones + 26 connections have transceiver_module_type set.
        The case must apply without any transceiver-missing errors.
        """
        call_command('load_diet_reference_data', stdout=StringIO(), stderr=StringIO())
        _, _, exc = _apply_case(
            'ux_case_128gpu_odd_ports',
            extra_args=['--clean', '--prune'],
        )
        if exc is not None:
            error_text = str(exc)
            has_zone_error = _ZONE_INGEST_MSG in error_text
            has_conn_error = _CONN_INGEST_MSG in error_text
            if has_zone_error or has_conn_error:
                self.fail(
                    f'Fully-annotated 128GPU case must not produce '
                    f'transceiver-missing errors; got: {error_text[:400]}'
                )
            else:
                # Some other error — still a failure but not a transceiver-missing one
                self.fail(f'128GPU case apply failed: {error_text[:400]}')


# ---------------------------------------------------------------------------
# Group A10 — fully-annotated case success after GREEN
# ---------------------------------------------------------------------------

class MandatoryTransceiverIngestXoc64ShTest(TestCase):
    """
    A10: After GREEN (all zones and connections annotated in the YAML),
    apply_diet_test_case --case training_xoc64_1xopg64_mesh_conv_sh must
    succeed and all 7 zones + 14 connections must have transceiver set.
    """

    def test_a10_xoc64_sh_applies_with_all_transceivers_set(self):
        """
        A10: After GREEN, apply_diet_test_case for training_xoc64_1xopg64_mesh_conv_sh
        must succeed (no CommandError) and all zones+connections must have
        transceiver_module_type set.
        """
        call_command('load_diet_reference_data', stdout=StringIO(), stderr=StringIO())
        _, _, exc = _apply_case(
            'training_xoc64_1xopg64_mesh_conv_sh',
            extra_args=['--clean', '--prune'],
        )
        self.assertIsNone(
            exc,
            f'XOC-64 SH apply must succeed after GREEN YAML cleanup; '
            f'got CommandError: {exc}',
        )

        plan = TopologyPlan.objects.filter(
            custom_field_data__yaml_case_id='training_xoc64_1xopg64_mesh_conv_sh'
        ).first()
        self.assertIsNotNone(plan, 'Plan must be created by the apply command')

        # All 7 zones must have transceiver set
        total_zones = SwitchPortZone.objects.filter(switch_class__plan=plan).count()
        null_zones = SwitchPortZone.objects.filter(
            switch_class__plan=plan,
            transceiver_module_type__isnull=True,
        ).count()
        self.assertEqual(
            null_zones, 0,
            f'All {total_zones} zones must have transceiver_module_type set; '
            f'{null_zones} are null',
        )

        # All 14 connections must have transceiver set
        total_conns = PlanServerConnection.objects.filter(
            server_class__plan=plan
        ).count()
        null_conns = PlanServerConnection.objects.filter(
            server_class__plan=plan,
            transceiver_module_type__isnull=True,
        ).count()
        self.assertEqual(
            null_conns, 0,
            f'All {total_conns} connections must have transceiver_module_type set; '
            f'{null_conns} are null',
        )

    def test_a10_ux_case_128gpu_applies_with_all_transceivers_after_green(self):
        """
        A10b: After GREEN, ux_case_128gpu_odd_ports must also apply cleanly —
        all 15 zones and 26 connections annotated.
        """
        call_command('load_diet_reference_data', stdout=StringIO(), stderr=StringIO())
        _, _, exc = _apply_case(
            'ux_case_128gpu_odd_ports',
            extra_args=['--clean', '--prune'],
        )
        self.assertIsNone(
            exc,
            f'ux_case_128gpu_odd_ports must apply cleanly after GREEN; got: {exc}',
        )

        plan = TopologyPlan.objects.filter(name='UX Case 128GPU Odd Ports').first()
        self.assertIsNotNone(plan, 'UX Case 128GPU Odd Ports plan must be created')

        null_zones = SwitchPortZone.objects.filter(
            switch_class__plan=plan,
            transceiver_module_type__isnull=True,
        ).count()
        null_conns = PlanServerConnection.objects.filter(
            server_class__plan=plan,
            transceiver_module_type__isnull=True,
        ).count()
        self.assertEqual(
            null_zones, 0,
            f'All zones in 128GPU case must have transceiver; {null_zones} are null',
        )
        self.assertEqual(
            null_conns, 0,
            f'All connections in 128GPU case must have transceiver; {null_conns} are null',
        )
