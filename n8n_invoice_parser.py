"""
n8n Code Module - Invoice JSON Parser

Copy this entire code into your n8n Code Module (Python).
This will clean invoice data from nested JSON structures with markdown formatting.
"""

import json
import re

# Process each item in the n8n workflow
for item in items:
    # Get the input data from the item
    # n8n passes data as JsProxy objects, convert to Python first
    input_data = item.json

    # Convert JsProxy to Python object if needed
    if hasattr(input_data, 'to_py'):
        input_data = input_data.to_py()

    # Try to find the text content in various possible structures
    text_content = None

    # Try 1: Direct string (if the input is already just the text)
    if isinstance(input_data, str):
        text_content = input_data

    # Try 2: Object with "content" field: {"content": [{"text": "..."}]}
    elif isinstance(input_data, dict):
        if "content" in input_data:
            content_list = input_data["content"]
            if isinstance(content_list, list) and len(content_list) > 0:
                if isinstance(content_list[0], dict) and "text" in content_list[0]:
                    text_content = content_list[0]["text"]
        # Try 3: Direct "text" field: {"text": "..."}
        elif "text" in input_data:
            text_content = input_data["text"]

    # Try 4: Array of objects: [{"content": [{"text": "..."}]}]
    elif isinstance(input_data, list) and len(input_data) > 0:
        first_item = input_data[0]
        if isinstance(first_item, dict):
            if "content" in first_item:
                content_list = first_item["content"]
                if isinstance(content_list, list) and len(content_list) > 0:
                    if isinstance(content_list[0], dict) and "text" in content_list[0]:
                        text_content = content_list[0]["text"]
            elif "text" in first_item:
                text_content = first_item["text"]

    # If we still don't have text, provide helpful error message
    if text_content is None:
        error_msg = f"Could not find text content. Input type: {type(input_data).__name__}"
        if isinstance(input_data, dict):
            error_msg += f", Keys: {list(input_data.keys())}"
        raise ValueError(error_msg)

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

return items
