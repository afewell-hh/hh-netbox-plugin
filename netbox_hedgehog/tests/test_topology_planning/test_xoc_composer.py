"""Tests for XOC shared-spine composition (DIET-606)."""

from django.test import SimpleTestCase

from netbox_hedgehog.services.xoc_composer import (
    CompositionError,
    LeafProjection,
    compose_shared_spines,
)


def _leaf(domain: str, number: int, fabric: str) -> LeafProjection:
    return LeafProjection(
        domain=domain,
        name=f"{fabric}-leaf-{number:02d}",
        fabric=fabric,
        reserved_uplinks=tuple(f"E1/{port}" for port in range(33, 65)),
    )


class XOC3712ComposerTests(SimpleTestCase):
    def test_composes_the_3712_shared_spine_links(self):
        leaves = [
            *[_leaf(f"opg512-{domain}", number, "frontend") for domain in range(1, 7) for number in range(1, 3)],
            *[_leaf("opg640", number, "frontend") for number in range(1, 3)],
            *[_leaf(f"opg512-{domain}", number, "backend-plane-a") for domain in range(1, 7) for number in range(1, 9)],
            *[_leaf("opg640", number, "backend-plane-a") for number in range(1, 4)],
            *[_leaf(f"opg512-{domain}", number, "backend-plane-b") for domain in range(1, 7) for number in range(1, 9)],
            *[_leaf("opg640", number, "backend-plane-b") for number in range(1, 4)],
        ]

        fabrics = compose_shared_spines(leaves)

        self.assertEqual({name: len(value.links) for name, value in fabrics.items()}, {
            "frontend": 448,
            "backend-plane-a": 1632,
            "backend-plane-b": 1632,
        })
        self.assertEqual(sum(len(value.links) for value in fabrics.values()), 3712)
        for fabric in fabrics.values():
            self.assertEqual(len(fabric.spines), 32)
            for spine in fabric.spines:
                self.assertEqual(sum(link.spine == spine for link in fabric.links), len(fabric.links) // 32)

    def test_rejects_leaf_without_all_reserved_uplinks(self):
        leaf = LeafProjection("opg512-1", "leaf-01", "frontend", ("E1/33",))
        with self.assertRaisesMessage(CompositionError, "expected 32 reserved uplinks"):
            compose_shared_spines([leaf])

    def test_rejects_duplicate_domain_scoped_leaf_name(self):
        leaf = _leaf("opg512-1", 1, "frontend")
        with self.assertRaisesMessage(CompositionError, "duplicate namespaced leaf"):
            compose_shared_spines([leaf, leaf])

    def test_rejects_spine_capacity_overflow(self):
        leaves = [_leaf("opg512-1", number, "frontend") for number in range(1, 66)]
        with self.assertRaisesMessage(CompositionError, "exceed spine downlink capacity"):
            compose_shared_spines(leaves)
