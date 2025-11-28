# 🚀 Quick Start: Using in n8n (3 Steps)

## Step 1: Copy the Python Code

1. Open the file `n8n_reconcile.py` in this repository
2. **Copy the ENTIRE file contents** (all 262 lines)

## Step 2: Create Python Code Node in n8n

1. In your n8n workflow, add a **Code** node
2. Select **Python** as the language
3. **Paste** the entire code from `n8n_reconcile.py`

## Step 3: Prepare Your Input Data

The Code node needs input in this format:

```json
{
  "invoice": [
    {
      "part_number": "PMT1060011P",
      "description": "A12M-STFCR 11 BORING BAR",
      "quantity": 2,
      "price": 103.79,
      "total_value": 207.58
    }
  ],
  "delivery": [
    {
      "part_number": "PMT1060011P",
      "description": "A12M-STFCR 11 BORING BAR",
      "quantity": 2
    }
  ]
}
```

That's it! ✅

## What You Get Back

The node outputs:

```json
{
  "missing_items": [...],           // Items on invoice but not delivered
  "quantity_discrepancies": [...],  // Items with qty differences
  "stats": {
    "missing_count": 5,
    "discrepancy_count": 2,
    "total_value": 511.80
  },
  "report_text": "Full formatted report..."
}
```

## Common n8n Workflows

### From Google Sheets

```
[Google Sheets: Read Invoice] → [Set: Format Invoice] →
[Google Sheets: Read Delivery] → [Set: Merge Data] →
[Python Code: Reconcile] → [Send Email with Report]
```

### From OCR/API

```
[Webhook: Receive OCR Data] →
[Python Code: Reconcile] →
[IF: Check if issues found] →
  True: [Slack: Alert Team]
  False: [Log: All Good]
```

### From Email Attachments

```
[Email Trigger] → [Extract Attachments] →
[Parse CSV/JSON] → [Python Code: Reconcile] →
[Email: Send Report to Finance]
```

## Accessing Results in Next Node

```javascript
// Get number of missing items
{{ $json.stats.missing_count }}

// Get total value of discrepancies
{{ $json.stats.total_value }}

// Get formatted text report
{{ $json.report_text }}

// Check if any issues
{{ $json.stats.missing_count + $json.stats.discrepancy_count > 0 }}
```

## Example: Send Email Alert

Add **Send Email** node after reconciliation:

**Subject:**
```
Invoice Reconciliation Alert: {{ $json.stats.missing_count }} Missing Items
```

**Body:**
```
{{ $json.report_text }}
```

## Need More Details?

- See `N8N_INSTRUCTIONS.md` for comprehensive guide
- See `n8n_workflow_example.json` to import pre-built workflow
- Test with `sample_invoice.json` and `sample_delivery.json`

## Tips

💡 **Test First**: Use Manual Trigger with sample data to verify it works
💡 **Adjust Threshold**: Find line 68 in code to tune fuzzy matching sensitivity
💡 **Error Handling**: Wrap in Error Trigger node to catch data issues
💡 **Conditional Logic**: Use IF node to route based on discrepancy count

---

**That's all you need!** The code is self-contained with no external dependencies.
