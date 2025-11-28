"""
Invoice & Delivery Note Reconciliation for n8n
Copy this entire code into an n8n Python Code node

INPUT FORMAT:
The node expects input with two items:
- items[0].json.invoice = array of invoice items
- items[0].json.delivery = array of delivery items

Each item should have:
{
    "part_number": "PMT1060011P",
    "description": "A12M-STFCR 11 BORING BAR",
    "quantity": 2,
    "price": 103.79,        # optional for delivery
    "total_value": 207.58   # optional for delivery
}

OUTPUT FORMAT:
Returns a single item with:
{
    "missing_items": [...],
    "quantity_discrepancies": [...],
    "stats": {...},
    "report_text": "..."
}
"""

import re
from collections import defaultdict

# ============================================================================
# CORE FUNCTIONS
# ============================================================================

def normalize_text(text):
    """Normalize text for comparison"""
    text = str(text).upper().strip()
    text = re.sub(r'\s+', ' ', text)
    # Remove OCR artifacts like IC807, IC6025, TB430
    text = re.sub(r'\s*[A-Z]{2}\d+[A-Z]*\s*$', '', text)
    text = re.sub(r'^[^A-Z0-9]+', '', text)
    text = re.sub(r'[^A-Z0-9]+$', '', text)
    return text


def calculate_similarity(text1, text2):
    """Calculate similarity ratio using sequence matching"""
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)

    # Simple similarity calculation
    if norm1 == norm2:
        return 1.0

    # Check substring matching
    if norm1 in norm2 or norm2 in norm1:
        shorter = min(len(norm1), len(norm2))
        longer = max(len(norm1), len(norm2))
        return shorter / longer

    # Character-based similarity
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

invoice_items = input_data.get('invoice', [])
delivery_items = input_data.get('delivery', [])

# Run reconciliation
results = reconcile(invoice_items, delivery_items)

# Add formatted report text
results['report_text'] = format_report(results)

# Return results to n8n
return [{'json': results}]
