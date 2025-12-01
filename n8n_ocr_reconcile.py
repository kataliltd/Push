"""
Invoice & Delivery Note Reconciliation for n8n - OCR Text Version
Copy this entire code into an n8n Python Code node

This version handles BOTH:
1. RAW OCR TEXT OUTPUT (text blobs)
2. PRE-PARSED JSON DATA (structured invoice/delivery data)

INPUT FORMAT:
Option 1 - Raw OCR text:
{
    "invoice_text": "SALES INVOICE Customer Account No: WE1573 TAXPOINT/DATE: 29/09/25...",
    "delivery_text": "DELIVERY NOTE Qty Code Part No Description..."
}

Option 2 - Pre-parsed JSON data (wrapped in markdown):
{
    "invoice_text": "```json\\n{\\n  \\"invoice\\": {...}\\n}\\n```",
    "delivery_text": "```json\\n{\\n  \\"delivery_notes\\": [...]\\n}\\n```"
}

OUTPUT FORMAT:
Returns a single item with:
{
    "missing_items": [...],
    "quantity_discrepancies": [...],
    "stats": {...},
    "report_text": "...",
    "metadata": {
        "invoice_number": "...",
        "customer_name": "...",
        ...
    }
}
"""

import re
import json
from collections import defaultdict

# ============================================================================
# OCR TEXT PARSER
# ============================================================================

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


def extract_invoice_metadata(text):
    """Extract invoice metadata from OCR text"""
    metadata = {
        'invoice_number': '',
        'customer_account': '',
        'customer_name': '',
        'invoice_date': ''
    }

    # Extract invoice number
    inv_match = re.search(r'INVOICE\s+(?:NO|NUMBER|#)[:\s]+([A-Z0-9]+)', text, re.IGNORECASE)
    if inv_match:
        metadata['invoice_number'] = inv_match.group(1)

    # Extract customer account number
    acct_match = re.search(r'(?:Customer\s+)?Account\s+(?:No|Number|#)[:\s]+([A-Z0-9]+)', text, re.IGNORECASE)
    if acct_match:
        metadata['customer_account'] = acct_match.group(1)

    # Extract invoice date
    date_match = re.search(r'(?:TAX\s*POINT/)?DATE[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})', text, re.IGNORECASE)
    if date_match:
        metadata['invoice_date'] = date_match.group(1)

    # Extract customer name
    name_patterns = [
        r'INVOICE\s+ADDRESS[:\s]+([A-Z][A-Z\s&]+(?:LIMITED|LTD|LLP|PLC))',
        r'CUSTOMER[:\s]+([A-Z][A-Z\s&]+(?:LIMITED|LTD|LLP|PLC))',
        r'BILL\s+TO[:\s]+([A-Z][A-Z\s&]+(?:LIMITED|LTD|LLP|PLC))'
    ]

    for pattern in name_patterns:
        name_match = re.search(pattern, text, re.IGNORECASE)
        if name_match:
            metadata['customer_name'] = name_match.group(1).strip()
            break

    return metadata


