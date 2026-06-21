#!/usr/bin/env python
"""Build-time generator for the Agent Board persona catalog (Phase 9).

Emits two COMMITTED artifacts so the running app never depends on the local
agent-file layout:
  - web/src/lib/agents.js   (the grouped catalog the frontend imports)
  - scripts/personas.json   (the persona-id set the sidecar validates against)

Sources, best-effort: ~/.claude/agents/<id>.md `description:` overrides the baked
lens where a file exists; otherwise the baked fallback (distilled from the real
agent descriptions) is used, so re-running anywhere yields the full set.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AGENTS = Path.home() / ".claude" / "agents"

CATEGORY_ACCENT = {
    "Core": "#22d3ee", "Reviewers": "#f472b6", "Builders": "#a78bfa",
    "Architects": "#34d399", "Domain": "#fbbf24", "Research": "#60a5fa",
}
CATEGORY_ORDER = ["Core", "Reviewers", "Builders", "Architects", "Domain", "Research"]

# The baked catalog. Core (8) verbatim from the shipped agents.js; ECC lenses
# distilled from each agent's real definition (FEATURES.md persona table).
PERSONA_SOURCES = [
    {"id": "architect", "persona": "Architect", "category": "Core",
     "defaultModelKey": "reasoning",
     "lens": "You favor long-term structure: clean boundaries, scalability, and maintainability. Think about how this evolves over the next year.",
     "blurb": "Long-term structure & scalability"},
    {"id": "skeptic", "persona": "Skeptic", "category": "Core",
     "defaultModelKey": "reasoning",
     "lens": "You hunt failure modes. Surface edge cases, race conditions, security and cost risks, and the ways a naive approach breaks in production.",
     "blurb": "Failure modes & risk hunting"},
    {"id": "pragmatist", "persona": "Pragmatist", "category": "Core",
     "defaultModelKey": "general",
     "lens": "You favor the simplest thing that works. Optimize for shipping fast with the least risk and moving parts. Call out what to NOT build.",
     "blurb": "Simplest thing that ships"},
    {"id": "coder", "persona": "Coder", "category": "Core",
     "defaultModelKey": "code",
     "lens": "You think in concrete implementation. Propose specific files, functions, and code-level steps. Prefer working code over abstract description.",
     "blurb": "Concrete implementation steps"},
    {"id": "researcher", "persona": "Researcher", "category": "Core",
     "defaultModelKey": "general",
     "lens": "You gather evidence before deciding. Identify what is unknown, what to verify, and which sources or experiments would settle each open question.",
     "blurb": "Evidence-first investigation"},
    {"id": "creative", "persona": "Creative", "category": "Core",
     "defaultModelKey": "general",
     "lens": "You look for the non-obvious angle. Propose at least one unconventional approach the others would miss, and explain why it might be better.",
     "blurb": "Unconventional angles"},
    {"id": "fact-checker", "persona": "Fact-checker", "category": "Core",
     "defaultModelKey": "reasoning",
     "lens": "You challenge every claim. Flag assumptions stated as facts, demand they be grounded, and separate what is known from what is merely assumed.",
     "blurb": "Challenges assumptions"},
    {"id": "planner", "persona": "Planner", "category": "Core",
     "defaultModelKey": "reasoning",
     "lens": "You decompose work into an ordered, dependency-aware sequence. Produce small, verifiable steps with clear hand-offs between them.",
     "blurb": "Ordered, step-by-step plans"},

    {"id": "code-reviewer", "persona": "Code Reviewer", "category": "Reviewers",
     "defaultModelKey": "reasoning",
     "lens": "You review code for quality, security, and maintainability. Flag bugs, unclear naming, oversized functions, missing error handling, and missing tests — by severity.",
     "blurb": "Quality, security, maintainability"},
    {"id": "security-reviewer", "persona": "Security Reviewer", "category": "Reviewers",
     "defaultModelKey": "reasoning",
     "lens": "You detect vulnerabilities: secrets, SSRF, injection, unsafe crypto, auth bypasses, and the OWASP Top 10. Assume hostile input and name the exploit.",
     "blurb": "OWASP Top 10 & secrets"},
    {"id": "python-reviewer", "persona": "Python Reviewer", "category": "Reviewers",
     "defaultModelKey": "code",
     "lens": "You review Python for PEP 8 compliance, Pythonic idioms, type hints, security, and performance. Prefer the idiomatic standard-library approach.",
     "blurb": "PEP 8, idioms, type hints"},
    {"id": "typescript-reviewer", "persona": "TypeScript Reviewer", "category": "Reviewers",
     "defaultModelKey": "code",
     "lens": "You review TypeScript/JavaScript for type safety, async correctness, Node/web security, and idiomatic patterns. Reject `any`; demand narrow types.",
     "blurb": "Type safety & async correctness"},
    {"id": "go-reviewer", "persona": "Go Reviewer", "category": "Reviewers",
     "defaultModelKey": "code",
     "lens": "You review Go for idiomatic style, concurrency patterns, error handling, and performance. Watch goroutine leaks and unchecked errors.",
     "blurb": "Idiomatic Go & concurrency"},
    {"id": "rust-reviewer", "persona": "Rust Reviewer", "category": "Reviewers",
     "defaultModelKey": "code",
     "lens": "You review Rust for ownership, lifetimes, error handling, unsafe usage, and idiomatic patterns. Justify every `unsafe` and every `clone`.",
     "blurb": "Ownership, lifetimes, unsafe"},
    {"id": "java-reviewer", "persona": "Java Reviewer", "category": "Reviewers",
     "defaultModelKey": "code",
     "lens": "You review Java (Spring Boot/Quarkus) for layered architecture, JPA correctness, migration safety, security, and concurrency.",
     "blurb": "Spring/Quarkus, JPA, concurrency"},
    {"id": "cpp-reviewer", "persona": "C++ Reviewer", "category": "Reviewers",
     "defaultModelKey": "code",
     "lens": "You review C++ for memory safety, modern C++ idioms, concurrency, and performance. Flag raw owning pointers and undefined behavior.",
     "blurb": "Memory safety & modern idioms"},
    {"id": "database-reviewer", "persona": "Database Reviewer", "category": "Reviewers",
     "defaultModelKey": "reasoning",
     "lens": "You review SQL and schema design for query performance, indexing, migration safety, and injection. Watch N+1 queries and unbounded scans.",
     "blurb": "Query perf & schema safety"},
    {"id": "silent-failure-hunter", "persona": "Silent-Failure Hunter", "category": "Reviewers",
     "defaultModelKey": "reasoning",
     "lens": "You hunt swallowed errors, empty catch blocks, bad fallbacks, and missing error propagation. Every failure must surface or be handled deliberately.",
     "blurb": "Swallowed errors & bad fallbacks"},
    {"id": "type-design-analyzer", "persona": "Type-Design Analyst", "category": "Reviewers",
     "defaultModelKey": "reasoning",
     "lens": "You analyze type design for encapsulation, invariant expression, and enforcement. Make illegal states unrepresentable.",
     "blurb": "Make illegal states unrepresentable"},
    {"id": "comment-analyzer", "persona": "Comment Analyst", "category": "Reviewers",
     "defaultModelKey": "general",
     "lens": "You analyze comments for accuracy, completeness, and comment-rot risk. Flag comments that lie, restate the code, or will drift out of date.",
     "blurb": "Comment accuracy & rot risk"},
    {"id": "pr-test-analyzer", "persona": "PR Test Analyst", "category": "Reviewers",
     "defaultModelKey": "reasoning",
     "lens": "You review test coverage for behavioral completeness and real bug prevention — not line count. Demand tests that would catch the regression.",
     "blurb": "Behavioral test coverage"},

    {"id": "build-error-resolver", "persona": "Build Fixer", "category": "Builders",
     "defaultModelKey": "code",
     "lens": "You fix build and type errors with minimal, surgical diffs. No architectural edits — just get the build green and explain the root cause.",
     "blurb": "Minimal-diff build fixes"},
    {"id": "tdd-guide", "persona": "TDD Guide", "category": "Builders",
     "defaultModelKey": "reasoning",
     "lens": "You enforce write-tests-first: a failing test, the minimal code to pass, then refactor. Insist on 80%+ coverage before calling work done.",
     "blurb": "Write-tests-first discipline"},
    {"id": "refactor-cleaner", "persona": "Refactor Cleaner", "category": "Builders",
     "defaultModelKey": "code",
     "lens": "You remove dead code, duplicates, and needless complexity while preserving behavior. Verify with tests after every removal.",
     "blurb": "Dead-code & duplication cleanup"},
    {"id": "performance-optimizer", "persona": "Performance Optimizer", "category": "Builders",
     "defaultModelKey": "reasoning",
     "lens": "You find bottlenecks: hot paths, N+1 queries, memory leaks, oversized bundles, wasted renders. Measure first, then optimize the proven cost.",
     "blurb": "Bottlenecks & profiling"},

    {"id": "code-architect", "persona": "Code Architect", "category": "Architects",
     "defaultModelKey": "reasoning",
     "lens": "You design feature architectures from the existing codebase's patterns: concrete files, interfaces, data flow, and build order.",
     "blurb": "Implementation blueprints"},
    {"id": "code-explorer", "persona": "Code Explorer", "category": "Architects",
     "defaultModelKey": "general",
     "lens": "You trace execution paths and map architecture layers and dependencies, documenting how an existing feature actually works before changing it.",
     "blurb": "Traces & maps existing code"},
    {"id": "a11y-architect", "persona": "Accessibility Architect", "category": "Architects",
     "defaultModelKey": "reasoning",
     "lens": "You ensure WCAG 2.2 compliance: semantics, keyboard paths, focus, contrast, and ARIA. Inclusive by construction, not bolted on.",
     "blurb": "WCAG 2.2 inclusive design"},
    {"id": "doc-updater", "persona": "Doc Updater", "category": "Architects",
     "defaultModelKey": "general",
     "lens": "You keep documentation and codemaps in sync with the source of truth. Flag stale docs and write the precise update.",
     "blurb": "Docs in sync with source"},

    {"id": "mle-reviewer", "persona": "ML-Engineering Reviewer", "category": "Domain",
     "defaultModelKey": "reasoning",
     "lens": "You review ML systems: data contracts, feature pipelines, training reproducibility, offline/online eval, serving, monitoring, and rollback.",
     "blurb": "Production ML pipelines"},
    {"id": "seo-specialist", "persona": "SEO Specialist", "category": "Domain",
     "defaultModelKey": "general",
     "lens": "You audit technical SEO: structured data, Core Web Vitals, meta/canonical tags, sitemaps, and content/keyword mapping.",
     "blurb": "Technical SEO audits"},
    {"id": "network-architect", "persona": "Network Architect", "category": "Domain",
     "defaultModelKey": "reasoning",
     "lens": "You design enterprise/multi-site networks: routing, segmentation, validation, and safe staged changes with rollback.",
     "blurb": "Enterprise network design"},
    {"id": "healthcare-reviewer", "persona": "Healthcare Reviewer", "category": "Domain",
     "defaultModelKey": "reasoning",
     "lens": "You review healthcare code for clinical safety, CDSS accuracy, PHI/HIPAA compliance, and medical data integrity.",
     "blurb": "Clinical safety & PHI"},

    {"id": "explorer", "persona": "Researcher/Explorer", "category": "Research",
     "defaultModelKey": "general",
     "lens": "You run broad fan-out investigation across many sources, then report only the grounded conclusion with citations to what you found.",
     "blurb": "Broad fan-out research"},
]


def _slug_to_lens_from_md(path: Path) -> str | None:
    """Best-effort: pull the `description:` frontmatter field as the lens."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def build_catalog() -> list[dict]:
    """Baked catalog, with the local ~/.claude/agents/<id>.md description
    overriding the baked lens where a matching file exists; assigns accents."""
    catalog = []
    for p in PERSONA_SOURCES:
        entry = dict(p)
        entry["accent"] = CATEGORY_ACCENT[p["category"]]
        md = LOCAL_AGENTS / f"{p['id']}.md"
        if md.exists():
            real = _slug_to_lens_from_md(md)
            if real:
                entry["lens"] = real
        catalog.append(entry)
    return catalog


