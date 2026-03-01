"""
Device Generation Job for NetBox Background Execution.

Issue: https://github.com/afewell-hh/hh-netbox-plugin/issues/132

This job wraps the DeviceGenerator service to run device generation
as a NetBox background job, providing progress tracking and avoiding
browser timeouts for long-running operations.
"""

from netbox.jobs import JobRunner
from netbox_hedgehog.services.device_generator import DeviceGenerator
from netbox_hedgehog.choices import GenerationStatusChoices


class DeviceGenerationJob(JobRunner):
    """
    Background job for generating NetBox devices from a TopologyPlan.

    Executes DeviceGenerator.generate_all() in the netbox-worker process
    via django-rq. Progress and logs are visible in NetBox Jobs UI.

    The job updates GenerationState status throughout execution:
    - IN_PROGRESS when starting
    - GENERATED on success
    - FAILED on error
    """

    class Meta:
        name = "Generate Topology Devices"
        description = "Generate devices, interfaces, and cables from topology plan"

    def run(self, plan_id, *args, **kwargs):
        """
        Execute device generation for the specified TopologyPlan.

        Args:
            plan_id: Primary key of the TopologyPlan to generate devices for

        Progress is logged via self.logger (visible in NetBox Jobs UI).
        """
        from netbox_hedgehog.models import TopologyPlan

        # Get the TopologyPlan instance from plan_id
        plan = TopologyPlan.objects.get(pk=plan_id)

        self.logger.info(f"Starting device generation for plan: {plan.name} (ID: {plan.pk})")

        # Get or create GenerationState and update to IN_PROGRESS
        from netbox_hedgehog.models import GenerationState
        state, created = GenerationState.objects.get_or_create(
            plan=plan,
            defaults={
                'status': GenerationStatusChoices.IN_PROGRESS,
                'device_count': 0,
                'interface_count': 0,
                'cable_count': 0,
                'snapshot': {},
                'job': self.job,
            }
        )
        if not created:
            state.status = GenerationStatusChoices.IN_PROGRESS
            state.job = self.job
            state.save()

        self.logger.info("Status updated to IN_PROGRESS")

        # Execute device generation
        generator = DeviceGenerator(plan=plan, logger=self.logger)

        try:
            self.logger.info("Calling DeviceGenerator.generate_all()...")
            result = generator.generate_all()

            # Success: Update state to GENERATED
            # Note: DeviceGenerator._upsert_generation_state() deletes and recreates
            # the GenerationState, so we must re-fetch it and re-link the job
            plan.refresh_from_db()
            state = plan.generation_state
            state.status = GenerationStatusChoices.GENERATED
            state.job = self.job  # Re-link job to new state object
            state.save()

            self.logger.info(
                f"Generation complete: {result.device_count} devices, "
                f"{result.interface_count} interfaces, {result.cable_count} cables"
            )

        except Exception as exc:
            import traceback as tb
            full_traceback = tb.format_exc()
            # Failure: Update state to FAILED
            # Re-fetch state in case it was recreated during partial execution
            plan.refresh_from_db()
            if hasattr(plan, 'generation_state'):
                state = plan.generation_state
                state.status = GenerationStatusChoices.FAILED
                state.job = self.job  # Re-link job to state
                state.save()

            self.logger.error(f"Generation failed: {exc}")
            self.logger.error(f"Full traceback:\n{full_traceback}")
            # Re-raise exception so NetBox marks job as failed
            raise
