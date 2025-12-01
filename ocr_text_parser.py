"""
OCR Text Blob Parser
Parses raw OCR text output from invoices and delivery notes
Handles unstructured text blobs and extracts structured data
"""

import re
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ParsedInvoice:
    """Structured invoice data extracted from OCR text"""
    invoice_number: str
    customer_account: str
    customer_name: str
    invoice_date: str
    items: List[Dict]
    raw_text: str


@dataclass
class ParsedDeliveryNote:
    """Structured delivery note data extracted from OCR text"""
    delivery_number: str
    customer_name: str
    delivery_date: str
    items: List[Dict]
    raw_text: str


class OCRTextParser:
    """Parse raw OCR text blobs into structured data"""

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean OCR text by normalizing whitespace and escape characters"""
        # Replace common OCR escape characters
        text = text.replace('\\n', '\n')
        text = text.replace('\\t', '\t')
        text = text.replace('\\\\', ' ')

        # Normalize whitespace
        text = re.sub(r'[ \t]+', ' ', text)

        return text.strip()

    @staticmethod
    def extract_invoice_metadata(text: str) -> Dict[str, str]:
        """Extract invoice metadata from OCR text"""
        metadata = {
            'invoice_number': '',
            'customer_account': '',
            'customer_name': '',
            'invoice_date': ''
        }

        # Extract invoice number
        # Patterns: "INVOICE NO: 0012451278", "Invoice Number: 123456"
        inv_match = re.search(r'INVOICE\s+(?:NO|NUMBER|#)[:\s]+([A-Z0-9]+)', text, re.IGNORECASE)
        if inv_match:
            metadata['invoice_number'] = inv_match.group(1)

        # Extract customer account number
        # Patterns: "Customer Account No: WE1573", "Account: 12345"
        acct_match = re.search(r'(?:Customer\s+)?Account\s+(?:No|Number|#)[:\s]+([A-Z0-9]+)', text, re.IGNORECASE)
        if acct_match:
            metadata['customer_account'] = acct_match.group(1)

        # Extract invoice date
        # Patterns: "DATE: 29/09/25", "TAXPOINT/DATE: 29/09/25"
        date_match = re.search(r'(?:TAX\s*POINT/)?DATE[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})', text, re.IGNORECASE)
        if date_match:
            metadata['invoice_date'] = date_match.group(1)

        # Extract customer name
        # Look for patterns after "INVOICE ADDRESS" or similar headers
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

    @staticmethod
    def extract_invoice_line_items(text: str) -> List[Dict]:
        """
        Extract line items from invoice OCR text

        Looks for patterns that indicate line items with:
        - Description (product name)
        - Quantity
        - Unit (EA, PK, etc.)
        - Price
        - Total value
        """
        items = []

        # Clean the text first
        text = OCRTextParser.clean_text(text)

        # Split into lines for processing
        lines = text.split('\n')

        # Track previous lines for description lookup
        prev_lines = []

        # Pattern for line items - flexible to handle various OCR outputs
        # New approach: descriptions and quantities are often on separate lines
        # Example:
        # "A12M-STFCR 11 BORING BAR"
        # "Our part no. PMT1060011P"
        # "2 103.790 EA 0.00 207.58 1"

        for line in lines:
            line = line.strip()

            # Skip empty lines and headers
            if not line or len(line) < 5:
                continue

            # Skip common header/footer lines
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
                    'total_value': total_value,
                    'source_line': line
                })

            # Keep track of previous lines for description lookup
            prev_lines.append(line)
            if len(prev_lines) > 5:
                prev_lines.pop(0)

        return items

    @staticmethod
    def extract_delivery_metadata(text: str) -> Dict[str, str]:
        """Extract delivery note metadata from OCR text"""
        metadata = {
            'delivery_number': '',
            'customer_name': '',
            'delivery_date': ''
        }

        # Extract delivery note number
        # Patterns: "DEL ADV NUMBER", "Delivery Note: 123456"
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

    @staticmethod
    def extract_delivery_line_items(text: str) -> List[Dict]:
        """
        Extract line items from delivery note OCR text

        Delivery notes typically have:
        - Quantity
        - Code
        - Part number
        - Description
        - Branch/location
        """
        items = []

        # Clean the text first
        text = OCRTextParser.clean_text(text)

        # Split into lines
        lines = text.split('\n')

        # Pattern for delivery note line items
        # Due to OCR quality issues, we need multiple fallback patterns
        # Examples from actual OCR:
        # "1 tsc1152169H WSFO18 CCMT"
        # "1sc1152969P WSF149 SNMG 120412.M3M"

        for line in lines:
            line = line.strip()

            if not line or len(line) < 10:
                continue

            # Skip headers and garbled lines
            skip_patterns = [
                r'^(?:QTY|QUANTITY|CODE|PART|DESCRIPTION|BRANCH|LINE|DELIVERY|ADVICE|NOTE)',
                r'^[-=]+$',
                r'^R\.gLte',  # Garbled OCR header
                r'^VAI\s+Reg',
                r'^\d+\s+Cho',  # Garbled address
                r'^United\s+',
                r'^VENDA\s+365',
                r'lso\s*\d+',  # Garbled ISO numbers
                r'^Registered\s+in'
            ]

            if any(re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
                continue

            # Try multiple patterns to handle OCR variations

            # Pattern 1: QTY PART_NUMBER CODE DESCRIPTION
            # Example: "1 tsc1152169H WSFO18 CCMT"
            pattern1 = r'^(\d+)\s+([a-z0-9]{8,})\s+([A-Z0-9]{3,})\s+(.+?)$'
            match = re.search(pattern1, line, re.IGNORECASE)

            if match:
                quantity = int(match.group(1))
                part_number = match.group(2).upper()
                code = match.group(3).upper()
                description = match.group(4).strip()

                items.append({
                    'quantity': quantity,
                    'part_number': part_number,
                    'code': code,
                    'description': description,
                    'branch': '',
                    'price': 0.0,
                    'total_value': 0.0,
                    'source_line': line
                })
                continue

            # Pattern 2: QTY+PART_NUMBER CODE DESCRIPTION (no space after qty)
            # Example: "1sc1152969P WSF149 SNMG 120412.M3M"
            pattern2 = r'^(\d+)([a-z]{2}[0-9]{7}[A-Z])\s+([A-Z0-9]{3,})\s+(.+?)$'
            match = re.search(pattern2, line, re.IGNORECASE)

            if match:
                quantity = int(match.group(1))
                part_number = match.group(2).upper()
                code = match.group(3).upper()
                description = match.group(4).strip()

                items.append({
                    'quantity': quantity,
                    'part_number': part_number,
                    'code': code,
                    'description': description,
                    'branch': '',
                    'price': 0.0,
                    'total_value': 0.0,
                    'source_line': line
                })
                continue

            # Pattern 3: Generic part number pattern (fallback)
            # Just look for qty + part number with alphanumeric code
            pattern3 = r'^(\d+)\s*([A-Z0-9\-]{6,})\s+(.+)$'
            match = re.search(pattern3, line, re.IGNORECASE)

            if match and len(line) > 15:
                quantity = int(match.group(1))
                part_number = match.group(2).upper()
                description = match.group(3).strip()

                # Extract code from description if possible
                code_match = re.match(r'^([A-Z0-9]{3,})', description)
                code = code_match.group(1) if code_match else ""

                items.append({
                    'quantity': quantity,
                    'part_number': part_number,
                    'code': code,
                    'description': description,
                    'branch': '',
                    'price': 0.0,
                    'total_value': 0.0,
                    'source_line': line
                })

        return items

    @staticmethod
    def parse_invoice_text(text: str) -> ParsedInvoice:
        """
        Parse raw invoice OCR text into structured data

        Args:
            text: Raw OCR text from invoice (can be a single blob or multi-line)

        Returns:
            ParsedInvoice object with structured data
        """
        metadata = OCRTextParser.extract_invoice_metadata(text)
        items = OCRTextParser.extract_invoice_line_items(text)

        return ParsedInvoice(
            invoice_number=metadata['invoice_number'],
            customer_account=metadata['customer_account'],
            customer_name=metadata['customer_name'],
            invoice_date=metadata['invoice_date'],
            items=items,
            raw_text=text
        )

    @staticmethod
    def parse_delivery_text(text: str) -> ParsedDeliveryNote:
        """
        Parse raw delivery note OCR text into structured data

        Args:
            text: Raw OCR text from delivery note

        Returns:
            ParsedDeliveryNote object with structured data
        """
        metadata = OCRTextParser.extract_delivery_metadata(text)
        items = OCRTextParser.extract_delivery_line_items(text)

        return ParsedDeliveryNote(
            delivery_number=metadata['delivery_number'],
            customer_name=metadata['customer_name'],
            delivery_date=metadata['delivery_date'],
            items=items,
            raw_text=text
        )


# Helper function for n8n integration
def parse_ocr_for_n8n(invoice_text: str, delivery_text: str) -> Dict:
    """
    Parse OCR text for both invoice and delivery note
    Returns data in n8n-compatible format

    Args:
        invoice_text: Raw OCR text from invoice
        delivery_text: Raw OCR text from delivery note

    Returns:
        Dict with 'invoice' and 'delivery' arrays ready for reconciliation
    """
    parser = OCRTextParser()

    # Parse invoice
    invoice_data = parser.parse_invoice_text(invoice_text)

    # Parse delivery note
    delivery_data = parser.parse_delivery_text(delivery_text)

    return {
        'invoice': invoice_data.items,
        'delivery': delivery_data.items,
        'metadata': {
            'invoice_number': invoice_data.invoice_number,
            'invoice_date': invoice_data.invoice_date,
            'customer_account': invoice_data.customer_account,
            'customer_name': invoice_data.customer_name,
            'delivery_number': delivery_data.delivery_number,
            'delivery_date': delivery_data.delivery_date
        }
    }


if __name__ == '__main__':
    # Example usage
    sample_invoice_text = """
    SALES INVOICE \\ Customer Account No: WE1573\\ TAXPOINT/DATE: 29/09/25 Doc. Count: 1 of 4 \\ INVOICE
    ADDRESS \\ WEST SPECIAL FASTENERS LIMITED \\ ***VENDA 365 ACCOUNT*** \\ UNIT 3B, CALLYWHITE
    LANE \\ DRONFIELD, DERBYSHIRE \\ S18 2XA \\ INVOICE NO: 0012451278 \\ CUSTOMER ORDER \\ NUMBER \\
    DEL ADV \\ NUMBER \\ DESCRIPTION QTY \\ DEL \\ PRICE UNIT DISCOUNT TOTAL VALUE V \\ C \\ 2025-09-22 MS-ISSUES 001281
    A12M-STFCR 11 BORING BAR INSERT 2 103.79 EA 0 207.58 0
    """

    parser = OCRTextParser()
    invoice = parser.parse_invoice_text(sample_invoice_text)

    print(f"Invoice Number: {invoice.invoice_number}")
    print(f"Customer: {invoice.customer_name}")
    print(f"Date: {invoice.invoice_date}")
    print(f"\nItems found: {len(invoice.items)}")
    for item in invoice.items:
        print(f"  - {item['description']}: {item['quantity']} @ £{item['price']}")
