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

**Trigger phrase for demo**: *"Localize this invoice output class for Vietnam e-invoicing: [PRESET_CODE]"*

When the user sends the trigger phrase containing the preset code below, agents should analyze it using the Vietnam background knowledge above and produce the expected outputs described in the "Expected Agent Outputs" section.

### Preset ABAP Code (paste this into the demo message)

```abap
CLASS zcl_invoice_output DEFINITION
  PUBLIC
  FINAL
  CREATE PUBLIC.

  PUBLIC SECTION.
    METHODS:
      generate_invoice
        IMPORTING
          iv_vbeln TYPE vbeln_vf
        EXPORTING
          ev_xml   TYPE string,

      validate_tax_data
        IMPORTING
          iv_stceg TYPE stceg
        RETURNING
          VALUE(rv_valid) TYPE abap_bool.

  PRIVATE SECTION.
    METHODS:
      get_invoice_header
        IMPORTING
          iv_vbeln   TYPE vbeln_vf
        RETURNING
          VALUE(rs_header) TYPE zs_inv_header,

      build_xml_output
        IMPORTING
          is_header  TYPE zs_inv_header
        RETURNING
          VALUE(rv_xml) TYPE string.

ENDCLASS.

CLASS zcl_invoice_output IMPLEMENTATION.

  METHOD generate_invoice.
    DATA(ls_header) = get_invoice_header( iv_vbeln ).
    ev_xml = build_xml_output( ls_header ).
  ENDMETHOD.

  METHOD validate_tax_data.
    " Basic tax ID validation - generic format check only
    IF strlen( iv_stceg ) BETWEEN 10 AND 14.
      rv_valid = abap_true.
    ENDIF.
  ENDMETHOD.

  METHOD get_invoice_header.
    SELECT SINGLE
      vbeln, fkdat, waerk, netwr, mwsbp,
      kunrg, name1, stceg AS seller_tax_id
    FROM vbrk
    INTO CORRESPONDING FIELDS OF rs_header
    WHERE vbeln = iv_vbeln.
  ENDMETHOD.

  METHOD build_xml_output.
    " Generic XML output - not country-specific
    rv_xml = |<Invoice>| &&
             |<Date>{ is_header-fkdat }</Date>| &&
             |<Amount>{ is_header-netwr }</Amount>| &&
             |<Tax>{ is_header-mwsbp }</Tax>| &&
             |</Invoice>|.
  ENDMETHOD.

ENDCLASS.
```

### What This Code Represents

This is a generic invoice output class used across multiple countries. It has no Vietnam-specific logic, missing required VN fields, and uses a generic tax validation that does not enforce Vietnam's 10-digit MST format.

### Expected Agent Outputs (for guiding prompt injection)

**SAP Regulatory Researcher should surface:**
- Decree 123/2020/ND-CP mandatory fields: MST (10-digit tax code), invoice series, sequential number, digital signature, buyer tax code
- SAP Notes 3099869 and 3158633 for DRC Vietnam
- Requirement for transmission to HTKK portal or certified e-invoice provider

**SAP ABAP Explorer should identify:**
- Package `LOCO_VN`, base class `CL_EDIN_OUTPUT_BASE` to extend
- Existing `CL_EDIN_VN_*` series as reference
- Custom table `ZTVINV_SERIES` for invoice series management

**SAP Localization Advisor should flag these gaps in the code:**
1. `validate_tax_data` — accepts 10-14 chars, must enforce exactly 10 digits for Vietnam MST
2. `get_invoice_header` — missing buyer tax code (`stceg` on customer master), invoice series, sequential number
3. `build_xml_output` — generic XML, must follow VN e-invoice XML schema (TTĐT format) with namespace
4. No digital signature method — must add `sign_invoice` method calling VN CA API
5. No transmission method — must add `transmit_to_portal` for HTKK or provider API call

**SAP Solution Architect final plan should include:**
- Extend `zcl_invoice_output` or create `zcl_vn_invoice_output` inheriting from `CL_EDIN_OUTPUT_BASE`
- Add `validate_vn_tax_id` enforcing `/^[0-9]{10}(-[0-9]{3})?$/` pattern
- Enrich header query with buyer MST, invoice series from `ZTVINV_SERIES`
- Implement VN XML schema builder referencing `CL_EDIN_VN_XML_BUILDER`
- Add digital signature via HTTP call to VNPT-CA endpoint
- Add async transmission with status tracking in `ZTVINV_STATUS`
