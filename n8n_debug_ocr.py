"""
OCR Text Extraction Debugger for n8n
Copy this into an n8n Python Code node to see what's being extracted

This will show you:
1. What text is being received
2. How many items are extracted from each document
3. Sample lines from the OCR text to help debug regex patterns
"""

import re
from collections import defaultdict

# ============================================================================
# SAME FUNCTIONS AS n8n_ocr_reconcile.py (for testing)
# ============================================================================

def clean_ocr_text(text):
    """Clean OCR text by normalizing whitespace and escape characters"""
    text = str(text)
    text = text.replace('\\n', '\n')
    text = text.replace('\\t', '\t')
    text = text.replace('\\\\', ' ')
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def extract_invoice_items(text):
    """Extract line items from invoice OCR text"""
    items = []
    text = clean_ocr_text(text)
    lines = text.split('\n')

    debug_lines = []

    # Track previous lines for description lookup
    prev_lines = []

    for i, line in enumerate(lines):
        line = line.strip()

        if not line or len(line) < 5:
            continue

        # Skip headers and common text
        skip_patterns = [
            r'^(?:CUSTOMER|INVOICE|DELIVERY|ADDRESS|ORDER|NUMBER|QTY|PRICE|DESCRIPTION|TOTAL|PAGE|DATE|TAXPOINT)',
            r'^(?:DEL|CUSTOMER)\s+(?:ADV|ORDER)',  # Skip "DEL ADV NUMBER", "CUSTOMER ORDER" etc
            r'^[-=]+$',
            r'^\d+\s+of\s+\d+',
            r'^(?:EA|PK)\s*$',
            r'^Cromwell\s+Tools',
            r'^Telephone|^Fax',
            r'^\d{4}-\d{2}-\d{2}'
        ]

        if any(re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
            continue

        # NEW PATTERN: Match quantity/price line format
        # Format: "2 103.790 EA 0.00 207.58 1" or "1 2.310 EA 0.00 4.62 1"
        # Pattern: [QTY] [PRICE with 2-3 decimals] [UNIT] [DISCOUNT] [TOTAL] [optional extra digit]
        item_pattern = r'^(\d+)\s+(\d+\.\d{2,3})\s+(EA|PK|PC|BOX|SET|EACH)\s+\d+\.\d+\s+(\d+\.\d+)'

        match = re.search(item_pattern, line, re.IGNORECASE)

        if match:
            quantity = int(match.group(1))
            price = float(match.group(2))
            unit = match.group(3).upper()
            total_value = float(match.group(4))

            # Look back 1-3 lines for description (product name)
            description = ""
            part_number = ""

            for j in range(1, min(4, len(prev_lines) + 1)):
                prev_line = prev_lines[-j] if len(prev_lines) >= j else ""

                # Look for part number pattern (e.g., "Our part no. PMT1060011P")
                if 'part no.' in prev_line.lower():
                    # Extract the part number AFTER "part no."
                    part_match = re.search(r'part\s+no[.:\s]+([A-Z0-9]{6,})', prev_line, re.IGNORECASE)
                    if part_match:
                        part_number = part_match.group(1).upper()

                # Look for description (product name line - usually has caps and dashes)
                elif re.search(r'^[A-Z0-9][A-Z0-9\s\-\/]+', prev_line) and len(prev_line) > 5:
                    # Avoid lines that are addresses or headers
                    # IMPORTANT: Also avoid lines with decimal numbers (these are quantity/price lines)
                    # Skip address components (LANE, DERBYSHIRE, postcodes, etc)
                    if not re.search(r'(ACCOUNT|LANE|DERBYSHIRE|LIMITED|VEND|UNIT\s+\d+|ROAD|STREET|AVENUE|DRIVE)', prev_line, re.IGNORECASE):
                        # Skip UK postcodes (e.g., S18 2XA, DE21 7BF)
                        if not re.match(r'^[A-Z]{1,2}\d{1,2}\s*\d[A-Z]{2}$', prev_line.strip()):
                            # Check if line contains decimal numbers (quantity/price pattern)
                            if not re.search(r'\d+\.\d+', prev_line):
                                description = prev_line.strip()
                                # Also try to extract part number from description
                                if not part_number:
                                    part_match = re.search(r'\b([A-Z]{2,}\d{3,}[A-Z0-9\-]*)\b', description)
                                    if part_match:
                                        part_number = part_match.group(1)

            if not description:
                description = f"Item (see part no. {part_number})" if part_number else "Unknown item"

            items.append({
                'description': description,
                'part_number': part_number,
                'quantity': quantity,
                'price': price,
                'unit': unit,
                'total_value': total_value
            })
            debug_lines.append(f"✓ MATCHED: {line} -> {description[:40]}")
        else:
            # Keep track of lines that might be items but didn't match
            if len(line) > 15 and not line.startswith(('CUSTOMER', 'INVOICE', 'DELIVERY', 'ADDRESS', 'WEST ', 'UNIT ')):
                debug_lines.append(f"✗ NOT MATCHED: {line}")

        # Keep track of previous lines for description lookup
        prev_lines.append(line)
        if len(prev_lines) > 5:
            prev_lines.pop(0)

    return items, debug_lines


def extract_delivery_items(text):
    """Extract line items from delivery note OCR text"""
    items = []
    text = clean_ocr_text(text)
    lines = text.split('\n')

    debug_lines = []

    for line in lines:
        line = line.strip()

        if not line or len(line) < 10:
            continue

        # Skip headers and garbled lines
        skip_patterns = [
            r'^(?:QTY|QUANTITY|CODE|PART|DESCRIPTION|BRANCH|LINE|DELIVERY|ADVICE|NOTE)',
            r'^[-=]+$',
            r'^R\.gLte',  # Garbled OCR header
            r'^VAI\s+Reg',
            r'^\d+\s+Cho',  # Garbled address
            r'^United\s+',
            r'^VENDA\s+365',
            r'lso\s*\d+',  # Garbled ISO numbers
            r'^Registered\s+in'
        ]

        if any(re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
            continue

        # NEW PATTERN: More flexible matching for delivery notes
        # Format examples:
        # "1 tsc1152169H WSFO18 CCMT"
        # "1sc1152969P WSF149 SNMG 120412.M3M"
        # Try multiple patterns:

        # Pattern 1: QTY PART_NUMBER CODE DESCRIPTION
        # Example: "1 tsc1152169H WSFO18 CCMT"
        pattern1 = r'^(\d+)\s+([a-z0-9]{8,})\s+([A-Z0-9]{3,})\s+(.+?)$'
        match = re.search(pattern1, line, re.IGNORECASE)

        if match:
            quantity = int(match.group(1))
            part_number = match.group(2).upper()
            code = match.group(3).upper()
            description = match.group(4).strip()

            items.append({
                'quantity': quantity,
                'part_number': part_number,
                'code': code,
                'description': description,
                'price': 0.0,
                'total_value': 0.0
            })
            debug_lines.append(f"✓ MATCHED (P1): {line}")
            continue

        # Pattern 2: QTY+PART_NUMBER CODE DESCRIPTION (no space after qty)
        # Example: "1sc1152969P WSF149 SNMG 120412.M3M"
        pattern2 = r'^(\d+)([a-z]{2}[0-9]{7}[A-Z])\s+([A-Z0-9]{3,})\s+(.+?)$'
        match = re.search(pattern2, line, re.IGNORECASE)

        if match:
            quantity = int(match.group(1))
            part_number = match.group(2).upper()
            code = match.group(3).upper()
            description = match.group(4).strip()

            items.append({
                'quantity': quantity,
                'part_number': part_number,
                'code': code,
                'description': description,
                'price': 0.0,
                'total_value': 0.0
            })
            debug_lines.append(f"✓ MATCHED (P2): {line}")
            continue

        # Pattern 3: Generic part number pattern (fallback)
        # Just look for qty + part number with alphanumeric code
        pattern3 = r'^(\d+)\s*([A-Z0-9\-]{6,})\s+(.+)$'
        match = re.search(pattern3, line, re.IGNORECASE)

        if match and len(line) > 15:
            quantity = int(match.group(1))
            part_number = match.group(2).upper()
            description = match.group(3).strip()

            # Extract code from description if possible
            code_match = re.match(r'^([A-Z0-9]{3,})', description)
            code = code_match.group(1) if code_match else ""

            items.append({
                'quantity': quantity,
                'part_number': part_number,
                'code': code,
                'description': description,
                'price': 0.0,
                'total_value': 0.0
            })
            debug_lines.append(f"✓ MATCHED (P3): {line}")
            continue

        # Keep track of potential item lines that didn't match
        if len(line) > 15 and re.match(r'^\d+', line):
            debug_lines.append(f"✗ NOT MATCHED: {line}")

    return items, debug_lines


# ============================================================================
# DEBUG OUTPUT
# ============================================================================

# Get input data from n8n
input_data = items[0]['json']

# Extract OCR text from input
invoice_text = input_data.get('invoice_text', input_data.get('text', ''))
delivery_text = input_data.get('delivery_text', '')

# Parse with debug info
invoice_items, invoice_debug = extract_invoice_items(invoice_text)
delivery_items, delivery_debug = extract_delivery_items(delivery_text)

# Create detailed debug output
results = {
    'extraction_summary': {
        'invoice_items_found': len(invoice_items),
        'delivery_items_found': len(delivery_items),
        'invoice_text_length': len(invoice_text),
        'delivery_text_length': len(delivery_text)
    },
    'invoice_items': invoice_items,
    'delivery_items': delivery_items,
    'invoice_text_sample': '\n'.join(invoice_text.split('\n')[:30]),  # First 30 lines
    'delivery_text_sample': '\n'.join(delivery_text.split('\n')[:30]),  # First 30 lines
    'invoice_debug_lines': invoice_debug[:20],  # First 20 debug lines
    'delivery_debug_lines': delivery_debug[:20],  # First 20 debug lines
}

# Return debug info
return [{'json': results}]
