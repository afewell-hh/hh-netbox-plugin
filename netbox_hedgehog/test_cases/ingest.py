"""Ingestion engine for validated YAML case payloads."""

from __future__ import annotations

from django.db import transaction
from dcim.models import DeviceType, InterfaceTemplate, Manufacturer, ModuleType

from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    GenerationState,
    PlanServerClass,
    PlanServerConnection,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)

from .assertions import planning_counts
from .exceptions import TestCaseValidationError
from .schema import validate_case_dict


def _owned_case_filter(case_id: str):
    return TopologyPlan.objects.filter(
        custom_field_data__managed_by="yaml",
        custom_field_data__yaml_case_id=case_id,
    )


def _validate_reference_data(case: dict, reference_mode: str) -> None:
    if reference_mode != "require":
        return
    reference_data = case.get("reference_data", {})
    manufacturers = reference_data.get("manufacturers", [])
    errors = []
    for index, manufacturer in enumerate(manufacturers):
        name = manufacturer.get("name")
        slug = manufacturer.get("slug")
        exists = False
        if name:
            exists = Manufacturer.objects.filter(name=name).exists()
        elif slug:
            exists = Manufacturer.objects.filter(slug=slug).exists()
        if not exists:
            errors.append(
                {
                    "severity": "error",
                    "code": "missing_reference",
                    "path": f"reference_data.manufacturers[{index}]",
                    "message": f"Missing manufacturer: name={name!r} slug={slug!r}",
                    "hint": "Use ensure mode or pre-create reference data.",
                }
            )
    if errors:
        raise TestCaseValidationError(errors)


