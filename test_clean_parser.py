import re
import json

def parse_invoice(text):
    data = {
        "invoice_number": None,
        "invoice_date": None,
        "customer_account": None,
        "customer_name": None,
        "line_items": [],
        "total": None,
        "total_tax": None,
        "grand_total": None,
        "currency": None
    }

    # Extract basic info
    inv = re.search(r'INVOICE NO:\s*(\d+)', text)
    if inv:
        data["invoice_number"] = inv.group(1)

    acc = re.search(r'Customer Account No:\s*(\w+)', text)
    if acc:
        data["customer_account"] = acc.group(1)

    date = re.search(r'TAXPOINT/DATE:\s*(\d{2}/\d{2}/\d{2})', text)
    if date:
        data["invoice_date"] = date.group(1)

    name = re.search(r'INVOICE ADDRESS\n(.*?)\n', text)
    if name:
        data["customer_name"] = name.group(1).strip()

    # Parse line items
    items = []
    pattern = r'Our part no\.\s+(\w+)\s+(\d+)\s+([\d.]+)\s+(\w+)\s+([\d.]+)\s+([\d.]+)\s+(\d)'

    for m in re.finditer(pattern, text):
        items.append({
            "part_no": m.group(1),
            "qty": int(m.group(2)),
            "price": float(m.group(3)),
            "unit": m.group(4),
            "discount": float(m.group(5)),
            "total_value": float(m.group(6)),
            "vat_code": int(m.group(7))
        })

    data["line_items"] = items

    # Extract totals
    total = re.search(r'TOTAL TAX:\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+(\w+)', text)
    if total:
        data["total"] = float(total.group(1).replace(',', ''))
        data["total_tax"] = float(total.group(2).replace(',', ''))
        data["grand_total"] = float(total.group(3).replace(',', ''))
        data["currency"] = total.group(4)

    return data

# Test with actual input
test_text = "SALES INVOICE\nCustomer Account No: WE1573\nTAXPOINT/DATE: 29/09/25 Doc. Count: 1 of 4\nINVOICE ADDRESS\nWEST SPECIAL FASTENERS LIMITED\n**VENDA 365 ACCOUNT**\nUNIT 3B, CALLYWHITE LANE\nDRONFIELD\nDERBYSHIRE\nS18 2XR\nINVOICE NO: 0012415278\nA12M-STFCR 11 BORING BAR\nOur part no. PMT1060011P\n2 103.790 EA 0.00 207.58 1\nTOTAL TAX: 4,746.06 949.21 5,695.27 GBP"

result = parse_invoice(test_text)
print(json.dumps(result, indent=2))
print("\nJSON is valid!")
