"""T3 emission-path inventory for #682's UI/paste seam.

Test-only evidence inventory.  It deliberately records future UI paths as
``unverified`` rather than pretending absent code is already safe.  Dev B owns
the inventory and Dev A is its independent reviewer (lead confirmation on
#681); no UI implementation or merge may self-certify this inventory.
"""

from netbox_hedgehog.tests.seam_evidence import EmissionPath, SeamInventory


UI_PASTE_INVENTORY = SeamInventory(
    seam="interchange-ui-paste",
    secret_fields=("kubernetes_token", "kubernetes_ca_cert", "password", "secret"),
    touches_credentials=True,
    touches_audit=True,
    notes=("#682 is RED only. Owner: Dev B; independent reviewer: Dev A; "
           "lead verifies the inventory and paired evidence before merge."),
    paths=(
        EmissionPath("paste request body", "import_template", "unverified",
                     "Pasted document reaches the import form; U26 must reject values safely."),
        EmissionPath("form re-render HTML", "import_template", "unverified",
                     "Validation failures must not echo a secret-shaped submitted value."),
        EmissionPath("source-located errors", "error_handling", "unverified",
                     "Errors may show location but never a credential value."),
        EmissionPath("template context", "import_template", "unverified",
                     "Rendered context must contain only safe error and provenance facts."),
        EmissionPath("interchange audit", "changelog", "unverified",
                     "Successful lifecycle mutation needs actor/time/scope/provenance evidence."),
        EmissionPath("ObjectChange/event payload", "event", "unverified",
                     "Lifecycle writes can emit NetBox snapshots and webhooks."),
        EmissionPath("download response and filename", "exporter", "unverified",
                     "View-authorized export must carry no secret material."),
        EmissionPath("application logs and traces", "log", "unverified",
                     "Parser and view exceptions must not serialize pasted content."),
        EmissionPath("retained artifact", "retention_backup", "unverified",
                     "Draft/locked artifact paths require paired evidence when implemented."),
        EmissionPath("file upload/quarantine/reaper", "retention_backup", "out_of_scope",
                     "Paste-only #682 creates no retained upload; #678 owns upload quarantine/reaper.",
                     owner_issue="#678"),
    ),
)
