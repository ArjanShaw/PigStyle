import csv
import io
from pathlib import Path

class DraftCSVHandler:
    INFO_LINE = "#INFO,Version=0.0.2,Template= eBay-draft-listings-template_US,,,,,,,,"
    HEADERS = [
        "Action(SiteID=US|Country=US|Currency=USD|Version=1193|CC=UTF-8)",
        "Custom label (SKU)",
        "Category ID",
        "Title",
        "UPC",
        "Price",
        "Quantity",
        "Item photo URL",
        "Condition ID",
        "Description",
        "C:Artist",   
    ]

    REQUIRED_FIELDS = [
        "Title",
        "Price",
        "Item photo URL",
        "Condition ID",
        "Description",
    ]

    def __init__(self, file_path="ebay_drafts.csv"):
        self.file_path = Path(file_path)
        self.rows = []
        self.load_existing()

    def load_existing(self):
        if self.file_path.exists():
            with open(self.file_path, newline='', encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    clean_row = {h: (row.get(h, "") or "").strip() for h in self.HEADERS}
                    if self._is_valid(clean_row):
                        self.rows.append(clean_row)

    def _is_valid(self, row: dict) -> bool:
        missing = [field for field in self.REQUIRED_FIELDS if not str(row.get(field, "")).strip()]
        if missing:
            return False
        return True

    def add_row(self, data: dict):
        clean_row = {h: str(data.get(h, "")).strip() for h in self.HEADERS}
        if not self._is_valid(clean_row):
            return False
        self.rows.append(clean_row)
        return True

    def save_csv(self, file_obj=None):
        """
        Save CSV. If file_obj is provided (like io.StringIO), write to it.
        Otherwise, write to self.file_path.
        """
        valid_rows = [row for row in self.rows if self._is_valid(row)]
        if file_obj:
            writer = csv.DictWriter(file_obj, fieldnames=self.HEADERS)
            file_obj.write(self.INFO_LINE + "\n")
            writer.writeheader()
            writer.writerows(valid_rows)
        else:
            with open(self.file_path, "w", newline="", encoding="utf-8") as f:
                f.write(self.INFO_LINE + "\n")
                writer = csv.DictWriter(f, fieldnames=self.HEADERS)
                writer.writeheader()
                writer.writerows(valid_rows)

    def generate_ebay_txt_from_records(self, records, price_handler=None):
        """Generate eBay formatted TXT content from record data"""
        output = io.StringIO()
        
        # Write info line
        output.write(self.INFO_LINE + "\n")
        
        # Write headers
        output.write(",".join(self.HEADERS) + "\n")
        
        # Write data rows
        for record in records:
            row_data = self._format_record_for_ebay(record, price_handler)
            if row_data:
                row_values = [str(row_data.get(header, "")) for header in self.HEADERS]
                output.write(",".join(row_values) + "\n")
        
        return output.getvalue()

    def _format_record_for_ebay(self, record, price_handler=None):
        """Format a single record for eBay import - use calculated eBay price"""
        # Map format to eBay category ID
        category_map = {
            "Vinyl": "176985",
            "CDs": "176984", 
            "Cassettes": "176983"
        }
        
        # Map condition to eBay condition ID
        condition_map = {
            "1": "3000",
            "2": "3000",  
            "3": "3000",
            "4": "3000",
            "5": "1000",
        }
        
        # Get basic fields
        artist = record.get('artist', 'Unknown Artist')
        title = record.get('title', 'Unknown Title')
        format_type = record.get('format', 'Vinyl')
        condition = record.get('condition', '4')
        barcode = record.get('barcode', '')
        image_url = record.get('image_url', '')
        
        # Calculate eBay price using PriceHandler
        if price_handler:
            ebay_price = price_handler.calculate_ebay_price(record.get('ebay_lowest_price'))
        else:
            # Fallback: use discogs median price if no price handler
            ebay_price = record.get('discogs_median_price', 0) or 0
        
        # Simple SKU from barcode or title
        if barcode:
            sku = f"VINYL_{barcode}"
        else:
            sku = f"{title.replace(' ', '')}-{format_type.upper()}"
        sku = sku[:30]
        
        # Simple description
        description = f"{artist} - {title}"
        
        # Title includes artist
        ebay_title = f"{artist} - {title}"
        
        return {
            "Action(SiteID=US|Country=US|Currency=USD|Version=1193|CC=UTF-8)": "Draft",
            "Custom label (SKU)": sku,
            "Category ID": category_map.get(format_type, "176985"),
            "Title": ebay_title,
            "UPC": barcode,
            "Price": f"{float(ebay_price):.2f}",
            "Quantity": "1",
            "Item photo URL": image_url,
            "Condition ID": condition_map.get(condition, "3000"),
            "Description": description,
            "C:Artist": artist,
        }