def extract_invoice_items(text):
    """Extract line items from invoice OCR text"""
    items = []
    text = clean_ocr_text(text)
    lines = text.split('\n')

    # Track previous lines for description lookup
    prev_lines = []

    for line in lines:
        line = line.strip()

        if not line or len(line) < 5:
            continue

        # Skip headers and common text
        skip_patterns = [
            r'^(?:CUSTOMER|INVOICE|DELIVERY|ADDRESS|ORDER|NUMBER|QTY|PRICE|DESCRIPTION|TOTAL|PAGE|DATE|TAXPOINT)',
            r'^(?:DEL|CUSTOMER)\s+(?:ADV|ORDER)',  # Skip "DEL ADV NUMBER", "CUSTOMER ORDER" etc
            r'^[-=]+$',
            r'^\d+\s+of\s+\d+',
            r'^(?:EA|PK)\s*$',
            r'^Cromwell\s+Tools',
            r'^Telephone|^Fax',
            r'^\d{4}-\d{2}-\d{2}'
        ]

        if any(re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
            continue

        # NEW PATTERN: Match quantity/price line format
        # Format: "2 103.790 EA 0.00 207.58 1" or "1 2.310 EA 0.00 4.62 1"
        # Pattern: [QTY] [PRICE with 2-3 decimals] [UNIT] [DISCOUNT] [TOTAL] [optional extra digit]
        item_pattern = r'^(\d+)\s+(\d+\.\d{2,3})\s+(EA|PK|PC|BOX|SET|EACH)\s+\d+\.\d+\s+(\d+\.\d+)'

        match = re.search(item_pattern, line, re.IGNORECASE)

        if match:
            quantity = int(match.group(1))
            price = float(match.group(2))
            unit = match.group(3).upper()
            total_value = float(match.group(4))

            # Look back 1-3 lines for description (product name)
            description = ""
            part_number = ""

            for j in range(1, min(4, len(prev_lines) + 1)):
                prev_line = prev_lines[-j] if len(prev_lines) >= j else ""

                # Look for part number pattern (e.g., "Our part no. PMT1060011P")
                if 'part no.' in prev_line.lower():
                    # Extract the part number AFTER "part no."
                    part_match = re.search(r'part\s+no[.:\s]+([A-Z0-9]{6,})', prev_line, re.IGNORECASE)
                    if part_match:
                        part_number = part_match.group(1).upper()

                # Look for description (product name line - usually has caps and dashes)
                elif re.search(r'^[A-Z0-9][A-Z0-9\s\-\/]+', prev_line) and len(prev_line) > 5:
                    # Avoid lines that are addresses or headers
                    # IMPORTANT: Also avoid lines with decimal numbers (these are quantity/price lines)
                    # Skip address components (LANE, DERBYSHIRE, postcodes, etc)
                    if not re.search(r'(ACCOUNT|LANE|DERBYSHIRE|LIMITED|VEND|UNIT\s+\d+|ROAD|STREET|AVENUE|DRIVE)', prev_line, re.IGNORECASE):
                        # Skip UK postcodes (e.g., S18 2XA, DE21 7BF)
                        if not re.match(r'^[A-Z]{1,2}\d{1,2}\s*\d[A-Z]{2}$', prev_line.strip()):
                            # Check if line contains decimal numbers (quantity/price pattern)
                            if not re.search(r'\d+\.\d+', prev_line):
                                description = prev_line.strip()
                                # Also try to extract part number from description
                                if not part_number:
                                    part_match = re.search(r'\b([A-Z]{2,}\d{3,}[A-Z0-9\-]*)\b', description)
                                    if part_match:
                                        part_number = part_match.group(1)

            if not description:
                description = f"Item (see part no. {part_number})" if part_number else "Unknown item"

            items.append({
                'description': description,
                'part_number': part_number,
                'quantity': quantity,
                'price': price,
                'unit': unit,
                'total_value': total_value
            })

        # Keep track of previous lines for description lookup
        prev_lines.append(line)
        if len(prev_lines) > 5:
            prev_lines.pop(0)

    return items


# ============================================================================
# JSON DATA PARSER (for pre-parsed structured data)
# ============================================================================

def strip_markdown_json(text):
    """Remove markdown code block wrappers from JSON strings"""
    text = str(text).strip()
    # Remove ```json and ``` wrappers
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def is_json_data(text):
    """Check if text appears to be JSON data rather than raw OCR text"""
    # Check if it's already a parsed dict/list object
    if isinstance(text, (dict, list)):
        return True
    text = str(text).strip()
    # Check for markdown JSON wrapper
    if text.startswith('```json'):
        return True
    # Check if it starts with { or [
    stripped = strip_markdown_json(text)
    return stripped.startswith('{') or stripped.startswith('[')


def parse_json_invoice_data(json_text):
    """
    Parse pre-structured JSON invoice data

    Expected format:
    {
      "invoice": {
        "invoice_number": "0012415278",
        "invoice_date": "29/09/25",
        "customer_account": "WE1573",
        "pages": [
          {
            "page": 1,
            "line_items": [
              {
                "date": "2025-09-22",
                "del_adv_number": "0012816646",
                "description": "A12M-STFCR 11 BORING BAR",
                "part_no": "PMT1060011P",
                "qty": "2",
                "price": "103.790",
                "unit": "EA",
                "discount": "0.00",
                "total_value": "207.58"
              },
              ...
            ]
          }
        ]
      }
    }
    """
    items = []
    metadata = {
        'invoice_number': '',
        'customer_account': '',
        'customer_name': '',
        'invoice_date': ''
    }

    debug_info = {}

    try:
        # Check if data is already parsed as dict/list
        if isinstance(json_text, (dict, list)):
            data = json_text
            debug_info['source'] = 'already_parsed_object'
        else:
            # Strip markdown wrapper and parse JSON
            clean_text = strip_markdown_json(json_text)
            data = json.loads(clean_text)
            debug_info['source'] = 'parsed_from_string'

        # Debug: Check what keys are in the top-level data
        debug_info['top_level_keys'] = list(data.keys()) if isinstance(data, dict) else 'not_a_dict'
        debug_info['data_type'] = type(data).__name__

        # Extract invoice data
        invoice = data.get('invoice', {})
        debug_info['invoice_found'] = bool(invoice)
        debug_info['invoice_keys'] = list(invoice.keys()) if isinstance(invoice, dict) else 'not_a_dict'

        # Extract metadata
        metadata['invoice_number'] = invoice.get('invoice_number', '')
        metadata['invoice_date'] = invoice.get('invoice_date', '')
        metadata['customer_account'] = invoice.get('customer_account', '')
        metadata['customer_name'] = invoice.get('customer_name', '')

        # Extract line items from all pages
        pages = invoice.get('pages', [])
        debug_info['pages_count'] = len(pages)

        for page_idx, page in enumerate(pages):
            line_items = page.get('line_items', [])
            debug_info[f'page_{page_idx}_items'] = len(line_items)

            for item in line_items:
                items.append({
                    'description': item.get('description', ''),
                    'part_number': item.get('part_no', ''),
                    'quantity': float(item.get('qty', 0)),
                    'price': float(item.get('price', 0)),
                    'unit': item.get('unit', 'EA'),
                    'total_value': float(item.get('total_value', 0))
                })

    except (json.JSONDecodeError, ValueError, AttributeError) as e:
        # If JSON parsing fails, return empty results
        error_msg = f"Failed to parse JSON invoice data: {e}"
        print(f"Warning: {error_msg}")
        debug_info['error'] = error_msg

    return items, metadata, debug_info


def parse_json_delivery_data(json_text):
    """
    Parse pre-structured JSON delivery data

    Expected format:
    {
      "delivery_notes": [
        {
          "page": 1,
          "delivery_note_number": "IMS-20575866",
          "date": "19/09/2025",
          "time": "08:38",
          "line_items": [
            {
              "qty": "6",
              "code": "PMT1291012F",
              "part_no": "WSF568",
              "description": "TCMT 110204E-FM INSERT GRADE T8430",
              "branch_bin": "AB02-10"
            },
            ...
          ]
        }
      ]
    }
    """
    items = []
    metadata = {
        'delivery_number': '',
        'customer_name': '',
        'delivery_date': ''
    }

    debug_info = {}

    try:
        # Check if data is already parsed as dict/list
        if isinstance(json_text, (dict, list)):
            data = json_text
            debug_info['source'] = 'already_parsed_object'
        else:
            # Strip markdown wrapper and parse JSON
            clean_text = strip_markdown_json(json_text)
            data = json.loads(clean_text)
            debug_info['source'] = 'parsed_from_string'

        # Debug: Check what keys are in the top-level data
        debug_info['top_level_keys'] = list(data.keys()) if isinstance(data, dict) else 'not_a_dict'
        debug_info['data_type'] = type(data).__name__

        # Extract delivery notes
        delivery_notes = data.get('delivery_notes', [])
        debug_info['delivery_notes_count'] = len(delivery_notes)

        if delivery_notes:
            # Use first delivery note for metadata
            first_note = delivery_notes[0]
            metadata['delivery_number'] = first_note.get('delivery_note_number', '')
            metadata['delivery_date'] = first_note.get('date', '')

        # Extract line items from all delivery notes
        for note_idx, note in enumerate(delivery_notes):
            line_items = note.get('line_items', [])
            debug_info[f'note_{note_idx}_items'] = len(line_items)

            for item in line_items:
                items.append({
                    'quantity': float(item.get('qty', 0)),
                    'part_number': item.get('code', ''),  # Note: 'code' field maps to part_number
                    'code': item.get('part_no', ''),      # Note: 'part_no' field maps to code
                    'description': item.get('description', ''),
                    'price': 0.0,  # Delivery notes don't have prices
                    'total_value': 0.0
                })

    except (json.JSONDecodeError, ValueError, AttributeError) as e:
        # If JSON parsing fails, return empty results
        error_msg = f"Failed to parse JSON delivery data: {e}"
        print(f"Warning: {error_msg}")
        debug_info['error'] = error_msg

    return items, metadata, debug_info


def extract_delivery_metadata(text):
    """Extract delivery note metadata from OCR text"""
    metadata = {
        'delivery_number': '',
        'customer_name': '',
        'delivery_date': ''
    }

    # Extract delivery note number
    del_match = re.search(r'(?:DEL(?:IVERY)?\s+(?:ADV|NOTE)|DELIVERY)\s+(?:NUMBER|NO|#)[:\s]+([A-Z0-9]+)', text, re.IGNORECASE)
    if del_match:
        metadata['delivery_number'] = del_match.group(1)

    # Extract delivery date
    date_match = re.search(r'(?:DATE|DELIVERY\s+DATE)[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})', text, re.IGNORECASE)
    if date_match:
        metadata['delivery_date'] = date_match.group(1)

    # Extract customer name
    name_patterns = [
        r'DELIVERY\s+(?:ADDRESS|TO)[:\s]+([A-Z][A-Z\s&]+(?:LIMITED|LTD|LLP|PLC))',
        r'CUSTOMER[:\s]+([A-Z][A-Z\s&]+(?:LIMITED|LTD|LLP|PLC))'
    ]

    for pattern in name_patterns:
        name_match = re.search(pattern, text, re.IGNORECASE)
        if name_match:
            metadata['customer_name'] = name_match.group(1).strip()
            break

    return metadata


def extract_delivery_items(text):
    """
    Extract line items from delivery note OCR text with strict validation

    Delivery notes typically have TWO formats:
    FORMAT 1 (all on one line): "QTY PART_NUMBER CODE DESCRIPTION"
    FORMAT 2 (multi-line - each field on separate line):
        Line 1: QTY
        Line 2: PART_NUMBER
        Line 3: CODE
        Line 4+: DESCRIPTION (spread across multiple lines)

    This parser handles BOTH formats.
    """
    items = []
    text = clean_ocr_text(text)
    lines = text.split('\n')

    # Track previous lines for multi-line items
    prev_lines = []

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
        # Allow common OCR artifacts like +, *, /, etc.
        if 3 <= len(code) <= 15:
            # Should contain some letters and/or digits
            # Allow more symbols due to OCR errors
            if re.match(r'^[A-Z0-9\-\+\*\/]+$', code):
                return True
        return False

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
                        if re.match(r'^[A-Z]{2}\d{2}-\d{1,2}$', desc_line):
                            break
                        if re.match(r'^[A-Z]{1}\d{2}-\d{1,2}$', desc_line):
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

        # FALLBACK Pattern: Line with part number but no clear quantity
        # Example: "rsc1316880N wsF491 TAG N3J INSERT" or "tscl 152226W wsrsz+ CNMG..."
        # This catches items where quantity field is completely missing/mangled
        # Pattern: [junk] PART_NUMBER [CODE] [DESCRIPTION]
        # Strip any leading junk (non-letter) first
        fallback_line = re.sub(r'^[^A-Za-z]+', '', cleaned_line)

        # Pattern: PART_NUMBER CODE DESCRIPTION (no quantity)
        # More lenient: match a token that looks like a part number (letters+digits+spaces, 9+ chars)
        # Then a code (3-15 chars), then description
        fallback_pattern = r'^([A-Za-z0-9\'\s]{9,}?)\s+([A-Za-z0-9\-\+\*\/]{3,15})\s+(.+)$'
        match = re.search(fallback_pattern, fallback_line)

        if match:
            part_number = normalize_part_number(match.group(1))
            code = match.group(2).upper()
            description = match.group(3).strip()

            # Validate part number format
            if is_valid_part_number(part_number):
                # Use quantity = 1 as default for items with missing quantity
                items.append({
                    'quantity': 1,
                    'part_number': part_number,
                    'code': code,
                    'description': description,
                    'price': 0.0,
                    'total_value': 0.0
                })
                continue

    return items


# ============================================================================
# RECONCILIATION ENGINE (same as before)
# ============================================================================

def normalize_text(text):
    """Normalize text for comparison"""
    text = str(text).upper().strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s*[A-Z]{2}\d+[A-Z]*\s*$', '', text)
    text = re.sub(r'^[^A-Z0-9]+', '', text)
    text = re.sub(r'[^A-Z0-9]+$', '', text)
    return text


def calculate_similarity(text1, text2):
    """Calculate similarity ratio"""
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)

    if norm1 == norm2:
        return 1.0

    if norm1 in norm2 or norm2 in norm1:
        shorter = min(len(norm1), len(norm2))
        longer = max(len(norm1), len(norm2))
        return shorter / longer

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

