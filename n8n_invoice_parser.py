"""
n8n Code Module - Invoice JSON Parser

Copy this entire code into your n8n Code Module (Python).
This will clean invoice data from nested JSON structures with markdown formatting.
"""

import json
import re


def parse_invoice_json(input_data):
    """Parse and clean invoice JSON data."""
    # If input is a string, parse it first
    if isinstance(input_data, str):
        data = json.loads(input_data)
    else:
        data = input_data

    # Extract the text content from the nested structure
    if isinstance(data, list) and len(data) > 0:
        if "content" in data[0]:
            content_list = data[0]["content"]
            if len(content_list) > 0 and "text" in content_list[0]:
                text_content = content_list[0]["text"]
            else:
                raise ValueError("Expected 'text' field in content array")
        else:
            raise ValueError("Expected 'content' field in input data")
    else:
        raise ValueError("Expected input to be a non-empty list")

    # Remove markdown code block markers
    text_content = re.sub(r'^```json\s*', '', text_content)
    text_content = re.sub(r'```\s*$', '', text_content)

    # Remove XML-like tags
    text_content = re.sub(r'</?invoice_data>\s*', '', text_content)

    # Clean up whitespace
    text_content = text_content.strip()

    # Parse the cleaned JSON
    invoice_data = json.loads(text_content)

    return invoice_data


# Process each item in the n8n workflow
for item in items:
    # Get the input data from the item
    input_data = item.json

    # Parse and clean the invoice data
    cleaned_data = parse_invoice_json(input_data)

    # Update the item with cleaned data
    item.json = cleaned_data

return items
