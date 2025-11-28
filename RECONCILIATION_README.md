# Invoice & Delivery Note Reconciliation Tool

A Python tool for comparing invoice and delivery note data to identify discrepancies. Designed to handle OCR errors and match items with fuzzy text matching.

## Features

- **Smart Matching**: Handles OCR errors and extra text in descriptions (e.g., "INSERT GRADE" vs "INSERT GRADEIC6025")
- **Quantity Aggregation**: Automatically sums quantities when the same item appears on multiple lines
- **Discrepancy Detection**:
  - Step 1: Items on invoice but missing from delivery note
  - Step 2: Items where invoice quantity exceeds delivery quantity
- **Financial Summary**: Calculates total value of discrepancies

## Quick Start

### Installation

No external dependencies required! Uses Python 3.6+ standard library only.

### Basic Usage

1. Create JSON files for your invoice and delivery note:

```bash
python reconcile.py sample_invoice.json sample_delivery.json
```

2. Save report to file:

```bash
python reconcile.py sample_invoice.json sample_delivery.json --output report.txt
```

## JSON Format

### Invoice JSON

Each item should include:
- `part_number`: Product part/SKU number
- `description`: Product description
- `quantity`: Quantity ordered
- `price`: Unit price (optional)
- `total_value`: Total line value (optional)
- `unit`: Unit of measure (optional, defaults to "EA")

Example:
```json
[
  {
    "part_number": "PMT1060011P",
    "description": "A12M-STFCR 11 BORING BAR",
    "quantity": 2,
    "price": 103.79,
    "total_value": 207.58,
    "unit": "EA"
  }
]
```

### Delivery Note JSON

Simpler format (no pricing needed):
```json
[
  {
    "part_number": "PMT1060011P",
    "description": "A12M-STFCR 11 BORING BAR",
    "quantity": 2,
    "unit": "EA"
  }
]
```

## How It Works

### 1. Text Normalization

Descriptions are normalized for matching:
- Converted to uppercase
- Extra whitespace removed
- Trailing OCR artifacts removed (e.g., "IC6025", "TB430")
- Special characters at boundaries removed

### 2. Fuzzy Matching

Items are matched using:
- **Similarity score**: Compares normalized descriptions (default threshold: 85%)
- **Substring matching**: Handles cases where one description contains the other

Examples of matches:
- "DNMG 110408-M3M INSERT GRADE" ✓ matches "DNMG 110408-M3M INSERT GRADEIC6025"
- "CLEAR PROTECTIVE OVERGLASSES" ✓ matches "CLEAR PROTECTIVE OVERGLASSESEN166 1FT"

### 3. Quantity Aggregation

If the same item appears multiple times, quantities are automatically summed:
- Invoice has 2 lines of "TCMT INSERT GRADE" (qty 4 + qty 1) = 5 total
- Delivery has 1 line of "TCMT INSERT GRADE" (qty 5)
- ✓ Quantities match

### 4. Discrepancy Detection

**Step 1 - Missing Items**: Items on invoice but not found on delivery note
- Reports item description, part number, quantity, and value
- These items were invoiced but not delivered

**Step 2 - Quantity Discrepancies**: Items where invoice qty > delivery qty
- Reports both quantities and the difference
- These items were partially delivered

## Sample Data

The included `sample_invoice.json` and `sample_delivery.json` demonstrate:

### Expected Discrepancies

Running the sample data will show:

**Missing from Delivery:**
- GLOVES DISPOSABLE BLUE NITRILE 5G (3 PK)
- AURA 9322+ VALVED DUST/MIST RESPIRATOR (5 EA)
- 18762 152x25.4x25.4 9SFNDBWL (2 EA)
- GOPR4CH1600R032HBM KCU20 GOMILL (3 EA)
- SHERWOOD STD TAP & DRILLCOMPOUND (3 EA)
- SNMG 120412-M3M INSERT GRADE (4 EA)
- SNMG 120408E-SF INSERT GRADE (4 EA)

**Quantity Discrepancies:**
- A12M-STFCR 11 BORING BAR: Invoice 3, Delivered 3 (but note: part number differs!)

### Interesting Cases Demonstrated

1. **Aggregation**:
   - BORING BAR appears 2x on invoice (qty 2 + qty 1) = 3 total
   - Compared to delivery qty of 3

2. **Fuzzy Matching**:
   - "DNMG 060408-M3M INSERT GRADE" matches "WNMG 060408-M3M INSERT GRADEIC6025"
   - Note: The "D" vs "W" difference - adjust threshold if too strict

3. **OCR Artifact Handling**:
   - "TAG N3J INSERT GRADE IC807" matches despite trailing code
   - "CLEAR PROTECTIVE OVERGLASSES" matches variant with "EN166 1FT"

## Advanced Usage

### Adjusting Match Threshold

Edit `reconcile.py` to change the similarity threshold:

```python
def texts_match(text1: str, text2: str, threshold: float = 0.85):
    # Lower threshold = more lenient matching (0.7-0.8 for very noisy OCR)
    # Higher threshold = stricter matching (0.9-0.95 for clean data)
```

### Custom Normalization

Extend the `normalize_text()` function for specific OCR patterns:

```python
def normalize_text(text: str) -> str:
    text = text.upper().strip()
    text = re.sub(r'\s+', ' ', text)

    # Add custom patterns here
    text = re.sub(r'\s*YOUR_PATTERN\s*$', '', text)

    return text
```

## Workflow for Your Data

### From OCR Images to JSON

1. **Extract text from OCR** (your images already processed)

2. **Create invoice JSON**:
   - For each line item in the invoice OCR:
   - Extract: part number, description, quantity, price, total
   - Save as JSON array

3. **Create delivery JSON**:
   - For each line in delivery note OCR:
   - Extract: part number, description, quantity
   - Save as JSON array

4. **Run reconciliation**:
   ```bash
   python reconcile.py your_invoice.json your_delivery.json --output report.txt
   ```

5. **Review report**:
   - Check missing items
   - Verify quantity discrepancies
   - Investigate high-value discrepancies first

### Tips for Best Results

- **Clean obvious OCR errors** in part numbers/descriptions before creating JSON
- **Keep descriptions consistent** between invoice and delivery where possible
- **Use original descriptions** - the tool handles variations
- **Review false positives** - adjust threshold if needed
- **Verify high-value discrepancies** manually

## Files

- `reconcile.py` - Main reconciliation script (simple, JSON-based)
- `invoice_delivery_reconciliation.py` - Advanced version with OCR text parsing
- `sample_invoice.json` - Sample invoice data
- `sample_delivery.json` - Sample delivery note data
- `RECONCILIATION_README.md` - This file

## Troubleshooting

### Items not matching when they should

- Check if descriptions are too different (adjust threshold lower)
- Verify part numbers are consistent
- Check for extra spaces or special characters
- Review normalization rules

### Too many false matches

- Increase similarity threshold (0.9 or higher)
- Check normalization isn't removing too much text
- Consider matching on part numbers first, descriptions second

### Aggregation issues

- Verify JSON data has correct quantities
- Check that duplicate items have same/similar descriptions
- Review normalized descriptions in output

## License

MIT License - Free to use and modify

## Support

For issues or questions, review the code comments or adjust the matching logic as needed.
