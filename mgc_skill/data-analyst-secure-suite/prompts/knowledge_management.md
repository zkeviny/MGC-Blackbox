# Knowledge Management Workflow

This document guides data analysts on how to securely manage knowledge assets such as analysis frameworks, prompt templates, business rules, and methodologies in **MGC Blackbox**, implementing local encrypted storage and zero-exposure access.

All sensitive operations must be explicitly authorized by the user before proceeding.

---

# Overview

MGC Blackbox provides local encrypted storage and zero-exposure access for knowledge content:

- Knowledge content never exposed to AI
- Knowledge decrypted only on user's local machine
- AI can read knowledge after user authorization, but cannot see plaintext
- All access requires user authorization

Knowledge management is the core capability for building reusable analysis systems.

---

# Types of Storable Knowledge

| Type | Description | Example |
|------|-------------|---------|
| Analysis Frameworks | Standardized analysis structures | "Monthly Sales Analysis Framework" |
| Prompt Templates | Reusable prompts | "Data Quality Check Prompt" |
| Methodologies | Analysis methods | "Cohort Analysis Methodology" |
| Business Rules | Domain rules | "Customer Segmentation Rules" |
| Best Practices | Experience summaries | "Data Validation Best Practices" |

All knowledge content must be provided by the user; this suite does not generate knowledge content.

---

# How to Securely Store Knowledge Content

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

# How to Securely Read Knowledge Content (Zero-Exposure)

AI can read knowledge after user authorization, but cannot see plaintext content.

---

## Standard Reading Method (Requires User Authorization)

```python
knowledge = mgc_get(
    info_type="prompt",
    info_owner="framework_monthly_sales"
)
```

## Security Features

- AI cannot see knowledge plaintext
- All access completed locally
- All access requires user authorization

---

# How to Use Knowledge Content in Analysis

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

## Security Features

- Recipient can read knowledge locally
- Knowledge content never exposed

---

# Authorization Template (AI Must Ask)

When AI needs to read knowledge, it must ask the user:

```
Knowledge Name: framework_monthly_sales
Operation: Read Knowledge Content
Authorization Required: YES

Do you authorize reading this knowledge? Reply "yes" to proceed or "no" to cancel.
```

AI must not read any knowledge without user authorization.

---

# Best Practices

## 1. Use Descriptive Knowledge Names
For example:
- `framework_monthly_sales`
- `prompt_data_quality_check`
- `rule_customer_segmentation`

## 2. Knowledge Content Should Be Structured
For example:
- Markdown
- JSON
- Step-by-step structure

## 3. Do Not Paste Knowledge Plaintext in AI Conversations
AI cannot protect sensitive content.

## 4. All Reading Requires Authorization
AI must not automatically read knowledge.

---

# FAQ

| Issue | Solution |
|-------|----------|
| Cannot read knowledge | Check if info_owner matches |
| Knowledge is empty | Check if WebUI stored correctly |
| Sealing failed | Check if target node has MGC 1.4.6+ |

---

# Summary

This knowledge management document provides:

- Encrypted knowledge storage
- Zero-exposure reading
- User authorization mechanism
- Analysis framework and prompt reuse capabilities

This is the core capability for building reusable analysis systems.

---
