"""
Browser UX tests for the Generate / Regenerate / Export workflow.

Reconciled with the current NetBox UI (DIET-616): the plan-detail page uses a
unified ``#generate-btn`` that opens a confirmation modal and posts to the
ASYNC ``generate-update`` endpoint (redirects to the NetBox job page; a worker
performs generation). There is no legacy ``/generate/`` preview navigation.

Interaction contract (verified live + confirmed by Dev B):
  * ungenerated plan  -> button "Generate Devices"   -> #expectationGuidanceModal
  * out-of-sync plan  -> button "Update Devices"      -> #destructiveConfirmModal
  * in-sync plan      -> button "Regenerate Devices"  -> #destructiveConfirmModal
  * #destructiveConfirmModal (#confirmDestructiveBtn "Yes, Continue")
        chains to #expectationGuidanceModal
  * #expectationGuidanceModal (#proceedGenerationBtn "Start Generation")
        submits #generate-form -> POST generate-update -> /core/jobs/<id>/
  * Export YAML: <a class="btn"> only when generated; disabled <button> otherwise
"""

import re
import pytest
from playwright.sync_api import Page, expect
from .conftest import NETBOX_URL

PLAN1 = "UX Test Plan 1 - Generate Devices"       # ungenerated, ready
PLAN2 = "UX Test Plan 2 - Multi-Plan Isolation"   # pre-generated
PLAN3 = "UX Test Plan 3 - Empty (Warnings)"       # empty

PLAN_DETAIL_RE = re.compile(r'.*/plugins/hedgehog/topology-plans/\d+/$')
JOB_URL_RE = re.compile(r'.*/core/jobs/\d+/.*')


# --------------------------------------------------------------------------- #
# Helpers — dynamic plan lookup by NAME (no fixed PKs) and real modal/async flow
# --------------------------------------------------------------------------- #

def open_plan_by_name(page: Page, name: str) -> None:
    """Open a plan's detail page via the list, matched by fixture name."""
    page.goto(f'{NETBOX_URL}/plugins/hedgehog/topology-plans/')
    link = page.get_by_role("link", name=name, exact=True)
    if link.count() == 0:
        pytest.skip(f"UX test plan {name!r} not found - run setup_ux_test_data --clean")
    link.first.click()
    expect(page).to_have_url(PLAN_DETAIL_RE)


def start_generation_via_modal(page: Page) -> None:
    """Drive the real confirmation-modal progression, then submit (async).

    Handles both first-generation (expectation modal directly) and
    update/regeneration (destructive modal -> expectation modal). Leaves the
    browser on whatever URL the POST redirects to (job page on success, or the
    plan detail with an error for an invalid/empty plan).
    """
    btn = page.locator('#generate-btn')
    expect(btn).to_be_visible()
    target = btn.get_attribute('data-bs-target')
    btn.click()

    if target == '#destructiveConfirmModal':
        modal = page.locator('#destructiveConfirmModal')
        expect(modal).to_be_visible()
        expect(modal).to_contain_text('Confirm Destructive Regeneration')
        page.click('#confirmDestructiveBtn')

    expect(page.locator('#expectationGuidanceModal')).to_be_visible()
    page.click('#proceedGenerationBtn')


def wait_until_generated(page: Page, plan_name: str, timeout_ms: int = 90000) -> None:
    """Poll the plan detail until the async job completes (Export YAML link
    appears, i.e. generation_state.status == 'generated')."""
    deadline = timeout_ms
    step = 2000
    while deadline > 0:
        open_plan_by_name(page, plan_name)
        if page.locator('a.btn:has-text("Export YAML")').count() > 0:
            return
        page.wait_for_timeout(step)
        deadline -= step
    raise AssertionError(
        f"Async generation for {plan_name!r} did not complete within {timeout_ms}ms")


# --------------------------------------------------------------------------- #
# Navigation + control-visibility
# --------------------------------------------------------------------------- #

class TestGenerateControls:

    def test_navigate_to_topology_plans(self, authenticated_page: Page):
        page = authenticated_page
        page.click('text=Hedgehog')
        page.click('a:has-text("Topology Plans")')
        expect(page).to_have_url(re.compile(r'.*/plugins/hedgehog/topology-plans/.*'))
        expect(page.locator('.page-title, h1.page-title')).to_contain_text('Topology Plans')

    def test_generate_button_visible_on_ungenerated_plan(self, authenticated_page: Page):
        page = authenticated_page
        open_plan_by_name(page, PLAN1)
        btn = page.locator('#generate-btn')
        expect(btn).to_be_visible()
        expect(btn).to_contain_text('Generate Devices')
        expect(btn).to_have_attribute('data-bs-target', '#expectationGuidanceModal')

    def test_generate_opens_expectation_modal_with_counts(self, authenticated_page: Page):
        """Replaces the legacy /generate/ preview-page test: the pre-submit
        expectation modal shows the expected device/interface/cable counts."""
        page = authenticated_page
        open_plan_by_name(page, PLAN1)
        page.locator('#generate-btn').click()
        modal = page.locator('#expectationGuidanceModal')
        expect(modal).to_be_visible()
        expect(modal).to_contain_text(re.compile(r'Devices:', re.I))
        expect(modal).to_contain_text(re.compile(r'Interfaces:', re.I))
        expect(modal).to_contain_text(re.compile(r'Cables:', re.I))
        expect(page.locator('#proceedGenerationBtn')).to_be_visible()


