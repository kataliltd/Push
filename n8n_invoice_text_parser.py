"""
n8n Code Module - Invoice Text Parser

Parses raw invoice text from PDF into structured JSON.
Copy this entire code into your n8n Code Module (Python).
"""

import re
import json

def parse_invoice_text(text):
    """Parse invoice text into structured JSON."""

    invoice_data = {
        "invoice_number": None,
        "invoice_date": None,
        "customer_account": None,
        "customer_name": None,
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

    # Parse line items - look for "Our part no." pattern
    line_items = []
    part_no_pattern = r'Our part no\.\s+(\w+)\s+(\d+)\s+([\d.]+)\s+(\w+)\s+([\d.]+)\s+([\d.]+)\s+(\d)'

    for match in re.finditer(part_no_pattern, text):
        # Get the description (text before "Our part no.")
        start_pos = max(0, match.start() - 200)
        context = text[start_pos:match.start()]

        # Find the last newline before "Our part no." to get description
        desc_lines = context.split('\n')
        description = desc_lines[-1].strip() if desc_lines else ""

        # Try to find date and del adv number in nearby text
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', text[max(0, match.start()-100):match.start()])
        del_adv_match = re.search(r'(\d{10})', text[max(0, match.start()-100):match.start()])

        item = {
            "date": date_match.group(1) if date_match else None,
            "del_adv_number": del_adv_match.group(1) if del_adv_match else None,
            "description": description,
            "part_no": match.group(1),
            "qty": int(match.group(2)),
            "price": float(match.group(3)),
            "unit": match.group(4),
            "discount": float(match.group(5)),
            "total_value": float(match.group(6)),
            "vat_code": int(match.group(7))
        }
        line_items.append(item)

    invoice_data["line_items"] = line_items

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


# Process each item in the n8n workflow
for item in items:
    # Get the input data from the item
    input_data = item.json

    # Convert JsProxy to Python object if needed
    if hasattr(input_data, 'to_py'):
        input_data = input_data.to_py()

    # Handle array input
    if isinstance(input_data, list) and len(input_data) > 0:
        input_data = input_data[0]

    # Extract the text field
    if isinstance(input_data, dict) and "text" in input_data:
        invoice_text = input_data["text"]
    else:
        raise ValueError(f"Expected 'text' field in input. Got: {type(input_data).__name__}")

    # Parse the invoice text
    parsed_invoice = parse_invoice_text(invoice_text)

    # Update the item with parsed data
    item.json = parsed_invoice

return items
