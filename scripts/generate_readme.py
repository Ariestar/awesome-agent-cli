#!/usr/bin/env python3
"""Generate README.md from data/tools/*.yaml.

The README generator and registry linter share the same safe YAML loader so
the rendered catalog and validation use one input format.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

from registry import load_card

ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "data" / "tools"
README = ROOT / "README.md"
RISK_ORDER = ("low", "medium", "high")
RISK_LABEL = {"low": "Low", "medium": "Medium", "high": "High"}


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9 -]", "", value)
    value = value.replace(" ", "-")
    value = re.sub(r"-+", "-", value)
    return value.strip("-")


def parse_tool(path: Path) -> dict:
    tool = dict(load_card(path))
    tool["slug"] = path.stem
    tool.setdefault("name", path.stem)
    tool.setdefault("binary", tool["name"])
    tool.setdefault("summary", "")
    tool.setdefault("homepage", "")
    tool.setdefault("docs", "")
    tool.setdefault("category", [])
    tool.setdefault("lang", ["all"])
    tool.setdefault("platform", [])
    tool.setdefault("aliases", [])
    if isinstance(tool.get("risk"), dict):
        tool["risk_level"] = tool["risk"].get("level", "medium")
    else:
        tool["risk_level"] = "medium"
    return tool


def md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def link_for(tool: dict) -> str:
    return str(tool.get("docs") or tool.get("homepage") or "").strip()


def badge(label: str, message: str, color: str, href: str | None = None) -> str:
    image = f"https://img.shields.io/badge/{label}-{message}-{color}"
    markdown = f"![{label}: {message}]({image})"
    return f"[{markdown}]({href})" if href else markdown


def risk_badge(level: str) -> str:
    color = {"low": "2ea44f", "medium": "d29922", "high": "cf222e"}.get(level, "6e7781")
    return badge("risk", level, color)


def github_repo(value: str) -> tuple[str, str] | None:
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.netloc.lower() != "github.com":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1].removesuffix(".git")
    if owner in {"orgs", "topics", "marketplace", "features"}:
        return None
    return owner, repo


def github_stars_badge(tool: dict) -> str | None:
    for field in ("homepage", "docs"):
        repo = github_repo(str(tool.get(field) or ""))
        if repo:
            owner, name = repo
            href = f"https://github.com/{owner}/{name}"
            image = f"https://img.shields.io/github/stars/{owner}/{name}?style=social"
            return f"[![GitHub Repo stars]({image})]({href})"
    return None


def format_meta(tool: dict) -> str:
    parts = [f"`{tool['binary']}`", risk_badge(str(tool.get("risk_level") or "medium"))]
    langs = tool.get("lang") or []
    if langs:
        parts.append("lang: " + ", ".join(f"`{lang}`" for lang in langs[:4]))
    cats = tool.get("category") or []
    if len(cats) > 1:
        parts.append("also: " + ", ".join(f"`{cat}`" for cat in cats[1:4]))
    stars = github_stars_badge(tool)
    if stars:
        parts.append(stars)
    return " · ".join(parts)


def render_tool_line(tool: dict) -> str:
    name = md_escape(str(tool["name"]))
    summary = md_escape(str(tool.get("summary") or ""))
    href = link_for(tool)
    title = f"[{name}]({href})" if href else name
    meta = format_meta(tool)
    return f"- {title} — {summary}  \\\n  {meta}"


def render_category_card(category: str, tools: list[dict], risks: Counter[str]) -> str:
    high = risks.get("high", 0)
    medium = risks.get("medium", 0)
    low = risks.get("low", 0)
    if high:
        posture = "control plane"
    elif medium:
        posture = "operator surface"
    else:
        posture = "safe default"
    return (
        f"| [`{md_escape(category)}`](#{slugify(category)}) "
        f"| {len(tools)} | {low} | {medium} | {high} | {posture} |"
    )


def main() -> None:
    tools = sorted((parse_tool(path) for path in TOOLS_DIR.glob("*.yaml")), key=lambda item: str(item["name"]).lower())
    if not tools:
        raise SystemExit("No tool YAML files found in data/tools")

    category_groups: dict[str, list[dict]] = defaultdict(list)
    category_counts: Counter[str] = Counter()
    risk_by_category: dict[str, Counter[str]] = defaultdict(Counter)
    lang_counts: Counter[str] = Counter()
    risk_counts: Counter[str] = Counter()
    github_backed = 0
    tool_by_name = {str(tool["name"]): tool for tool in tools}

    for tool in tools:
        categories = tool.get("category") or ["uncategorized"]
        risk_level = str(tool.get("risk_level") or "medium")
        if github_stars_badge(tool):
            github_backed += 1
        for category in categories:
            category_groups[category].append(tool)
            risk_by_category[category].update([risk_level])
        category_counts.update(categories)
        lang_counts.update(tool.get("lang") or [])
        risk_counts.update([risk_level])

    risk_summary = " · ".join(f"{RISK_LABEL.get(risk, risk.title())}: **{risk_counts.get(risk, 0)}**" for risk in RISK_ORDER)
    top_categories = sorted(category_groups, key=lambda cat: (-len(category_groups[cat]), cat))[:8]

    lines: list[str] = []
    lines.extend(
        [
            '<div align="center">',
            "",
            "# Awesome Agent CLI",
            "",
            "**A machine-readable awesome list of CLI tools, risks, effects, and guardrails for AI coding agents.**",
            "",
            f"{badge('tools', str(len(tools)), '0969da')} {badge('categories', str(len(category_counts)), '8250df')} {badge('yaml', 'registry', '2ea44f')} [![GitHub Repo stars](https://img.shields.io/github/stars/Ariestar/awesome-agent-cli?style=social)](https://github.com/Ariestar/awesome-agent-cli) [![Awesome](https://awesome.re/badge-flat.svg)](https://awesome.re) [![Update README](https://github.com/Ariestar/awesome-agent-cli/actions/workflows/update-readme.yml/badge.svg)](https://github.com/Ariestar/awesome-agent-cli/actions/workflows/update-readme.yml)",
            "",
            "</div>",
            "",
            "Awesome Agent CLI is a compact registry for teaching agents which command-line tools exist, what each tool is good for, and when a tool is risky enough to need extra care.",
            "Each entry is a plain YAML card under [`data/tools/`](data/tools/) so the registry is easy to diff, review, vendor, and consume from other projects.",
            "",
            "> [!NOTE]",
            "> This README is generated by [`scripts/generate_readme.py`](scripts/generate_readme.py). Edit the YAML cards, then regenerate the README instead of hand-editing the catalog sections.",
            "",
            "## Why this exists",
            "",
            "AI coding agents do not just need a list of binaries. They need operational context:",
            "",
            "- **When to use** a tool and when to avoid it.",
            "- **What side effects** the tool may have: file writes, network calls, auth, remote mutation, command execution.",
            "- **Which guardrails** are required before dangerous actions.",
            "- **How tools map** to categories like `shell`, `agent`, `mcp`, `security`, `deploy`, or `test`.",
            "",
            "## Designed for",
            "",
            "| Audience | What they get |",
            "| --- | --- |",
            "| Agent builders | A ready-made tool taxonomy with side-effect metadata. |",
            "| Coding agents | Decision hints for choosing safer CLIs before acting. |",
            "| Maintainers | A reviewable YAML source of truth instead of a hand-written list. |",
            "",
            "## What's inside",
            "",
            "| Signal | Value |",
            "| --- | ---: |",
            f"| Tool cards | **{len(tools)}** |",
            f"| Category tags | **{len(category_counts)}** |",
            f"| Language/ecosystem tags | **{len(lang_counts)}** |",
            f"| GitHub-backed tools | **{github_backed}** with live star badges |",
            f"| Risk distribution | {risk_summary} |",
            "",
            "## Quick use",
            "",
            "```bash",
            "# Regenerate this README from the YAML registry",
            "python scripts/generate_readme.py",
            "",
            "# Inspect a card",
            "sed -n '1,120p' data/tools/gh.yaml",
            "```",
            "",
            "A tool card looks like this:",
            "",
            "```yaml",
            "name: gh",
            "binary: gh",
            "category:",
            "  - vcs",
            "  - ci",
            "risk:",
            "  level: high",
            "  effects:",
            "    - remote_read",
            "    - remote_write",
            "guardrails:",
            "  - Verify gh auth status before write operations.",
            "```",
            "",
            "## Agent workflow highlights",
            "",
            "These entries are especially useful when designing or hardening agent workflows:",
            "",
        ]
    )

    featured = [
        "bash", "pwsh", "tmux", "pueue",
        "crush", "repomix", "files-to-prompt", "llm",
        "mcp-inspector", "mcp-proxy",
        "actionlint", "zizmor", "detect-secrets", "osv-scanner",
    ]
    for name in featured:
        if name in tool_by_name:
            lines.append(render_tool_line(tool_by_name[name]))

    lines.extend(
        [
            "",
            "## Category map",
            "",
            "The matrix below shows category coverage and risk posture. A tool can appear in more than one category, so totals count category tags rather than unique files.",
            "",
            "> [!IMPORTANT]",
            "> `control plane` categories contain at least one high-risk tool and should be gated by stronger confirmation, auth, and rollback checks in agent workflows.",
            "",
            "| Category | Total | Low | Medium | High | Posture |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for category in sorted(category_counts):
        lines.append(render_category_card(category, category_groups[category], risk_by_category[category]))

    lines.extend(
        [
            "",
            "## Catalog",
            "",
            "Browse by category. Multi-category tools intentionally appear in every relevant section.",
            "",
            "<details open>",
            "<summary><strong>Popular categories</strong></summary>",
            "",
        ]
    )
    for category in top_categories:
        lines.append(f"- [`{category}`](#{slugify(category)}) — {len(category_groups[category])} tools")
    lines.extend(["", "</details>", ""])

    for category in sorted(category_groups):
        lines.append(f"### {category}")
        lines.append("")
        for tool in sorted(category_groups[category], key=lambda item: str(item["name"]).lower()):
            lines.append(render_tool_line(tool))
        lines.append("")

    lines.extend(
        [
            "## Maintaining the registry",
            "",
            "Add or edit a YAML card under [`data/tools/`](data/tools/). Keep entries short, factual, and operational:",
            "",
            "- describe the real command-line action surface an agent can call;",
            "- write `use_when` and `avoid_when` as decision rules, not marketing copy;",
            "- declare risk level and side effects honestly;",
            "- include guardrails for auth, secrets, network calls, writes, deployments, and destructive operations;",
            "- prefer official docs for `docs` or `homepage` links.",
            "",
            "> [!TIP]",
            "> If a tool can mutate remote state, expose secrets, execute generated code, or deploy infrastructure, mark it as high risk and add concrete guardrails.",
            "",
            "The GitHub workflow regenerates this README on pushes to `main` and checks generated output on pull requests.",
            "",
            "---",
            "",
            '<div align="center">',
            "",
            "If this registry saves you time when building or evaluating agents, please consider starring the repo.",
            "",
            "[![GitHub Repo stars](https://img.shields.io/github/stars/Ariestar/awesome-agent-cli?style=social)](https://github.com/Ariestar/awesome-agent-cli)",
            "",
            "</div>",
            "",
        ]
    )

    README.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
