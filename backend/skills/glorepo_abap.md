---
name: glorepo-abap
description: "Use this skill when the user asks about SAP Globalization ABAP artifacts — classes, methods, interfaces, tables, structures, CDS views, programs, function groups/modules, maintenance views, data elements, domains, or any DDIC object. Trigger for: analyzing ABAP class dependencies, finding table fields, exploring CDS view chains, investigating package composition, searching for reusable ABAP implementations, understanding existing code patterns, or designing new ABAP solutions following existing codebase conventions. Also trigger when the user mentions ABAP code, DDIC objects, ABAP development, or SAP localization implementation."
---

# ABAP Developer

## Quick Answers — Single-Turn Lookups

**STOP HERE** if the user's question matches one of these patterns. Answer directly with a single tool call — do NOT read context files, run additional queries, or continue reading this skill.

The KG stores source code as embeddings (TYPE=`CODE`). Two tools search this code:
- `fuzzy_search_codes` (fuzzyScore: 0.95) — finds code by exact technical name
- `search_embeddings` (TYPE=CODE, includeCode=true) — finds code by business meaning

**Case-sensitivity:** NAME filters are case-sensitive. If mixed-case returns empty, retry with fully uppercased name.

| Question Pattern | Action | Example |
|-----------------|--------|---------|
| "List methods of class X" | Run: `python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --traversal class_methods --json --filter class=X` | "List methods of CL_SRF_REPORT_RUNNER" |
| "List fields of table X" | Run: `python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --traversal table_fields --json --filter table=X` | "List fields of BSET" |
| "List fields of structure X" | Run: `python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --traversal structure_fields --json --filter structure=X` | "List fields of ACR_TH_VAT_DATA" |
| "What's in package X?" | Run: `python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --artifact DEVC X --json` | "What's in package FIN_LOC_TH?" |
| "Tell me about class X" | Run: `python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --artifact CLAS X --json` | "Tell me about CL_SRF_REPORT_RUNNER" |
| "Show CDS view X metadata" | Run: `python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --artifact DDLS X --json` | "Show CDS view I_STRPBPTAXITEM" |
| "List interfaces of class X" | Run: `python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --traversal class_interfaces --json --filter class=X` | "List interfaces of CL_SRF_REPORT_RUNNER" |
| "Find code matching pattern X" | Run: `python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --code-search X --json` | "Find code matching IF_SRF_DATA_PROVIDER" |
| "Find code by meaning Y" | Run: `python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --code-search "Y" --semantic --json` | "Find code for VAT tax posting calculation" |
| "What predicates does entity X have?" | Run: `python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --explore {entity_path}` | "Explore ABAPClass/CL_SRF_REPORT_RUNNER" |

These are **single-turn** questions. Run the one tool/script, extract the answer, and respond immediately.

---

## What This Skill Does

This skill analyzes ABAP code and DDIC artifacts stored in GLOREP KG by executing structured SPARQL queries and semantic searches across the ABAP ontology hierarchy. It searches for classes, methods, tables, CDS views, programs, and other technical objects, analyzes their relationships and dependencies, identifies reuse patterns, and provides design recommendations following existing codebase conventions.

The KG contains two complementary data stores:

- **Triple Store (RDF)**: Relationships between artifacts — class→methods, table→fields, package membership, country assignments, etc.
- **Vector Store (Embeddings)**: Semantic descriptions and source code chunks — searchable via natural language or fuzzy text matching

See [glorepo_kg_ontology_hierarchy_abap.md](references/glorepo_kg_ontology_hierarchy_abap.md) — Common Artifact Types section for the full table of ABAP/DDIC artifact types.

## Usage

Apply this skill when:

- Analyzing ABAP class structure — methods, interfaces, dependencies
- Investigating table or structure fields and their relationships
- Exploring CDS view dependency chains
- Understanding package composition — what artifacts belong to a package
- Searching for reusable ABAP implementations
- Designing new ABAP solutions based on existing patterns
- Finding source code patterns via fuzzy search or semantic search
- Investigating country-specific ABAP localization artifacts

## Shared Workflow Reference

See [common_workflow.md](../_shared/glorepo/references/common_workflow.md) for role, query approach selection, general principles, code retrieval strategy, and post-analysis reflection.

