# Topology Planning Tests
#
# Helper additions for DIET-334 transceiver modeling (Phase 3 RED tests).


def get_test_transceiver_module_type():
    """
    Return (or create) a Network Transceiver ModuleType for use in DIET-334 tests.

    Uses get_or_create so repeated calls in --keepdb runs return the same object.
    If the 'Network Transceiver' ModuleTypeProfile does not exist (bare test DB),
    the ModuleType is created without a profile and tests that rely on profile
    validation will assert the expected ValidationError correctly.
    """
    from dcim.models import Manufacturer, ModuleType, ModuleTypeProfile

    mfr, _ = Manufacturer.objects.get_or_create(
        name='XCVR-Test-Vendor', defaults={'slug': 'xcvr-test-vendor'}
    )
    profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
    mt, _ = ModuleType.objects.get_or_create(
        manufacturer=mfr,
        model='XCVR-QSFP112-MMF-TEST',
        defaults={
            'profile': profile,
            'attribute_data': {
                'cage_type': 'QSFP112',
                'medium': 'MMF',
                'connector': 'MPO-12',
                'standard': '200GBASE-SR4',
                'reach_class': 'SR',
            },
        },
    )
    return mt


def get_test_transceiver_module_type_osfp():
    """
    Return (or create) a Network Transceiver ModuleType with OSFP cage type.

    Used in migration tests that verify OSFP is valid after migration 0044 adds
    it to the profile schema enum. In RED state this ModuleType may fail profile
    schema validation -- that is the expected RED failure for E.3.
    """
    from dcim.models import Manufacturer, ModuleType, ModuleTypeProfile

    mfr, _ = Manufacturer.objects.get_or_create(
        name='XCVR-Test-Vendor', defaults={'slug': 'xcvr-test-vendor'}
    )
    profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
    mt, _ = ModuleType.objects.get_or_create(
        manufacturer=mfr,
        model='XCVR-OSFP-400G-TEST',
        defaults={
            'profile': profile,
            'attribute_data': {
                'cage_type': 'OSFP',
                'medium': 'MMF',
                'standard': '400GBASE-SR4',
                'reach_class': 'SR',
            },
        },
    )
    return mt


def get_test_non_transceiver_module_type():
    """
    Return (or create) a ModuleType WITHOUT the Network Transceiver profile.

    Used in validation tests that assert a non-transceiver ModuleType is rejected
    when set as transceiver_module_type on PlanServerConnection or SwitchPortZone.
    """
    from dcim.models import InterfaceTemplate, Manufacturer, ModuleType

    mfr, _ = Manufacturer.objects.get_or_create(
        name='XCVR-Test-Vendor', defaults={'slug': 'xcvr-test-vendor'}
    )
    mt, created = ModuleType.objects.get_or_create(
        manufacturer=mfr,
        model='NON-XCVR-NIC-TEST',
    )
    if created:
        InterfaceTemplate.objects.get_or_create(
            module_type=mt, name='p0', defaults={'type': '200gbase-x-qsfp112'}
        )
    return mt


def get_test_nic_module_type():
    """
    Return the BlueField-3 BF3220 ModuleType seeded by migration 0029.

    Use this in any test helper that creates PlanServerConnection to satisfy
    the NOT NULL constraint on nic_module_type added in migration 0030.

    Uses get_or_create so tests are robust whether or not migration 0029 has
    already run (in --keepdb runs the seeded data will simply be returned).
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
    Return (or create) a PlanServerNIC for use in tests (DIET-294).

    Creates the ModuleType with InterfaceTemplates if needed via
    get_test_nic_module_type(). Use this for any test that creates a
    PlanServerConnection under the new NIC-first schema.
    """
    from netbox_hedgehog.models.topology_planning import PlanServerNIC
    module_type = get_test_nic_module_type()
    nic, _ = PlanServerNIC.objects.get_or_create(
        server_class=server_class,
        nic_id=nic_id,
        defaults={'module_type': module_type},
    )
    return nic
