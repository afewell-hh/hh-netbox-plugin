"""
Mesh link pairing for prefer-mesh topology fabrics (DIET-309/311).

Creates PlanMeshLink rows for each pair of physical switches in a prefer-mesh
fabric.  IPs (subnet) are intentionally omitted — hhfab auto-assigns all mesh
link IPs via its all-or-nothing hydration model (DIET-311).
"""

from itertools import combinations


def _expand_switch_names(switch_class, render_device_name_fn=None):
    """
    Expand a PlanSwitchClass into individual physical switch names.

    Uses the same naming convention as DeviceGenerator: <class_id>-<index:02d>
    (or the naming template if one is configured, but we fall back to the
    default convention here since we run outside DeviceGenerator context).

    Args:
        switch_class: PlanSwitchClass instance
        render_device_name_fn: optional callable(index) -> str override

    Returns:
        List of switch name strings, sorted alphabetically
    """
    from django.utils.text import slugify

    names = []
    for index in range(1, (switch_class.effective_quantity or 0) + 1):
        if render_device_name_fn:
            name = render_device_name_fn(index)
        else:
            name = f"{slugify(switch_class.switch_class_id)}-{index:02d}"
        names.append(name)
    return names


def allocate_mesh_links(plan, fabric_name, render_device_name_fn=None):
    """
    Pair all physical switches in a prefer-mesh fabric and create PlanMeshLink rows.

    Operates on individual switch instances (not switch-class pairs), using the
    same naming convention as DeviceGenerator.  Each pair (sorted alphabetically)
    is assigned a stable link_index.  subnet is left blank — IPs are assigned by
    hhfab at hydration time (DIET-311).

    Stability: existing PlanMeshLink rows with matching (plan, fabric_name,
    link_index) are reused.  Stale rows are deleted.

    Args:
        plan: TopologyPlan instance
        fabric_name: str — the fabric to pair switches for
        render_device_name_fn: optional callable(switch_class, index) -> str.
            When provided, used instead of the default slugify-based naming so
            that names match the DeviceGenerator's NamingTemplate exactly.

    Returns:
        list of PlanMeshLink instances (created or updated)
    """
    from netbox_hedgehog.models.topology_planning import PlanSwitchClass, PlanMeshLink
    from netbox_hedgehog.choices import TopologyModeChoices

    # Get all prefer-mesh switch classes for this fabric, sorted deterministically
    switch_classes = list(
        PlanSwitchClass.objects.filter(
            plan=plan,
            fabric_name=fabric_name,
            topology_mode=TopologyModeChoices.PREFER_MESH,
        ).order_by('switch_class_id')
    )

    # Expand to individual physical switch names
    all_switch_names = []
    for sc in switch_classes:
        per_class_fn = None
        if render_device_name_fn is not None:
            per_class_fn = lambda index, _sc=sc: render_device_name_fn(_sc, index)
        all_switch_names.extend(_expand_switch_names(sc, render_device_name_fn=per_class_fn))
    all_switch_names.sort()

    # Generate all pairs from individual switch names (sorted for determinism)
    pairs = list(combinations(all_switch_names, 2))

    # Build a map: switch_name -> PlanSwitchClass
    name_to_class = {}
    for sc in switch_classes:
        per_class_fn = None
        if render_device_name_fn is not None:
            per_class_fn = lambda index, _sc=sc: render_device_name_fn(_sc, index)
        for name in _expand_switch_names(sc, render_device_name_fn=per_class_fn):
            name_to_class[name] = sc

    # Create or update PlanMeshLink rows (subnet left blank — hhfab assigns IPs)
    created_links = []
    desired_indices = set()
    for link_index, (name_a, name_b) in enumerate(pairs):
        desired_indices.add(link_index)
        sc_a = name_to_class.get(name_a)
        sc_b = name_to_class.get(name_b)
        link, _ = PlanMeshLink.objects.update_or_create(
            plan=plan,
            fabric_name=fabric_name,
            link_index=link_index,
            defaults={
                'switch_class_a': sc_a,
                'switch_class_b': sc_b,
                'subnet': '',
                'leaf1_name': name_a,
                'leaf2_name': name_b,
            },
        )
        created_links.append(link)

    # Delete stale links (link_index no longer in desired set)
    PlanMeshLink.objects.filter(
        plan=plan,
        fabric_name=fabric_name,
    ).exclude(link_index__in=desired_indices).delete()

    return created_links
