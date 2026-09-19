"""#687: keep the T3 inventory's source-location claim tied to real behaviour.

Test-only. This module changes no production code and authorizes no upload
surface; #678's no-file-upload boundary and the paste-only UI are untouched.

The #686 secure-ingress review found that
``interchange_ui_inventory.UI_PASTE_INVENTORY`` marked ``source-located errors``
as ``asserted`` on the strength of U26, which posts valid JSON and therefore
only exercises semantic credential rejection. The YAML decoder does not hold
that boundary. #687 downgrades the row to ``known_false``; this module is the
part that makes the downgrade mean something.

A status check alone would be self-referential -- it would pass just as happily
if someone edited the string back. So the binding test below drives the *real*
decoder and requires the declared status to agree with what the decoder
actually does:

  decoder echoes untrusted input  ->  the row must be ``known_false``
  decoder echoes nothing          ->  the row must no longer be ``known_false``

Restoring ``asserted`` while the leak is still present fails. Remediating the
decoder under #688 without updating the inventory also fails, which is how the
row gets flipped back honestly rather than optimistically.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.test import SimpleTestCase

from netbox_hedgehog import interchange
from netbox_hedgehog.tests.interchange_ui_inventory import UI_PASTE_INVENTORY
from netbox_hedgehog.tests.seam_evidence import EmissionPath


#: The row this module governs.
ROW_NAME = "source-located errors"

#: Remediation owner for the decoder defect. Referenced by the row itself.
REMEDIATION_ISSUE = "#688"

#: Distinctive enough that a match cannot be coincidental, and shaped like the
#: things that actually matter: a credential value, and a mapping key.
#:
#: Deliberately SHORT, and placed early on their line by the probes below.
#: PyYAML truncates the source-line snippet it embeds in an error at roughly
#: fifty characters, appending " ... ". A long sentinel, or one pushed right by
#: a long key, is therefore echoed only in part -- still a disclosure, but one
#: an exact-substring check does not see. Probe A originally used a 36-character
#: value behind an 18-character key and silently failed to detect a reverted
#: scanner branch for exactly that reason. Keep these short, keep them early,
#: and see `_echoes` for the partial-disclosure check that backs them up.
SENTINEL_VALUE = "HH687VALSENT"
SENTINEL_KEY = "hh687KeySent"

#: Shortest run of a sentinel whose appearance still proves submitted bytes
#: reached the surface. Short enough to survive truncation, long enough that a
#: coincidental match in fixed diagnostic text is not credible.
_PARTIAL_ECHO_CHARS = 8


def _echoes(surface: str) -> bool:
    """True if `surface` carries a sentinel whole *or* truncated.

    A partially echoed secret is a leak. Checking only for the whole string
    lets a truncating formatter hide one.
    """
    for sentinel in (SENTINEL_VALUE, SENTINEL_KEY):
        if sentinel in surface:
            return True
        if sentinel[:_PARTIAL_ECHO_CHARS] in surface:
            return True
    return False


@dataclass(frozen=True)
class DecoderProbe:
    """One attempt to make the decoder echo untrusted input back to a caller."""

    name: str
    reached_error_path: bool
    echoed: bool
    detail: str


def _probe_scanner_error_message() -> DecoderProbe:
    """A credential authored on a line the YAML scanner rejects.

    ``_yaml_restricted`` passes ``str(exc)`` straight into ``_error``; PyYAML's
    message embeds the offending source line, so the credential rides along.
    """
    document = f'token: "{SENTINEL_VALUE}\n'
    try:
        interchange.decode_document(document)
    except interchange.InterchangeError as exc:
        return DecoderProbe(
            "YAML scanner error message",
            reached_error_path=True,
            echoed=_echoes(str(exc)),
            detail=str(exc),
        )
    return DecoderProbe("YAML scanner error message", False, False,
                        "decode_document did not raise for a malformed document")


def _probe_untrusted_key_in_source_location() -> DecoderProbe:
    """An attacker-chosen mapping key reaching ``SourceLocation.path``.

    ``_json_pairs`` builds the location as ``f"$.{key}"`` from the submitted
    key, and the import template renders ``location.path``.
    """
    document = f'{{"{SENTINEL_KEY}": 1, "{SENTINEL_KEY}": 2}}'
    try:
        interchange.decode_document(document)
    except interchange.InterchangeError as exc:
        location = getattr(exc, "source_location", None)
        rendered = f"{exc} {getattr(location, 'path', '')}"
        return DecoderProbe(
            "untrusted key in source location",
            reached_error_path=True,
            echoed=_echoes(rendered),
            detail=rendered,
        )
    return DecoderProbe("untrusted key in source location", False, False,
                        "decode_document did not raise for a duplicate mapping key")


def run_decoder_probes() -> list:
    """Every probe drives the real decoder; none mocks it.

    That is a deliberate limit as well as a strength. These two reach the YAML
    *scanner* branch and the JSON duplicate-key path. They cannot reach the
    ``yaml.load`` constructor branch, which only fails for inputs the scanner
    already accepted; provoking it needs a patched ``yaml.load``. That branch is
    covered at the core level by
    ``test_interchange.test_error_disclosure.DecoderDisclosureTestCase``.

    Recorded here so the split is visible: a reverted constructor branch fails
    that module, not this one. If this module is ever treated as the sole guard
    for decoder disclosure, that assumption is wrong.
    """
    return [_probe_scanner_error_message(), _probe_untrusted_key_in_source_location()]


def source_location_row() -> EmissionPath:
    for path in UI_PASTE_INVENTORY.paths:
        if path.name == ROW_NAME:
            return path
    raise AssertionError(
        f"the {ROW_NAME!r} row has been removed from UI_PASTE_INVENTORY. A row "
        f"recording a known disclosure is deleted only when {REMEDIATION_ISSUE} "
        f"has remediated it and this module's probes show no echo; deleting it "
        f"otherwise erases the gap instead of closing it."
    )


class SourceLocationDisclosureTestCase(SimpleTestCase):
    """The downgraded row, bound to the decoder's observed behaviour."""

    def test_probes_still_reach_the_decoder_error_path(self):
        """Guard against the binding test passing for the wrong reason.

        If a probe stops raising, it stops exercising the boundary, and
        ``echoed`` would be False for a reason that has nothing to do with the
        leak being fixed -- which the binding test would read as remediation.
        Repair a broken probe; never delete it.
        """
        for probe in run_decoder_probes():
            with self.subTest(probe=probe.name):
                self.assertTrue(
                    probe.reached_error_path,
                    f"{probe.name}: {probe.detail}. This probe no longer reaches "
                    f"the decoder's error path, so it can no longer detect the "
                    f"disclosure it exists to detect.",
                )

    def test_declared_status_matches_observed_decoder_behaviour(self):
        """The row may only claim secrecy the decoder actually provides."""
        probes = run_decoder_probes()
        echoing = [p for p in probes if p.echoed]
        row = source_location_row()

        if echoing:
            self.assertEqual(
                row.status, "known_false",
                "the decoder still echoes untrusted input back through its error "
                "path ("
                + "; ".join(p.name for p in echoing)
                + f"), so the {ROW_NAME!r} row cannot claim any status other than "
                f"known_false. Restoring 'asserted' here would reinstate exactly "
                f"the false security claim {REMEDIATION_ISSUE} exists to remove.",
            )
        else:
            self.assertNotEqual(
                row.status, "known_false",
                f"no probe observed an echo, which suggests {REMEDIATION_ISSUE} has "
                f"remediated the decoder. Update the {ROW_NAME!r} row to the status "
                f"its new evidence supports, and extend the probes to cover the "
                f"remediated paths, rather than leaving a stale known_false claim.",
            )

    def test_known_false_row_names_its_remediation_and_states_why(self):
        row = source_location_row()
        self.assertEqual(row.status, "known_false")
        self.assertEqual(row.owner_issue, REMEDIATION_ISSUE)
        self.assertIn("#687", row.detail)
        self.assertGreater(
            len(row.detail), 180,
            "a known_false row must carry a reason a reviewer can act on, not a label",
        )

    def test_known_false_is_never_counted_as_secret_absence_coverage(self):
        row = source_location_row()
        self.assertNotIn(row, UI_PASTE_INVENTORY.by_status("asserted"))
        self.assertNotIn(row, UI_PASTE_INVENTORY.proven_paths())
        self.assertIn(row, UI_PASTE_INVENTORY.known_false_paths())

    def test_schema_requires_a_remediation_issue_for_known_false(self):
        """An unowned known_false row would be a gap with nobody to close it."""
        with self.assertRaises(ValueError):
            EmissionPath("unowned", "error_handling", "known_false", "no owner named")

    def test_unrelated_inventory_rows_are_preserved(self):
        """#687 touches exactly one row; collateral drift must fail here."""
        expected = {
            "paste request body": "asserted",
            "form re-render HTML": "asserted",
            "source-located errors": "known_false",
            "template context": "asserted",
            "interchange audit": "asserted",
            "failed import audit": "asserted",
            "ObjectChange/event payload": "unverified",
            "download response and filename": "asserted",
            "application logs and traces": "unverified",
            "retained artifact": "asserted",
            "file upload/quarantine/reaper": "out_of_scope",
        }
        self.assertEqual({p.name: p.status for p in UI_PASTE_INVENTORY.paths}, expected)

    def test_upload_boundary_is_untouched_by_this_correction(self):
        """#678's no-upload boundary is not in scope and must not have moved."""
        upload = next(p for p in UI_PASTE_INVENTORY.paths
                      if p.name.startswith("file upload"))
        self.assertEqual(upload.status, "out_of_scope")
        self.assertEqual(upload.owner_issue, "#678")
