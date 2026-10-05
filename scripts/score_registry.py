#!/usr/bin/env python3
"""Pluggable Agent-Ready Scoring Engine for tool cards."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Protocol

from registry import load_card

ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "data" / "tools"


class ScorerPlugin(Protocol):
    id: str
    name: str

    def score(self, card: dict[str, Any]) -> tuple[int, int, str]:
        """Returns (raw_score, max_score, reasoning)."""
        ...


class MachineReadabilityScorer:
    id = "readability"
    name = "Machine Readability"

    def score(self, card: dict[str, Any]) -> tuple[int, int, str]:
        points = 12
        reasons = []

        summary = str(card.get("summary", "")).lower()
        use_when = " ".join(card.get("use_when", [])).lower()
        corpus = f"{summary} {use_when}"

        if any(term in corpus for term in ("json", "structured", "ast")):
            points += 5
            reasons.append("supports structured data/json")

        if any(term in corpus for term in ("batch", "scriptable", "headless", "automation")):
            points += 4
            reasons.append("headless/automation friendly")
        else:
            points += 2

        if card.get("binary"):
            points += 4

        return min(points, 25), 25, (", ".join(reasons) if reasons else "standard CLI interface")


class SafetyScorer:
    id = "safety"
    name = "Safety & Containment"

    def score(self, card: dict[str, Any]) -> tuple[int, int, str]:
        risk = card.get("risk", {})
        level = str(risk.get("level", "medium")).lower()

        points = {"low": 22, "medium": 16, "high": 10}.get(level, 12)
        reasons = [f"{level} risk level"]

        if risk.get("destructive"):
            points = max(0, points - 6)
            reasons.append("destructive")
        else:
            points += 2

        guardrails = card.get("guardrails", [])
        if guardrails:
            points += 3
            reasons.append(f"{len(guardrails)} guardrail(s)")

        return min(points, 25), 25, ", ".join(reasons)


class EfficiencyScorer:
    id = "efficiency"
    name = "Context Efficiency"

    def score(self, card: dict[str, Any]) -> tuple[int, int, str]:
        risk = card.get("risk", {})
        effects = risk.get("effects", [])

        points = 14
        reasons = []

        if len(effects) <= 2:
            points += 6
            reasons.append("bounded side-effects")
        elif len(effects) <= 4:
            points += 3
            reasons.append("standard effects")
        else:
            points = max(0, points - 2)
            reasons.append("broad side-effects")

        summary = card.get("summary", "")
        word_count = len(summary.split())
        if 5 <= word_count <= 25:
            points += 5
            reasons.append("concise summary")
        else:
            points += 2

        return min(points, 25), 25, ", ".join(reasons)


class MaturityScorer:
    id = "maturity"
    name = "Ecosystem Maturity"

    def score(self, card: dict[str, Any]) -> tuple[int, int, str]:
        points = 10
        reasons = []

        docs = str(card.get("docs", ""))
        if docs.startswith("https://"):
            points += 8
            reasons.append("https documentation")

        homepage = str(card.get("homepage", ""))
        if homepage:
            points += 4

        detect = card.get("detect", {})
        if detect.get("version_args"):
            points += 3
            reasons.append("version detection supported")

        return min(points, 25), 25, ", ".join(reasons)


class ScoringPipeline:
    def __init__(self, plugins: list[ScorerPlugin] | None = None, weights: dict[str, float] | None = None):
        self.plugins = plugins or [
            MachineReadabilityScorer(),
            SafetyScorer(),
            EfficiencyScorer(),
            MaturityScorer(),
        ]
        self.weights = weights or {
            "readability": 0.25,
            "safety": 0.25,
            "efficiency": 0.25,
            "maturity": 0.25,
        }

    def register(self, plugin: ScorerPlugin, weight: float = 0.1) -> None:
        self.plugins.append(plugin)
        self.weights[plugin.id] = weight

    def score_card(self, card: dict[str, Any]) -> dict[str, Any]:
        dimensions = {}
        total_weighted = 0.0

        for plugin in self.plugins:
            raw, max_score, reasoning = plugin.score(card)
            weight = self.weights.get(plugin.id, 0.25)
            weighted = (raw / max_score) * weight * 100.0
            total_weighted += weighted
            dimensions[plugin.id] = {
                "name": plugin.name,
                "score": raw,
                "max": max_score,
                "weight": weight,
                "reasoning": reasoning,
            }

        total = min(100, round(total_weighted))
        grade = "A+" if total >= 90 else "A" if total >= 80 else "B" if total >= 70 else "C" if total >= 60 else "D"

        return {
            "name": card.get("name"),
            "binary": card.get("binary"),
            "category": card.get("category", []),
            "total_score": total,
            "grade": grade,
            "dimensions": dimensions,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate tool cards with Agent-Ready Score")
    parser.add_argument("--category", help="Filter tools by category")
    parser.add_argument("--json", action="store_true", help="Output full JSON evaluation")
    parser.add_argument("--top", type=int, default=20, help="Number of top tools to display")
    args = parser.parse_args()

    pipeline = ScoringPipeline()
    cards = []

    for path in sorted(TOOLS_DIR.glob("*.yaml")):
        card = load_card(path)
        if args.category and args.category not in card.get("category", []):
            continue
        evaluated = pipeline.score_card(card)
        cards.append(evaluated)

    cards.sort(key=lambda c: -c["total_score"])

    if args.json:
        print(json.dumps(cards, indent=2, ensure_ascii=False))
        return 0

    print(f"{'Tool':<22} {'Score':<8} {'Grade':<8} {'Category':<24} {'Summary Reasons'}")
    print("-" * 80)
    for c in cards[: args.top]:
        dims = c["dimensions"]
        reasons = "; ".join(dims[k]["reasoning"] for k in ("readability", "safety") if k in dims)
        cats = ", ".join(c["category"][:2])
        print(f"{c['name']:<22} {c['total_score']:<8} {c['grade']:<8} {cats:<24} {reasons[:40]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
