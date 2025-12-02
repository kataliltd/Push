# Invoice JSON Parser

Python scripts to parse and clean invoice JSON data from nested structures with markdown formatting.

## Files

- **parse_invoice_json.py** - Standalone Python script with testing capability
- **n8n_invoice_parser.py** - Ready-to-use code for n8n Code Module

## Problem Solved

Converts nested JSON structures containing markdown-formatted invoice data into clean JSON:

**Input Format:**
```json
[
  {
    "content": [
      {
        "type": "text",
        "text": "```json\n<invoice_data>\n{...}\n</invoice_data>\n```"
      }
    ]
  }
]
```

**Output Format:**
```json
{
  "invoice": {
    "invoice_number": "0012415278",
    "invoice_date": "29/09/25",
    ...
  }
}
```

## Usage

### For n8n Code Module

1. In your n8n workflow, add a **Code** node (Python)
2. Copy the entire contents of `n8n_invoice_parser.py`
3. Paste into the code editor
4. The script will automatically process all items in your workflow

### Standalone Testing

Run the standalone script to test with your data:

```bash
python3 parse_invoice_json.py
```

## What It Does

1. Extracts text content from nested JSON structure
2. Removes markdown code block markers (` ```json ` and ` ``` `)
3. Removes XML-like tags (`<invoice_data>` and `</invoice_data>`)
4. Cleans escape characters (like `\"` → `"`)
5. Returns clean, properly formatted JSON

## Example

The script successfully parses invoice data including:
- Invoice numbers and dates
- Customer accounts
- Line items with descriptions, quantities, prices
- Multiple pages of invoice data
