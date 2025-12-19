"""
Tests for Topology Planning Reference Data Models

Following TDD approach - these tests are written BEFORE model implementation.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from netbox_hedgehog.models.topology_planning import (
    SwitchModel,
    SwitchPortGroup,
    NICModel,
    BreakoutOption,
)


class SwitchModelTestCase(TestCase):
    """Test cases for SwitchModel"""

    def test_create_switch_model(self):
        """Test basic SwitchModel creation with all fields"""
        switch = SwitchModel.objects.create(
            model_id='DS5000',
            vendor='Celestica',
            part_number='DS5432-ON',
            total_ports=64,
            mclag_capable=True,
            hedgehog_roles=['spine', 'server-leaf'],
            notes='Test switch model'
        )
        self.assertEqual(switch.model_id, 'DS5000')
        self.assertEqual(switch.vendor, 'Celestica')
        self.assertEqual(switch.part_number, 'DS5432-ON')
        self.assertEqual(switch.total_ports, 64)
        self.assertTrue(switch.mclag_capable)
        self.assertEqual(switch.hedgehog_roles, ['spine', 'server-leaf'])
        self.assertEqual(switch.notes, 'Test switch model')

    def test_create_switch_model_minimal(self):
        """Test SwitchModel creation with only required fields"""
        switch = SwitchModel.objects.create(
            model_id='DS3000',
            vendor='Celestica',
            part_number='DS3000-ON',
            total_ports=32
        )
        self.assertEqual(switch.model_id, 'DS3000')
        self.assertFalse(switch.mclag_capable)  # Default False
        self.assertEqual(switch.hedgehog_roles, [])  # Default empty list
        self.assertEqual(switch.notes, '')  # Default empty string

    def test_switch_model_str(self):
        """Test __str__ returns vendor and model_id"""
        switch = SwitchModel.objects.create(
            model_id='DS5000',
            vendor='Celestica',
            part_number='DS5432-ON',
            total_ports=64
        )
        self.assertEqual(str(switch), 'Celestica DS5000')

    def test_switch_model_unique_model_id(self):
        """Test model_id must be unique"""
        SwitchModel.objects.create(
            model_id='DS5000',
            vendor='Celestica',
            part_number='DS5432-ON',
            total_ports=64
        )
        with self.assertRaises(IntegrityError):
            SwitchModel.objects.create(
                model_id='DS5000',  # Duplicate
                vendor='Different Vendor',
                part_number='Different-PN',
                total_ports=32
            )

    def test_total_ports_positive_validation(self):
        """Test total_ports must be positive"""
        switch = SwitchModel(
            model_id='TEST',
            vendor='Test Vendor',
            part_number='TEST-001',
            total_ports=-1  # Invalid
        )
        with self.assertRaises(ValidationError):
            switch.full_clean()

    def test_total_ports_zero_validation(self):
        """Test total_ports cannot be zero"""
        switch = SwitchModel(
            model_id='TEST',
            vendor='Test Vendor',
            part_number='TEST-001',
            total_ports=0  # Invalid
        )
        with self.assertRaises(ValidationError):
            switch.full_clean()

    def test_switch_model_ordering(self):
        """Test switches are ordered by vendor, then model_id"""
        SwitchModel.objects.create(
            model_id='DS5000', vendor='Celestica', part_number='P1', total_ports=64
        )
        SwitchModel.objects.create(
            model_id='DS3000', vendor='Celestica', part_number='P2', total_ports=32
        )
        SwitchModel.objects.create(
            model_id='SN5600', vendor='NVIDIA', part_number='P3', total_ports=64
        )

        switches = list(SwitchModel.objects.all())
        self.assertEqual(switches[0].model_id, 'DS3000')  # Celestica DS3000
        self.assertEqual(switches[1].model_id, 'DS5000')  # Celestica DS5000
        self.assertEqual(switches[2].model_id, 'SN5600')  # NVIDIA SN5600

    def test_switch_model_has_timestamps(self):
        """Test NetBoxModel provides created and last_updated timestamps"""
        switch = SwitchModel.objects.create(
            model_id='DS5000',
            vendor='Celestica',
            part_number='DS5432-ON',
            total_ports=64
        )
        self.assertIsNotNone(switch.created)
        self.assertIsNotNone(switch.last_updated)

    def test_switch_model_get_absolute_url(self):
        """Test get_absolute_url returns proper URL for detail view"""
        switch = SwitchModel.objects.create(
            model_id='DS5000',
            vendor='Celestica',
            part_number='DS5432-ON',
            total_ports=64
        )
        url = switch.get_absolute_url()
        self.assertIn('/plugins/hedgehog/topology-planning/switch-models/', url)
        self.assertIn(str(switch.pk), url)


class SwitchPortGroupTestCase(TestCase):
    """Test cases for SwitchPortGroup"""

    def setUp(self):
        """Create a test switch model for FK relationships"""
        self.switch_model = SwitchModel.objects.create(
            model_id='DS5000',
            vendor='Celestica',
            part_number='DS5432-ON',
            total_ports=64
        )

    def test_create_port_group(self):
        """Test basic SwitchPortGroup creation"""
        port_group = SwitchPortGroup.objects.create(
            switch_model=self.switch_model,
            group_name='Primary QSFP-DD',
            port_count=64,
            native_speed=800,
            supported_breakouts='1x800G,2x400G,4x200G',
            port_range='E1/1-E1/64'
        )
        self.assertEqual(port_group.switch_model, self.switch_model)
        self.assertEqual(port_group.group_name, 'Primary QSFP-DD')
        self.assertEqual(port_group.port_count, 64)
        self.assertEqual(port_group.native_speed, 800)
        self.assertEqual(port_group.supported_breakouts, '1x800G,2x400G,4x200G')
        self.assertEqual(port_group.port_range, 'E1/1-E1/64')

    def test_port_group_str(self):
        """Test __str__ returns switch model and group name"""
        port_group = SwitchPortGroup.objects.create(
            switch_model=self.switch_model,
            group_name='Primary QSFP-DD',
            port_count=64,
            native_speed=800,
            supported_breakouts='1x800G',
            port_range='E1/1-E1/64'
        )
        self.assertIn('DS5000', str(port_group))
        self.assertIn('Primary QSFP-DD', str(port_group))

    def test_port_group_cascade_delete(self):
        """Test port groups are deleted when switch model is deleted"""
        port_group = SwitchPortGroup.objects.create(
            switch_model=self.switch_model,
            group_name='Test Group',
            port_count=32,
            native_speed=400,
            supported_breakouts='1x400G',
            port_range='E1/1-E1/32'
        )
        port_group_id = port_group.id

        # Delete the switch model
        self.switch_model.delete()

        # Port group should also be deleted
        with self.assertRaises(SwitchPortGroup.DoesNotExist):
            SwitchPortGroup.objects.get(id=port_group_id)

    def test_port_count_positive_validation(self):
        """Test port_count must be positive"""
        port_group = SwitchPortGroup(
            switch_model=self.switch_model,
            group_name='Test',
            port_count=-1,  # Invalid
            native_speed=800,
            supported_breakouts='1x800G',
            port_range='E1/1-E1/64'
        )
        with self.assertRaises(ValidationError):
            port_group.full_clean()

    def test_port_group_related_name(self):
        """Test port groups accessible via switch_model.port_groups"""
        SwitchPortGroup.objects.create(
            switch_model=self.switch_model,
            group_name='Group 1',
            port_count=32,
            native_speed=800,
            supported_breakouts='1x800G',
            port_range='E1/1-E1/32'
        )
        SwitchPortGroup.objects.create(
            switch_model=self.switch_model,
            group_name='Group 2',
            port_count=4,
            native_speed=10,
            supported_breakouts='1x10G',
            port_range='E1/49-E1/52'
        )
        self.assertEqual(self.switch_model.port_groups.count(), 2)

    def test_port_group_get_absolute_url(self):
        """Test get_absolute_url returns proper URL"""
        port_group = SwitchPortGroup.objects.create(
            switch_model=self.switch_model,
            group_name='Primary',
            port_count=64,
            native_speed=800,
            supported_breakouts='1x800G',
            port_range='E1/1-E1/64'
        )
        url = port_group.get_absolute_url()
        self.assertIn('/plugins/hedgehog/topology-planning/switch-port-groups/', url)
        self.assertIn(str(port_group.pk), url)


class NICModelTestCase(TestCase):
    """Test cases for NICModel"""

    def test_create_nic_model(self):
        """Test basic NICModel creation with all fields"""
        nic = NICModel.objects.create(
            model_id='CX7-2P-400G',
            vendor='NVIDIA',
            part_number='MCX755106AS-HEAT',
            port_count=2,
            port_speed=400,
            port_type='QSFP112',
            notes='ConnectX-7 dual port 400G'
        )
        self.assertEqual(nic.model_id, 'CX7-2P-400G')
        self.assertEqual(nic.vendor, 'NVIDIA')
        self.assertEqual(nic.part_number, 'MCX755106AS-HEAT')
        self.assertEqual(nic.port_count, 2)
        self.assertEqual(nic.port_speed, 400)
        self.assertEqual(nic.port_type, 'QSFP112')
        self.assertEqual(nic.notes, 'ConnectX-7 dual port 400G')

    def test_create_nic_model_minimal(self):
        """Test NICModel creation with only required fields"""
        nic = NICModel.objects.create(
            model_id='CX6-2P-200G',
            vendor='NVIDIA',
            part_number='MCX653106A-HDAT',
            port_count=2,
            port_speed=200,
            port_type='QSFP56'
        )
        self.assertEqual(nic.notes, '')  # Default empty string

    def test_nic_model_str(self):
        """Test __str__ returns vendor and model_id"""
        nic = NICModel.objects.create(
            model_id='CX7-2P-400G',
            vendor='NVIDIA',
            part_number='MCX755106AS-HEAT',
            port_count=2,
            port_speed=400,
            port_type='QSFP112'
        )
        self.assertEqual(str(nic), 'NVIDIA CX7-2P-400G')

    def test_nic_model_unique_model_id(self):
        """Test model_id must be unique"""
        NICModel.objects.create(
            model_id='CX7-2P-400G',
            vendor='NVIDIA',
            part_number='MCX755106AS-HEAT',
            port_count=2,
            port_speed=400,
            port_type='QSFP112'
        )
        with self.assertRaises(IntegrityError):
            NICModel.objects.create(
                model_id='CX7-2P-400G',  # Duplicate
                vendor='Different',
                part_number='Different',
                port_count=1,
                port_speed=200,
                port_type='QSFP56'
            )

    def test_port_count_positive_validation(self):
        """Test port_count must be positive"""
        nic = NICModel(
            model_id='TEST',
            vendor='Test',
            part_number='TEST-001',
            port_count=0,  # Invalid
            port_speed=400,
            port_type='QSFP112'
        )
        with self.assertRaises(ValidationError):
            nic.full_clean()

    def test_nic_model_ordering(self):
        """Test NICs are ordered by vendor, then model_id"""
        NICModel.objects.create(
            model_id='CX7-2P-400G', vendor='NVIDIA', part_number='P1',
            port_count=2, port_speed=400, port_type='QSFP112'
        )
        NICModel.objects.create(
            model_id='CX6-2P-200G', vendor='NVIDIA', part_number='P2',
            port_count=2, port_speed=200, port_type='QSFP56'
        )
        NICModel.objects.create(
            model_id='X710-DA2', vendor='Intel', part_number='P3',
            port_count=2, port_speed=10, port_type='SFP+'
        )

        nics = list(NICModel.objects.all())
        self.assertEqual(nics[0].vendor, 'Intel')
        self.assertEqual(nics[1].model_id, 'CX6-2P-200G')
        self.assertEqual(nics[2].model_id, 'CX7-2P-400G')

    def test_nic_model_get_absolute_url(self):
        """Test get_absolute_url returns proper URL"""
        nic = NICModel.objects.create(
            model_id='CX7-2P-400G',
            vendor='NVIDIA',
            part_number='MCX755106AS-HEAT',
            port_count=2,
            port_speed=400,
            port_type='QSFP112'
        )
        url = nic.get_absolute_url()
        self.assertIn('/plugins/hedgehog/topology-planning/nic-models/', url)
        self.assertIn(str(nic.pk), url)


class BreakoutOptionTestCase(TestCase):
    """Test cases for BreakoutOption"""

    def test_create_breakout_option(self):
        """Test basic BreakoutOption creation with all fields"""
        breakout = BreakoutOption.objects.create(
            breakout_id='800g-4x200g',
            from_speed=800,
            logical_ports=4,
            logical_speed=200,
            optic_type='QSFP-DD'
        )
        self.assertEqual(breakout.breakout_id, '800g-4x200g')
        self.assertEqual(breakout.from_speed, 800)
        self.assertEqual(breakout.logical_ports, 4)
        self.assertEqual(breakout.logical_speed, 200)
        self.assertEqual(breakout.optic_type, 'QSFP-DD')

    def test_create_breakout_option_minimal(self):
        """Test BreakoutOption creation with only required fields"""
        breakout = BreakoutOption.objects.create(
            breakout_id='400g-2x200g',
            from_speed=400,
            logical_ports=2,
            logical_speed=200
        )
        self.assertEqual(breakout.optic_type, '')  # Default empty string

    def test_breakout_option_str(self):
        """Test __str__ returns breakout_id"""
        breakout = BreakoutOption.objects.create(
            breakout_id='800g-4x200g',
            from_speed=800,
            logical_ports=4,
            logical_speed=200
        )
        self.assertEqual(str(breakout), '800g-4x200g (800G → 4x200G)')

    def test_breakout_option_unique_breakout_id(self):
        """Test breakout_id must be unique"""
        BreakoutOption.objects.create(
            breakout_id='800g-4x200g',
            from_speed=800,
            logical_ports=4,
            logical_speed=200
        )
        with self.assertRaises(IntegrityError):
            BreakoutOption.objects.create(
                breakout_id='800g-4x200g',  # Duplicate
                from_speed=400,
                logical_ports=2,
                logical_speed=200
            )

    def test_logical_ports_positive_validation(self):
        """Test logical_ports must be positive"""
        breakout = BreakoutOption(
            breakout_id='test',
            from_speed=800,
            logical_ports=0,  # Invalid
            logical_speed=200
        )
        with self.assertRaises(ValidationError):
            breakout.full_clean()

    def test_breakout_option_ordering(self):
        """Test breakouts are ordered by from_speed descending, then logical_ports"""
        BreakoutOption.objects.create(
            breakout_id='800g-1x800g', from_speed=800, logical_ports=1, logical_speed=800
        )
        BreakoutOption.objects.create(
            breakout_id='800g-4x200g', from_speed=800, logical_ports=4, logical_speed=200
        )
        BreakoutOption.objects.create(
            breakout_id='400g-2x200g', from_speed=400, logical_ports=2, logical_speed=200
        )

        breakouts = list(BreakoutOption.objects.all())
        # Ordered by from_speed DESC, then logical_ports
        self.assertEqual(breakouts[0].breakout_id, '800g-1x800g')
        self.assertEqual(breakouts[1].breakout_id, '800g-4x200g')
        self.assertEqual(breakouts[2].breakout_id, '400g-2x200g')

    def test_breakout_option_get_absolute_url(self):
        """Test get_absolute_url returns proper URL"""
        breakout = BreakoutOption.objects.create(
            breakout_id='800g-4x200g',
            from_speed=800,
            logical_ports=4,
            logical_speed=200
        )
        url = breakout.get_absolute_url()
        self.assertIn('/plugins/hedgehog/topology-planning/breakout-options/', url)
        self.assertIn(str(breakout.pk), url)
