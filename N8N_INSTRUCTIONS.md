# Using the Reconciliation Code in n8n

## Quick Start

### Step 1: Create Python Code Node

1. In your n8n workflow, add a **Code** node
2. Select **Python** as the language
3. Copy the **entire contents** of `n8n_reconcile.py`
4. Paste it into the Python Code editor

### Step 2: Prepare Your Input Data

The Code node expects input in this format:

```json
{
  "invoice": [
    {
      "part_number": "PMT1060011P",
      "description": "A12M-STFCR 11 BORING BAR",
      "quantity": 2,
      "price": 103.79,
      "total_value": 207.58
    },
    {
      "part_number": "SSF9601520K",
      "description": "CLEAR PROTECTIVE OVERGLASSES",
      "quantity": 2,
      "price": 2.31,
      "total_value": 4.62
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

### Step 3: What You Get Out

The node outputs a single item with:

```json
{
  "missing_items": [
    {
      "description": "CLEAR PROTECTIVE OVERGLASSES",
      "part_numbers": ["SSF9601520K"],
      "quantity": 2,
      "price": 2.31,
      "total_value": 4.62,
      "num_lines": 1
    }
  ],
  "quantity_discrepancies": [],
  "stats": {
    "invoice_items": 2,
    "delivery_items": 1,
    "missing_count": 1,
    "discrepancy_count": 0,
    "missing_value": 4.62,
    "discrepancy_value": 0.0,
    "total_value": 4.62
  },
  "report_text": "Full formatted text report here..."
}
```

## Complete n8n Workflow Example

### Workflow Structure

```
[Trigger] → [Prepare Invoice Data] → [Prepare Delivery Data] →
[Merge Data] → [Python Reconciliation] → [Output/Action]
```

### Example Nodes

#### 1. Manual Trigger or Webhook
Start your workflow however you receive the data

#### 2. Set Node - Prepare Invoice Data
```json
{
  "invoice": {{ $json.invoice_items }}
}
```

#### 3. Set Node - Prepare Delivery Data (merge with previous)
Add to the existing data:
```json
{
  "invoice": {{ $json.invoice }},
  "delivery": {{ $json.delivery_items }}
}
```

#### 4. Python Code Node
Paste the entire `n8n_reconcile.py` code here

#### 5. Output Options

**Option A: Send Email with Report**
```
Subject: Invoice Reconciliation Report
Body: {{ $json.report_text }}
```

**Option B: Create Slack Message**
```
Message: Found {{ $json.stats.missing_count }} missing items worth £{{ $json.stats.total_value }}
```

**Option C: Save to Database**
Store the `missing_items` and `quantity_discrepancies` arrays

**Option D: Conditional Alert**
Use an IF node:
```
Condition: {{ $json.stats.total_value > 100 }}
Then: Send urgent notification
Else: Log quietly
```

## Common Data Sources

### From Google Sheets

1. **Google Sheets Node** - Read invoice sheet
2. **Set Node** - Format as:
   ```json
   {
     "invoice": {{ $json }}
   }
   ```

3. **Google Sheets Node** - Read delivery sheet
4. **Set Node** - Merge:
   ```json
   {
     "invoice": {{ $node["Previous Node"].json.invoice }},
     "delivery": {{ $json }}
   }
   ```

### From API/Webhook

If receiving JSON directly from OCR service or API:

```json
{
  "invoice": [/* array from OCR */],
  "delivery": [/* array from OCR */]
}
```

Just pass directly to the Python Code node!

### From Email Attachments

1. **Email Trigger** - Receive emails with attachments
2. **Extract Attachment** - Get CSV/JSON files
3. **Parse** - Convert to JSON format
4. **Prepare Data** - Format for reconciliation
5. **Python Code Node** - Run reconciliation

## Accessing Results in Subsequent Nodes

### Get Missing Items Count
```
{{ $json.stats.missing_count }}
```

### Get Total Value at Risk
```
{{ $json.stats.total_value }}
```

### Loop Through Missing Items
Use **Split Out** node with:
```
{{ $json.missing_items }}
```

Then process each missing item individually.

### Get Full Text Report
```
{{ $json.report_text }}
```

### Check If Any Issues Found
```javascript
{{ $json.stats.missing_count + $json.stats.discrepancy_count > 0 }}
```

## Tips & Tricks

### 1. Adjust Matching Sensitivity

In the code, find this line:
```python
def texts_match(text1, text2, threshold=0.85):
```

- **Lower threshold (0.7-0.8)**: More lenient, catches more matches (good for noisy OCR)
- **Higher threshold (0.9-0.95)**: Stricter matching (good for clean data)

### 2. Handle Empty Data

Add validation before the Python node:

**IF Node**:
```javascript
{{ $json.invoice && $json.delivery &&
   $json.invoice.length > 0 && $json.delivery.length > 0 }}
```

### 3. Format Currency

Use n8n expressions:
```javascript
£{{ $json.stats.total_value.toFixed(2) }}
```

### 4. Date Stamping

Add a Set node after reconciliation:
```json
{
  "reconciliation_date": "{{ $now }}",
  "results": "{{ $json }}"
}
```

### 5. Error Handling

Wrap in Error Trigger node to catch:
- Missing fields
- Invalid data types
- Empty arrays

## Full Workflow JSON

See `n8n_workflow_example.json` for a complete importable workflow.

## Testing in n8n

### Test with Sample Data

1. Use **Manual Trigger** node
2. Add **Set Node** with sample data:
   ```json
   {
     "invoice": [/* paste from sample_invoice.json */],
     "delivery": [/* paste from sample_delivery.json */]
   }
   ```
3. Execute and verify output

### Debugging

- **View Output**: Click on Python Code node after execution
- **Check Logs**: Look at execution logs for errors
- **Step Through**: Execute node by node to isolate issues

## Performance Notes

- Handles hundreds of line items efficiently
- Aggregation happens automatically
- Memory efficient (uses generators where possible)
- Typical execution time: < 1 second for 100 items

## Support

For issues:
1. Check input format matches expected structure
2. Verify both `invoice` and `delivery` arrays exist
3. Ensure items have required fields (`description`, `quantity`)
4. Review threshold if matching seems off
