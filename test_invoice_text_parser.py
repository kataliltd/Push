"""
Test the invoice text parser with actual data
"""

import re
import json

# Your actual invoice text (truncated for testing)
test_text = """SALES INVOICE
Customer Account No: WE1573
TAXPOINT/DATE: 29/09/25 Doc. Count: 1 of 4
INVOICE ADDRESS
WEST SPECIAL FASTENERS LIMITED
**VENDA 365 ACCOUNT**
UNIT 3B, CALLYWHITE LANE
DRONFIELD
DERBYSHIRE
S18 2XR
INVOICE NO: 0012415278
2025-09-22 IMS-ISSUES 0012816646
Pg . 001
A12M-STFCR 11 BORING BAR
Our part no. PMT1060011P
2 103.790 EA 0.00 207.58 1
A12M-STFCR 11 BORING BAR
Our part no. PMT1060011P
1 103.790 EA 0.00 103.79 1
SUBTOTAL 1,633.87
TOTAL TAX: 4,746.06 949.21 5,695.27 GBP"""

def parse_invoice_text(text):
    """Parse invoice text into structured JSON."""

    invoice_data = {
        "invoice_number": None,
        "invoice_date": None,
        "customer_account": None,
        "customer_name": None,
        "invoice_address": {},
        "line_items": [],
        "subtotals": [],
        "total": None,
        "total_tax": None,
        "grand_total": None,
        "currency": None
    }

    # Extract invoice number
    inv_match = re.search(r'INVOICE NO:\s*(\d+)', text)
    if inv_match:
        invoice_data["invoice_number"] = inv_match.group(1)

    # Extract customer account
    acc_match = re.search(r'Customer Account No:\s*(\w+)', text)
    if acc_match:
        invoice_data["customer_account"] = acc_match.group(1)

    # Extract date
    date_match = re.search(r'TAXPOINT/DATE:\s*(\d{2}/\d{2}/\d{2})', text)
    if date_match:
        invoice_data["invoice_date"] = date_match.group(1)

    # Extract customer name
    name_match = re.search(r'INVOICE ADDRESS\n(.*?)\n', text)
    if name_match:
        invoice_data["customer_name"] = name_match.group(1).strip()

    # Extract subtotals
    subtotals = re.findall(r'SUBTOTAL\s+([\d,]+\.?\d*)', text)
    invoice_data["subtotals"] = [float(s.replace(',', '')) for s in subtotals]

    # Extract final totals
    total_match = re.search(r'TOTAL TAX:\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+(\w+)', text)
    if total_match:
        invoice_data["total"] = float(total_match.group(1).replace(',', ''))
        invoice_data["total_tax"] = float(total_match.group(2).replace(',', ''))
        invoice_data["grand_total"] = float(total_match.group(3).replace(',', ''))
        invoice_data["currency"] = total_match.group(4)

    return invoice_data

# Test the parser
result = parse_invoice_text(test_text)
print("Parsed Invoice Data:")
print(json.dumps(result, indent=2))
