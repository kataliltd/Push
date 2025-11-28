#!/usr/bin/env python3
"""
Simple Invoice and Delivery Note Reconciliation Tool

This script compares items between an invoice and a delivery note using JSON input.
Handles fuzzy matching for OCR errors and aggregates quantities.

Usage:
    python reconcile.py invoice.json delivery.json
    python reconcile.py invoice.json delivery.json --output report.txt
"""

import json
import re
from typing import List, Dict, Optional
from dataclasses import dataclass
from difflib import SequenceMatcher
from collections import defaultdict
import sys


@dataclass
class Item:
    """Represents an item from invoice or delivery note"""
    part_number: str
    description: str
    quantity: float
    price: float = 0.0
    total_value: float = 0.0
    unit: str = "EA"


def normalize_text(text: str) -> str:
    """Normalize text for comparison"""
    # Convert to uppercase
    text = text.upper().strip()
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    # Remove common OCR artifacts at end (like IC807, IC6025, etc.)
    text = re.sub(r'\s*[A-Z]{2}\d+[A-Z]*\s*$', '', text)
    # Remove special characters at boundaries
    text = re.sub(r'^[^A-Z0-9]+', '', text)
    text = re.sub(r'[^A-Z0-9]+$', '', text)
    return text


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity ratio between two text strings"""
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)
    return SequenceMatcher(None, norm1, norm2).ratio()


def texts_match(text1: str, text2: str, threshold: float = 0.85) -> bool:
    """
    Check if two texts match, accounting for OCR errors.
    Uses fuzzy matching and substring matching.
    """
    ratio = calculate_similarity(text1, text2)

    # Also check substring matching for descriptions
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)

    # Check if one is contained in the other (for appended codes)
    substring_match = (norm1 in norm2) or (norm2 in norm1)

    # Match if high similarity OR if substring match with decent similarity
    return ratio >= threshold or (substring_match and ratio >= 0.7)


def aggregate_items(items: List[Item]) -> Dict[str, Dict]:
    """
    Aggregate items by normalized description.
    Sums quantities for items with same description.
    """
    aggregated = defaultdict(lambda: {
        'quantity': 0.0,
        'total_value': 0.0,
        'price': 0.0,
        'part_numbers': set(),
        'original_description': '',
        'items': []
    })

    for item in items:
        # Use normalized description as key
        key = normalize_text(item.description)

        if not aggregated[key]['original_description']:
            aggregated[key]['original_description'] = item.description

        aggregated[key]['quantity'] += item.quantity
        aggregated[key]['total_value'] += item.total_value
        aggregated[key]['part_numbers'].add(item.part_number)
        aggregated[key]['items'].append(item)

        # Use first non-zero price
        if item.price > 0 and aggregated[key]['price'] == 0:
            aggregated[key]['price'] = item.price

    return dict(aggregated)


def find_matching_key(target_key: str, search_dict: Dict[str, Dict]) -> Optional[str]:
    """Find a matching key in the search dictionary using fuzzy matching"""
    for key in search_dict.keys():
        if texts_match(target_key, key):
            return key
    return None


def reconcile(invoice_items: List[Item], delivery_items: List[Item]) -> Dict:
    """
    Main reconciliation function.

    Returns dict with:
        - missing_items: Items on invoice but not on delivery
        - quantity_discrepancies: Items where invoice qty > delivery qty
        - stats: Summary statistics
    """
    # Aggregate items
    invoice_agg = aggregate_items(invoice_items)
    delivery_agg = aggregate_items(delivery_items)

    missing_items = []
    quantity_discrepancies = []

    # Check each invoice item
    for inv_key, inv_data in invoice_agg.items():
        # Try to find matching delivery item
        matching_key = find_matching_key(inv_key, delivery_agg)

        if matching_key is None:
            # Item on invoice but not on delivery
            missing_items.append({
                'description': inv_data['original_description'],
                'part_numbers': list(inv_data['part_numbers']),
                'quantity': inv_data['quantity'],
                'price': inv_data['price'],
                'total_value': inv_data['total_value'],
                'num_lines': len(inv_data['items'])
            })
        else:
            # Item exists on both, check quantity
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

    # Calculate statistics
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


def format_report(results: Dict) -> str:
    """Format reconciliation results as a readable report"""
    lines = []
    lines.append("=" * 80)
    lines.append("INVOICE & DELIVERY NOTE RECONCILIATION REPORT")
    lines.append("=" * 80)
    lines.append("")

    # Step 1: Missing items
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

    # Step 2: Quantity discrepancies
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

    # Summary
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


def load_json_file(filepath: str) -> List[Item]:
    """Load items from JSON file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    items = []
    for item_data in data:
        items.append(Item(
            part_number=item_data.get('part_number', ''),
            description=item_data['description'],
            quantity=float(item_data['quantity']),
            price=float(item_data.get('price', 0.0)),
            total_value=float(item_data.get('total_value', 0.0)),
            unit=item_data.get('unit', 'EA')
        ))

    return items


def main():
    """Main entry point"""
    if len(sys.argv) < 3:
        print("Usage: python reconcile.py <invoice.json> <delivery.json> [--output report.txt]")
        print("\nJSON format:")
        print('[')
        print('  {')
        print('    "part_number": "PMT1060011P",')
        print('    "description": "A12M-STFCR 11 BORING BAR",')
        print('    "quantity": 2,')
        print('    "price": 103.79,')
        print('    "total_value": 207.58')
        print('  }')
        print(']')
        sys.exit(1)

    invoice_file = sys.argv[1]
    delivery_file = sys.argv[2]
    output_file = None

    if '--output' in sys.argv:
        output_idx = sys.argv.index('--output')
        if output_idx + 1 < len(sys.argv):
            output_file = sys.argv[output_idx + 1]

    # Load data
    print(f"Loading invoice from: {invoice_file}")
    invoice_items = load_json_file(invoice_file)
    print(f"  Found {len(invoice_items)} invoice line items")

    print(f"\nLoading delivery note from: {delivery_file}")
    delivery_items = load_json_file(delivery_file)
    print(f"  Found {len(delivery_items)} delivery line items")

    # Reconcile
    print("\nReconciling...")
    results = reconcile(invoice_items, delivery_items)

    # Generate report
    report = format_report(results)

    # Output
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n✓ Report written to: {output_file}")
        print("\nQuick Summary:")
        print(f"  Missing items: {results['stats']['missing_count']}")
        print(f"  Quantity discrepancies: {results['stats']['discrepancy_count']}")
        print(f"  Total value at risk: £{results['stats']['total_value']:.2f}")
    else:
        print("\n" + report)


if __name__ == '__main__':
    main()