def _ensure_reference_data(case: dict, reference_mode: str) -> dict:
    """
    Ensure or resolve reference data.

    Returns dict of reference maps keyed by case-local IDs.
    """
    reference_data = case.get("reference_data", {})
    refs = {
        "manufacturers": {},
        "device_types": {},
        "device_type_extensions": {},
        "breakout_options": {},
        "module_types": {},
    }
    errors: list[dict] = []

    # Manufacturers
    for item in reference_data.get("manufacturers", []):
        rid = item.get("id")
        name = item.get("name")
        slug = item.get("slug")
        if not rid or not name:
            errors.append(
                {
                    "severity": "error",
                    "code": "missing_required",
                    "path": "reference_data.manufacturers",
                    "message": "Manufacturer requires id and name",
                }
            )
            continue
        obj = Manufacturer.objects.filter(name=name).first()
        if not obj and slug:
            obj = Manufacturer.objects.filter(slug=slug).first()
        if reference_mode == "require":
            if not obj:
                errors.append(
                    {
                        "severity": "error",
                        "code": "missing_reference",
                        "path": f"reference_data.manufacturers[{rid}]",
                        "message": f"Missing manufacturer '{name}'",
                    }
                )
                continue
        else:
            obj, _ = Manufacturer.objects.get_or_create(name=name, defaults={"slug": slug or rid})
        refs["manufacturers"][rid] = obj

    # Device types
    for item in reference_data.get("device_types", []):
        rid = item.get("id")
        manufacturer_ref = item.get("manufacturer")
        model = item.get("model")
        slug = item.get("slug")
        if not rid or not manufacturer_ref or not model:
            errors.append(
                {
                    "severity": "error",
                    "code": "missing_required",
                    "path": f"reference_data.device_types[{rid or 'unknown'}]",
                    "message": "DeviceType requires id, manufacturer, and model",
                }
            )
            continue
        manufacturer = refs["manufacturers"].get(manufacturer_ref)
        if not manufacturer:
            errors.append(
                {
                    "severity": "error",
                    "code": "unknown_reference",
                    "path": f"reference_data.device_types[{rid}].manufacturer",
                    "message": f"Unknown manufacturer ref '{manufacturer_ref}'",
                }
            )
            continue

        obj = DeviceType.objects.filter(manufacturer=manufacturer, model=model).first()
        if reference_mode == "require":
            if not obj:
                errors.append(
                    {
                        "severity": "error",
                        "code": "missing_reference",
                        "path": f"reference_data.device_types[{rid}]",
                        "message": f"Missing DeviceType '{model}'",
                    }
                )
                continue
        else:
            obj, _ = DeviceType.objects.get_or_create(
                manufacturer=manufacturer,
                model=model,
                defaults={
                    "slug": slug or model.lower().replace(" ", "-"),
                    "u_height": item.get("u_height", 1),
                    "is_full_depth": item.get("is_full_depth", False),
                },
            )
        for iface in item.get("interface_templates", []):
            InterfaceTemplate.objects.get_or_create(
                device_type=obj,
                name=iface["name"],
                defaults={"type": iface.get("type", "other")},
            )
        refs["device_types"][rid] = obj

    # DeviceTypeExtensions
    for item in reference_data.get("device_type_extensions", []):
        rid = item.get("id")
        device_type_ref = item.get("device_type")
        if not rid or not device_type_ref:
            errors.append(
                {
                    "severity": "error",
                    "code": "missing_required",
                    "path": "reference_data.device_type_extensions",
                    "message": "DeviceTypeExtension requires id and device_type",
                }
            )
            continue
        device_type = refs["device_types"].get(device_type_ref)
        if not device_type:
            errors.append(
                {
                    "severity": "error",
                    "code": "unknown_reference",
                    "path": f"reference_data.device_type_extensions[{rid}].device_type",
                    "message": f"Unknown device_type ref '{device_type_ref}'",
                }
            )
            continue
        defaults = {
            "mclag_capable": item.get("mclag_capable", False),
            "hedgehog_roles": item.get("hedgehog_roles", []),
            "supported_breakouts": item.get("supported_breakouts", []),
            "native_speed": item.get("native_speed"),
            "uplink_ports": item.get("uplink_ports"),
            "hedgehog_profile_name": item.get("hedgehog_profile_name"),
            "notes": item.get("notes", ""),
        }
        if reference_mode == "require":
            obj = DeviceTypeExtension.objects.filter(device_type=device_type).first()
            if not obj:
                errors.append(
                    {
                        "severity": "error",
                        "code": "missing_reference",
                        "path": f"reference_data.device_type_extensions[{rid}]",
                        "message": f"Missing DeviceTypeExtension for '{device_type}'",
                    }
                )
                continue
        else:
            obj, _ = DeviceTypeExtension.objects.update_or_create(device_type=device_type, defaults=defaults)
        refs["device_type_extensions"][rid] = obj

    # Breakout options
    for item in reference_data.get("breakout_options", []):
        rid = item.get("id")
        breakout_id = item.get("breakout_id")
        if not rid or not breakout_id:
            errors.append(
                {
                    "severity": "error",
                    "code": "missing_required",
                    "path": "reference_data.breakout_options",
                    "message": "BreakoutOption requires id and breakout_id",
                }
            )
            continue
        defaults = {
            "from_speed": item.get("from_speed", 0),
            "logical_ports": item.get("logical_ports", 1),
            "logical_speed": item.get("logical_speed", 0),
            "optic_type": item.get("optic_type", ""),
        }
        if reference_mode == "require":
            obj = BreakoutOption.objects.filter(breakout_id=breakout_id).first()
            if not obj:
                errors.append(
                    {
                        "severity": "error",
                        "code": "missing_reference",
                        "path": f"reference_data.breakout_options[{rid}]",
                        "message": f"Missing BreakoutOption '{breakout_id}'",
                    }
                )
                continue
        else:
            obj, _ = BreakoutOption.objects.update_or_create(breakout_id=breakout_id, defaults=defaults)
        refs["breakout_options"][rid] = obj

    # Module types
    for item in reference_data.get("module_types", []):
        rid = item.get("id")
        manufacturer_ref = item.get("manufacturer")
        model = item.get("model")
        if not rid or not manufacturer_ref or not model:
            errors.append(
                {
                    "severity": "error",
                    "code": "missing_required",
                    "path": "reference_data.module_types",
                    "message": "ModuleType requires id, manufacturer, model",
                }
            )
            continue
        manufacturer = refs["manufacturers"].get(manufacturer_ref)
        if not manufacturer:
            errors.append(
                {
                    "severity": "error",
                    "code": "unknown_reference",
                    "path": f"reference_data.module_types[{rid}].manufacturer",
                    "message": f"Unknown manufacturer ref '{manufacturer_ref}'",
                }
            )
            continue
        obj = ModuleType.objects.filter(manufacturer=manufacturer, model=model).first()
        if reference_mode == "require":
            if not obj:
                errors.append(
                    {
                        "severity": "error",
                        "code": "missing_reference",
                        "path": f"reference_data.module_types[{rid}]",
                        "message": f"Missing ModuleType '{model}'",
                    }
                )
                continue
        else:
            obj, _ = ModuleType.objects.get_or_create(
                manufacturer=manufacturer,
                model=model,
                defaults={"attribute_data": item.get("attribute_data", {})},
            )
            if item.get("attribute_data"):
                obj.attribute_data = item["attribute_data"]
                obj.save(update_fields=["attribute_data"])
        for iface in item.get("interface_templates", []):
            InterfaceTemplate.objects.get_or_create(
                module_type=obj,
                name=iface["name"],
                defaults={"type": iface.get("type", "other")},
            )
        refs["module_types"][rid] = obj

    if errors:
        raise TestCaseValidationError(errors)
    return refs


