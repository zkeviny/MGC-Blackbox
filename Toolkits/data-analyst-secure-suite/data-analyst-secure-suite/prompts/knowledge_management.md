# Knowledge Management

This document guides data analysts on how to securely manage knowledge assets — analysis frameworks, prompt templates, business rules, methodologies — in **MGC Blackbox ≥ 1.5.1**, implementing local encrypted storage and zero-exposure access.

All sensitive operations must be explicitly authorized by the user before proceeding.

---

# 1. Overview

MGC Blackbox provides local encrypted storage and zero-exposure access for knowledge content:

- Knowledge content never exposed to AI
- Knowledge decrypted only on the user's local machine
- AI can read knowledge after user authorization, but cannot see plaintext
- All access must be authorized by the user

Knowledge management is the core capability for building reusable analysis systems.

---

# 2. Storable Knowledge Types

| Type | Description | Example |
|------|-------------|---------|
| Analysis Frameworks | Standardized analysis structures | "Monthly Sales Analysis Framework" |
| Prompt Templates | Reusable prompts | "Data Quality Check Prompt" |
| Methodologies | Analysis methods | "Cohort Analysis Methodology" |
| Business Rules | Domain rules | "Customer Segmentation Rules" |
| Best Practices | Experience summaries | "Data Validation Best Practices" |

All knowledge content must be provided by the user; this suite does not generate knowledge content.

---

# 3. How to Securely Store Knowledge Content

Knowledge storage is recommended via **MGC WebUI** or **mgc_save** tool.

---

## Method 1: Via WebUI (Recommended)

1. Start MGC:
   ```
   mgc
   ```
2. Open WebUI:
   ```
   http://127.0.0.1:57218
   ```
3. Navigate to **Save page**
4. Fill in fields:

```
info_type: "prompt" or "knowledge"
info_owner: "framework_monthly_sales"   # Custom name
content: <your knowledge content>
```

---

## Method 2: Via mgc_save

```python
mgc_save(
    info_type="prompt",
    info_owner="framework_monthly_sales",
    content="""
# Monthly Sales Analysis Framework
## Step 1: Data Validation
- Check data completeness
- Verify date range

## Step 2: Key Metrics
- Total revenue
- Growth rate
- Customer count
"""
)
```

---

# 4. How to Securely Read Knowledge Content (Zero-Exposure)

AI can read knowledge after user authorization, but cannot see plaintext content.

---

## Standard Reading Method (Requires User Authorization)

```python
knowledge = mgc_get(
    info_type="prompt",
    info_owner="framework_monthly_sales"
)
```

### Locating Knowledge Entries (Recommended Workflow, v1.4.10+)

Before reading knowledge, locate it with **mgc_find** (fuzzy search by name):

```python
# Fuzzy search for knowledge by name
matches = mgc_find(
    info_owner="framework",  # partial name; substring match by default
    info_type="prompt",
)
# Returns metadata list — never the knowledge plain_text.
# After locating the exact (info_type, info_owner), call mgc_get to read.
```

**Security features**:
- `mgc_find` never returns knowledge plain_text — only metadata
- After locating, `mgc_get` decrypts locally
- All access still requires user authorization

---

## Security Features

- AI cannot see knowledge plaintext
- All access completed locally
- All access must be authorized by the user

---

# 5. How to Use Knowledge Content in Analysis

Knowledge content can be used for:

- Building analysis report structures
- Guiding analysis steps
- Generating prompts
- Reusing business rules
- Reusing methodologies

Example (AI uses knowledge after user authorization):

```
User: "Use the monthly sales analysis framework to analyze this data."

→ AI requests authorization to read knowledge
→ User authorizes
→ AI uses knowledge content to build analysis structure
```

---

# 6. Authorization Template (AI Must Ask)

When AI needs to read knowledge, it must ask the user:

```
Knowledge Name: framework_monthly_sales
Operation: Read Knowledge Content
Authorization Required: YES

Do you authorize reading this knowledge? Reply "yes" to proceed, or "no" to cancel.
```

AI must not read any knowledge without user authorization.

---

# 7. Best Practices

### ✔ 1. Use Descriptive Knowledge Names
For example:
- `framework_monthly_sales`
- `prompt_data_quality_check`
- `rule_customer_segmentation`

### ✔ 2. Knowledge Content Should Be Structured
For example:
- Markdown
- JSON
- Step-by-step structure

### ✔ 3. Do Not Paste Knowledge Plaintext in AI Conversations
AI cannot protect sensitive content.

### ✔ 4. All Reading Requires Authorization
AI must not automatically read knowledge.

---

# 8. FAQ

| Issue | Solution |
|-------|----------|
| Cannot read knowledge | Check whether `info_owner` matches |
| Knowledge is empty | Check whether WebUI stored correctly |
| Sealing failed | Check whether the target node has MGC 1.4.6+ installed |

---

# 9. Summary

This knowledge management document provides:

- Encrypted knowledge storage
- Zero-exposure reading
- User authorization mechanism
- Analysis framework and prompt reuse capabilities

This is the core capability for building reusable analysis systems.