## ABAP Ontology Hierarchy

See [glorepo_kg_ontology_hierarchy_abap.md](references/glorepo_kg_ontology_hierarchy_abap.md) for the canonical hierarchy: URI construction patterns, ontology predicates, known empty predicates, and namespace notes.

## Choose: Scripts or Interactive SPARQL

**Default to scripts.** The analysis scripts handle pagination, URI parsing, deduplication, and output formatting — work that manual SPARQL would have to recreate each time. Use interactive SPARQL only for custom queries that no named traversal or `--artifact` mode covers.

Use **analysis scripts** (default) when:
- **Single artifact deep-dive** — `abap_queries.py --artifact {TYPE} {NAME}` covers metadata + relationships
- **Bulk/aggregate tasks** (e.g. "find all interfaces", "list all table fields")
- **Reuse analysis** — `abap_analysis.py` ranks interface reuse, package composition, class complexity
- Results would exceed ~100 rows — scripts handle pagination and avoid context window overflow
- User wants structured JSON output for further processing

Use **interactive SPARQL** (steps below) only when:
- Running a custom query not covered by any of the 13 named traversals or `--artifact` mode
- Exploring a novel ontology relationship or debugging KG data

## Automated Analysis Scripts

Python scripts in `.claude/skills/glorepo-abap/scripts/` that call the MCP HTTP API directly using the shared `mcp_client.py` from `.claude/skills/_shared/glorepo/`.

### Which script to use

| Question | Script | Mode | Expected Runtime |
|----------|--------|------|-----------------|
| "Tell me about class X" | `abap_queries.py` | `--artifact CLAS {name} --json` | ~10-30s |
| "What fields does table X have?" | `abap_queries.py` | `--artifact TABL {name} --json` | ~5-15s |
| "What's in package X?" | `abap_queries.py` | `--artifact DEVC {name} --json` | ~10-30s |
| "Show me CDS view X metadata" | `abap_queries.py` | `--artifact DDLS {name} --json` | ~5-15s |
| "List methods of class X" | `abap_queries.py` | `--traversal class_methods --json --filter class=X` | ~10-30s |
| "What predicates does entity X have?" | `abap_queries.py` | `--explore {entity_path}` | ~2-3s |
| "Which interfaces are most reused?" | `abap_analysis.py` | `--analysis interface_reuse --json` | ~30-60s |
| "Search code for method name X" | `abap_queries.py` | `--code-search {pattern} --json` | ~5-10s |

### `abap_queries.py` — Reusable ABAP Query Library (primary tool)

Covers all ABAP/DDIC ontology traversals with a named registry, SPARQL generation, pagination, and CLI.

**Named traversals:** See [glorepo_kg_ontology_hierarchy_abap.md](references/glorepo_kg_ontology_hierarchy_abap.md) — Named Traversal Registry section for the full table of 13 traversals with ontology paths, variables, fast-path filters, and notes.

**Always provide `--filter`** when running `--traversal`. Without a filter, the script errors out to prevent slow full-graph scans. Every question targets a specific entity — use `--filter class=X`, `--filter table=X`, `--filter package=X`, etc.

**Ontology-aware fast path:** When `--filter` specifies the parent entity (e.g. `--filter class=CL_FOO` for `class_methods`), traversals automatically query directly from that entity's URI instead of scanning all entities. This makes single-entity traversals ~10-50x faster (~2-5s vs 60-120s).

**CLI usage:**

```bash
# List all traversal names
python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --list

# Run any named traversal (JSON output)
python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --traversal class_methods --json --filter class=CL_SRF_REPORT_RUNNER

# Run traversal with parent filter (fast path)
python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --traversal class_methods --json --filter class=CL_ACR_ID_VAT_OUT_XML
python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --traversal table_fields --json --filter table=BSET
python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --traversal package_members --json --filter package=GLO_FIN_IS_VAT_ID

# Explore all predicates for a specific entity
python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --explore ABAPClass/CL_SRF_REPORT_RUNNER

# Single-artifact deep-dive (class)
python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --artifact CLAS CL_SRF_REPORT_RUNNER --json

# Single-artifact deep-dive (table)
python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --artifact TABL BSET --json

# Single-artifact deep-dive (CDS view)
python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --artifact DDLS I_STRPBPTAXITEM --json

# Package composition
python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --artifact DEVC FIN_LOC_TH --json

# Code search (fuzzy — confirms technical name exists in code)
python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --code-search IF_SRF_DATA_PROVIDER --json

# Code search (semantic — finds code by meaning)
python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --code-search "VAT tax posting calculation" --semantic --json

# Output to file
python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_queries.py --artifact CLAS CL_SRF_REPORT_RUNNER -o /tmp/details.json
```

