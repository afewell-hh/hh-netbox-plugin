"""T3 emission-path inventory for #682's UI/paste seam.

Test-only evidence inventory.  It deliberately records future UI paths as
``unverified`` rather than pretending absent code is already safe.  Dev B owns
the inventory and Dev A is its independent reviewer (lead confirmation on
#681); no UI implementation or merge may self-certify this inventory.

A status here is a security claim, so a claim found to be false is corrected
immediately rather than waiting for the code it describes to be fixed: #687
downgraded ``source-located errors`` to ``known_false`` on that basis, and
``test_interchange_inventory_integrity`` binds that status to the decoder's
actual observed behaviour so it cannot drift back without the fix.
"""

from netbox_hedgehog.tests.seam_evidence import EmissionPath, SeamInventory


UI_PASTE_INVENTORY = SeamInventory(
    seam="interchange-ui-paste",
    secret_fields=("kubernetes_token", "kubernetes_ca_cert", "password", "secret"),
    touches_credentials=True,
    touches_audit=True,
    notes=("#684 paste-only GREEN. Owner: Dev B; independent reviewer: Dev A; "
           "lead verifies the inventory and paired evidence before merge. "
           "The asserted paths are exercised by U26/U27/U32; unverified "
           "paths remain explicitly visible rather than inferred safe. "
           "#687 downgraded 'source-located errors' to known_false after the "
           "#686 secure-ingress review measured the decoder echoing untrusted "
           "input; its remediation is #688 and it must not be counted as "
           "secret-absence coverage in the meantime."),
    paths=(
        EmissionPath("paste request body", "import_template", "asserted",
                     "U26 submits a synthetic credential and proves the rendered response omits its value."),
        EmissionPath("form re-render HTML", "import_template", "asserted",
                     "U26 proves a source-located validation re-render never echoes the submitted credential."),
        EmissionPath("source-located errors", "error_handling", "known_false",
                     "DOWNGRADED from asserted by #687; the previous status was false. It "
                     "generalised U26 -- which posts valid JSON and therefore only exercises "
                     "semantic credential rejection -- to the whole error-handling surface. "
                     "The YAML decoder does not hold that boundary: _yaml_restricted raises "
                     "_error(str(exc)) in both its event-scan and constructor branches, and "
                     "PyYAML embeds the offending source line verbatim in that message, so a "
                     "credential authored on a malformed line is echoed back through the "
                     "rendered error. Untrusted mapping keys separately reach "
                     "SourceLocation.path, which the import template renders. This row is "
                     "therefore evidence of a known disclosure, not of secrecy. Decoder "
                     "remediation is #688; the paired behaviour check lives in "
                     "test_interchange_inventory_integrity.py and will not permit this row "
                     "to return to asserted while the decoder still echoes untrusted input.",
                     owner_issue="#688"),
        EmissionPath("template context", "import_template", "asserted",
                     "U26 exercises the rendered context through the real Django response, not a template mock."),
        EmissionPath("interchange audit", "changelog", "asserted",
                     "U27 proves successful UI import records actor, time, scope, provenance, and no secret."),
        EmissionPath("failed import audit", "changelog", "asserted",
                     "U32 proves failed paste validation retains a minimal actor/time/scope/provenance audit without the submitted secret."),
        EmissionPath("ObjectChange/event payload", "event", "unverified",
                     "Lifecycle writes can emit NetBox snapshots and webhooks."),
        EmissionPath("download response and filename", "exporter", "asserted",
                     "U27 downloads a successful imported draft and proves the response omits the secret sentinel."),
        EmissionPath("application logs and traces", "log", "unverified",
                     "Parser and view exceptions must not serialize pasted content."),
        EmissionPath("retained artifact", "retention_backup", "asserted",
                     "U27 inspects the persisted draft after a real import and proves the secret sentinel is absent."),
        EmissionPath("file upload/quarantine/reaper", "retention_backup", "out_of_scope",
                     "Paste-only #682 creates no retained upload; #678 owns upload quarantine/reaper.",
                     owner_issue="#678"),
    ),
)
