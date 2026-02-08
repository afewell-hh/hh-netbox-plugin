"""
Hedgehog Fabric (hhfab) CLI integration for wiring validation (Issue #159).

This module provides helpers to invoke `hhfab validate` for validating
generated wiring YAML diagrams against Hedgehog's authoritative schema.

Execution Model:
    hhfab requires an initialized working directory with:
    - fab.yaml (created by `hhfab init --dev`)
    - include/ directory (for YAML files to validate)
    - result/ directory (for validation outputs)

    The validate_yaml function:
    1. Creates a temporary working directory
    2. Runs `hhfab init --dev` to initialize it
    3. Writes YAML to <tmp>/include/<name>.yaml
    4. Runs `hhfab validate` with cwd in that directory
    5. Cleans up the temporary directory
"""

import subprocess
import tempfile
import os
import shutil
from pathlib import Path
from typing import Tuple


def is_hhfab_available() -> bool:
    """
    Check if hhfab CLI is available in PATH.

    Returns:
        True if hhfab is installed and executable, False otherwise
    """
    try:
        result = subprocess.run(
            ['which', 'hhfab'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def validate_yaml(yaml_content: str, timeout: int = 60) -> Tuple[bool, str, str]:
    """
    Validate Hedgehog wiring YAML using `hhfab validate`.

    Creates a temporary hhfab working directory, initializes it with
    `hhfab init --dev`, writes YAML to include/, and runs validation.

    Args:
        yaml_content: YAML string to validate
        timeout: Command timeout in seconds (default: 60 - includes init time)

    Returns:
        Tuple of (success, stdout, stderr):
        - success: True if validation passed, False if failed or hhfab unavailable
        - stdout: Standard output from hhfab command
        - stderr: Standard error from hhfab command (or helpful message if not installed)

    Example:
        >>> success, stdout, stderr = validate_yaml(yaml_content)
        >>> if not success:
        ...     print(f"Validation failed: {stderr}")
    """
    # Check if hhfab is available
    if not is_hhfab_available():
        return (
            False,
            "",
            "hhfab CLI not found in PATH. Install with: curl -fsSL https://i.hhdev.io/hhfab | bash"
        )

    # Create temporary working directory
    workdir = None
    try:
        workdir = tempfile.mkdtemp(prefix='hhfab_validate_')
        workdir_path = Path(workdir)

        # Initialize hhfab working directory
        init_result = subprocess.run(
            ['hhfab', 'init', '--dev'],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=30
        )

        if init_result.returncode != 0:
            return (
                False,
                init_result.stdout,
                f"hhfab init failed: {init_result.stderr}"
            )

        # Write YAML to include/ directory
        include_dir = workdir_path / 'include'
        include_dir.mkdir(exist_ok=True)

        yaml_file = include_dir / 'wiring.yaml'
        yaml_file.write_text(yaml_content, encoding='utf-8')

        # Run hhfab validate from the working directory
        validate_result = subprocess.run(
            ['hhfab', 'validate'],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        # Clean up temp directory
        shutil.rmtree(workdir)

        # Return result
        return (
            validate_result.returncode == 0,
            validate_result.stdout,
            validate_result.stderr
        )

    except subprocess.TimeoutExpired:
        # Clean up temp directory on timeout
        if workdir and os.path.exists(workdir):
            try:
                shutil.rmtree(workdir)
            except Exception:
                pass

        return (
            False,
            "",
            f"hhfab validate command timed out after {timeout} seconds"
        )

    except Exception as e:
        # Clean up temp directory on error
        if workdir and os.path.exists(workdir):
            try:
                shutil.rmtree(workdir)
            except Exception:
                pass

        return (
            False,
            "",
            f"Error running hhfab validate: {str(e)}"
        )


def validate_plan_yaml(plan) -> Tuple[bool, str, str, str]:
    """
    Generate and validate wiring YAML for a TopologyPlan.

    Convenience wrapper that generates YAML from a plan and validates it.

    Args:
        plan: TopologyPlan instance

    Returns:
        Tuple of (success, yaml_content, stdout, stderr):
        - success: True if validation passed, False otherwise
        - yaml_content: Generated YAML string
        - stdout: Standard output from hhfab command
        - stderr: Standard error from hhfab command

    Example:
        >>> from netbox_hedgehog.models.topology_planning import TopologyPlan
        >>> plan = TopologyPlan.objects.get(pk=1)
        >>> success, yaml_str, stdout, stderr = validate_plan_yaml(plan)
    """
    from .yaml_generator import generate_yaml_for_plan

    # Generate YAML
    yaml_content = generate_yaml_for_plan(plan)

    # Validate
    success, stdout, stderr = validate_yaml(yaml_content)

    return success, yaml_content, stdout, stderr
