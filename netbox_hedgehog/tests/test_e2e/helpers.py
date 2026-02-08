"""
Helper functions for E2E test data creation.

Provides consistent test data setup across all E2E tests, ensuring
model fields match actual database schema.

IMPORTANT: These helpers create only REFERENCE DATA (Manufacturer, DeviceType,
DeviceTypeExtension, BreakoutOption). They do NOT create plan-specific objects
(TopologyPlan, PlanServerClass, PlanSwitchClass, SwitchPortZone) as those
require a TopologyPlan which each test creates individually.
"""

from dcim.models import DeviceType, Manufacturer
from netbox_hedgehog.models.topology_planning import (
    DeviceTypeExtension,
    BreakoutOption,
)


def create_test_manufacturer():
    """Create a test manufacturer."""
    manufacturer, _ = Manufacturer.objects.get_or_create(
        name='E2E Test Manufacturer',
        defaults={'slug': 'e2e-test-mfg'}
    )
    return manufacturer


def create_test_device_types(manufacturer):
    """
    Create test device types for servers and switches.

    Args:
        manufacturer: Manufacturer instance

    Returns:
        tuple: (server_type, switch_type)
    """
    server_type, _ = DeviceType.objects.get_or_create(
        manufacturer=manufacturer,
        model='E2E Test Server',
        defaults={'slug': 'e2e-test-server', 'u_height': 2}
    )

    switch_type, _ = DeviceType.objects.get_or_create(
        manufacturer=manufacturer,
        model='E2E Test Switch',
        defaults={'slug': 'e2e-test-switch', 'u_height': 1}
    )

    return server_type, switch_type


def create_test_device_type_extension(switch_type):
    """
    Create DeviceTypeExtension for switch with required metadata.

    Args:
        switch_type: DeviceType instance

    Returns:
        DeviceTypeExtension instance
    """
    switch_ext, _ = DeviceTypeExtension.objects.get_or_create(
        device_type=switch_type,
        defaults={
            'mclag_capable': False,
            'hedgehog_roles': ['spine', 'server-leaf']
        }
    )
    return switch_ext


def create_test_breakout_option():
    """
    Create a breakout option for port configuration.

    Returns:
        BreakoutOption instance
    """
    breakout, _ = BreakoutOption.objects.get_or_create(
        breakout_id='e2e-test-4x200g',
        defaults={
            'from_speed': 800,
            'logical_ports': 4,
            'logical_speed': 200,
            'optic_type': 'QSFP-DD'
        }
    )
    return breakout


def create_base_test_data():
    """
    Create all base REFERENCE DATA needed for E2E tests.

    This creates only reference data that can be shared across tests:
    - Manufacturer
    - Server and Switch DeviceTypes
    - DeviceTypeExtension for switches
    - BreakoutOption

    Does NOT create plan-specific objects (TopologyPlan, PlanServerClass,
    PlanSwitchClass, SwitchPortZone) as those require a TopologyPlan instance.

    Returns:
        dict: Dictionary with created reference data objects
    """
    manufacturer = create_test_manufacturer()
    server_type, switch_type = create_test_device_types(manufacturer)
    switch_ext = create_test_device_type_extension(switch_type)
    breakout = create_test_breakout_option()

    return {
        'manufacturer': manufacturer,
        'server_type': server_type,
        'switch_type': switch_type,
        'switch_ext': switch_ext,
        'breakout': breakout,
    }


def cleanup_base_test_data():
    """
    Clean up base reference data.

    Call this in tearDown or tearDownClass to remove test data.
    Deletes in reverse order of dependencies.
    """
    # Delete in reverse order of dependencies
    BreakoutOption.objects.filter(breakout_id='e2e-test-4x200g').delete()
    DeviceTypeExtension.objects.filter(device_type__slug__startswith='e2e-test-').delete()
    DeviceType.objects.filter(slug__startswith='e2e-test-').delete()
    Manufacturer.objects.filter(slug='e2e-test-mfg').delete()
