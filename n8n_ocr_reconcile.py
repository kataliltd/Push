"""
Invoice & Delivery Note Reconciliation for n8n - OCR Text Version
Copy this entire code into an n8n Python Code node

This version handles RAW OCR TEXT OUTPUT (text blobs) instead of pre-structured data.

INPUT FORMAT:
The node expects input with ONE item containing raw OCR text:
{
    "invoice_text": "SALES INVOICE Customer Account No: WE1573 TAXPOINT/DATE: 29/09/25...",
    "delivery_text": "DELIVERY NOTE Qty Code Part No Description..."
}

Or alternatively, if your workflow has the text in a 'text' field from the OCR node:
{
    "text": "SALES INVOICE Customer Account No: WE1573..."
}
In this case, provide both invoice and delivery OCR outputs separately.

OUTPUT FORMAT:
Returns a single item with:
{
    "missing_items": [...],
    "quantity_discrepancies": [...],
    "stats": {...},
    "report_text": "...",
    "metadata": {
        "invoice_number": "...",
        "customer_name": "...",
        ...
    }
}
"""

import re
from collections import defaultdict

# ============================================================================
# OCR TEXT PARSER
# ============================================================================

def clean_ocr_text(text):
    """Clean OCR text by normalizing whitespace and escape characters"""
    text = str(text)
    # Replace common OCR escape characters
    text = text.replace('\\n', '\n')
    text = text.replace('\\t', '\t')
    text = text.replace('\\\\', ' ')
    # Normalize whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def extract_invoice_metadata(text):
    """Extract invoice metadata from OCR text"""
    metadata = {
        'invoice_number': '',
        'customer_account': '',
        'customer_name': '',
        'invoice_date': ''
    }

    # Extract invoice number
    inv_match = re.search(r'INVOICE\s+(?:NO|NUMBER|#)[:\s]+([A-Z0-9]+)', text, re.IGNORECASE)
    if inv_match:
        metadata['invoice_number'] = inv_match.group(1)

    # Extract customer account number
    acct_match = re.search(r'(?:Customer\s+)?Account\s+(?:No|Number|#)[:\s]+([A-Z0-9]+)', text, re.IGNORECASE)
    if acct_match:
        metadata['customer_account'] = acct_match.group(1)

    # Extract invoice date
    date_match = re.search(r'(?:TAX\s*POINT/)?DATE[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})', text, re.IGNORECASE)
    if date_match:
        metadata['invoice_date'] = date_match.group(1)

    # Extract customer name
    name_patterns = [
        r'INVOICE\s+ADDRESS[:\s]+([A-Z][A-Z\s&]+(?:LIMITED|LTD|LLP|PLC))',
        r'CUSTOMER[:\s]+([A-Z][A-Z\s&]+(?:LIMITED|LTD|LLP|PLC))',
        r'BILL\s+TO[:\s]+([A-Z][A-Z\s&]+(?:LIMITED|LTD|LLP|PLC))'
    ]

    for pattern in name_patterns:
        name_match = re.search(pattern, text, re.IGNORECASE)
        if name_match:
            metadata['customer_name'] = name_match.group(1).strip()
            break

    return metadata


def extract_invoice_items(text):
    """Extract line items from invoice OCR text"""
    items = []
    text = clean_ocr_text(text)
    lines = text.split('\n')

    # Track previous lines for description lookup
    prev_lines = []

    for line in lines:
        line = line.strip()

        if not line or len(line) < 5:
            continue

        # Skip headers and common text
        skip_patterns = [
            r'^(?:CUSTOMER|INVOICE|DELIVERY|ADDRESS|ORDER|NUMBER|QTY|PRICE|DESCRIPTION|TOTAL|PAGE|DATE|TAXPOINT)',
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
                    part_match = re.search(r'([A-Z0-9]+[A-Z][A-Z0-9]+)', prev_line, re.IGNORECASE)
                    if part_match:
                        part_number = part_match.group(1).upper()

                # Look for description (product name line - usually has caps and dashes)
                elif re.search(r'^[A-Z0-9][A-Z0-9\s\-\/]+', prev_line) and len(prev_line) > 5:
                    # Avoid lines that are addresses or headers
                    if not re.search(r'(ACCOUNT|LANE|DERBYSHIRE|LIMITED|VEND)', prev_line):
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

        # Keep track of previous lines for description lookup
        prev_lines.append(line)
        if len(prev_lines) > 5:
            prev_lines.pop(0)

    return items


def extract_delivery_metadata(text):
    """Extract delivery note metadata from OCR text"""
    metadata = {
        'delivery_number': '',
        'customer_name': '',
        'delivery_date': ''
    }

    # Extract delivery note number
    del_match = re.search(r'(?:DEL(?:IVERY)?\s+(?:ADV|NOTE)|DELIVERY)\s+(?:NUMBER|NO|#)[:\s]+([A-Z0-9]+)', text, re.IGNORECASE)
    if del_match:
        metadata['delivery_number'] = del_match.group(1)

    # Extract delivery date
    date_match = re.search(r'(?:DATE|DELIVERY\s+DATE)[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})', text, re.IGNORECASE)
    if date_match:
        metadata['delivery_date'] = date_match.group(1)

    # Extract customer name
    name_patterns = [
        r'DELIVERY\s+(?:ADDRESS|TO)[:\s]+([A-Z][A-Z\s&]+(?:LIMITED|LTD|LLP|PLC))',
        r'CUSTOMER[:\s]+([A-Z][A-Z\s&]+(?:LIMITED|LTD|LLP|PLC))'
    ]

    for pattern in name_patterns:
        name_match = re.search(pattern, text, re.IGNORECASE)
        if name_match:
            metadata['customer_name'] = name_match.group(1).strip()
            break

    return metadata


def extract_delivery_items(text):
    """Extract line items from delivery note OCR text"""
    items = []
    text = clean_ocr_text(text)
    lines = text.split('\n')

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

        # Try multiple patterns to handle OCR variations

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

    return items


# ============================================================================
# RECONCILIATION ENGINE (same as before)
# ============================================================================

def normalize_text(text):
    """Normalize text for comparison"""
    text = str(text).upper().strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s*[A-Z]{2}\d+[A-Z]*\s*$', '', text)
    text = re.sub(r'^[^A-Z0-9]+', '', text)
    text = re.sub(r'[^A-Z0-9]+$', '', text)
    return text


def calculate_similarity(text1, text2):
    """Calculate similarity ratio"""
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)

    if norm1 == norm2:
        return 1.0

    if norm1 in norm2 or norm2 in norm1:
        shorter = min(len(norm1), len(norm2))
        longer = max(len(norm1), len(norm2))
        return shorter / longer

    matches = sum(1 for a, b in zip(norm1, norm2) if a == b)
    max_len = max(len(norm1), len(norm2))
    return matches / max_len if max_len > 0 else 0.0


