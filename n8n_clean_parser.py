import re
import json

# Parse invoice text into structured JSON
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

# Process n8n items
for item in items:
    input_data = item.json

    # Convert JsProxy
    if hasattr(input_data, 'to_py'):
        input_data = input_data.to_py()

    # Handle array
    if isinstance(input_data, list):
        input_data = input_data[0]

    # Get text
    text = input_data.get("text", "")

    # Parse and return
    item.json = parse_invoice(text)

return items