# --------------------------------------------------------------------------- #
# Generate / Regenerate / Export workflows (modal + async job)
# --------------------------------------------------------------------------- #

class TestGenerateWorkflow:

    def test_empty_plan_modal_shows_zero_counts_and_errors_on_submit(
            self, authenticated_page: Page):
        """Empty plan: expectation modal shows zero counts, and submitting
        surfaces the 'requires at least one server class' error (the intentional
        replacement for the retired /generate/ warning page)."""
        page = authenticated_page
        open_plan_by_name(page, PLAN3)
        page.locator('#generate-btn').click()
        modal = page.locator('#expectationGuidanceModal')
        expect(modal).to_be_visible()
        expect(modal).to_contain_text(re.compile(r'Devices:\s*0', re.I))
        page.click('#proceedGenerationBtn')
        page.wait_for_load_state('load')
        body = page.content().lower()
        assert ('at least one server class' in body or 'cannot generate' in body), \
            "Expected empty-plan generation error not found"

    def test_generate_confirm_creates_devices(self, authenticated_page: Page):
        """Full flow: modal -> Start Generation -> async job page -> worker
        completes -> devices exist. Full request/result assertion."""
        page = authenticated_page
        plan1_pk = _plan_pk_by_name(page, PLAN1)
        open_plan_by_name(page, PLAN1)
        start_generation_via_modal(page)
        # Async: submitting redirects to the NetBox job page.
        expect(page).to_have_url(JOB_URL_RE, timeout=15000)
        # Worker performs generation; wait for completion via plan detail.
        wait_until_generated(page, PLAN1)
        # Verify PLAN 1's OWN generated devices exist (plan-ID scoped — Plan 2 is
        # already generated, so a global-tag check could pass even if Plan 1 failed).
        assert _count_plan_devices(page, plan1_pk) > 0, \
            "Plan 1's generated devices not found (plan-ID scoped)"

    def test_regeneration_uses_destructive_modal(self, authenticated_page: Page):
        """Generated plan: control is 'Regenerate Devices' and opens the
        destructive-confirmation modal (the regeneration warning surface)."""
        page = authenticated_page
        open_plan_by_name(page, PLAN2)
        btn = page.locator('#generate-btn')
        expect(btn).to_contain_text(re.compile(r'Regenerate|Update', re.I))
        expect(btn).to_have_attribute('data-bs-target', '#destructiveConfirmModal')
        btn.click()
        modal = page.locator('#destructiveConfirmModal')
        expect(modal).to_be_visible()
        expect(modal).to_contain_text('Confirm Destructive Regeneration')
        expect(page.locator('#confirmDestructiveBtn')).to_be_visible()

    def test_export_yaml_link_on_generated_plan_downloads(
            self, authenticated_page: Page):
        """Generated plan exposes Export YAML as an enabled link, and clicking
        it produces a YAML download (exercise, not selector-only)."""
        page = authenticated_page
        open_plan_by_name(page, PLAN2)
        export = page.locator('a.btn:has-text("Export YAML")')
        expect(export.first).to_be_visible()
        with page.expect_download(timeout=15000) as dl_info:
            export.first.click()
        download = dl_info.value
        name = download.suggested_filename.lower()
        assert name.endswith(('.yaml', '.yml')), \
            f"Export did not produce a YAML download: {download.suggested_filename}"

    def test_export_yaml_disabled_on_ungenerated_plan(self, authenticated_page: Page):
        """Separate assertion (per Dev B): ungenerated plan shows Export YAML as
        a disabled button, not an enabled link."""
        page = authenticated_page
        open_plan_by_name(page, PLAN3)  # empty, never generated
        assert page.locator('a.btn:has-text("Export YAML")').count() == 0, \
            "Ungenerated plan must not expose an enabled Export YAML link"
        expect(page.locator('button:disabled:has-text("Export YAML")')).to_be_visible()

    def test_permission_denied_without_change_permission(self, viewer_page: Page):
        """Viewer (no change_topologyplan) is denied generation access.

        Dynamic plan lookup by name (no fixed PK): resolve a real plan URL as a
        privileged step is unavailable to the viewer, so derive the pk from the
        detail link the viewer CAN see, then GET its /generate/ URL -> 403.
        """
        page = viewer_page
        page.goto(f'{NETBOX_URL}/plugins/hedgehog/topology-plans/')
        link = page.get_by_role("link", name=PLAN1, exact=True)
        if link.count() == 0:
            pytest.skip("UX test plan data not found - run setup_ux_test_data --clean")
        href = link.first.get_attribute('href')  # e.g. /plugins/hedgehog/topology-plans/75/
        m = re.search(r'/topology-plans/(\d+)/', href)
        assert m, f"Could not resolve plan pk from href {href!r}"
        resp = page.goto(
            f'{NETBOX_URL}/plugins/hedgehog/topology-plans/{m.group(1)}/generate/')
        # Strict HTTP 403 (PermissionRequiredMixin raise_exception), not just text.
        assert resp is not None and resp.status == 403, \
            f"Expected HTTP 403 for viewer generate access, got {getattr(resp, 'status', None)}"
        assert 'access denied' in page.title().lower(), \
            f"Expected Access Denied page, got title: {page.title()}"