def texts_match(text1, text2, threshold=0.85):
    """Check if two texts match with fuzzy logic"""
    ratio = calculate_similarity(text1, text2)
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)
    substring_match = (norm1 in norm2) or (norm2 in norm1)
    return ratio >= threshold or (substring_match and ratio >= 0.7)


def aggregate_items(items):
    """Aggregate items by normalized description"""
    aggregated = defaultdict(lambda: {
        'quantity': 0.0,
        'total_value': 0.0,
        'price': 0.0,
        'part_numbers': set(),
        'original_description': '',
        'items': []
    })

    for item in items:
        key = normalize_text(item.get('description', ''))

        if not aggregated[key]['original_description']:
            aggregated[key]['original_description'] = item.get('description', '')

        aggregated[key]['quantity'] += float(item.get('quantity', 0))
        aggregated[key]['total_value'] += float(item.get('total_value', 0))

        part_num = item.get('part_number', '')
        if part_num:
            aggregated[key]['part_numbers'].add(part_num)

        aggregated[key]['items'].append(item)

        price = float(item.get('price', 0))
        if price > 0 and aggregated[key]['price'] == 0:
            aggregated[key]['price'] = price

    return dict(aggregated)


def find_matching_key(target_key, search_dict):
    """Find matching key using fuzzy matching"""
    for key in search_dict.keys():
        if texts_match(target_key, key):
            return key
    return None


def reconcile(invoice_items, delivery_items):
    """Main reconciliation function"""
    invoice_agg = aggregate_items(invoice_items)
    delivery_agg = aggregate_items(delivery_items)

    missing_items = []
    quantity_discrepancies = []

    for inv_key, inv_data in invoice_agg.items():
        matching_key = find_matching_key(inv_key, delivery_agg)

        if matching_key is None:
            missing_items.append({
                'description': inv_data['original_description'],
                'part_numbers': list(inv_data['part_numbers']),
                'quantity': inv_data['quantity'],
                'price': inv_data['price'],
                'total_value': inv_data['total_value'],
                'num_lines': len(inv_data['items'])
            })
        else:
            del_data = delivery_agg[matching_key]

            if inv_data['quantity'] > del_data['quantity']:
                quantity_discrepancies.append({
                    'description': inv_data['original_description'],
                    'part_numbers': list(inv_data['part_numbers']),
                    'invoice_quantity': inv_data['quantity'],
                    'delivery_quantity': del_data['quantity'],
                    'difference': inv_data['quantity'] - del_data['quantity'],
                    'price': inv_data['price'],
                    'total_value': inv_data['total_value'],
                    'invoice_lines': len(inv_data['items']),
                    'delivery_lines': len(del_data['items'])
                })

    total_missing_value = sum(item['total_value'] for item in missing_items)
    total_discrepancy_value = sum(item['total_value'] for item in quantity_discrepancies)

    return {
        'missing_items': missing_items,
        'quantity_discrepancies': quantity_discrepancies,
        'stats': {
            'invoice_items': len(invoice_agg),
            'delivery_items': len(delivery_agg),
            'missing_count': len(missing_items),
            'discrepancy_count': len(quantity_discrepancies),
            'missing_value': total_missing_value,
            'discrepancy_value': total_discrepancy_value,
            'total_value': total_missing_value + total_discrepancy_value
        }
    }


