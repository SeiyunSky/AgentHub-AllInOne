---
name: glo-document-grounding
description: Answers generic SAP Globalization questions by searching internal GLO documentation via the l2a-document-grounding MCP tool. Use when users ask about DRC reports, e-invoicing, country-specific localization, SAP Notes, KBAs, or globalization processes.
---

# GLO Document Grounding

A knowledge-retrieval skill for answering SAP Globalization (GLO) questions using internal documentation. It searches the Spec-to-Code document grounding index to find relevant SAP Notes, KBAs, implementation guides, and team documentation.

## Purpose

This skill provides:
- Retrieval-augmented answers grounded in internal SAP Globalization documentation
- SAP Note and KBA lookup with implementation steps
- Country-specific regulatory and localization guidance
- DRC report configuration and troubleshooting references
- e-Invoicing and e-Document process documentation

## When to Use

Invoke this skill when the user asks about:
- SAP Globalization topics (DRC, e-invoicing, localization, statutory reporting)
- SAP Notes or KBAs related to globalization features
- Country-specific regulatory requirements or implementations
- Configuration or troubleshooting of GLO-related features
- Best practices for DRC report development or e-Document setup

## Available Tools

### Spec-to-Code MCP Server

- `l2a-document-grounding`: Vector search over internal SAP GLO documentation. Returns matched documents with content, title, and URL. Parameters:
  - `query` (required): The search query string. Include domain and country terms for best results.
  - `cloud_type` (required): `public_cloud` or `private_cloud`.
  - `component` (optional): ServiceNow application component identifier (e.g., `CA-GTF-CSC-EDO-PL`, `LOD-LH-DRC-PAP`). Automatically resolves to the correct knowledge collection. Preferred over `use_case` when the component is known from case metadata.
  - `use_case` (optional): Target a specific knowledge collection by name (e.g., `poland_support`, `brazil_tax_reform`, `peppol_support`, `spain_support`, `italy_support`, `edoc_framework_support`). When omitted, searches the general collection. Use the pattern `<country>_support` or `<domain>_support`.
  - **Priority**: `component` > `use_case` > context-based routing > general collection fallback.
- `perplexity-search`: Web search for SAP technical knowledge and regulatory information not covered by internal docs.
- `url-retriever`: Fetch and extract content from documentation URLs.

## Workflow

When invoked, this skill will:

1. **Parse the question**: Identify the domain (DRC, e-invoicing, tax, localization), country, product (S/4HANA public/private cloud, DRC Cloud Edition), and specific topic.

2. **Search internal documentation**: Use `l2a-document-grounding` with a clear query that includes domain and country terms. Choose the appropriate `cloud_type` based on the user's context:
   - `public_cloud` for SAP S/4HANA Cloud questions
   - `private_cloud` for SAP S/4HANA on-premise or private cloud questions
   - If the ServiceNow component is known (e.g., from case metadata), pass the `component` parameter to automatically route to the correct collection.
   - Otherwise, if the question is clearly about a specific country or domain, pass the `use_case` parameter to target that collection directly (e.g., `poland_support`, `brazil_tax_reform`, `peppol_support`).

3. **Evaluate results**: Check whether the returned documents sufficiently answer the question.

4. **Supplement if needed**: If internal docs are insufficient, use `perplexity-search` to find additional context from SAP community, help.sap.com, or regulatory sources.

5. **Synthesize and respond**: Provide a concise, grounded answer with references to the source documents (titles and URLs).

## Example Invocations

**By user:**
```
/glo-document-grounding What are the manual activities for SAP Note 3481252?
/glo-document-grounding How do I configure DRC reports for Brazil NFe?
/glo-document-grounding What is the e-invoicing process for France?
/glo-document-grounding Explain the Peppol BIS 3.0 integration in SAP
```

**By Claude (automatic):**
When Claude detects the user is asking a generic GLO knowledge question, it may invoke this skill to ground the answer in internal documentation.

## Best Practices

- Include country names and specific product versions in queries for better search results
- Specify whether the context is public cloud or private cloud
- Use the `component` parameter when the ServiceNow component is known (e.g., from incident metadata) — this is the most reliable routing method
- Use the `use_case` parameter when the query targets a specific country or domain with a dedicated collection (e.g., `poland_support` for Polish localization questions)
- For SAP Note queries, include the note number in the search
- Combine `l2a-document-grounding` results with `perplexity-search` only when internal docs are insufficient
- Always cite source documents in the response

## Output

The skill provides:
- Concise answers grounded in SAP GLO documentation
- References to source documents (title + URL)
- Country-specific and product-specific guidance where applicable

## Settings

- **Model**: Uses Sonnet for balanced speed and capability
- **Invocation**: Can be invoked by both user and Claude
