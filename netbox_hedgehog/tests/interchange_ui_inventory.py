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
    notes=("#684 paste-only GREEN. Owner: Dev B; independent reviewer: Dev A; "
           "lead verifies the inventory and paired evidence before merge. "
           "The asserted paths are exercised by U26/U27/U32; unverified "
           "paths remain explicitly visible rather than inferred safe."),
    paths=(
        EmissionPath("paste request body", "import_template", "asserted",
                     "U26 submits a synthetic credential and proves the rendered response omits its value."),
        EmissionPath("form re-render HTML", "import_template", "asserted",
                     "U26 proves a source-located validation re-render never echoes the submitted credential."),
        EmissionPath("source-located errors", "error_handling", "asserted",
                     "#688 U26 drives hostile YAML and JSON-key failures through the real "
                     "response; fixed decoder diagnostics retain line/column while omitting "
                     "untrusted values and paths."),
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
                     "#688 proves handled decoder failures do not call a plugin logger, but "
                     "does not yet exercise the django.request/unhandled-exception trace path."),
        EmissionPath("Django exception reporting", "error_handling", "asserted",
                     "#688 U26 proves handled hostile decoder errors do not reach the "
                     "available Django exception-reporting signal."),
        EmissionPath("retained artifact", "retention_backup", "asserted",
                     "U27 inspects the persisted draft after a real import and proves the secret sentinel is absent."),
        EmissionPath("file upload/quarantine/reaper", "retention_backup", "out_of_scope",
                     "Paste-only #682 creates no retained upload; #678 owns upload quarantine/reaper.",
                     owner_issue="#678"),
    ),
)