def _run_expected_assertions(case: dict, plan: TopologyPlan) -> None:
    expected = case.get("expected", {})
    counts = expected.get("counts", {})
    if not counts:
        return

    actual = planning_counts(plan)
    errors = []
    for key, expected_value in counts.items():
        if key in actual and actual[key] != expected_value:
            errors.append(
                {
                    "severity": "error",
                    "code": "assertion_failed",
                    "path": f"expected.counts.{key}",
                    "message": f"Expected {expected_value}, got {actual[key]}",
                }
            )
    if errors:
        raise TestCaseValidationError(errors)


def _delete_plan_graph(plan: TopologyPlan) -> None:
    """
    Delete a plan and dependent DIET planning objects in safe order.
    """
    PlanServerConnection.objects.filter(server_class__plan=plan).delete()
    PlanServerConnection.objects.filter(target_switch_class__plan=plan).delete()
    SwitchPortZone.objects.filter(switch_class__plan=plan).delete()
    PlanSwitchClass.objects.filter(plan=plan).delete()
    PlanServerClass.objects.filter(plan=plan).delete()
    GenerationState.objects.filter(plan=plan).delete()
    plan.delete()


@transaction.atomic
def apply_case(
    case: dict,
    *,
    clean: bool = False,
    prune: bool = False,
    reference_mode: str = "ensure",
) -> TopologyPlan:
    """
    Apply one validated YAML case into DIET planning models.
    """
    case = validate_case_dict(case)
    case_id = case["meta"]["case_id"]
    plan_name = case["plan"]["name"]
    plan_status = case["plan"]["status"]
    plan_description = case["plan"].get("description", "")

    _validate_reference_data(case, reference_mode)
    refs = _ensure_reference_data(case, reference_mode)

    owned_plans = list(_owned_case_filter(case_id).order_by("id"))
    if clean and owned_plans:
        for old_plan in owned_plans:
            _delete_plan_graph(old_plan)
        owned_plans = []

    # Conflict: a plan with this name exists but is not YAML-managed for this case.
    name_match = TopologyPlan.objects.filter(name=plan_name).first()
    if name_match and (
        name_match.custom_field_data.get("managed_by") != "yaml"
        or name_match.custom_field_data.get("yaml_case_id") != case_id
    ):
        raise TestCaseValidationError(
            [
                {
                    "severity": "error",
                    "code": "ownership_conflict",
                    "path": "plan.name",
                    "message": f"Plan name '{plan_name}' is already used by non-YAML-managed data.",
                    "hint": "Rename the plan or mark ownership explicitly.",
                }
            ]
        )

    if owned_plans:
        plan = owned_plans[0]
        plan.name = plan_name
        plan.status = plan_status
        plan.description = plan_description
    else:
        plan = TopologyPlan(
            name=plan_name,
            status=plan_status,
            description=plan_description,
        )

    cf = dict(plan.custom_field_data or {})
    cf["managed_by"] = "yaml"
    cf["yaml_case_id"] = case_id
    plan.custom_field_data = cf
    plan.save()

    # Upsert switch classes.
    switch_map = {}
    declared_switch_ids = set()
    for item in case.get("switch_classes", []):
        switch_id = item["switch_class_id"]
        declared_switch_ids.add(switch_id)
        dte_ref = item.get("device_type_extension")
        dte = refs["device_type_extensions"].get(dte_ref) if dte_ref else None
        if not dte:
            raise TestCaseValidationError(
                [
                    {
                        "severity": "error",
                        "code": "unknown_reference",
                        "path": f"switch_classes[{switch_id}].device_type_extension",
                        "message": f"Unknown device_type_extension ref '{dte_ref}'",
                    }
                ]
            )
        sw, _ = PlanSwitchClass.objects.update_or_create(
            plan=plan,
            switch_class_id=switch_id,
            defaults={
                "fabric": item.get("fabric", ""),
                "hedgehog_role": item.get("hedgehog_role", ""),
                "device_type_extension": dte,
                "uplink_ports_per_switch": item.get("uplink_ports_per_switch"),
                "mclag_pair": item.get("mclag_pair", False),
                "override_quantity": item.get("override_quantity"),
            },
        )
        switch_map[switch_id] = sw

    # Upsert port zones.
    declared_zone_keys = set()
    for item in case.get("switch_port_zones", []):
        switch_id = item["switch_class"]
        zone_name = item["zone_name"]
        declared_zone_keys.add((switch_id, zone_name))
        switch = switch_map.get(switch_id)
        breakout = refs["breakout_options"].get(item.get("breakout_option")) if item.get("breakout_option") else None
        if not switch:
            raise TestCaseValidationError(
                [
                    {
                        "severity": "error",
                        "code": "unknown_reference",
                        "path": f"switch_port_zones[{zone_name}].switch_class",
                        "message": f"Unknown switch_class ref '{switch_id}'",
                    }
                ]
            )
        SwitchPortZone.objects.update_or_create(
            switch_class=switch,
            zone_name=zone_name,
            defaults={
                "zone_type": item["zone_type"],
                "port_spec": item["port_spec"],
                "breakout_option": breakout,
                "allocation_strategy": item.get("allocation_strategy", "sequential"),
                "priority": item.get("priority", 100),
            },
        )

    # Upsert server classes.
    server_map = {}
    declared_server_ids = set()
    for item in case.get("server_classes", []):
        server_id = item["server_class_id"]
        declared_server_ids.add(server_id)
        dt_ref = item.get("server_device_type")
        device_type = refs["device_types"].get(dt_ref) if dt_ref else None
        if not device_type:
            raise TestCaseValidationError(
                [
                    {
                        "severity": "error",
                        "code": "unknown_reference",
                        "path": f"server_classes[{server_id}].server_device_type",
                        "message": f"Unknown device_type ref '{dt_ref}'",
                    }
                ]
            )
        sc, _ = PlanServerClass.objects.update_or_create(
            plan=plan,
            server_class_id=server_id,
            defaults={
                "description": item.get("description", ""),
                "category": item.get("category", ""),
                "quantity": item.get("quantity", 0),
                "gpus_per_server": item.get("gpus_per_server", 0),
                "server_device_type": device_type,
            },
        )
        server_map[server_id] = sc

    # Upsert connections.
    declared_conn_keys = set()
    for item in case.get("server_connections", []):
        server_id = item["server_class"]
        conn_id = item["connection_id"]
        declared_conn_keys.add((server_id, conn_id))
        server = server_map.get(server_id)
        target = switch_map.get(item.get("target_switch_class"))
        nic = refs["module_types"].get(item.get("nic_module_type"))
        if not server or not target or not nic:
            raise TestCaseValidationError(
                [
                    {
                        "severity": "error",
                        "code": "unknown_reference",
                        "path": f"server_connections[{conn_id}]",
                        "message": "Unknown server_class, target_switch_class, or nic_module_type reference",
                    }
                ]
            )
        PlanServerConnection.objects.update_or_create(
            server_class=server,
            connection_id=conn_id,
            defaults={
                "connection_name": item.get("connection_name", ""),
                "nic_module_type": nic,
                "port_index": item.get("port_index", 0),
                "ports_per_connection": item["ports_per_connection"],
                "hedgehog_conn_type": item.get("hedgehog_conn_type", "unbundled"),
                "distribution": item.get("distribution", ""),
                "target_switch_class": target,
                "speed": item["speed"],
                "rail": item.get("rail"),
                "port_type": item.get("port_type", ""),
            },
        )

    # Prune extra owned plans (if duplicates ever existed).
    if prune and len(owned_plans) > 1:
        for old_plan in owned_plans[1:]:
            _delete_plan_graph(old_plan)

    if prune:
        for sw in PlanSwitchClass.objects.filter(plan=plan).exclude(switch_class_id__in=declared_switch_ids):
            sw.delete()
        for sc in PlanServerClass.objects.filter(plan=plan).exclude(server_class_id__in=declared_server_ids):
            sc.delete()
        for sw in PlanSwitchClass.objects.filter(plan=plan):
            valid_zone_names = {name for sid, name in declared_zone_keys if sid == sw.switch_class_id}
            SwitchPortZone.objects.filter(switch_class=sw).exclude(zone_name__in=valid_zone_names).delete()
        for sc in PlanServerClass.objects.filter(plan=plan):
            valid_conn_ids = {cid for sid, cid in declared_conn_keys if sid == sc.server_class_id}
            PlanServerConnection.objects.filter(server_class=sc).exclude(connection_id__in=valid_conn_ids).delete()

    _run_expected_assertions(case, plan)

    return plan
