"""
Hedgehog Fabric (hhfab) CLI integration for wiring validation (Issue #159).

This module provides helpers to invoke `hhfab validate` for validating
generated wiring YAML diagrams against Hedgehog's authoritative schema.
"""

import subprocess
import tempfile
import os
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


def validate_yaml(yaml_content: str, timeout: int = 30) -> Tuple[bool, str, str]:
    """
    Validate Hedgehog wiring YAML using `hhfab validate`.

    Writes YAML content to a temporary file and invokes hhfab validate.
    Handles graceful degradation when hhfab is not installed.

    Args:
        yaml_content: YAML string to validate
        timeout: Command timeout in seconds (default: 30)

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
            "hhfab CLI not found in PATH. Install hhfab to enable wiring validation."
        )

    # Create temporary file for YAML content
    try:
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.yaml',
            delete=False,
            encoding='utf-8'
        ) as tmp_file:
            tmp_file.write(yaml_content)
            tmp_path = tmp_file.name

        # Run hhfab validate
        result = subprocess.run(
            ['hhfab', 'validate', tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        # Clean up temp file
        os.unlink(tmp_path)

        # Return result
        return (
            result.returncode == 0,
            result.stdout,
            result.stderr
        )

    except subprocess.TimeoutExpired:
        # Clean up temp file on timeout
        if 'tmp_path' in locals():
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass

        return (
            False,
            "",
            f"hhfab validate command timed out after {timeout} seconds"
        )

    except Exception as e:
        # Clean up temp file on error
        if 'tmp_path' in locals():
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
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