# --------------------------------------------------------------------------- #
# Multi-plan isolation + generated artifacts
# --------------------------------------------------------------------------- #

def _plan_pk_by_name(page: Page, name: str) -> str:
    page.goto(f'{NETBOX_URL}/plugins/hedgehog/topology-plans/')
    link = page.get_by_role("link", name=name, exact=True)
    if link.count() == 0:
        pytest.skip(f"UX test plan {name!r} not found - run setup_ux_test_data --clean")
    href = link.first.get_attribute('href')
    m = re.search(r'/topology-plans/(\d+)/', href)
    assert m, f"Could not resolve plan pk from {href!r}"
    return m.group(1)


def _count_plan_devices(page: Page, plan_pk: str) -> int:
    page.goto(
        f'{NETBOX_URL}/dcim/devices/'
        f'?cf_hedgehog_plan_id={plan_pk}&tag=hedgehog-generated')
    rows = page.locator('table.object-list tbody tr, table tbody tr.device')
    if rows.count() == 0:
        rows = page.locator('table tbody tr')
    return rows.count()


def _count_plan_cables(page: Page, plan_pk: str) -> int:
    page.goto(
        f'{NETBOX_URL}/dcim/cables/'
        f'?cf_hedgehog_plan_id={plan_pk}&tag=hedgehog-generated')
    return page.locator('table tbody tr').count()


class TestMultiPlanIsolation:

    def test_generation_creates_cables(self, authenticated_page: Page):
        """After generation, the DCIM cable list contains hedgehog-generated
        cables (interfaces + cables are produced by the async job)."""
        page = authenticated_page
        plan1_pk = _plan_pk_by_name(page, PLAN1)
        open_plan_by_name(page, PLAN1)
        # Generate only if not already generated in this run.
        if page.locator('a.btn:has-text("Export YAML")').count() == 0:
            start_generation_via_modal(page)
            expect(page).to_have_url(JOB_URL_RE, timeout=15000)
            wait_until_generated(page, PLAN1)
        # Plan-ID scoped: Plan 2 is also generated, so a global-tag check could
        # pass even if Plan 1 produced no cables.
        assert _count_plan_cables(page, plan1_pk) > 0, \
            "Expected Plan 1's hedgehog-generated cables after generation"

    def test_plan_scoped_regeneration_isolation(self, authenticated_page: Page):
        """Regenerating Plan 1 must not change Plan 2's generated devices."""
        page = authenticated_page

        # Ensure Plan 1 is generated.
        open_plan_by_name(page, PLAN1)
        if page.locator('a.btn:has-text("Export YAML")').count() == 0:
            start_generation_via_modal(page)
            expect(page).to_have_url(JOB_URL_RE, timeout=15000)
            wait_until_generated(page, PLAN1)

        # Plan 2 is pre-generated; record its device count.
        plan2_pk = _plan_pk_by_name(page, PLAN2)
        before = _count_plan_devices(page, plan2_pk)
        assert before > 0, "Plan 2 should be pre-generated with devices"

        # Regenerate Plan 1 (destructive modal -> expectation modal -> async).
        open_plan_by_name(page, PLAN1)
        start_generation_via_modal(page)
        expect(page).to_have_url(JOB_URL_RE, timeout=15000)
        wait_until_generated(page, PLAN1)

        # Plan 2 device count is unchanged (plan-scoped isolation).
        after = _count_plan_devices(page, plan2_pk)
        assert after == before, \
            f"Plan 2 device count changed after regenerating Plan 1: {before} -> {after}"
