# Handling OCR Text Blob Output - Quick Start Guide

## The Problem

When using OCR tools (like PDF extractors), you might get **raw text blobs** instead of structured data:

```
SALES INVOICE \\ Customer Account No: WE1573\\ TAXPOINT/DATE: 29/09/25 Doc. Count: 1 of 4 \\ INVOICE
ADDRESS \\ WEST SPECIAL FASTENERS LIMITED \\ ***VENDA 365 ACCOUNT*** \\ UNIT 3B, CALLYWHITE
LANE \\ DRONFIELD, DERBYSHIRE \\ S18 2XA \\ Cromwell Tools Sheffield Telephone: ...
```

**This won't work** with the original reconciliation code, which expects structured JSON data.

## The Solution

Use the new **OCR Text Parser** that automatically extracts structured data from raw OCR text.

---

## Option 1: For n8n Workflows (Recommended)

### Step 1: Set Up Your n8n Workflow

Your workflow should look like this:

```
[Extract Data from Invoice (PDF)]
    ↓
[Python Code - OCR Reconciliation]
    ↓
[Process Results]
```

### Step 2: Configure the "Extract Data from Invoice" Node

Make sure your OCR/PDF extraction node outputs the text in a field called `text` or you can customize the field name.

**Important**: You need TWO separate OCR extractions:
- One for the **Invoice PDF**
- One for the **Delivery Note PDF**

### Step 3: Merge the OCR Outputs

Use an **Edit Fields (Set)** node or **Code** node to combine both OCR outputs into one item:

```json
{
  "invoice_text": "{{$json.text from invoice OCR}}",
  "delivery_text": "{{$json.text from delivery OCR}}"
}
```

### Step 4: Add Python Code Node

Copy the **entire contents** of `n8n_ocr_reconcile.py` into a **Python Code** node.

The code will:
1. ✅ Parse the raw OCR text from both documents
2. ✅ Extract invoice metadata (number, date, customer, etc.)
3. ✅ Extract line items (description, quantity, price)
4. ✅ Run the reconciliation
5. ✅ Return structured results + formatted report

### Step 5: Review Output

The Python Code node will return:

```json
{
  "missing_items": [
    {
      "description": "M12 PROTECTIVE CAPS",
      "quantity": 100,
      "price": 0.15,
      "total_value": 15.00
    }
  ],
  "quantity_discrepancies": [...],
  "stats": {
    "missing_count": 1,
    "discrepancy_count": 0,
    "total_value": 15.00
  },
  "report_text": "Full formatted report here...",
  "metadata": {
    "invoice_number": "0012451278",
    "customer_name": "WEST SPECIAL FASTENERS LIMITED",
    "invoice_date": "29/09/25"
  },
  "debug": {
    "invoice_items_extracted": 15,
    "delivery_items_extracted": 13
  }
}
```

---

## Option 2: Standalone Python Script

If you want to use the parser outside of n8n:

### Example Code:

```python
from ocr_text_parser import OCRTextParser, parse_ocr_for_n8n
from invoice_delivery_reconciliation import ReconciliationEngine

# Your raw OCR text
invoice_text = """
SALES INVOICE \\ Customer Account No: WE1573\\ TAXPOINT/DATE: 29/09/25...
A12M-STFCR 11 BORING BAR INSERT 2 103.79 EA 0 207.58 0
M12 PROTECTIVE CAPS 100 0.15 EA 0 15.00 0
"""

delivery_text = """
DELIVERY NOTE
2 EA PMT1060011P A12M-STFCR 11 BORING BAR SHEFF-01
"""

# Parse the OCR text
parser = OCRTextParser()
invoice_data = parser.parse_invoice_text(invoice_text)
delivery_data = parser.parse_delivery_text(delivery_text)

print(f"Found {len(invoice_data.items)} invoice items")
print(f"Found {len(delivery_data.items)} delivery items")

# Run reconciliation
engine = ReconciliationEngine(invoice_data.items, delivery_data.items)
report = engine.generate_report()
print(report)
```

### Or use the helper function:

```python
from ocr_text_parser import parse_ocr_for_n8n
from n8n_reconcile import reconcile, format_report

# Parse both documents at once
data = parse_ocr_for_n8n(invoice_text, delivery_text)

# Reconcile
results = reconcile(data['invoice'], data['delivery'])
print(format_report(results))
```

---

## Troubleshooting

### "No items extracted" or Debug shows 0 items

**Problem**: The OCR text format doesn't match the expected patterns.

**Solution**:
1. Check the `debug` output to see `invoice_text_length` and `delivery_text_length`
2. If text length > 0 but items = 0, the regex patterns need adjustment
3. Provide a sample of your actual OCR text and we can customize the patterns

### Line items not matching correctly

**Problem**: Items appear as "missing" but they're actually on both documents.

**Solution**:
- The fuzzy matching threshold might need adjustment
- OCR text might have extra characters or formatting issues
- Try lowering the threshold in `texts_match()` function (currently 0.85)

### Wrong quantities or prices

**Problem**: Numbers are extracted incorrectly.

**Solution**:
- Check if your OCR output has different decimal separators (comma vs period)
- Verify the OCR text doesn't have spaces in numbers (e.g., "10 3.79" instead of "103.79")
- The regex patterns can be adjusted for different number formats

---

## Common OCR Text Formats

### Format 1: Space-separated line items
```
BORING BAR INSERT 2 103.79 EA 0 207.58
```
Pattern: `[description] [qty] [price] [unit] [discount] [total]`

### Format 2: Tab-separated
```
BORING BAR INSERT\t2\t103.79\tEA\t0\t207.58
```

### Format 3: With part numbers
```
PMT1060011P A12M-STFCR 11 BORING BAR 2 103.79 EA 207.58
```

**The parser handles all these formats automatically!**

---

## Customizing the Parser

If your OCR output has a different format, you can customize the regex patterns in:

1. `extract_invoice_items()` - Line item extraction for invoices
2. `extract_delivery_items()` - Line item extraction for delivery notes
3. `extract_invoice_metadata()` - Header/footer information

### Example: Custom line item pattern

```python
# Change this pattern in n8n_ocr_reconcile.py
item_pattern = r'([A-Z][A-Z0-9\s\-\+\/]+?)\s+(\d+)\s+(\d+\.\d{2})\s+(EA|PK|PC|BOX|SET)\s+(?:\d+\s+)?(\d+\.\d{2})'

# To match your specific format, e.g.:
# Part No: ABC123 | Description: WIDGET | Qty: 5 | Price: 10.00
custom_pattern = r'Part No:\s*([A-Z0-9]+)\s*\|\s*Description:\s*(.+?)\s*\|\s*Qty:\s*(\d+)\s*\|\s*Price:\s*([\d.]+)'
```

---

## Next Steps

1. ✅ Use `n8n_ocr_reconcile.py` in your n8n workflow
2. ✅ Test with a sample invoice and delivery note
3. ✅ Check the `debug` output to verify items are being extracted
4. ✅ Review the `report_text` for the reconciliation results
5. ✅ If needed, customize the regex patterns for your specific OCR format

---

## Files You Need

- **n8n_ocr_reconcile.py** - Complete n8n integration with OCR text parsing (copy this into Python Code node)
- **ocr_text_parser.py** - Standalone parser library (for Python scripts)
- **invoice_delivery_reconciliation.py** - Original reconciliation engine

## Questions?

Common issues and their solutions are in the Troubleshooting section above. If you need help customizing the parser for your specific OCR format, provide:

1. Sample OCR text output (redacted if needed)
2. Expected structure/format
3. Any error messages from the `debug` output
