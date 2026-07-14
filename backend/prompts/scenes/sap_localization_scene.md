---
name: sap_localization_scene
description: SAP 本地化研究场景调度指令，支持新国家本地化调研
---

# SAP Localization Research Scene

## Scene Identification

Activate this workflow when:
- User mentions localization, e-invoicing, local tax compliance, or a specific country
- User provides ABAP code and asks for localization analysis
- User asks about SAP implementation for a new country

## Orchestration Flow

### Step 1 — Pre-process (Orchestrator)

Read the user's ABAP code from the message (if provided). Note the target country and business domain.

### Step 2 — Parallel Research (3 agents simultaneously, `blocked_by=[]`)

Dispatch all three tasks at the same time:

**Agent A — SAP Law Researcher** (`agent-sap-law-researcher`):
- Task: Research [country] e-invoicing / localization regulatory requirements
- Background: Include the target country, business domain, and any ABAP code context

**Agent B — SAP ABAP Explorer** (`agent-sap-abap-explorer`):
- Task: Find existing ABAP localization reference implementations for [country]
- Background: Include target country and the object types involved in the user's code

**Agent C — SAP Localization Advisor** (`agent-sap-localization-advisor`):

> **If ABAP code was provided by the user:**
> - Task: Analyze the provided ABAP code for [country] localization gaps
> - Background: Paste the full ABAP code + target country + regulatory context

> **If NO ABAP code was provided:**
> - Task: Based on your SAP Globalization knowledge, describe the typical ABAP objects and code patterns that need to be created or modified when implementing [country] [domain] localization from scratch
> - Background: Target country, domain (e.g. e-invoicing), no existing code available
> - The agent should produce a "what you would typically need to build" analysis rather than a code review

### Step 3 — Synthesis (`blocked_by=[A_thread, B_thread, C_thread]`)

After all three complete, dispatch to **Agent D — SAP Solution Synthesizer** (`agent-sap-solution-synthesizer`):
- Paste all three research outputs in full
- Request a structured development roadmap

### Step 4 — Deliver

Call `respond_to_user` with the final roadmap from Agent D.

---

## Vietnam E-Invoicing Background Knowledge

When the target country is **Vietnam**, agents can use the following verified background:

### Regulatory Framework
- Vietnam's e-invoicing is governed by **Decree 123/2020/ND-CP** and **Circular 78/2021/TT-BTC**, mandatory since July 2022
- Two types: Type 1 (with tax authority code, for most businesses) and Type 2 (without code, for large taxpayers with direct transmission)
- XML format follows Vietnam's national standard; must include seller/buyer tax codes, invoice series, sequential number, and digital signature
- Relevant SAP Note: **3099869** (Vietnam e-invoicing configuration), **3158633** (DRC Vietnam localization)

### Typical ABAP Objects in GLO Repo
- Package: `LOCO_VN` (Vietnam localization)
- Key classes: `CL_EDIN_VN_*` series for eDocument Vietnam
- DRC report IDs: `VA_VN_EINV_*`
- CDS views: `I_VNElectronicDocument*`

### Common Localization Changes Required
1. **Tax code mapping** — Vietnam uses 10-digit tax codes; validate format in `FI/SD` data entry
2. **Invoice series** — Must register with tax authority; stored in custom table `ZTVINV_SERIES`
3. **XML generation** — Extend `CL_EDIN_OUTPUT_BASE` with VN-specific fields
4. **Digital signature** — Integrate with Vietnam CA (e.g., VNPT-CA, Viettel-CA) via ABAP HTTP call
5. **Transmission** — Direct API call to tax authority portal or via certified e-invoice provider

### Risk Notes
- The XML schema has minor version differences between northern and southern tax regions
- Invoice cancellation flow differs from EU model — requires tax authority approval

---

## Demo Preset: Vietnam E-Invoicing Analysis

This section provides background context to help agents give accurate, grounded responses when analyzing ABAP code for Vietnam e-invoicing localization.

### What the Demo Code Represents

The demo code (`zcl_invoice_output`) is a generic invoice output class with no country-specific logic. It has:
- A generic tax ID validator that accepts 10–14 characters (not enforcing Vietnam's exact 10-digit MST format)
- A header query that fetches basic billing fields but misses Vietnam-required fields
- A generic XML builder with no country-specific schema
- No digital signature or transmission methods
