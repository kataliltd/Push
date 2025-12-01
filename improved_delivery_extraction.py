#!/usr/bin/env python3
"""
Improved delivery note OCR extraction that handles:
1. Leading OCR artifacts (checkmarks, symbols) before quantity
2. Multi-line format where fields are on separate lines
3. Single-line format with all fields on one line
"""

import re
from typing import List, Dict


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


def normalize_part_number(pn):
    """Normalize part number: remove spaces/apostrophes, uppercase, fix OCR errors"""
    pn = pn.replace(' ', '').replace("'", '').upper()
    # Fix common OCR errors: leading '1' -> 'I', leading '0' -> 'O'
    if pn and pn[0] in '10':
        if pn[0] == '1':
            pn = 'I' + pn[1:]
        elif pn[0] == '0':
            pn = 'O' + pn[1:]
    return pn


def is_valid_part_number(pn):
    """
    Check if string looks like a valid part number
    Expected formats:
    - PMT1060011P (3 letters + 7 digits + 1 letter)
    - ISC1152169H (3 letters + 7 digits + 1 letter)
    - HAL96'14183A (with apostrophe from OCR)
    - tsc1152169H (lowercase variants due to OCR)
    - 1sc1152169H (leading '1' is OCR error for 'I')
    """
    # Remove any spaces and apostrophes (OCR errors)
    pn = pn.replace(' ', '').replace("'", '').upper()

    # Must be at least 9 characters
    if len(pn) < 9:
        return False

    # Common OCR errors: leading digits that should be letters
    # Fix: 1 -> I, 0 -> O (only at the start)
    if pn[0].isdigit():
        if pn[0] == '1':
            pn = 'I' + pn[1:]
        elif pn[0] == '0':
            pn = 'O' + pn[1:]
        # If it starts with other digits (2-9), likely not a part number
        elif pn[0] in '23456789':
            return False

    # Should start with letters (2-4 chars) after OCR correction
    if not re.match(r'^[A-Z]{2,4}', pn):
        return False

    # Should contain digits
    if not re.search(r'\d{4,}', pn):
        return False

    # Should end with letter or digit
    if not re.match(r'^[A-Z]{2,4}\d{4,}[A-Z0-9]$', pn):
        return False

    # Should NOT contain common description words
    invalid_patterns = [
        r'INSERT', r'GRADE', r'TOOL', r'BAR', r'BORING',
        r'PROTECTIVE', r'GLASS', r'HAND', r'BLADE'
    ]
    if any(re.search(pattern, pn, re.IGNORECASE) for pattern in invalid_patterns):
        return False

    return True


def is_valid_code(code):
    """Check if string looks like a product code"""
    code = code.strip().upper()
    # Codes are typically 3-15 alphanumeric characters
    if 3 <= len(code) <= 15:
        # Should contain some letters and/or digits
        if re.match(r'^[A-Z0-9\-]+$', code):
            return True
    return False


