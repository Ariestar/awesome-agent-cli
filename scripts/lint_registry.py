#!/usr/bin/env python3
"""Validate the machine-readable tool registry."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlparse

import yaml
from registry import load_card

ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "data" / "tools"

TOP_LEVEL_FIELDS = {
    "name",
    "binary",
    "aliases",
    "category",
    "lang",
    "platform",
    "summary",
    "homepage",
    "docs",
    "detect",
    "use_when",
    "avoid_when",
    "risk",
    "guardrails",
}
REQUIRED_TOP_LEVEL_FIELDS = {
    "name",
    "binary",
    "category",
    "lang",
    "summary",
    "homepage",
    "docs",
    "detect",
    "risk",
}
RISK_FIELDS = {
    "level",
    "effects",
    "requires_auth",
    "destructive",
    "confirmation_required_for",
}
EFFECTS = {
    "cloud_mutation",
    "container_mutation",
    "delete_files",
    "deployment",
    "environment_mutation",
    "execute_code",
    "install_packages",
    "network_access",
    "read_files",
    "read_processes",
    "remote_read",
    "remote_write",
    "requires_auth",
    "secret_exposure",
    "vcs_mutation",
    "write_files",
}


def error(path: Path, message: str) -> str:
    return f"{path.relative_to(ROOT)}: {message}"


def mapping(value: object, label: str, errors: list[str], path: Path) -> Mapping[str, object] | None:
    if not isinstance(value, Mapping):
        errors.append(error(path, f"{label} must be a mapping"))
        return None
    return value


def string_field(card: Mapping[str, object], key: str, errors: list[str], path: Path) -> str | None:
    value = card.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(error(path, f"{key} must be a non-empty string"))
        return None
    return value


def string_list(
    value: object,
    key: str,
    errors: list[str],
    path: Path,
    *,
    required: bool = False,
    unique: bool = True,
) -> list[str]:
    if value is None and not required:
        return []
    if not isinstance(value, list):
        errors.append(error(path, f"{key} must be a list of strings"))
        return []

    values: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            errors.append(error(path, f"{key} must contain only non-empty strings"))
            continue
        values.append(item)

    normalized = [item.casefold() for item in values]
    if unique and len(normalized) != len(set(normalized)):
        errors.append(error(path, f"{key} must not contain duplicate values"))
    return values


def validate_card(path: Path) -> tuple[list[str], str | None]:
    try:
        card = load_card(path)
    except (OSError, TypeError, yaml.YAMLError) as exc:
        return [error(path, f"invalid YAML: {exc}")], None

    errors: list[str] = []
    unknown = sorted(set(card) - TOP_LEVEL_FIELDS)
    errors.extend(error(path, f"unknown field: {key}") for key in unknown)
    missing = sorted(REQUIRED_TOP_LEVEL_FIELDS - set(card))
    if missing:
        errors.append(error(path, f"missing required field(s): {', '.join(missing)}"))

    name = string_field(card, "name", errors, path)
    string_field(card, "binary", errors, path)
    string_field(card, "summary", errors, path)
    for key in ("homepage", "docs"):
        value = string_field(card, key, errors, path)
        if value:
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                errors.append(error(path, f"{key} must be an http(s) URL"))

    if name and path.stem != name:
        errors.append(error(path, f"file name must match tool name {name!r}"))

    string_list(card.get("category"), "category", errors, path, required=True)
    languages = string_list(card.get("lang"), "lang", errors, path, required=True)
    string_list(card.get("aliases"), "aliases", errors, path)
    string_list(card.get("platform"), "platform", errors, path)
    string_list(card.get("use_when"), "use_when", errors, path)
    string_list(card.get("avoid_when"), "avoid_when", errors, path)
    guardrails = string_list(card.get("guardrails"), "guardrails", errors, path)

    if any(language.casefold() == "all" for language in languages) and len(languages) > 1:
        errors.append(error(path, "lang=all must not be mixed with other values"))

    detect = mapping(card.get("detect"), "detect", errors, path)
    if detect is not None:
        unknown = sorted(set(detect) - {"version_args", "local"})
        errors.extend(error(path, f"unknown detect field: {key}") for key in unknown)
        string_list(detect.get("version_args"), "detect.version_args", errors, path, required=True)

        local = mapping(detect.get("local"), "detect.local", errors, path) if "local" in detect else None
        if local is not None:
            unknown = sorted(set(local) - {"files", "dirs", "package_json"})
            errors.extend(error(path, f"unknown detect.local field: {key}") for key in unknown)
            if "files" in local:
                string_list(
                    local.get("files"),
                    "detect.local.files",
                    errors,
                    path,
                    unique=False,
                )
            if "dirs" in local:
                string_list(
                    local.get("dirs"),
                    "detect.local.dirs",
                    errors,
                    path,
                    unique=False,
                )

            if "package_json" in local:
                package_json = mapping(local.get("package_json"), "detect.local.package_json", errors, path)
            else:
                package_json = None
            if package_json is not None:
                unknown = sorted(set(package_json) - {"package_manager_prefixes"})
                errors.extend(
                    error(path, f"unknown detect.local.package_json field: {key}")
                    for key in unknown
                )
                string_list(
                    package_json.get("package_manager_prefixes"),
                    "detect.local.package_json.package_manager_prefixes",
                    errors,
                    path,
                )

    risk = mapping(card.get("risk"), "risk", errors, path)
    if risk is not None:
        unknown = sorted(set(risk) - RISK_FIELDS)
        errors.extend(error(path, f"unknown risk field: {key}") for key in unknown)
        missing = sorted(RISK_FIELDS - set(risk))
        if missing:
            errors.append(error(path, f"missing required risk field(s): {', '.join(missing)}"))

        level = risk.get("level")
        if level not in {"low", "medium", "high"}:
            errors.append(error(path, "risk.level must be low, medium, or high"))

        effects = string_list(risk.get("effects"), "risk.effects", errors, path, required=True)
        invalid_effects = sorted(set(effects) - EFFECTS)
        errors.extend(error(path, f"unknown risk effect: {effect}") for effect in invalid_effects)

        for key in ("requires_auth", "destructive"):
            if not isinstance(risk.get(key), bool):
                errors.append(error(path, f"risk.{key} must be true or false"))

        confirmations = string_list(
            risk.get("confirmation_required_for"),
            "risk.confirmation_required_for",
            errors,
            path,
            required=True,
        )
        if level == "high" and not guardrails:
            errors.append(error(path, "high-risk cards require guardrails"))
        if risk.get("destructive") is True and not confirmations:
            errors.append(error(path, "destructive cards require confirmation_required_for"))

    return errors, name


def main() -> int:
    paths = sorted(TOOLS_DIR.glob("*.yaml"))
    if not paths:
        print(f"No tool YAML files found in {TOOLS_DIR}", file=sys.stderr)
        return 1

    errors: list[str] = []
    names: dict[str, Path] = {}
    for path in paths:
        card_errors, name = validate_card(path)
        errors.extend(card_errors)
        if name:
            key = name.casefold()
            if key in names:
                errors.append(error(path, f"duplicate tool name; already defined in {names[key].relative_to(ROOT)}"))
            else:
                names[key] = path

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    print(f"Validated {len(paths)} tool cards.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
