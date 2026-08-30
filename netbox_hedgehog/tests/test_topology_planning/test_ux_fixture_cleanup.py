"""
DIET-616 regression: setup_ux_test_data --clean must scope generated-object
deletion to the UX fixture plans only, NOT the shared 'hedgehog-generated' tag.

Guards against the destructive-data blocker Dev B flagged: an unrelated
generated DIET plan (its devices/cables) must survive `--clean`.
"""

from django.core.management import call_command
from django.test import TestCase

from dcim.models import (
    Cable, Device, DeviceRole, DeviceType, Interface, Manufacturer, Site,
)
from extras.models import Tag

from netbox_hedgehog.models.topology_planning import TopologyPlan


class UXFixtureCleanupScopeTestCase(TestCase):
    """`setup_ux_test_data --clean` must not delete non-UX generated objects."""

    def _make_generated_device(self, plan_pk, name):
        mfr, _ = Manufacturer.objects.get_or_create(
            name='NonUX-Vendor', defaults={'slug': 'nonux-vendor'})
        dt, _ = DeviceType.objects.get_or_create(
            manufacturer=mfr, model='NONUX-DT',
            defaults={'slug': 'nonux-dt', 'u_height': 1})
        role, _ = DeviceRole.objects.get_or_create(
            name='nonux-role', defaults={'slug': 'nonux-role'})
        site, _ = Site.objects.get_or_create(
            slug='nonux-site', defaults={'name': 'NonUX Site'})
        tag, _ = Tag.objects.get_or_create(
            slug='hedgehog-generated', defaults={'name': 'hedgehog-generated'})
        dev = Device.objects.create(
            name=name, device_type=dt, role=role, site=site, status='active')
        dev.custom_field_data = {'hedgehog_plan_id': str(plan_pk)}
        dev.save()
        dev.tags.add(tag)
        return dev

    def test_clean_preserves_non_ux_generated_plan(self):
        # A separate, non-UX plan with a generated + tagged device.
        other = TopologyPlan.objects.create(name='Unrelated Production Plan')
        survivor = self._make_generated_device(other.pk, 'unrelated-generated-sw')
        self.assertTrue(
            Device.objects.filter(pk=survivor.pk).exists())

        # Run the fixture bootstrap with cleanup.
        call_command('setup_ux_test_data', '--clean', verbosity=0)

        # The unrelated plan and its generated device must survive.
        self.assertTrue(
            TopologyPlan.objects.filter(pk=other.pk).exists(),
            'Non-UX plan was deleted by setup_ux_test_data --clean')
        self.assertTrue(
            Device.objects.filter(pk=survivor.pk).exists(),
            'Non-UX generated device was deleted by --clean (tag-scoped bug)')

        # And the UX fixture plans WERE (re)created.
        self.assertTrue(
            TopologyPlan.objects.filter(
                name__startswith='UX Test Plan').exists(),
            'UX fixture plans were not created')
