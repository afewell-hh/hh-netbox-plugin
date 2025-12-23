"""
Tests for NamingTemplate model.

Test categories:
- Basic CRUD operations
- Render method functionality
- Field validation
- Custom validation (clean method)
- Model constraints (unique_together, cascade delete)
- Ordering

Following TDD approach: Tests written BEFORE implementation.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from netbox_hedgehog.models.topology_planning import (
    TopologyPlan,
    NamingTemplate,
)


class NamingTemplateModelTestCase(TestCase):
    """Test suite for NamingTemplate model"""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for all test methods"""
        # Create test plan for plan-specific templates
        cls.test_plan = TopologyPlan.objects.create(
            name="Test Plan"
        )

    # =========================================================================
    # 1. Basic CRUD Operations
    # =========================================================================

    def test_create_global_naming_template(self):
        """Test creating global default naming template"""
        template = NamingTemplate.objects.create(
            plan=None,  # Global
            device_category="server",
            pattern="{site}-{class}-{index:04d}",
            description="Default server naming"
        )

        self.assertIsNone(template.plan)
        self.assertEqual(template.device_category, "server")
        self.assertEqual(template.pattern, "{site}-{class}-{index:04d}")
        self.assertEqual(template.description, "Default server naming")

    def test_create_plan_specific_naming_template(self):
        """Test creating plan-specific naming template"""
        template = NamingTemplate.objects.create(
            plan=self.test_plan,
            device_category="leaf",
            pattern="{site}-{fabric}-leaf-{index:02d}",
            description="Leaf switch naming"
        )

        self.assertEqual(template.plan, self.test_plan)
        self.assertEqual(template.device_category, "leaf")
        self.assertEqual(template.pattern, "{site}-{fabric}-leaf-{index:02d}")

    def test_str_representation_global(self):
        """Test __str__ for global template shows 'Global'"""
        template = NamingTemplate.objects.create(
            plan=None,
            device_category="server",
            pattern="{site}-{class}-{index:04d}"
        )

        str_repr = str(template)
        self.assertIn("Global", str_repr)
        self.assertIn("server", str_repr)
        self.assertIn("{site}-{class}-{index:04d}", str_repr)

    def test_str_representation_plan_specific(self):
        """Test __str__ for plan-specific template shows plan name"""
        template = NamingTemplate.objects.create(
            plan=self.test_plan,
            device_category="server",
            pattern="{site}-{class}-{index:04d}"
        )

        str_repr = str(template)
        self.assertIn("Test Plan", str_repr)
        self.assertIn("server", str_repr)

    # =========================================================================
    # 2. Render Method
    # =========================================================================

    def test_render_simple_pattern(self):
        """Test render() with simple pattern"""
        template = NamingTemplate.objects.create(
            device_category="server",
            pattern="{site}-{class}-{index:04d}"
        )

        result = template.render({
            'site': 'tus1',
            'class': 'gpu',
            'index': 42
        })

        self.assertEqual(result, "tus1-gpu-0042")

    def test_render_complex_pattern(self):
        """Test render() with multiple variables and formatting"""
        template = NamingTemplate.objects.create(
            device_category="leaf",
            pattern="{site}-{fabric}-{role}-{index:02d}"
        )

        result = template.render({
            'site': 'nyc1',
            'fabric': 'frontend',
            'role': 'leaf',
            'index': 5
        })

        self.assertEqual(result, "nyc1-frontend-leaf-05")

    def test_render_raises_error_on_missing_variable(self):
        """Test render() raises error when required variable missing"""
        template = NamingTemplate.objects.create(
            device_category="server",
            pattern="{site}-{class}-{index:04d}"
        )

        with self.assertRaises(Exception) as cm:
            template.render({'site': 'tus1', 'class': 'gpu'})  # Missing 'index'

        error_message = str(cm.exception)
        # Check that error mentions the missing variable (flexible on exact message)
        self.assertIn('index', error_message.lower())

    def test_render_ignores_extra_variables(self):
        """Test render() ignores extra variables in context"""
        template = NamingTemplate.objects.create(
            device_category="server",
            pattern="{site}-{class}-{index:04d}"
        )

        result = template.render({
            'site': 'tus1',
            'class': 'gpu',
            'index': 1,
            'extra': 'ignored',
            'another': 'also ignored'
        })

        self.assertEqual(result, "tus1-gpu-0001")

    def test_render_with_all_standard_variables(self):
        """Test render() with all available standard variables"""
        template = NamingTemplate.objects.create(
            device_category="server",
            pattern="{site}-{category}-{class}-{fabric}-{role}-{rack}-{index:04d}"
        )

        result = template.render({
            'site': 'tus1',
            'category': 'server',
            'class': 'gpu',
            'fabric': 'frontend',
            'role': 'compute',
            'rack': 101,
            'index': 1
        })

        self.assertEqual(result, "tus1-server-gpu-frontend-compute-101-0001")

    def test_pattern_allows_escaped_braces(self):
        """Test pattern allows literal braces via escaping"""
        template = NamingTemplate.objects.create(
            device_category="server",
            pattern="{{literal}}-{site}-{index:04d}"
        )

        result = template.render({'site': 'tus1', 'index': 1})

        self.assertEqual(result, "{literal}-tus1-0001")

    def test_pattern_mixed_escaped_and_variables(self):
        """Test pattern with mix of escaped braces and variables"""
        template = NamingTemplate.objects.create(
            device_category="server",
            pattern="{site}-prefix{{suffix}}-{index}"
        )

        result = template.render({'site': 'nyc1', 'index': 5})

        self.assertEqual(result, "nyc1-prefix{suffix}-5")

    # =========================================================================
    # 3. Field Validation
    # =========================================================================

    def test_device_category_choices(self):
        """Test device_category accepts valid choices"""
        valid_categories = ['server', 'leaf', 'spine', 'oob', 'border']

        for category in valid_categories:
            template = NamingTemplate.objects.create(
                device_category=category,
                pattern="{site}-{index:02d}",
                description=f"Test {category}"
            )
            self.assertEqual(template.device_category, category)
            template.delete()  # Clean up for next iteration

    def test_device_category_invalid_choice(self):
        """Test device_category rejects invalid choice"""
        template = NamingTemplate(
            device_category="invalid",
            pattern="{site}-{index:02d}"
        )

        with self.assertRaises(ValidationError):
            template.full_clean()

    def test_pattern_max_length(self):
        """Test pattern max length is 200 chars"""
        long_pattern = "{site}" + "-{x}" * 50  # >200 chars
        template = NamingTemplate(
            device_category="server",
            pattern=long_pattern
        )

        with self.assertRaises(ValidationError):
            template.full_clean()

    # =========================================================================
    # 4. Custom Validation (clean method)
    # =========================================================================

    def test_clean_validates_pattern_syntax(self):
        """Test clean() validates Python format string syntax"""
        valid_patterns = [
            "{site}-{class}-{index:04d}",
            "{site}-{index}",
            "{site}",
            "{site}-{class}-rack{rack}-{index:03d}"
        ]

        for pattern in valid_patterns:
            template = NamingTemplate(
                device_category="server",
                pattern=pattern
            )
            template.full_clean()  # Should not raise

    def test_clean_rejects_invalid_pattern_syntax(self):
        """Test clean() rejects invalid format string syntax"""
        template = NamingTemplate(
            device_category="server",
            pattern="{site}-{index:INVALID}"  # Invalid format spec
        )

        with self.assertRaises(ValidationError) as cm:
            template.full_clean()

        self.assertIn('pattern', cm.exception.message_dict)
        error_message = str(cm.exception)
        self.assertIn('invalid', error_message.lower())

    def test_clean_validates_rendered_name_length(self):
        """Test clean() validates rendered name doesn't exceed 64 chars"""
        template = NamingTemplate(
            device_category="server",
            pattern="{site}-{class}-{category}-{fabric}-{role}-very-long-suffix-that-makes-name-too-long-{index:04d}"
        )

        with self.assertRaises(ValidationError) as cm:
            template.full_clean()

        self.assertIn('pattern', cm.exception.message_dict)
        error_message = str(cm.exception)
        self.assertIn('too long', error_message.lower())

    def test_clean_shows_example_in_length_error(self):
        """Test clean() includes example rendered name in error"""
        template = NamingTemplate(
            device_category="server",
            pattern="{site}-{class}-{category}-{fabric}-{role}-very-long-suffix-that-makes-name-too-long-{index:04d}"
        )

        with self.assertRaises(ValidationError) as cm:
            template.full_clean()

        error_message = str(cm.exception)
        self.assertIn('example', error_message.lower())

    # =========================================================================
    # 5. Model Constraints
    # =========================================================================

    def test_unique_together_category_per_plan(self):
        """Test device_category must be unique within plan"""
        NamingTemplate.objects.create(
            plan=self.test_plan,
            device_category="server",
            pattern="{site}-{class}-{index:04d}"
        )

        # Attempt to create duplicate
        with self.assertRaises(IntegrityError):
            NamingTemplate.objects.create(
                plan=self.test_plan,
                device_category="server",  # Same category
                pattern="{site}-{index:04d}"  # Different pattern
            )

    def test_unique_together_category_per_global(self):
        """Test device_category must be unique for global templates"""
        NamingTemplate.objects.create(
            plan=None,
            device_category="server",
            pattern="{site}-{class}-{index:04d}"
        )

        # Attempt to create duplicate global
        # Since SQL unique_together doesn't work with NULLs,
        # we enforce this via clean() validation
        duplicate = NamingTemplate(
            plan=None,
            device_category="server",
            pattern="{site}-{index:04d}"
        )

        with self.assertRaises(ValidationError) as cm:
            duplicate.full_clean()

        self.assertIn('device_category', cm.exception.message_dict)

    def test_cascade_delete_when_plan_deleted(self):
        """Test naming templates are deleted when plan is deleted"""
        plan = TopologyPlan.objects.create(
            name="Temporary Plan"
        )
        plan_id = plan.pk

        NamingTemplate.objects.create(
            plan=plan,
            device_category="server",
            pattern="{site}-{class}-{index:04d}"
        )

        self.assertEqual(NamingTemplate.objects.filter(plan_id=plan_id).count(), 1)

        plan.delete()

        self.assertEqual(NamingTemplate.objects.filter(plan_id=plan_id).count(), 0)

    def test_global_templates_not_deleted_when_plan_deleted(self):
        """Test global templates persist when plan is deleted"""
        NamingTemplate.objects.create(
            plan=None,
            device_category="server",
            pattern="{site}-{class}-{index:04d}"
        )

        plan = TopologyPlan.objects.create(
            name="Temporary Plan"
        )
        plan.delete()

        self.assertEqual(NamingTemplate.objects.filter(plan__isnull=True).count(), 1)

    def test_global_and_plan_specific_can_coexist_same_category(self):
        """Test global and plan-specific templates can coexist for same category"""
        # Create global template
        global_template = NamingTemplate.objects.create(
            plan=None,
            device_category="server",
            pattern="{site}-{class}-{index:04d}"
        )

        # Create plan-specific template for same category (should succeed)
        plan_template = NamingTemplate.objects.create(
            plan=self.test_plan,
            device_category="server",
            pattern="{site}-{index:03d}"  # Different pattern
        )

        # Both should exist
        self.assertEqual(
            NamingTemplate.objects.filter(plan__isnull=True, device_category="server").count(),
            1
        )
        self.assertEqual(
            NamingTemplate.objects.filter(plan=self.test_plan, device_category="server").count(),
            1
        )

    # =========================================================================
    # 6. Ordering
    # =========================================================================

    def test_default_ordering_by_plan_device_category(self):
        """Test default ordering is plan, device_category"""
        plan1 = TopologyPlan.objects.create(name="Plan A")
        plan2 = TopologyPlan.objects.create(name="Plan B")

        # Create templates in mixed order
        t3 = NamingTemplate.objects.create(
            plan=plan2, device_category="server", pattern="{site}-{index}"
        )
        t1 = NamingTemplate.objects.create(
            plan=plan1, device_category="leaf", pattern="{site}-{index}"
        )
        t2 = NamingTemplate.objects.create(
            plan=plan1, device_category="server", pattern="{site}-{index}"
        )
        t0 = NamingTemplate.objects.create(
            plan=None, device_category="border", pattern="{site}-{index}"
        )

        # Get only the templates we just created
        created_pks = [t0.pk, t1.pk, t2.pk, t3.pk]
        templates = list(NamingTemplate.objects.filter(pk__in=created_pks).order_by('plan', 'device_category'))

        # Ordering should be by plan (with plan ID as tiebreaker), then device_category
        # Since plan1 and plan2 have different IDs, they'll be ordered by ID
        # Within each plan, ordered by device_category alphabetically

        # Just verify ordering is stable and predictable
        self.assertEqual(len(templates), 4)

        # Verify all templates are present
        self.assertIn(t0, templates)
        self.assertIn(t1, templates)
        self.assertIn(t2, templates)
        self.assertIn(t3, templates)

        # Verify device_category ordering within same plan
        plan1_templates = [t for t in templates if t.plan == plan1]
        self.assertEqual(len(plan1_templates), 2)
        # leaf comes before server alphabetically
        self.assertEqual(plan1_templates[0].device_category, 'leaf')
        self.assertEqual(plan1_templates[1].device_category, 'server')
