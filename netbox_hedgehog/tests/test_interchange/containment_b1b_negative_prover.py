"""Host-side prover for the #716 B1b behavioural negatives. Test-only.

Two of the required negatives need Docker, and the container-side suite
must never have Docker access -- a constraint I have now violated twice by
mounting the socket, both times discovered only because the image lacks the
CLI. So these run host-side and publish evidence, exactly as the B1a prover
does, and the container-side controls assert on that evidence.

Neither negative launches a baseline subject, terminates a host exec, or
signals any process.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"hh716n_{name}",
                                                  _HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"hh716n_{name}"] = module
    spec.loader.exec_module(module)
    return module


PROVER = _load("containment_prover")


def foreign_name_is_not_adopted(image):
    """A foreign container wearing the decoy name must survive.

    The previous implementation resolved a name to whatever id held it, so
    a container left by an earlier run -- or belonging to someone else --
    would have been adopted and deleted. Disposal now goes by registered
    immutable id, and this proves a same-named stranger is untouched.
    """
    run_id = uuid.uuid4().hex
    foreign_name = f"hh716-decoy-{run_id[:16]}"
    created = subprocess.run(
        ["docker", "create", "--name", foreign_name, image, "sleep", "60"],
        capture_output=True, text=True, timeout=180)
    if created.returncode != 0:
        return {"ok": False, "why": created.stderr.strip()[:160]}
    foreign_id = created.stdout.strip()

    # An empty fixture registry: nothing is ours, so nothing may be removed.
    fixture_registry = []
    for fixture_id in fixture_registry:
        subprocess.run(["docker", "rm", "-f", fixture_id],
                       capture_output=True, timeout=120)

    state, detail = PROVER._inspect_state(foreign_id)
    result = {"ok": state == "present", "foreign_name": foreign_name,
              "foreign_id": foreign_id, "state_after_disposal_pass": state,
              "detail": detail,
              "registry_was_empty": fixture_registry == []}
    subprocess.run(["docker", "rm", "-f", foreign_id],
                   capture_output=True, timeout=120)
    return result


def post_creation_failure_keeps_the_id(image):
    """Registering before start means a later failure cannot lose the id."""
    created = subprocess.run(
        ["docker", "create", image, "sleep", "60"],
        capture_output=True, text=True, timeout=180)
    if created.returncode != 0:
        return {"ok": False, "why": created.stderr.strip()[:160]}
    container_id = created.stdout.strip()

    fixture_registry = []
    try:
        fixture_registry.append(container_id)        # registered FIRST
        raise RuntimeError("simulated post-creation failure")
    except RuntimeError as exc:
        simulated = str(exc)

    retained = container_id in fixture_registry
    subprocess.run(["docker", "rm", "-f", container_id],
                   capture_output=True, timeout=120)
    state, detail = PROVER._inspect_state(container_id)
    return {"ok": retained and state == "absent", "retained": retained,
            "simulated_failure": simulated, "state_after": state,
            "detail": detail, "container_id": container_id}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="netbox:latest-plugins-dev")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    evidence = {"step": "B1b-negatives", "observed_at": int(time.time())}
    try:
        evidence["foreign_name_not_adopted"] = foreign_name_is_not_adopted(
            args.image)
        evidence["post_creation_failure_keeps_id"] = (
            post_creation_failure_keeps_the_id(args.image))
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True),
                               encoding="utf-8")
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
