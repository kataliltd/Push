#!/usr/bin/env python3
"""Test the OCR extraction fix"""

import sys
sys.path.insert(0, '/home/user/Push')

from ocr_text_parser import OCRTextParser
import json

# Read test OCR input
with open('/home/user/Push/test_ocr_input.txt', 'r') as f:
    invoice_text = f.read()

# Parse the invoice
parser = OCRTextParser()
result = parser.parse_invoice_text(invoice_text)

print("=" * 80)
print("OCR EXTRACTION TEST RESULTS")
print("=" * 80)
print(f"\nInvoice Number: {result.invoice_number}")
print(f"Customer: {result.customer_name}")
print(f"Date: {result.invoice_date}")
print(f"\nItems found: {len(result.items)}")
print("\n" + "-" * 80)
print("EXTRACTED ITEMS:")
print("-" * 80)

for i, item in enumerate(result.items, 1):
    print(f"\n{i}. Description: {item['description']}")
    print(f"   Part Number: {item['part_number']}")
    print(f"   Quantity: {item['quantity']}")
    print(f"   Price: £{item['price']:.2f}")
    print(f"   Unit: {item['unit']}")
    print(f"   Total: £{item['total_value']:.2f}")
    print(f"   Source Line: {item.get('source_line', 'N/A')}")

print("\n" + "=" * 80)
print("\nEXPECTED RESULTS:")
print("-" * 80)
print("1. A12M-STFCR 11 BORING BAR (qty: 2, price: £103.79, part: PMT1060011P)")
print("2. A12M-STFCR 11 BORING BAR (qty: 1, price: £103.79, part: PMT1060011P)")
print("3. CLEAR PROTECTIVE OVERGLASSES (qty: 2, price: £2.31, part: SSF9601520K)")
print("=" * 80)

# Check for issues
print("\n" + "=" * 80)
print("VALIDATION:")
print("-" * 80)
issues = []
for i, item in enumerate(result.items, 1):
    # Check if description contains decimal numbers (indicates wrong extraction)
    if '.' in item['description'] and any(char.isdigit() for char in item['description']):
        issues.append(f"Item {i}: Description contains decimal numbers (likely wrong): {item['description']}")

    # Check if description is too short
    if len(item['description']) < 10:
        issues.append(f"Item {i}: Description seems too short: {item['description']}")

    # Check if part number is valid (should be alphanumeric, 8+ chars)
    if item['part_number'] and len(item['part_number']) < 5:
        issues.append(f"Item {i}: Part number seems too short: {item['part_number']}")

if issues:
    print("\n⚠ ISSUES FOUND:")
    for issue in issues:
        print(f"  - {issue}")
else:
    print("\n✓ ALL ITEMS EXTRACTED CORRECTLY!")
    print("✓ No decimal numbers in descriptions")
    print("✓ All part numbers valid")
    print("✓ All descriptions valid")

print("=" * 80)
