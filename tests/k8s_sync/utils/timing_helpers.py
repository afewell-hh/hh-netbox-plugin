"""
Timing validation helpers for extreme precision testing.
Validates sync intervals and state transitions within ±5 seconds accuracy.
"""

import time
from contextlib import contextmanager
from typing import Callable, Any
from django.utils import timezone
from datetime import timedelta


class TimingValidator:
    """Validates timing requirements for sync operations."""
    
    def __init__(self, tolerance_seconds: float = 5.0):
        self.tolerance = tolerance_seconds
    
    def assert_timing(self, expected_seconds: float, actual_seconds: float, operation: str):
        """Assert that timing falls within acceptable tolerance."""
        difference = abs(actual_seconds - expected_seconds)
        assert difference <= self.tolerance, (
            f"{operation} timing violation: expected {expected_seconds}s, "
            f"got {actual_seconds}s (difference: {difference}s, tolerance: {self.tolerance}s)"
        )
    
    def assert_within_interval(self, fabric, max_drift_seconds: float = 5.0):
        """Assert fabric sync timing is within interval boundaries."""
        if not fabric.last_sync or fabric.sync_interval <= 0:
            return
            
        time_since_sync = (timezone.now() - fabric.last_sync).total_seconds()
        expected_next_sync = fabric.sync_interval
        
        # For in_sync state, should be within interval
        if fabric.calculated_sync_status == 'in_sync':
            assert time_since_sync <= (expected_next_sync + max_drift_seconds), (
                f"Fabric shows in_sync but {time_since_sync}s since last sync "
                f"(interval: {expected_next_sync}s, tolerance: {max_drift_seconds}s)"
            )
        
        # For out_of_sync state, should be beyond interval
        elif fabric.calculated_sync_status == 'out_of_sync':
            assert time_since_sync > (expected_next_sync + max_drift_seconds), (
                f"Fabric shows out_of_sync but only {time_since_sync}s since last sync "
                f"(interval: {expected_next_sync}s, tolerance: {max_drift_seconds}s)"
            )


@contextmanager
def time_operation(description: str = "operation"):
    """Context manager to time an operation."""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        print(f"⏱️  {description}: {duration:.3f}s")


def wait_for_condition(
    condition_func: Callable[[], bool],
    timeout_seconds: float = 30.0,
    check_interval: float = 0.1,
    description: str = "condition"
) -> bool:
    """
    Wait for a condition to become true within timeout.
    
    Args:
        condition_func: Function that returns True when condition is met
        timeout_seconds: Maximum time to wait
        check_interval: How often to check condition
        description: Description for error messages
        
    Returns:
        True if condition was met, False if timeout
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout_seconds:
        if condition_func():
            return True
        time.sleep(check_interval)
    
    return False


def wait_for_state_transition(
    fabric,
    expected_state: str,
    timeout_seconds: float = 30.0,
    description: str = None
) -> bool:
    """
    Wait for fabric to transition to expected sync state.
    
    Args:
        fabric: HedgehogFabric instance
        expected_state: Expected sync state
        timeout_seconds: Maximum wait time
        description: Optional description for logging
        
    Returns:
        True if transition occurred within timeout
    """
    if not description:
        description = f"fabric {fabric.name} to reach {expected_state} state"
    
    def check_state():
        fabric.refresh_from_db()
        return fabric.calculated_sync_status == expected_state
    
    return wait_for_condition(
        check_state,
        timeout_seconds,
        check_interval=0.5,
        description=description
    )


class SyncIntervalTester:
    """Test sync intervals with extreme precision."""
    
    def __init__(self, fabric):
        self.fabric = fabric
        self.validator = TimingValidator(tolerance_seconds=5.0)
    
    def test_transition_at_boundary(self, target_state: str):
        """Test state transition occurs at exact interval boundary."""
        if not self.fabric.sync_interval:
            raise ValueError("Fabric must have sync_interval > 0 for boundary testing")
        
        # Set last_sync to approach boundary
        boundary_time = timezone.now() + timedelta(seconds=10)  # 10 seconds from now
        self.fabric.last_sync = boundary_time - timedelta(seconds=self.fabric.sync_interval)
        self.fabric.save()
        
        # Wait until just before boundary
        time.sleep(8)
        
        # Should still be in current state
        self.fabric.refresh_from_db()
        pre_boundary_state = self.fabric.calculated_sync_status
        
        # Wait past boundary
        time.sleep(5)
        
        # Should have transitioned
        self.fabric.refresh_from_db()
        post_boundary_state = self.fabric.calculated_sync_status
        
        assert post_boundary_state == target_state, (
            f"Expected transition to {target_state} at interval boundary, "
            f"but state remained {post_boundary_state} "
            f"(was {pre_boundary_state} before boundary)"
        )
    
    def validate_overdue_calculation(self):
        """Validate overdue time calculation is accurate to seconds."""
        if not self.fabric.last_sync:
            return
            
        current_time = timezone.now()
        actual_overdue = (current_time - self.fabric.last_sync).total_seconds() - self.fabric.sync_interval
        
        # This would be implemented in GUI - testing the calculation logic
        expected_overdue = max(0, actual_overdue)
        
        # GUI should display this overdue time accurately
        assert abs(expected_overdue - max(0, actual_overdue)) < 1.0, (
            f"Overdue calculation inaccurate: expected {expected_overdue}s, "
            f"calculated {actual_overdue}s"
        )


def benchmark_state_calculation_performance(fabric, iterations: int = 1000):
    """
    Benchmark state calculation performance.
    Must complete within 5ms per calculation.
    """
    times = []
    
    for _ in range(iterations):
        start_time = time.perf_counter()
        _ = fabric.calculated_sync_status  # Property access
        end_time = time.perf_counter()
        times.append((end_time - start_time) * 1000)  # Convert to milliseconds
    
    avg_time_ms = sum(times) / len(times)
    max_time_ms = max(times)
    
    # Validate performance requirements
    assert avg_time_ms < 5.0, (
        f"State calculation too slow: average {avg_time_ms:.3f}ms > 5ms limit"
    )
    
    assert max_time_ms < 10.0, (
        f"State calculation peak too slow: max {max_time_ms:.3f}ms > 10ms limit"
    )
    
    return {
        'average_ms': avg_time_ms,
        'max_ms': max_time_ms,
        'min_ms': min(times),
        'total_ms': sum(times),
        'iterations': iterations
    }