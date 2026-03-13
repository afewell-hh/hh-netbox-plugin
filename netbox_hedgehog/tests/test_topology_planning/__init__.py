# Topology Planning Tests


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