# Initialize error tracking and debug info
parsing_errors = []
debug_info = {
    'invoice_items_extracted': 0,
    'delivery_items_extracted': 0,
    'invoice_text_length': 0,
    'delivery_text_length': 0,
    'invoice_text_type': '',
    'delivery_text_type': '',
    'invoice_is_json': False,
    'delivery_is_json': False,
    'parsing_errors': []
}

try:
    # Get input data from n8n
    input_data = items[0]['json']

    # Extract invoice and delivery text from input
    invoice_text = input_data.get('invoice_text', input_data.get('text', ''))
    delivery_text = input_data.get('delivery_text', '')

    # If you're using separate OCR nodes for invoice and delivery,
    # they might come from different items:
    # invoice_text = items[0]['json'].get('text', '')
    # delivery_text = items[1]['json'].get('text', '') if len(items) > 1 else ''

    # Record debug info about input data
    debug_info['invoice_text_type'] = type(invoice_text).__name__
    debug_info['delivery_text_type'] = type(delivery_text).__name__
    debug_info['invoice_text_length'] = len(str(invoice_text)) if invoice_text else 0
    debug_info['delivery_text_length'] = len(str(delivery_text)) if delivery_text else 0

    # Detect data format and parse accordingly
    invoice_items = []
    invoice_metadata = {
        'invoice_number': '',
        'customer_account': '',
        'customer_name': '',
        'invoice_date': ''
    }

    if invoice_text:
        try:
            debug_info['invoice_is_json'] = is_json_data(invoice_text)

            if debug_info['invoice_is_json']:
                # NEW FORMAT: Pre-parsed JSON data
                invoice_items, invoice_metadata, invoice_parse_debug = parse_json_invoice_data(invoice_text)
                debug_info['invoice_parse_debug'] = invoice_parse_debug
            else:
                # OLD FORMAT: Raw OCR text
                invoice_metadata = extract_invoice_metadata(invoice_text)
                invoice_items = extract_invoice_items(invoice_text)
        except Exception as e:
            error_msg = f"Invoice parsing error: {type(e).__name__}: {str(e)}"
            parsing_errors.append(error_msg)
            debug_info['parsing_errors'].append(error_msg)

    debug_info['invoice_items_extracted'] = len(invoice_items)

    # Parse delivery data
    delivery_items = []
    delivery_metadata = {
        'delivery_number': '',
        'customer_name': '',
        'delivery_date': ''
    }

    if delivery_text:
        try:
            debug_info['delivery_is_json'] = is_json_data(delivery_text)

            if debug_info['delivery_is_json']:
                # NEW FORMAT: Pre-parsed JSON data
                delivery_items, delivery_metadata, delivery_parse_debug = parse_json_delivery_data(delivery_text)
                debug_info['delivery_parse_debug'] = delivery_parse_debug
            else:
                # OLD FORMAT: Raw OCR text
                delivery_metadata = extract_delivery_metadata(delivery_text)
                delivery_items = extract_delivery_items(delivery_text)
        except Exception as e:
            error_msg = f"Delivery parsing error: {type(e).__name__}: {str(e)}"
            parsing_errors.append(error_msg)
            debug_info['parsing_errors'].append(error_msg)

    debug_info['delivery_items_extracted'] = len(delivery_items)

    # Add sample items to debug output
    if invoice_items:
        debug_info['invoice_sample'] = invoice_items[0]
    if delivery_items:
        debug_info['delivery_sample'] = delivery_items[0]

    # Run reconciliation
    results = reconcile(invoice_items, delivery_items)

    # Add formatted report text
    results['report_text'] = format_report(results)

    # Add metadata
    results['metadata'] = {
        'invoice_number': invoice_metadata['invoice_number'],
        'invoice_date': invoice_metadata['invoice_date'],
        'customer_account': invoice_metadata['customer_account'],
        'customer_name': invoice_metadata['customer_name'],
        'delivery_number': delivery_metadata['delivery_number'],
        'delivery_date': delivery_metadata['delivery_date']
    }

    # Add debug info
    results['debug'] = debug_info

    # Add parsing errors if any
    if parsing_errors:
        results['errors'] = parsing_errors

    # Return results to n8n
    return [{'json': results}]

except Exception as e:
    # Catch-all error handler
    error_msg = f"Fatal error: {type(e).__name__}: {str(e)}"
    return [{
        'json': {
            'error': error_msg,
            'debug': debug_info,
            'missing_items': [],
            'quantity_discrepancies': [],
            'stats': {
                'invoice_items': 0,
                'delivery_items': 0,
                'missing_count': 0,
                'discrepancy_count': 0,
                'missing_value': 0,
                'discrepancy_value': 0,
                'total_value': 0
            }
        }
    }]
