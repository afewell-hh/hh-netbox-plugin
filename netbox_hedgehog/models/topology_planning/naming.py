"""
Naming template models for topology planning.

NamingTemplate enables customizable device naming patterns.
"""

from django.db import models
from django.core.exceptions import ValidationError
from django.urls import reverse
from netbox.models import NetBoxModel

from netbox_hedgehog.choices import DeviceCategoryChoices


class NamingTemplate(NetBoxModel):
    """
    Device naming pattern template.

    Supports plan-specific and global default naming templates.
    Uses Python format string syntax for patterns.

    Example patterns:
    - "{site}-{class}-{index:04d}" → "tus1-gpu-0042"
    - "{site}-{fabric}-leaf-{index:02d}" → "nyc1-fe-leaf-05"
    """

    plan = models.ForeignKey(
        to='netbox_hedgehog.TopologyPlan',
        on_delete=models.CASCADE,
        related_name='naming_templates',
        null=True,
        blank=True,
        help_text="Plan this template belongs to (null = global default)"
    )

    device_category = models.CharField(
        max_length=50,
        choices=DeviceCategoryChoices,
        help_text="Device category this template applies to"
    )

    pattern = models.CharField(
        max_length=200,
        help_text="Python format string pattern (e.g., '{site}-{class}-{index:04d}')"
    )

    description = models.TextField(
        blank=True,
        help_text="Optional description of this naming template"
    )

    class Meta:
        ordering = ['plan', 'device_category']
        unique_together = [('plan', 'device_category')]
        verbose_name = "Naming Template"
        verbose_name_plural = "Naming Templates"

    def __str__(self):
        """String representation"""
        plan_name = self.plan.name if self.plan else "Global"
        return f"{plan_name} / {self.device_category}: {self.pattern}"

    def get_absolute_url(self):
        """Get absolute URL for this object"""
        return reverse('plugins:netbox_hedgehog:namingtemplate', args=[self.pk])

    def render(self, context):
        """
        Render the pattern with the given context.

        Args:
            context: Dictionary of variable values

        Returns:
            Rendered device name string

        Raises:
            KeyError: If a required variable is missing from context
            ValueError: If pattern formatting fails
        """
        try:
            return self.pattern.format(**context)
        except KeyError as e:
            # Extract the missing variable name from the exception
            missing_var = str(e).strip("'")
            raise ValueError(
                f"Missing required variable '{missing_var}' for pattern '{self.pattern}'"
            ) from e

    def clean(self):
        """Custom validation"""
        super().clean()

        # Enforce uniqueness for global templates (plan=None)
        # SQL unique_together doesn't work with NULLs, so we enforce it here
        if self.plan is None:
            existing = NamingTemplate.objects.filter(
                plan__isnull=True,
                device_category=self.device_category
            )
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError({
                    'device_category': f'A global template for {self.device_category} already exists.'
                })

        # Validate pattern syntax
        self._validate_pattern_syntax()

        # Validate rendered name length
        self._validate_rendered_length()

    def _validate_pattern_syntax(self):
        """Validate that pattern is a valid Python format string"""
        # Test pattern with dummy values
        dummy_context = {
            'site': 'test',
            'class': 'test',
            'category': 'test',
            'fabric': 'test',
            'role': 'test',
            'rack': 999,
            'index': 9999,
        }

        try:
            # Test that pattern can be formatted
            self.pattern.format(**dummy_context)
        except (ValueError, KeyError) as e:
            raise ValidationError({
                'pattern': f'Invalid pattern syntax: {str(e)}'
            })

    def _validate_rendered_length(self):
        """Validate that rendered names won't exceed NetBox device name limit"""
        # NetBox device names have a 64 character limit
        MAX_DEVICE_NAME_LENGTH = 64

        # Generate example with max-length values
        example_context = {
            'site': 'site1234',  # 8 chars
            'class': 'classname123',  # 13 chars
            'category': 'server',  # 6 chars
            'fabric': 'frontend',  # 8 chars
            'role': 'compute',  # 7 chars
            'rack': 9999,  # 4 chars
            'index': 9999,  # 4 chars (before formatting)
        }

        try:
            example_name = self.pattern.format(**example_context)

            if len(example_name) > MAX_DEVICE_NAME_LENGTH:
                raise ValidationError({
                    'pattern': (
                        f'Rendered name too long ({len(example_name)} chars, '
                        f'max {MAX_DEVICE_NAME_LENGTH}). '
                        f'Example: "{example_name}"'
                    )
                })
        except KeyError:
            # Pattern uses variables we didn't provide in example
            # This is OK - just skip length validation
            pass
