#!/usr/bin/env python3
"""Test fallback pattern on specific lines"""

import re

def normalize_part_number(pn):
    pn = pn.replace(' ', '').replace("'", '').upper()
    if pn and pn[0] in '10':
        if pn[0] == '1':
            pn = 'I' + pn[1:]
        elif pn[0] == '0':
            pn = 'O' + pn[1:]
    return pn

def is_valid_part_number(pn):
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

test_lines = [
    "rz tscl 152226W wsrsz+ CNMG 120408-M3M INSERT GRADEIC6O2S",
    "tscl 152226W wsrsz+ CNMG 120408-M3M INSERT GRADEIC6O2S",
    "rsc1316880N wsF491 TAG N3J INSERT GRADE IC8O7",
    "tND1073430K wsF289 SO16 INSERT SCREW",
    "PMT1201013J wsF196 TNMG 16O4O4E-FF IIISERT GRADETE43O",
]

print("Testing fallback pattern on lines without clear quantity:\n")

for line in test_lines:
    print(f"Line: {line}")

    # Strip leading non-alphanumeric
    cleaned = re.sub(r'^[^A-Za-z0-9]+', '', line)
    print(f"  Cleaned: {cleaned}")

    # Try fallback pattern
    fallback_pattern = r'^([A-Za-z0-9\'\s]{2,4}\d{5,}[A-Za-z0-9]*)\s+([A-Za-z0-9\-\+\*\/]{3,15})\s+(.+)$'
    match = re.search(fallback_pattern, cleaned)

    if match:
        pn = normalize_part_number(match.group(1))
        code = match.group(2).upper()
        desc = match.group(3)
        valid = is_valid_part_number(pn)
        print(f"  ✓ MATCH! PN={pn}, CODE={code}, VALID={valid}")
        if not valid:
            print(f"    (Part number validation failed)")
    else:
        print(f"  ✗ No match")
    print()
