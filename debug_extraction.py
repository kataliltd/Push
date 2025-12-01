#!/usr/bin/env python3
"""
Debug script to understand why delivery note extraction is missing items
"""

import re

# Sample problematic lines from the OCR
test_cases = [
    # From line 442-446 area (should extract 12 items based on qty)
    "12\ntscl 152226W\nwsrsz+\nCNMG 120408-M3M INSERT GRADEIC6O2S\nAA07-1",
    # From line 450 area (should extract 1 item)
    "1 tsc1152169H WSFO18 CCMT O9T3O8.SM INSERT GRADE IC9O7",
    # From line 453-456 area (should extract 12 items)
    "12\nrsc1316880N\nwsF491\nTAG N3J INSERT GRADE IC8O7\n4806-7",
    # Single line with leading junk
    "--\\- rz 12 tscl152226W wsrsz+ CNMG 120408-M3M INSERT GRADEIC6O2S",
    "-+\" 1 tsc1152169H WSFO18 CCMT O9T3O8.SM INSERT GRADE IC9O7",
    "-\\ 12 rsc1316880N wsF491 TAG N3J INSERT GRADE IC8O7",
    # Line 625-631 area
    "10 HRN1208800G wsF573 S1OO.O3OO.E2 INSERT GRADE TF45",
    # Line 642
    "2 HAL96'14183A",
]

def clean_ocr_text(text):
    """Clean OCR text by normalizing whitespace and escape characters"""
    text = str(text)
    text = text.replace('\\n', '\n')
    text = text.replace('\\t', '\t')
    text = text.replace('\\\\', ' ')
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

def is_valid_part_number(pn):
    """Check if string looks like a valid part number"""
    pn = pn.replace(' ', '').replace("'", '').upper()
    if len(pn) < 9:
        return False
    if pn[0].isdigit():
        if pn[0] == '1':
            pn = 'I' + pn[1:]
        elif pn[0] == '0':
            pn = 'O' + pn[1:]
        elif pn[0] in '23456789':
            return False
    if not re.match(r'^[A-Z]{2,4}', pn):
        return False
    if not re.search(r'\d{4,}', pn):
        return False
    if not re.match(r'^[A-Z]{2,4}\d{4,}[A-Z0-9]$', pn):
        return False
    return True

print("=" * 80)
print("DEBUGGING DELIVERY NOTE EXTRACTION")
print("=" * 80)

for i, test in enumerate(test_cases, 1):
    print(f"\n{'='*80}")
    print(f"TEST CASE {i}:")
    print(f"{'='*80}")
    print(f"Input: {repr(test)}")

    lines = test.split('\n')
    print(f"Lines: {lines}")

    # Try cleaning leading artifacts
    for line in lines:
        print(f"\n  Processing line: {repr(line)}")

        # Strip leading OCR artifacts
        cleaned = re.sub(r'^[^0-9]+', '', line)
        print(f"    After strip non-digits: {repr(cleaned)}")

        if cleaned and cleaned[0].isdigit():
            cleaned2 = re.sub(r'^(\d{1,3})[^\d\sA-Za-z]*\s*', r'\1 ', cleaned)
            print(f"    After strip junk after digits: {repr(cleaned2)}")

            # Try pattern matching
            pattern1 = r'^(\d{1,3})\s+[^\d\sA-Za-z]{0,4}\s*([A-Za-z0-9\'\s]{2,}\d{5,}[A-Za-z0-9]*)\s+([A-Za-z0-9\-\']{3,})\s+(.+)$'
            match = re.search(pattern1, cleaned2)
            if match:
                qty = match.group(1)
                pn = match.group(2)
                code = match.group(3)
                desc = match.group(4)
                valid = is_valid_part_number(pn)
                print(f"    ✓ MATCH! QTY={qty}, PN={pn}, CODE={code}, VALID={valid}")
            else:
                print(f"    ✗ No match on pattern1")

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
