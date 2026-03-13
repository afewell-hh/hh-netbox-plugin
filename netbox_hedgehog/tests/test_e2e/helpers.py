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


def get_test_nic_module_type():
    """
    Return the BlueField-3 BF3220 ModuleType seeded by migration 0029.

    Use this in any test helper that creates PlanServerConnection to satisfy
    the NOT NULL constraint on nic_module_type added in migration 0030.
    """
    from dcim.models import InterfaceTemplate, Manufacturer, ModuleType

    nvidia, _ = Manufacturer.objects.get_or_create(
        name='NVIDIA', defaults={'slug': 'nvidia'}
    )
    module_type, created = ModuleType.objects.get_or_create(
        manufacturer=nvidia,
        model='BlueField-3 BF3220',
    )
    if created:
        InterfaceTemplate.objects.get_or_create(
            module_type=module_type, name='p0',
            defaults={'type': '200gbase-x-qsfp112'}
        )
        InterfaceTemplate.objects.get_or_create(
            module_type=module_type, name='p1',
            defaults={'type': '200gbase-x-qsfp112'}
        )
    return module_type


def get_test_server_nic(server_class, nic_id='nic-test'):
    """
    Return (or create) a PlanServerNIC for use in e2e tests (DIET-294).
    """
    from netbox_hedgehog.models.topology_planning import PlanServerNIC
    module_type = get_test_nic_module_type()
    nic, _ = PlanServerNIC.objects.get_or_create(
        server_class=server_class,
        nic_id=nic_id,
        defaults={'module_type': module_type},
    )
    return nic


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
