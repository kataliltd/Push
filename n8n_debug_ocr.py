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

    for line in lines:
        line = line.strip()

        if not line or len(line) < 10:
            continue

        # Skip headers and common text
        skip_patterns = [
            r'^(?:CUSTOMER|INVOICE|DELIVERY|ADDRESS|ORDER|NUMBER|QTY|PRICE|DESCRIPTION|TOTAL|PAGE|DATE)',
            r'^[-=]+$',
            r'^\d+\s+of\s+\d+',
            r'^(?:EA|PK)\s*$'
        ]

        if any(re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
            continue

        # Match line item pattern
        item_pattern = r'([A-Z][A-Z0-9\s\-\+\/]+?)\s+(\d+)\s+(\d+\.\d{2})\s+(EA|PK|PC|BOX|SET)\s+(?:\d+\s+)?(\d+\.\d{2})'

        match = re.search(item_pattern, line, re.IGNORECASE)

        if match:
            description = match.group(1).strip()
            quantity = int(match.group(2))
            price = float(match.group(3))
            unit = match.group(4).upper()
            total_value = float(match.group(5))

            part_match = re.search(r'\b([A-Z]{2,}\d{3,}[A-Z0-9]*)\b', description)
            part_number = part_match.group(1) if part_match else ""

            items.append({
                'description': description,
                'part_number': part_number,
                'quantity': quantity,
                'price': price,
                'unit': unit,
                'total_value': total_value
            })
            debug_lines.append(f"✓ MATCHED: {line}")
        else:
            # Keep track of lines that might be items but didn't match
            if len(line) > 20 and not line.startswith(('CUSTOMER', 'INVOICE', 'DELIVERY', 'ADDRESS')):
                debug_lines.append(f"✗ NOT MATCHED: {line}")

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

        # Skip headers
        skip_patterns = [
            r'^(?:QTY|QUANTITY|CODE|PART|DESCRIPTION|BRANCH|LINE)',
            r'^[-=]+$'
        ]

        if any(re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
            continue

        # Pattern: QTY CODE PART_NO DESCRIPTION BRANCH
        item_pattern = r'^(\d+)\s+([A-Z]{2,3})\s+([A-Z0-9\-]+)\s+(.+?)(?:\s+([A-Z]{2,}-\d{2}))?$'

        match = re.search(item_pattern, line, re.IGNORECASE)

        if match:
            quantity = int(match.group(1))
            code = match.group(2).upper()
            part_number = match.group(3)
            description = match.group(4).strip()

            items.append({
                'quantity': quantity,
                'part_number': part_number,
                'description': description,
                'price': 0.0,
                'total_value': 0.0
            })
            debug_lines.append(f"✓ MATCHED: {line}")
        else:
            # Keep track of potential item lines
            if len(line) > 20 and re.match(r'^\d+', line):
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