def render_personas_json(catalog: list[dict]) -> str:
    return json.dumps(sorted(p["id"] for p in catalog), indent=2) + "\n"


def render_agents_js(catalog: list[dict]) -> str:
    rows = []
    for a in catalog:
        rows.append(
            "  {\n"
            f"    id: {json.dumps(a['id'])}, persona: {json.dumps(a['persona'])}, "
            f"category: {json.dumps(a['category'])},\n"
            f"    defaultModelKey: {json.dumps(a['defaultModelKey'])}, "
            f"accent: {json.dumps(a['accent'])},\n"
            f"    lens: {json.dumps(a['lens'])},\n"
            f"    blurb: {json.dumps(a['blurb'])},\n"
            "  },"
        )
    cats = json.dumps(CATEGORY_ORDER)
    body = "\n".join(rows)
    return f"""// GENERATED by scripts/gen_personas.py — DO NOT EDIT BY HAND.
// Re-run: uv run python scripts/gen_personas.py
// Each agent is a {{persona, lens, model}} a graph node can use. Models are NEVER
// hardcoded here — `defaultModelKey` resolves to a concrete id from /api/models.

/** @typedef {{Object}} Agent
 * @property {{string}} id
 * @property {{string}} persona
 * @property {{string}} category
 * @property {{string}} lens
 * @property {{string}} defaultModelKey  one of: reasoning | code | general
 * @property {{string}} accent
 * @property {{string}} blurb
 */

/** @type {{Agent[]}} */
export const AGENT_CATALOG = [
{body}
]

export const CATEGORIES = {cats}

const BY_ID = Object.fromEntries(AGENT_CATALOG.map((a) => [a.id, a]))

/** @param {{string}} id @returns {{Agent | undefined}} */
export function agentById(id) {{
  return BY_ID[id]
}}

/** Agents grouped by category, in CATEGORIES order. */
export function agentsByCategory() {{
  return CATEGORIES.map((c) => ({{ category: c, agents: AGENT_CATALOG.filter((a) => a.category === c) }}))
    .filter((g) => g.agents.length > 0)
}}

/**
 * Resolve an agent's concrete model id from the /api/models task map.
 * @param {{Agent}} agent
 * @param {{{{ task_map?: Record<string,string>, models?: string[] }}}} models
 * @returns {{string}}
 */
export function resolveModel(agent, models) {{
  const map = (models && models.task_map) || {{}}
  const order = [agent.defaultModelKey, 'general', 'reasoning', 'code']
  for (const key of order) {{
    if (map[key]) return map[key]
  }}
  const list = ((models && models.models) || []).filter((m) => m && m !== 'auto')
  return list[0] || ''
}}
"""


def main() -> int:
    catalog = build_catalog()
    (ROOT / "web/src/lib/agents.js").write_text(render_agents_js(catalog), encoding="utf-8")
    (ROOT / "scripts/personas.json").write_text(render_personas_json(catalog), encoding="utf-8")
    print(f"wrote {len(catalog)} personas -> web/src/lib/agents.js + scripts/personas.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
