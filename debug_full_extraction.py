#!/usr/bin/env python3
"""
Full debug of delivery note extraction to see what's being skipped
"""

import re
import sys
sys.path.insert(0, '/home/user/Push')

# Get a sample section of the delivery text (lines 440-500)
delivery_text_sample = """--\\-
rz tscl 152226W
wsrsz+
/
CNMG 120408-M3M INSERT GRADEIC6O2S

AA07-1
AA12-7 €
-+"
1 tsc1152169H WSFO18 CCMT
O9T3O8.SM INI}ERT GRADE IC9O7
12
-\\
rsc1316880N
wsF491
TAG N3J
INSERT GRADE

IC8O7
4806-7
€
AD10-1
.+1
tND1073430K wsF289
SO16 INSERT SCREW
AD10-1
{r
PMT1201013J wsF196
TNMG 16O4O4E-FF IIISERT GRADETE43O"""

# Import the improved extraction
from improved_delivery_extraction import extract_delivery_items_improved

print("=" * 80)
print("DEBUGGING FULL EXTRACTION ON SAMPLE")
print("=" * 80)
print(f"\nInput text:\n{delivery_text_sample}\n")

items = extract_delivery_items_improved(delivery_text_sample)

print(f"\n{'='*80}")
print(f"RESULT: Found {len(items)} items")
print(f"{'='*80}\n")

for i, item in enumerate(items, 1):
    print(f"{i}. QTY: {item['quantity']}, Part#: {item['part_number']}, Code: {item['code']}")
    print(f"   Desc: {item['description'][:60]}")

# Now test individual problematic lines
print("\n" + "=" * 80)
print("TESTING SPECIFIC PROBLEM LINES")
print("=" * 80)

problem_lines = [
    "--\\-\nrz tscl 152226W\nwsrsz+\n/\nCNMG 120408-M3M INSERT GRADEIC6O2S\nAA07-1",
    "12\nrsc1316880N\nwsF491\nTAG N3J\nINSERT GRADE\nIC8O7",
]

for i, test in enumerate(problem_lines, 1):
    print(f"\nTest {i}:")
    print(f"  Input lines: {test.split(chr(10))}")
    items = extract_delivery_items_improved(test)
    print(f"  Found: {len(items)} items")
    if items:
        for item in items:
            print(f"    - QTY: {item['quantity']}, PN: {item['part_number']}, Code: {item['code']}")
