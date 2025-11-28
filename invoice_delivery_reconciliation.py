#!/usr/bin/env python3
"""
Invoice and Delivery Note Reconciliation Tool

This script compares items between an invoice and a delivery note,
identifying discrepancies in quantities and missing items.
Handles OCR errors through fuzzy matching.
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from difflib import SequenceMatcher
from collections import defaultdict


@dataclass
class LineItem:
    """Represents a line item from invoice or delivery note"""
    part_number: str
    description: str
    quantity: float
    price: float
    total_value: float
    unit: str
    source_line: str  # Original line for reference


class DocumentParser:
    """Parses OCR text from invoice and delivery note"""

    @staticmethod
    def normalize_description(description: str) -> str:
        """
        Normalize description for matching by:
        - Converting to uppercase
        - Removing extra whitespace
        - Removing special characters at boundaries
        - Keeping core alphanumeric content
        """
        # Convert to uppercase
        desc = description.upper().strip()

        # Remove multiple spaces
        desc = re.sub(r'\s+', ' ', desc)

        # Remove trailing codes that look like IC\d+ or similar patterns
        # These are often appended by OCR
        desc = re.sub(r'\s*[A-Z]{2}\d+[A-Z]*\s*$', '', desc)

        return desc

    @staticmethod
    def extract_core_description(description: str) -> str:
        """
        Extract core product description, removing potential OCR artifacts
        at the beginning or end
        """
        desc = DocumentParser.normalize_description(description)

        # Remove leading/trailing non-alphanumeric sequences
        desc = re.sub(r'^[^A-Z0-9]+', '', desc)
        desc = re.sub(r'[^A-Z0-9]+$', '', desc)

        return desc

    @staticmethod
    def similarity_ratio(desc1: str, desc2: str) -> float:
        """
        Calculate similarity ratio between two descriptions
        Returns value between 0.0 and 1.0
        """
        # Normalize both descriptions
        norm1 = DocumentParser.extract_core_description(desc1)
        norm2 = DocumentParser.extract_core_description(desc2)

        # Use SequenceMatcher for fuzzy matching
        return SequenceMatcher(None, norm1, norm2).ratio()

    @staticmethod
    def descriptions_match(desc1: str, desc2: str, threshold: float = 0.85) -> bool:
        """
        Check if two descriptions match, accounting for OCR errors
        and extra text at beginning/end
        """
        ratio = DocumentParser.similarity_ratio(desc1, desc2)

        # Also check if one description is contained in the other
        norm1 = DocumentParser.extract_core_description(desc1)
        norm2 = DocumentParser.extract_core_description(desc2)

        contains_match = (norm1 in norm2) or (norm2 in norm1)

        return ratio >= threshold or (contains_match and ratio >= 0.7)


class InvoiceParser(DocumentParser):
    """Parse invoice OCR data"""

    @staticmethod
    def parse_invoice_line(line: str) -> Optional[LineItem]:
        """
        Parse a single invoice line
        Expected format includes: Customer Order Number, Del Adv Number,
        Description, Qty Del, Price, Unit, Discount, Total Value
        """
        # This is a simplified parser - adjust regex based on actual OCR format
        # Looking for patterns like: description, quantity, price, total

        # Skip header lines
        if 'CUSTOMER ORDER' in line or 'DESCRIPTION' in line or 'QTY' in line:
            return None

        # Try to extract structured data
        # Pattern for part numbers (highlighted items in yellow)
        part_match = re.search(r'([A-Z0-9]+(?:\d+[A-Z]+)+)', line)
        part_number = part_match.group(1) if part_match else ""

        # Extract description (usually the main text before quantity)
        desc_match = re.search(r'([A-Z][A-Z0-9\s\-\+]+(?:INSERT|BORING|PROTECTIVE|DEBURRING|THREADING|LIME|GLOVES|RESPIRATOR|TAP|DRILL)[A-Z\s]*)', line)
        description = desc_match.group(1).strip() if desc_match else ""

        if not description:
            return None

        # Extract quantity (number before EA or PK)
        qty_match = re.search(r'(\d+)\s+[\d.]+\s+(?:EA|PK)', line)
        quantity = float(qty_match.group(1)) if qty_match else 0.0

        # Extract price
        price_match = re.search(r'(\d+\.\d+)\s+(?:EA|PK)', line)
        price = float(price_match.group(1)) if price_match else 0.0

        # Extract total value
        total_match = re.search(r'(\d+\.\d+)\s+\d\s*$', line)
        total_value = float(total_match.group(1)) if total_match else 0.0

        # Extract unit
        unit_match = re.search(r'(EA|PK)', line)
        unit = unit_match.group(1) if unit_match else "EA"

        if quantity > 0 and description:
            return LineItem(
                part_number=part_number,
                description=description,
                quantity=quantity,
                price=price,
                total_value=total_value,
                unit=unit,
                source_line=line
            )

        return None


class DeliveryNoteParser(DocumentParser):
    """Parse delivery note OCR data"""

    @staticmethod
    def parse_delivery_line(line: str) -> Optional[LineItem]:
        """Parse a single delivery note line"""
        # Skip header lines
        if 'Qty' in line and 'Code' in line and 'Part No' in line:
            return None

        # Extract quantity (at start of line, may have checkmark before it)
        qty_match = re.search(r'(\d+)\s+([A-Z0-9]+)\s+([A-Z0-9]+)\s+(.+?)\s+([A-Z0-9\-]+)\s*$', line)

        if not qty_match:
            return None

        quantity = float(qty_match.group(1))
        code = qty_match.group(2)
        part_number = qty_match.group(3)
        description = qty_match.group(4).strip()
        branch = qty_match.group(5)

        return LineItem(
            part_number=part_number,
            description=description,
            quantity=quantity,
            price=0.0,  # Delivery note typically doesn't have prices
            total_value=0.0,
            unit="EA",
            source_line=line
        )


class ReconciliationEngine:
    """Main engine for reconciling invoice and delivery note"""

    def __init__(self, invoice_items: List[LineItem], delivery_items: List[LineItem]):
        self.invoice_items = invoice_items
        self.delivery_items = delivery_items

        # Aggregate items by description
        self.invoice_aggregated = self._aggregate_items(invoice_items)
        self.delivery_aggregated = self._aggregate_items(delivery_items)

    def _aggregate_items(self, items: List[LineItem]) -> Dict[str, Dict]:
        """
        Aggregate items by normalized description
        Returns dict with description as key and aggregated data as value
        """
        aggregated = defaultdict(lambda: {
            'quantity': 0.0,
            'total_value': 0.0,
            'items': [],
            'part_numbers': set(),
            'original_description': ''
        })

        for item in items:
            # Use normalized description as key
            key = DocumentParser.extract_core_description(item.description)

            aggregated[key]['quantity'] += item.quantity
            aggregated[key]['total_value'] += item.total_value
            aggregated[key]['items'].append(item)
            aggregated[key]['part_numbers'].add(item.part_number)

            # Keep first occurrence as original description
            if not aggregated[key]['original_description']:
                aggregated[key]['original_description'] = item.description

        return dict(aggregated)

    def find_matching_delivery_item(self, invoice_desc: str) -> Optional[str]:
        """
        Find matching delivery item for an invoice item
        Returns the delivery item key if found
        """
        for delivery_desc in self.delivery_aggregated.keys():
            if DocumentParser.descriptions_match(invoice_desc, delivery_desc):
                return delivery_desc
        return None

    def find_items_on_invoice_not_on_delivery(self) -> List[Dict]:
        """
        Step 1: Find items that appear on invoice but not on delivery note
        """
        missing_items = []

        for inv_desc, inv_data in self.invoice_aggregated.items():
            # Try to find matching delivery item
            matching_delivery = self.find_matching_delivery_item(inv_desc)

            if matching_delivery is None:
                missing_items.append({
                    'description': inv_data['original_description'],
                    'part_numbers': list(inv_data['part_numbers']),
                    'quantity': inv_data['quantity'],
                    'total_value': inv_data['total_value'],
                    'line_items': inv_data['items']
                })

        return missing_items

    def find_quantity_discrepancies(self) -> List[Dict]:
        """
        Step 2: Find items where invoice quantity > delivery quantity
        """
        discrepancies = []

        for inv_desc, inv_data in self.invoice_aggregated.items():
            # Try to find matching delivery item
            matching_delivery = self.find_matching_delivery_item(inv_desc)

            if matching_delivery:
                del_data = self.delivery_aggregated[matching_delivery]

                if inv_data['quantity'] > del_data['quantity']:
                    discrepancies.append({
                        'description': inv_data['original_description'],
                        'part_numbers': list(inv_data['part_numbers']),
                        'invoice_quantity': inv_data['quantity'],
                        'delivery_quantity': del_data['quantity'],
                        'difference': inv_data['quantity'] - del_data['quantity'],
                        'total_value': inv_data['total_value'],
                        'invoice_items': inv_data['items'],
                        'delivery_items': del_data['items']
                    })

        return discrepancies

    def generate_report(self) -> str:
        """Generate a comprehensive reconciliation report"""
        report = []
        report.append("=" * 80)
        report.append("INVOICE & DELIVERY NOTE RECONCILIATION REPORT")
        report.append("=" * 80)
        report.append("")

        # Step 1: Items on invoice but not on delivery
        missing = self.find_items_on_invoice_not_on_delivery()
        report.append(f"STEP 1: Items on Invoice but NOT on Delivery Note ({len(missing)} items)")
        report.append("-" * 80)

        if missing:
            for i, item in enumerate(missing, 1):
                report.append(f"\n{i}. {item['description']}")
                report.append(f"   Part Number(s): {', '.join(filter(None, item['part_numbers']))}")
                report.append(f"   Quantity: {item['quantity']}")
                report.append(f"   Total Value: £{item['total_value']:.2f}")

                if len(item['line_items']) > 1:
                    report.append(f"   (Aggregated from {len(item['line_items'])} line items)")
        else:
            report.append("\nNo items found on invoice that are missing from delivery note.")

        report.append("\n" + "=" * 80)

        # Step 2: Quantity discrepancies
        discrepancies = self.find_quantity_discrepancies()
        report.append(f"STEP 2: Quantity Discrepancies ({len(discrepancies)} items)")
        report.append("-" * 80)

        if discrepancies:
            for i, item in enumerate(discrepancies, 1):
                report.append(f"\n{i}. {item['description']}")
                report.append(f"   Part Number(s): {', '.join(filter(None, item['part_numbers']))}")
                report.append(f"   Invoice Quantity: {item['invoice_quantity']}")
                report.append(f"   Delivery Quantity: {item['delivery_quantity']}")
                report.append(f"   Difference: {item['difference']} (Invoice has MORE)")
                report.append(f"   Total Value: £{item['total_value']:.2f}")

                if len(item['invoice_items']) > 1 or len(item['delivery_items']) > 1:
                    report.append(f"   Invoice lines: {len(item['invoice_items'])}, " +
                                f"Delivery lines: {len(item['delivery_items'])}")
        else:
            report.append("\nNo quantity discrepancies found.")

        report.append("\n" + "=" * 80)

        # Summary
        report.append("\nSUMMARY")
        report.append("-" * 80)
        report.append(f"Total invoice items (aggregated): {len(self.invoice_aggregated)}")
        report.append(f"Total delivery items (aggregated): {len(self.delivery_aggregated)}")
        report.append(f"Items missing from delivery: {len(missing)}")
        report.append(f"Items with quantity discrepancies: {len(discrepancies)}")

        total_missing_value = sum(item['total_value'] for item in missing)
        total_discrepancy_value = sum(item['total_value'] for item in discrepancies)

        report.append(f"\nTotal value of missing items: £{total_missing_value:.2f}")
        report.append(f"Total value of discrepancy items: £{total_discrepancy_value:.2f}")
        report.append(f"Combined discrepancy value: £{total_missing_value + total_discrepancy_value:.2f}")

        report.append("\n" + "=" * 80)

        return "\n".join(report)


def parse_ocr_text_file(filepath: str, doc_type: str) -> List[LineItem]:
    """
    Parse OCR text file and extract line items

    Args:
        filepath: Path to OCR text file
        doc_type: Either 'invoice' or 'delivery'

    Returns:
        List of LineItem objects
    """
    items = []

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if doc_type == 'invoice':
            item = InvoiceParser.parse_invoice_line(line)
        elif doc_type == 'delivery':
            item = DeliveryNoteParser.parse_delivery_line(line)
        else:
            raise ValueError(f"Unknown document type: {doc_type}")

        if item:
            items.append(item)

    return items


def main():
    """Main entry point for the script"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Reconcile invoice and delivery note from OCR text'
    )
    parser.add_argument(
        '--invoice',
        required=True,
        help='Path to invoice OCR text file'
    )
    parser.add_argument(
        '--delivery',
        required=True,
        help='Path to delivery note OCR text file'
    )
    parser.add_argument(
        '--output',
        help='Path to output report file (optional, prints to console if not specified)'
    )

    args = parser.parse_args()

    # Parse documents
    print("Parsing invoice...")
    invoice_items = parse_ocr_text_file(args.invoice, 'invoice')
    print(f"Found {len(invoice_items)} invoice line items")

    print("\nParsing delivery note...")
    delivery_items = parse_ocr_text_file(args.delivery, 'delivery')
    print(f"Found {len(delivery_items)} delivery line items")

    # Reconcile
    print("\nReconciling documents...")
    engine = ReconciliationEngine(invoice_items, delivery_items)

    # Generate report
    report = engine.generate_report()

    # Output report
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\nReport written to: {args.output}")
    else:
        print("\n" + report)


if __name__ == '__main__':
    main()
