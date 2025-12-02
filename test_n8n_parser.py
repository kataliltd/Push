"""
Test script for n8n invoice parser with actual data structure
"""

import json
import re

# Simulate the actual input structure from your n8n workflow
test_input = {
    "content": [
        {
            "type": "text",
            "text": '```json\n<invoice_data>\n{\n  "invoice": {\n    "invoice_number": "0012415278",\n    "invoice_date": "29/09/25",\n    "customer_account": "WE1573",\n    "pages": [\n      {\n        "page": "1 of 4",\n        "line_items": [\n          {\n            "date": "2025-09-22",\n            "del_adv_number": "0012816646",\n            "description": "A12M-STFCR 11 BORING BAR",\n            "part_no": "PMT1060011P",\n            "qty": "2",\n            "price": "103.790",\n            "unit": "EA",\n            "discount": "0.00",\n            "total_value": "207.58"\n          }\n        ]\n      }\n    ]\n  }\n}\n</invoice_data>\n```'
        }
    ]
}

# Mock the n8n items structure
class Item:
    def __init__(self, data):
        self.json = data

items = [Item(test_input)]

# Execute the n8n code
for item in items:
    # Get the input data from the item
    input_data = item.json

    # Extract the text content from the nested structure
    # Handle both: object with "content" field OR array with objects
    text_content = None

    if isinstance(input_data, dict) and "content" in input_data:
        # Direct object with content field: {"content": [{"text": "..."}]}
        content_list = input_data["content"]
        if len(content_list) > 0 and "text" in content_list[0]:
            text_content = content_list[0]["text"]
    elif isinstance(input_data, list) and len(input_data) > 0:
        # Array of objects: [{"content": [{"text": "..."}]}]
        if "content" in input_data[0]:
            content_list = input_data[0]["content"]
            if len(content_list) > 0 and "text" in content_list[0]:
                text_content = content_list[0]["text"]

    if text_content is None:
        raise ValueError("Could not find text content in expected structure")

    # Remove markdown code block markers (```json and ```)
    text_content = re.sub(r'^```json\s*', '', text_content)
    text_content = re.sub(r'```\s*$', '', text_content)

    # Remove XML-like tags (<invoice_data> and </invoice_data>)
    text_content = re.sub(r'</?invoice_data>\s*', '', text_content)

    # Clean up whitespace
    text_content = text_content.strip()

    # Parse the cleaned JSON string into a Python object
    cleaned_data = json.loads(text_content)

    # Update the item with cleaned data
    item.json = cleaned_data

# Print the result
print("SUCCESS! Cleaned Invoice Data:")
print(json.dumps(items[0].json, indent=2))