def extract_delivery_items_improved(text):
    """
    Extract line items from delivery note OCR text with improved handling
    Handles BOTH formats:
    - FORMAT 1 (all on one line): "QTY PART_NUMBER CODE DESCRIPTION"
    - FORMAT 2 (multi-line): each field on separate line

    KEY IMPROVEMENT: Strip leading OCR artifacts (checkmarks, symbols) before parsing
    """
    items = []
    text = clean_ocr_text(text)
    lines = text.split('\n')

    # Process lines with index to enable multi-line lookahead
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # FIRST: Try multi-line format (each field on separate line)
        # Pattern: Line is just a number (quantity), followed by part number, code, description
        if line.isdigit() and 1 <= int(line) <= 999:
            # Potential quantity found, check if next lines are part number and code
            if i + 2 < len(lines):
                potential_qty = int(line)
                potential_pn_raw = lines[i + 1].strip()
                potential_code = lines[i + 2].strip()

                # Strip leading symbols from part number (e.g., "-\ rsc1316880N" -> "rsc1316880N")
                potential_pn = re.sub(r'^[^A-Za-z0-9]+', '', potential_pn_raw)

                # Check if potential part number and code are valid
                if is_valid_part_number(potential_pn) and is_valid_code(potential_code):
                    # Valid multi-line item found!
                    normalized_pn = normalize_part_number(potential_pn)

                    # Collect description from subsequent lines (up to 5 lines or next quantity)
                    description_parts = []
                    desc_idx = i + 3
                    while desc_idx < len(lines) and desc_idx < i + 8:
                        desc_line = lines[desc_idx].strip()
                        # Stop if we hit another quantity (lone digit) or empty line
                        if not desc_line:
                            break
                        if desc_line.isdigit() and 1 <= int(desc_line) <= 999:
                            break
                        # Skip branch/bin codes (like "AB02-1", "M12-7")
                        if re.match(r'^[A-Z]{1,2}\d{2}-\d{1,2}$', desc_line):
                            break
                        description_parts.append(desc_line)
                        desc_idx += 1

                    description = ' '.join(description_parts) if description_parts else potential_code

                    items.append({
                        'quantity': potential_qty,
                        'part_number': normalized_pn,
                        'code': potential_code.upper(),
                        'description': description,
                        'price': 0.0,
                        'total_value': 0.0
                    })

                    # Skip ahead past this item (qty + pn + code + description lines)
                    i = desc_idx
                    continue

        # Continue to single-line format handling below
        i += 1
        line = lines[i-1].strip()  # Get current line for single-line processing

        if not line or len(line) < 10:
            continue

        # **KEY IMPROVEMENT**: Strip leading OCR artifacts
        # Remove leading symbols and letters that aren't part of the quantity
        # Patterns like: "--\- rz 12 ...", "-+" 1 ...", "-\ 12 ...", "-\z 1...", "-\'s 1...", "1',l, 1...", etc.
        # Strategy: Strip everything before the first digit, then also strip symbols AFTER the first digits
        # Step 1: Remove everything before first digit
        cleaned_line = re.sub(r'^[^0-9]+', '', line)
        # Step 2: If line starts with digit(s), remove any symbols/junk between digits and alphanumeric part number
        # Pattern: "1',l, 1sc..." -> "1 1sc..." (removes ',l, ')
        # Pattern: "12z abc..." -> "12 abc..." (removes 'z ')
        if cleaned_line and cleaned_line[0].isdigit():
            # Match: [digits][any junk][part number starting with letter]
            # Replace with: [digits] [part number]
            cleaned_line = re.sub(r'^(\d{1,3})[^\d\sA-Za-z]*\s*', r'\1 ', cleaned_line)

        # If we stripped too much or nothing changed, try original line
        if not cleaned_line or len(cleaned_line) < 10:
            cleaned_line = line

        # Skip headers and garbled lines
        skip_patterns = [
            r'^(?:QTY|QUANTITY|CODE|PART|DESCRIPTION|BRANCH|LINE|DELIVERY|ADVICE|NOTE|DEL\s+ADV)',
            r'^[-=]+$',
            r'^R\.gLte',  # Garbled OCR header
            r'^VAI\s+Reg',
            r'^\d+\s+Cho',  # Garbled address
            r'^United\s+',
            r'^VENDA\s+365',
            r'lso\s*\d+',  # Garbled ISO numbers
            r'^Registered\s+in',
            r'^(?:CUSTOMER|INVOICE|ADDRESS|ORDER|NUMBER|PRICE|TOTAL|PAGE|DATE|TAXPOINT)',
            r'^Cromwell\s+Tools',
            r'^Telephone|^Fax',
            r'^\d{4}-\d{2}-\d{2}',
            # Skip address-like lines
            r'(?:LANE|DERBYSHIRE|LIMITED|UNIT\s+\d+|ROAD|STREET|AVENUE|DRIVE)',
            # Skip UK postcodes
            r'^[A-Z]{1,2}\d{1,2}\s*\d[A-Z]{2}$'
        ]

        if any(re.match(pattern, cleaned_line, re.IGNORECASE) for pattern in skip_patterns):
            continue

        # Skip lines that look like invoice item lines (contain prices with decimals)
        # Invoice lines have patterns like "2 103.790 EA 0.00 207.58"
        if re.search(r'\d+\s+\d+\.\d{2,3}\s+(?:EA|PK|PC|BOX|SET)', cleaned_line, re.IGNORECASE):
            continue

        # Pattern 1: QTY [SYMBOLS] PART_NUMBER CODE DESCRIPTION
        # Example: "5 PMT1201012P TCMT INSERT" or "6 tsc1152169H wsFo18 CCMT..." or "3 .V PMT1201012P ..." or "2 HAL96'14183A ..."
        # Allow optional symbols (NOT letters) between QTY and PART_NUMBER (e.g., ".", "'", ",", etc.)
        # Allow spaces and apostrophes within part numbers (e.g., "lscl 152612F", "HAL96'14183A")
        # Pattern: QTY [optional symbols only] PART_NUMBER (with possible spaces/apostrophes) CODE DESCRIPTION
        pattern1 = r'^(\d{1,3})\s+[^\d\sA-Za-z]{0,4}\s*([A-Za-z0-9\'\s]{2,}\d{5,}[A-Za-z0-9]*)\s+([A-Za-z0-9\-\']{3,})\s+(.+)$'
        match = re.search(pattern1, cleaned_line)

        if match:
            quantity = int(match.group(1))
            part_number = normalize_part_number(match.group(2))
            code = match.group(3).upper()
            description = match.group(4).strip()

            # Validate part number format
            if is_valid_part_number(part_number):
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
        # Example: "5PMT1201012P TCMT INSERT" or "3PMT1201012P ..."
        # Allow apostrophes in part numbers (e.g., HAL96'14183A)
        pattern2 = r'^(\d{1,3})([A-Za-z0-9\'\s]{2,4}\d{5,}[A-Za-z0-9]*)\s+([A-Za-z0-9\-\']{3,})\s+(.+)$'
        match = re.search(pattern2, cleaned_line)

        if match:
            quantity = int(match.group(1))
            part_number = normalize_part_number(match.group(2))
            code = match.group(3).upper()
            description = match.group(4).strip()

            # Validate part number format
            if is_valid_part_number(part_number):
                items.append({
                    'quantity': quantity,
                    'part_number': part_number,
                    'code': code,
                    'description': description,
                    'price': 0.0,
                    'total_value': 0.0
                })
                continue

        # Pattern 3: QTY [SYMBOLS] PART_NUMBER DESCRIPTION (no separate code)
        # Example: "5 PMT1201012P TCMT 110204E-FM INSERT" or "2 HAL96'14183A ..."
        # Allow optional symbols between QTY and PART_NUMBER
        # Allow apostrophes and spaces in part numbers
        pattern3 = r'^(\d{1,3})\s+[^\d\s]{0,4}\s*([A-Za-z0-9\'\s]{2,4}\d{5,}[A-Za-z0-9]*)\s+(.+)$'
        match = re.search(pattern3, cleaned_line)

        if match:
            quantity = int(match.group(1))
            part_number = normalize_part_number(match.group(2))
            description = match.group(3).strip()

            # Validate part number format
            if is_valid_part_number(part_number):
                # Try to extract code from beginning of description
                code_match = re.match(r'^([A-Za-z0-9]{3,8})\s+', description)
                code = code_match.group(1).upper() if code_match else ""

                items.append({
                    'quantity': quantity,
                    'part_number': part_number,
                    'code': code,
                    'description': description,
                    'price': 0.0,
                    'total_value': 0.0
                })
                continue

    return items


if __name__ == '__main__':
    # Test with sample text
    sample = """--\- rz 12 tscl152226W wsrsz+ CNMG 120408-M3M INSERT GRADEIC6O2S
-+" 1 tsc1152169H WSFO18 CCMT O9T3O8.SM INSERT GRADE IC9O7
10 HRN1208800G wsF573 S1OO.O3OO.E2 INSERT GRADE TF45"""

    items = extract_delivery_items_improved(sample)
    print(f"Extracted {len(items)} items:")
    for item in items:
        print(f"  - QTY: {item['quantity']}, Part#: {item['part_number']}, Code: {item['code']}")