def format_report(results):
    """Format results as readable text report"""
    lines = []
    lines.append("=" * 80)
    lines.append("INVOICE & DELIVERY NOTE RECONCILIATION REPORT")
    lines.append("=" * 80)
    lines.append("")

    missing = results['missing_items']
    lines.append(f"STEP 1: Items on Invoice but NOT on Delivery Note ({len(missing)} items)")
    lines.append("-" * 80)

    if missing:
        for i, item in enumerate(missing, 1):
            lines.append(f"\n{i}. {item['description']}")
            part_nums = ', '.join(filter(None, item['part_numbers']))
            if part_nums:
                lines.append(f"   Part Number(s): {part_nums}")
            lines.append(f"   Quantity: {item['quantity']:.0f} @ £{item['price']:.2f}")
            lines.append(f"   Total Value: £{item['total_value']:.2f}")
            if item['num_lines'] > 1:
                lines.append(f"   (Aggregated from {item['num_lines']} invoice lines)")
    else:
        lines.append("\n✓ All invoice items found on delivery note")

    lines.append("\n" + "=" * 80)

    discrepancies = results['quantity_discrepancies']
    lines.append(f"STEP 2: Quantity Discrepancies ({len(discrepancies)} items)")
    lines.append("-" * 80)

    if discrepancies:
        for i, item in enumerate(discrepancies, 1):
            lines.append(f"\n{i}. {item['description']}")
            part_nums = ', '.join(filter(None, item['part_numbers']))
            if part_nums:
                lines.append(f"   Part Number(s): {part_nums}")
            lines.append(f"   Invoice Quantity: {item['invoice_quantity']:.0f}")
            lines.append(f"   Delivery Quantity: {item['delivery_quantity']:.0f}")
            lines.append(f"   ⚠ Difference: {item['difference']:.0f} (Invoice has MORE)")
            lines.append(f"   Price: £{item['price']:.2f}")
            lines.append(f"   Total Value: £{item['total_value']:.2f}")
            if item['invoice_lines'] > 1 or item['delivery_lines'] > 1:
                lines.append(f"   (Invoice: {item['invoice_lines']} lines, "
                           f"Delivery: {item['delivery_lines']} lines)")
    else:
        lines.append("\n✓ No quantity discrepancies found")

    lines.append("\n" + "=" * 80)

    stats = results['stats']
    lines.append("SUMMARY")
    lines.append("-" * 80)
    lines.append(f"Total invoice items (unique): {stats['invoice_items']}")
    lines.append(f"Total delivery items (unique): {stats['delivery_items']}")
    lines.append(f"Items missing from delivery: {stats['missing_count']}")
    lines.append(f"Items with quantity discrepancies: {stats['discrepancy_count']}")
    lines.append("")
    lines.append(f"Total value of missing items: £{stats['missing_value']:.2f}")
    lines.append(f"Total value of items with discrepancies: £{stats['discrepancy_value']:.2f}")
    lines.append(f"Combined total: £{stats['total_value']:.2f}")
    lines.append("")

    if stats['missing_count'] > 0 or stats['discrepancy_count'] > 0:
        lines.append("⚠ ACTION REQUIRED: Please review discrepancies above")
    else:
        lines.append("✓ Invoice and delivery note match perfectly!")

    lines.append("=" * 80)

    return "\n".join(lines)


# ============================================================================
# n8n EXECUTION
# ============================================================================

# Get input data from n8n
input_data = items[0]['json']

# Extract OCR text from input
invoice_text = input_data.get('invoice_text', input_data.get('text', ''))
delivery_text = input_data.get('delivery_text', '')

# If you're using separate OCR nodes for invoice and delivery,
# they might come from different items:
# invoice_text = items[0]['json'].get('text', '')
# delivery_text = items[1]['json'].get('text', '') if len(items) > 1 else ''

# Parse OCR text to extract structured data
invoice_metadata = extract_invoice_metadata(invoice_text)
invoice_items = extract_invoice_items(invoice_text)

delivery_metadata = extract_delivery_metadata(delivery_text)
delivery_items = extract_delivery_items(delivery_text)

# Run reconciliation
results = reconcile(invoice_items, delivery_items)

# Add formatted report text
results['report_text'] = format_report(results)

# Add metadata
results['metadata'] = {
    'invoice_number': invoice_metadata['invoice_number'],
    'invoice_date': invoice_metadata['invoice_date'],
    'customer_account': invoice_metadata['customer_account'],
    'customer_name': invoice_metadata['customer_name'],
    'delivery_number': delivery_metadata['delivery_number'],
    'delivery_date': delivery_metadata['delivery_date']
}

# Add debug info showing how many items were extracted
results['debug'] = {
    'invoice_items_extracted': len(invoice_items),
    'delivery_items_extracted': len(delivery_items),
    'invoice_text_length': len(invoice_text),
    'delivery_text_length': len(delivery_text)
}

# Return results to n8n
return [{'json': results}]