For Python import API, see script docstrings.

### `abap_analysis.py` — Cross-Artifact Reuse Analysis

Uses `abap_queries.py` internally. Runs traversals across all artifacts and computes reuse statistics: most-implemented interfaces, most-populated packages, class complexity (method counts).

```bash
# Human-readable summary
python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_analysis.py

# Full JSON output
python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_analysis.py --json

# Focus on specific analysis
python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_analysis.py --analysis interface_reuse --json
python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_analysis.py --analysis package_composition --json
python3 $HOME/.claude/skills/glorepo-abap/scripts/abap_analysis.py --analysis class_complexity --json
```

## Steps: Interactive Analysis

Follow common workflow steps 1-2 from [common_workflow.md](../_shared/glorepo/references/common_workflow.md), then:

### SPARQL Fallback Protocol

When scripts return empty or partial results, fall back to hand-written SPARQL using `query_triples`. See [glorepo_kg_ontology_hierarchy_abap.md](references/glorepo_kg_ontology_hierarchy_abap.md) — SPARQL Fallback Protocol section, [sparql_templates.md](references/sparql_templates.md) for ABAP query templates, and [glorepo_kg_sparql_reference.md](../_shared/glorepo/references/glorepo_kg_sparql_reference.md) for critical rules and common mistakes.

### 3. ABAP Relationship Analysis
   - Use **query_triples** with specific URIs — see [sparql_templates.md](references/sparql_templates.md) for ABAP query templates

### 4. Code Analysis
   - For **exact pattern search**: use `fuzzy_search_codes` with `fuzzyScore: 0.95`
   - For **semantic search**: use `search_embeddings` with `filters: {"TYPE": "CODE"}` and `includeCode: true`
   - Both tools search the same corpus of ABAP and CDS View source code
   - **Best practice**: Use both approaches together — fuzzy search to find classes by technical name, then semantic search to discover related code by business meaning. Organize results by package or functional area for clarity.
   - Analyze retrieved code for: design patterns, reuse opportunities, dependencies, compatibility
   - Base conclusions **ONLY on retrieved data** — never assume without evidence

## Post-Analysis Reflection

Follow the common reflection step from [common_workflow.md](../_shared/glorepo/references/common_workflow.md) Post-Analysis Reflection, plus these ABAP/DDIC-specific checks:

- Are URI namespaces correct throughout? (CDS → `cdsView/`, Tables → `abapTable/`, Domains → `domain/`, rest → `s4/`)
- If code was retrieved via both fuzzy search and semantic search, are the results reconciled (no contradictory conclusions from different search methods)?
- If package membership was queried, do the artifacts listed match the types expected for that package?
- For design recommendations: are they grounded in actually retrieved code patterns, not assumptions about code that wasn't retrieved?

## Quality Checklist

Common items from [common_workflow.md](../_shared/glorepo/references/common_workflow.md), plus:

- [ ] Artifact type correctly identified (CLAS vs INTF vs PROG, TABL vs STRU vs VIEW, etc.)
- [ ] URI namespace correct (CDS → `cdsView/`, Tables → `abapTable/`, Domains → `domain/`, rest → `s4/`)
- [ ] All relevant relationships queried for the artifact type
- [ ] Code analysis based on actual retrieved code (not assumptions)
- [ ] Package membership verified when analyzing artifact groupings
- [ ] Country codes verified when analyzing localization artifacts
- [ ] Reuse opportunities identified from existing implementations
- [ ] Post-analysis reflection completed (layer completeness, cross-layer consistency)

## Related Skills

None — ABAP is a foundational domain skill. Other domain skills (DRC Report, DRC eDocument) reference this skill for ABAP implementation analysis.
