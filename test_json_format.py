#!/usr/bin/env python3
"""
Test script for JSON-formatted invoice/delivery reconciliation
Tests the new JSON input format support
"""

# Simulate n8n items input
items = [
    {
        "json": {
            "invoice_text": """```json
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
          {
            "date": "2025-09-22",
            "del_adv_number": "0012816646",
            "description": "A12M-STFCR 11 BORING BAR",
            "part_no": "PMT1060011P",
            "qty": "1",
            "price": "103.790",
            "unit": "EA",
            "discount": "0.00",
            "total_value": "103.79"
          },
          {
            "date": "2025-09-22",
            "del_adv_number": "0012816646",
            "description": "CLEAR PROTECTIVE OVERGLASSES",
            "part_no": "SSF9601520K",
            "qty": "2",
            "price": "2.310",
            "unit": "EA",
            "discount": "0.00",
            "total_value": "4.62"
          },
          {
            "date": "2025-09-22",
            "del_adv_number": "0012816646",
            "description": "TCMT 110204E-FM INSERT GRADE",
            "part_no": "PMT1201012P",
            "qty": "4",
            "price": "5.620",
            "unit": "EA",
            "discount": "0.00",
            "total_value": "22.48"
          },
          {
            "date": "2025-09-22",
            "del_adv_number": "0012816646",
            "description": "TCMT 110204E-FM INSERT GRADE",
            "part_no": "PMT1201012P",
            "qty": "1",
            "price": "5.620",
            "unit": "EA",
            "discount": "0.00",
            "total_value": "5.62"
          },
          {
            "date": "2025-09-22",
            "del_adv_number": "0012816646",
            "description": "DNMG 110408-M3M INSERT GRADE",
            "part_no": "ISC1143463M",
            "qty": "3",
            "price": "8.420",
            "unit": "EA",
            "discount": "0.00",
            "total_value": "25.26"
          },
          {
            "date": "2025-09-22",
            "del_adv_number": "0012816646",
            "description": "E100 HAND DEBURRING BLADESTEEL/ALUMINIUM",
            "part_no": "SWT1091420C",
            "qty": "2",
            "price": "2.320",
            "unit": "EA",
            "discount": "0.00",
            "total_value": "4.64"
          },
          {
            "date": "2025-09-22",
            "del_adv_number": "0012816646",
            "description": "SOMT 120408-DT INSERT GRADE IC908",
            "part_no": "ISC1316600W",
            "qty": "4",
            "price": "10.170",
            "unit": "EA",
            "discount": "0.00",
            "total_value": "40.68"
          }
        ]
      }
    ]
  }
}
```""",
            "delivery_text": """```json
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
          "description": "TCMT 110204E-FM INSERT GRADET8430",
          "branch_bin": "AB02-10"
        },
        {
          "qty": "6",
          "code": "ISC1153821T",
          "part_no": "WSF424",
          "description": "WNMG 060408-M3M INSERT GRADEIC6025",
          "branch_bin": "AB04-1"
        },
        {
          "qty": "12",
          "code": "ISC1316880N",
          "part_no": "WSF491",
          "description": "TAG N3J INSERT GRADE IC807",
          "branch_bin": "AB06-7"
        },
        {
          "qty": "3",
          "code": "PMT1185380E",
          "part_no": "WSF232",
          "description": "SOLOPOL LIME 4LTR",
          "branch_bin": "AB10-1"
        },
        {
          "qty": "15",
          "code": "PMT1491420G",
          "part_no": "WSF080",
          "description": "E100 HAND DEBURRING BLADESTEEL/ALUMINIUM",
          "branch_bin": "AC03-5"
        },
        {
          "qty": "18",
          "code": "ISC1214520T",
          "part_no": "WSF123",
          "description": "16IR 8 UN THREADING INSERT GRADEIC908",
          "branch_bin": "AC13-2"
        },
        {
          "qty": "4",
          "code": "ISC1316000W",
          "part_no": "WSF227",
          "description": "SOMT 120408-DT INSERT GRADE IC908",
          "branch_bin": "AD01-3"
        },
        {
          "qty": "1",
          "code": "ISM1800013T",
          "part_no": "WSF566",
          "description": "A12M-STFCR 11 BORING BAR",
          "branch_bin": "AF01"
        },
        {
          "qty": "20",
          "code": "SHE0510IC20TC",
          "part_no": "WSF143",
          "description": "CLEAR PROTECTIVE OVERGLASSESEN166 1 FT",
          "branch_bin": "AS04-4"
        },
        {
          "qty": "5",
          "code": "ISC1152226Y",
          "part_no": "WSF529",
          "description": "CNMG 120408-M3M INSERT GRADEIC806",
          "branch_bin": "MEZZ-CF3"
        },
        {
          "qty": "5",
          "code": "ISC1143463M",
          "part_no": "WSF499",
          "description": "DNMG 110408-M3M INSERT GRADEIC6025",
          "branch_bin": "MEZZ-EA4"
        }
      ]
    },
    {
      "page": 2,
      "delivery_note_number": "IMS-20598436",
      "date": "24/09/2025",
      "time": "08:14",
      "line_items": [
        {
          "qty": "6",
          "code": "ISC1152169H",
          "part_no": "WSF018",
          "description": "CCMT 09T308-SM INSERT GRADE IC907",
          "branch_bin": "AA12-7"
        }
      ]
    }
  ]
}
```"""
        }
    }
]

# Read and execute the reconciliation code (excluding the return statement)
with open('n8n_ocr_reconcile.py', 'r') as f:
    code = f.read()
    # Remove the return statement at the end (last line)
    code_lines = code.split('\n')
    # Find and remove the return statement
    for i in range(len(code_lines) - 1, -1, -1):
        if code_lines[i].strip().startswith('return'):
            code_lines.pop(i)
            break
    code = '\n'.join(code_lines)
    exec(code)

# The script will create a 'results' variable
print("\n\n=== TEST RESULTS ===")
print(f"Invoice items extracted: {results['debug']['invoice_items_extracted']}")
print(f"Delivery items extracted: {results['debug']['delivery_items_extracted']}")
print(f"\nMissing items: {results['stats']['missing_count']}")
print(f"Quantity discrepancies: {results['stats']['discrepancy_count']}")
print("\n" + results['report_text'])
