#!/usr/bin/env python3
"""
Debug multi-line format detection
"""

import re

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

def is_valid_code(code):
    """Check if string looks like a product code"""
    code = code.strip().upper()
    if 3 <= len(code) <= 15:
        if re.match(r'^[A-Z0-9\-]+$', code):
            return True
    return False

# Test cases from delivery note
test_multiline = [
    ("12", "tscl 152226W", "wsrsz+"),  # Should work
    ("12", "rsc1316880N", "wsF491"),   # Should work
    ("10", "HRN1208800G", "wsF573"),   # Should work
    ("2", "HAL96'14183A", "M12-7"),    # Should work
]

print("=" * 80)
print("TESTING MULTI-LINE VALIDATORS")
print("=" * 80)

for qty, pn_raw, code_raw in test_multiline:
    print(f"\nQTY: {qty}")
    print(f"PN raw: {pn_raw}")
    print(f"CODE raw: {code_raw}")

    # Strip leading symbols from part number
    pn_stripped = re.sub(r'^[^A-Za-z0-9]+', '', pn_raw)
    print(f"  PN stripped: {pn_stripped}")

    pn_valid = is_valid_part_number(pn_stripped)
    print(f"  PN valid? {pn_valid}")

    if not pn_valid:
        # Debug why not valid
        pn_test = pn_stripped.replace(' ', '').replace("'", '').upper()
        print(f"    Normalized: {pn_test}")
        print(f"    Length: {len(pn_test)} (need >= 9)")
        letters_match = re.match(r'^[A-Z]{2,4}', pn_test)
        digits_match = re.search(r'\d{4,}', pn_test)
        full_match = re.match(r'^[A-Z]{2,4}\d{4,}[A-Z0-9]$', pn_test)
        print(f"    Starts with letters? {letters_match}")
        print(f"    Has 4+ digits? {digits_match}")
        print(f"    Full pattern match? {full_match}")

    code_valid = is_valid_code(code_raw)
    print(f"  CODE valid? {code_valid}")

    if not code_valid:
        # Debug why not valid
        code_test = code_raw.strip().upper()
        print(f"    Normalized: {code_test}")
        print(f"    Length: {len(code_test)} (need 3-15)")
        alpha_match = re.match(r'^[A-Z0-9\-]+$', code_test)
        print(f"    Alphanumeric? {alpha_match}")

    print(f"  ✓ BOTH VALID" if (pn_valid and code_valid) else "  ✗ FAILED")
