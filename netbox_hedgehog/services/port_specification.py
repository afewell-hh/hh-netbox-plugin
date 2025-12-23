"""
Port specification parser for switch port zones.

Parses port range specifications like "1-48", "1-32:2", "1,3,5,7" into lists of port numbers.
"""

from django.core.exceptions import ValidationError


class PortSpecification:
    """
    Helper class to parse port range specifications.
    
    Supported formats:
    - Single port: "5" → [5]
    - Range: "1-16" → [1,2,3,...,16]
    - List: "1,3,5,7" → [1,3,5,7]
    - Mixed: "1-4,6,8-10" → [1,2,3,4,6,8,9,10]
    - Interleaved: "1-32:2" → [1,3,5,...,31] (every 2nd port)
    
    Features:
    - Deduplicates overlapping ranges
    - Sorts output
    - Validates port numbers (1-1024)
    - Handles whitespace
    """
    
    MAX_PORT = 1024  # Maximum valid port number
    
    def __init__(self, spec: str):
        """
        Initialize with port specification string.
        
        Args:
            spec: Port specification string
        """
        self.spec = spec.strip()
    
    def parse(self) -> list[int]:
        """
        Parse specification into list of port numbers.
        
        Returns:
            Sorted list of unique port numbers
        
        Raises:
            ValidationError: If specification is invalid
        """
        if not self.spec:
            raise ValidationError("Port specification cannot be empty")
        
        ports = set()  # Use set for automatic deduplication
        
        # Split by comma to handle multiple parts
        parts = self.spec.split(',')
        
        for part in parts:
            part = part.strip()
            
            if not part:
                continue
            
            # Check for interleaved format (contains colon)
            if ':' in part:
                ports.update(self._parse_interleaved(part))
            # Check for range format (contains dash)
            elif '-' in part and not part.startswith('-'):
                ports.update(self._parse_range(part))
            # Single port number
            else:
                ports.add(self._parse_single(part))
        
        if not ports:
            raise ValidationError("Port specification must define at least one port")
        
        # Return sorted list
        return sorted(ports)
    
    def _parse_single(self, s: str) -> int:
        """Parse single port number"""
        try:
            port = int(s.strip())
        except ValueError:
            raise ValidationError(f"Invalid port number: '{s}'")
        
        self._validate_port(port)
        return port
    
    def _parse_range(self, s: str) -> set[int]:
        """Parse port range (e.g., '1-48')"""
        # Handle whitespace around dash
        s = s.replace(' ', '')
        
        parts = s.split('-')
        
        if len(parts) != 2:
            raise ValidationError(f"Invalid range format: '{s}'")
        
        try:
            start = int(parts[0])
            end = int(parts[1])
        except ValueError:
            raise ValidationError(f"Invalid range format: '{s}'")
        
        # Validate individual ports
        self._validate_port(start)
        self._validate_port(end)
        
        # Check for reversed range
        if start > end:
            raise ValidationError(
                f"Invalid range: start ({start}) must not be greater than end ({end})"
            )
        
        return set(range(start, end + 1))
    
    def _parse_interleaved(self, s: str) -> set[int]:
        """Parse interleaved format (e.g., '1-32:2' = every 2nd port)"""
        parts = s.split(':')
        
        if len(parts) != 2:
            raise ValidationError(
                f"Invalid interleaved format: '{s}'. Expected format: 'start-end:step'"
            )
        
        range_part = parts[0].strip()
        
        try:
            step = int(parts[1].strip())
        except ValueError:
            raise ValidationError(f"Invalid step value: '{parts[1]}'")
        
        # Validate step
        if step <= 0:
            raise ValidationError(
                f"Step must be positive integer, got: {step}"
            )
        
        # Parse range part
        if '-' not in range_part:
            raise ValidationError(
                f"Invalid interleaved format: '{s}'. Expected format: 'start-end:step'"
            )

        range_ports = self._parse_range(range_part)
        start = min(range_ports)
        end = max(range_ports)
        
        # Generate interleaved sequence
        return set(range(start, end + 1, step))
    
    def _validate_port(self, port: int):
        """Validate port number is within valid range"""
        if port <= 0:
            raise ValidationError(
                f"Port numbers must be positive integers. Got: {port}"
            )
        
        if port > self.MAX_PORT:
            raise ValidationError(
                f"Port number {port} exceeds maximum port number ({self.MAX_PORT})"
            )
    
    def __str__(self):
        """Return original specification"""
        return self.spec
