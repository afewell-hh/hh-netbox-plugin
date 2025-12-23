"""
Port allocation helpers for topology planning.

Allocates switch ports based on SwitchPortZone configuration and breakout rules.
"""

from dataclasses import dataclass
from typing import Iterable

from django.core.exceptions import ValidationError

from netbox_hedgehog.choices import AllocationStrategyChoices
from netbox_hedgehog.services.port_specification import PortSpecification


@dataclass(frozen=True)
class PortSlot:
    """Represents an allocated switch port."""

    physical_port: int
    breakout_index: int | None
    name: str


class PortAllocatorV2:
    """
    Zone-aware port allocator with breakout support.

    Tracks allocation state per switch instance and port zone.
    """

    def __init__(self):
        self._sequences: dict[tuple[str, int], list[PortSlot]] = {}
        self._cursors: dict[tuple[str, int], int] = {}

    def allocate(self, switch_name: str, zone, count: int) -> list[PortSlot]:
        """
        Allocate ports for a specific switch/zone.

        Args:
            switch_name: Unique switch instance name
            zone: SwitchPortZone instance
            count: Number of logical ports to allocate

        Returns:
            List of allocated PortSlot entries
        """
        if count <= 0:
            raise ValidationError("Allocation count must be a positive integer.")

        key = (switch_name, zone.pk)

        if key not in self._sequences:
            self._sequences[key] = self._build_sequence(zone)
            self._cursors[key] = 0

        cursor = self._cursors[key]
        sequence = self._sequences[key]
        remaining = len(sequence) - cursor

        if count > remaining:
            raise ValidationError(
                f"Requested {count} ports but only {remaining} remain in zone '{zone.zone_name}'."
            )

        allocated = sequence[cursor:cursor + count]
        self._cursors[key] = cursor + count
        return allocated

    def _build_sequence(self, zone) -> list[PortSlot]:
        ports = PortSpecification(zone.port_spec).parse()
        ordered_ports = self._apply_strategy(zone, ports)
        return self._expand_breakouts(ordered_ports, zone.breakout_option)

    def _apply_strategy(self, zone, ports: list[int]) -> list[int]:
        if zone.allocation_strategy == AllocationStrategyChoices.CUSTOM:
            return list(zone.allocation_order or [])

        if zone.allocation_strategy == AllocationStrategyChoices.INTERLEAVED:
            return self._interleave_by_index(ports)

        if zone.allocation_strategy == AllocationStrategyChoices.SPACED:
            return self._interleave_halves(ports)

        return ports

    def _expand_breakouts(self, ports: Iterable[int], breakout) -> list[PortSlot]:
        logical_ports = 1
        if breakout:
            logical_ports = breakout.logical_ports or 1

        expanded: list[PortSlot] = []
        for port in ports:
            if logical_ports > 1:
                for lane in range(1, logical_ports + 1):
                    expanded.append(
                        PortSlot(
                            physical_port=port,
                            breakout_index=lane,
                            name=f"E1/{port}/{lane}",
                        )
                    )
            else:
                expanded.append(
                    PortSlot(
                        physical_port=port,
                        breakout_index=None,
                        name=f"E1/{port}",
                    )
                )
        return expanded

    def _interleave_by_index(self, ports: list[int]) -> list[int]:
        """Return ports in odd-indexed order followed by even-indexed order."""
        return ports[::2] + ports[1::2]

    def _interleave_halves(self, ports: list[int]) -> list[int]:
        """Return ports interleaved across halves for wider spacing."""
        midpoint = (len(ports) + 1) // 2
        first_half = ports[:midpoint]
        second_half = ports[midpoint:]

        interleaved: list[int] = []
        for index in range(len(first_half)):
            interleaved.append(first_half[index])
            if index < len(second_half):
                interleaved.append(second_half[index])

        return interleaved
