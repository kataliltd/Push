#!/usr/bin/env python3
"""
Test improved patterns against the problematic lines
"""

import re
import sys
sys.path.insert(0, '/home/user/Push')

from improved_delivery_extraction import extract_delivery_items_improved

# Test cases from the debug analysis
test_lines = {
    'Page 2 Line 4': '3 .V PMT1201013J wsF196 TNMG 16O4O4E-FF INSERT GMDET843O AD10-1',
    'Page 2 Line 10': '1 Y lscl 152612F wsF429 WSF456 TAG N3J INSERT GMDE IC8O8',
    'Page 2 Line 11': "1',l, 1sc1141379H wsF519 CNMG O9O4O8-M3M INSERT GMDEtC6O25 MEZZ-EC2",
    'Page 3 Line 1': '--\\- rz tscl 152226W wsrsz+ / CNMG 120408-M3M INSERT GRADEIC6O2S AA07-1',
    'Page 3 Line 5': '-\\ rsc1316880N wsF491 TAG N3J INSERT GRADE IC8O7 4806-7',
    'Page 3 Line 12': '-\\z 1sc1152969P WSF149 SNMG 120412.M3M INSERT GMDEIC6O25 METZFAI',
    'Page 3 Line 14': "-\\'s 1sc1152226Y wsF529 CNMG 120408.M3M INSERT GRADEICSOo",
    'Page 3 Line 16': '-L1 lscl 141379H WSF489 WSF519 34-274MMIFLEX ELITE PALM COAT',
    'Page 4 Line 8': "2 HAL96'14183A wsF540 cLovEs DlsposABLE BLUE NlrRlLE3.sG",
    'Page 4 Line 10': '2 tscl 152969P wsF149 SNMG 120412.M3M INSERT GRADEtC6O25 ME7zFM',
}

print("=" * 80)
print("TESTING IMPROVED PATTERNS ON PROBLEMATIC LINES")
print("=" * 80)

for name, line in test_lines.items():
    # Create a mini test text with just this line
    items = extract_delivery_items_improved(line)
    if items:
        item = items[0]
        print(f"\n✓ {name}")
        print(f"  QTY: {item['quantity']}, PN: {item['part_number']}, Code: {item['code']}")
    else:
        print(f"\n✗ {name}")
        print(f"  Line: {line[:60]}...")

print("\n" + "=" * 80)
print(f"RESULTS: {sum(1 for name, line in test_lines.items() if extract_delivery_items_improved(line))}/{len(test_lines)} lines extracted")
print("=" * 80)
