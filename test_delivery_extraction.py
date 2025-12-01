#!/usr/bin/env python3
"""
Quick test to verify delivery note extraction improvements
"""

from ocr_text_parser import OCRTextParser

# Test with sample delivery note data that should be VALID
valid_delivery_text = """
DELIVERY NOTE
DEL ADV NUMBER: 123456

5 PMT1201012P TCMT INSERT GRADETB430
8 ISC1153821T WNMG INSERT GRADEIC6025
2 DEB7105350G SOLOPOL LIME 4LTR
3 PMT1060011F A12M-STFCR 11 BORING BAR
"""

# Test with data that should be REJECTED (invalid part numbers)
invalid_delivery_text = """
DELIVERY NOTE

11 0204E-FH INSERT @0ET8430
16 0404E-FF INSERT
65 CHDDISIL D.ir. Widgter
"""

# Test with invoice-like lines that should be SKIPPED
invoice_like_text = """
DELIVERY NOTE

A12M-STFCR 11 BORING BAR
Our part no. PMT1060011P
2 103.790 EA 0.00 207.58 I
"""

parser = OCRTextParser()

print("=" * 70)
print("TEST 1: Valid Delivery Note Items")
print("=" * 70)
result1 = parser.parse_delivery_text(valid_delivery_text)
print(f"Items extracted: {len(result1.items)}")
for item in result1.items:
    print(f"  ✓ {item['quantity']} x {item['part_number']} - {item['description'][:50]}")

print("\n" + "=" * 70)
print("TEST 2: Invalid Part Numbers (should be rejected)")
print("=" * 70)
result2 = parser.parse_delivery_text(invalid_delivery_text)
print(f"Items extracted: {len(result2.items)}")
if len(result2.items) == 0:
    print("  ✓ All invalid items correctly rejected")
else:
    print("  ✗ Some invalid items were accepted:")
    for item in result2.items:
        print(f"    - {item['part_number']} - {item['description']}")

print("\n" + "=" * 70)
print("TEST 3: Invoice Lines (should be skipped)")
print("=" * 70)
result3 = parser.parse_delivery_text(invoice_like_text)
print(f"Items extracted: {len(result3.items)}")
if len(result3.items) == 0:
    print("  ✓ Invoice-like lines correctly skipped")
else:
    print("  ✗ Some invoice lines were parsed:")
    for item in result3.items:
        print(f"    - {item['part_number']} - {item['description']}")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
total_tests = 3
passed_tests = 0

if len(result1.items) > 0:
    passed_tests += 1
    print("✓ Valid items extracted correctly")
else:
    print("✗ Valid items not extracted")

if len(result2.items) == 0:
    passed_tests += 1
    print("✓ Invalid items rejected correctly")
else:
    print("✗ Invalid items not rejected")

if len(result3.items) == 0:
    passed_tests += 1
    print("✓ Invoice lines skipped correctly")
else:
    print("✗ Invoice lines not skipped")

print(f"\nTests passed: {passed_tests}/{total_tests}")
