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

        # Pattern for line items - flexible to handle various OCR outputs
        # Typically: [description] [quantity] [price] [unit] [discount] [total]
        # Example: "M12 PROTECTIVE CAPS 100 0.15 EA 0 15.00"

        for line in lines:
            line = line.strip()

            # Skip empty lines and headers
            if not line or len(line) < 10:
                continue

            # Skip common header/footer lines
            skip_patterns = [
                r'^(?:CUSTOMER|INVOICE|DELIVERY|ADDRESS|ORDER|NUMBER|QTY|PRICE|DESCRIPTION|TOTAL|PAGE|DATE)',
                r'^[-=]+$',
                r'^\d+\s+of\s+\d+',
                r'^(?:EA|PK)\s*$'
            ]

            if any(re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
                continue

            # Try to extract structured line item data
            # Pattern: Look for quantity + price + unit pattern
            # This is a more flexible regex that can handle various formats

            # Match patterns like: "DESCRIPTION 10 5.50 EA 0 55.00"
            # or: "BORING BAR INSERT 2 103.79 EA 0 207.58"
            item_pattern = r'([A-Z][A-Z0-9\s\-\+\/]+?)\s+(\d+)\s+(\d+\.\d{2})\s+(EA|PK|PC|BOX|SET)\s+(?:\d+\s+)?(\d+\.\d{2})'

            match = re.search(item_pattern, line, re.IGNORECASE)

            if match:
                description = match.group(1).strip()
                quantity = int(match.group(2))
                price = float(match.group(3))
                unit = match.group(4).upper()
                total_value = float(match.group(5))

                # Extract part number if present (usually alphanumeric codes)
                part_match = re.search(r'\b([A-Z]{2,}\d{3,}[A-Z0-9]*)\b', description)
                part_number = part_match.group(1) if part_match else ""

                items.append({
                    'description': description,
                    'part_number': part_number,
                    'quantity': quantity,
                    'price': price,
                    'unit': unit,
                    'total_value': total_value,
                    'source_line': line
                })

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
        # Typically: [qty] [code] [part_no] [description] [branch]
        # Example: "2 EA PMT1060011P A12M-STFCR 11 BORING BAR SHEFF-01"

        for line in lines:
            line = line.strip()

            if not line or len(line) < 10:
                continue

            # Skip headers
            skip_patterns = [
                r'^(?:QTY|QUANTITY|CODE|PART|DESCRIPTION|BRANCH|LINE)',
                r'^[-=]+$'
            ]

            if any(re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
                continue

            # Try to extract delivery line item
            # Pattern: [quantity] [code] [part_number] [description] [optional branch]
            item_pattern = r'^(\d+)\s+([A-Z]{2,3})\s+([A-Z0-9\-]+)\s+(.+?)(?:\s+([A-Z]{2,}-\d{2}))?$'

            match = re.search(item_pattern, line, re.IGNORECASE)

            if match:
                quantity = int(match.group(1))
                code = match.group(2).upper()
                part_number = match.group(3)
                description = match.group(4).strip()
                branch = match.group(5) if match.group(5) else ""

                items.append({
                    'quantity': quantity,
                    'code': code,
                    'part_number': part_number,
                    'description': description,
                    'branch': branch,
                    'price': 0.0,  # Delivery notes typically don't have prices
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
