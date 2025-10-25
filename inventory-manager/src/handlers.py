import csv
import io
import time
import re
import requests
import json
from pathlib import Path
from PIL import Image
from typing import Dict, List, Optional

# Remove DraftCSVHandler class from this file - it's now in draft_csv_handler.py

class InventoryCSVHandler:
    def __init__(self, file_path="inventory.csv"):
        self.file_path = Path(file_path)
        self.headers = ["Artist", "Title", "Genre", "Inventory Price", "eBay Price", "Image URL", "Date Added"]
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Create the inventory file with headers if it doesn't exist"""
        if not self.file_path.exists():
            with open(self.file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.headers)
                writer.writeheader()

    def add_inventory_item(self, artist: str, title: str, genre: str, inventory_price: float, ebay_price: float = None, image_url: str = ""):
        """Add an item to the inventory CSV file"""
        row = {
            "Artist": artist.strip(),
            "Title": title.strip(),
            "Genre": genre.strip(),
            "Inventory Price": f"{inventory_price:.2f}",
            "eBay Price": f"{ebay_price:.2f}" if ebay_price is not None else "",
            "Image URL": image_url,
            "Date Added": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        # Append to the CSV file
        with open(self.file_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.headers)
            writer.writerow(row)

        return True

    def get_all_inventory(self):
        """Get all inventory items"""
        if not self.file_path.exists():
            return []
        
        items = []
        with open(self.file_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Clean the row to only include expected fields
                clean_row = {field: row.get(field, "") for field in self.headers}
                items.append(clean_row)
        return items

    def convert_to_ebay_csv(self, category="Vinyl"):
        """Convert inventory items to eBay CSV format"""
        ebay_rows = []
        inventory_items = self.get_all_inventory()
        
        # Category mapping
        category_map = {
            "Vinyl": "176985",
            "CDs": "176984", 
            "Cassettes": "176983"
        }
        category_id = category_map.get(category, "176985")
        
        for item in inventory_items:
            if not item.get("eBay Price") or float(item.get("eBay Price", 0) or 0) <= 0:
                continue
                
            # Extract artist and title
            artist = item.get("Artist", "")
            title = item.get("Title", "")
            ebay_price = float(item.get("eBay Price", 0))
            image_url = item.get("Image URL", "")
            
            # Generate SKU
            sku = f"{category[:3]}_{title.replace(' ', '_')}"[:30]
            sku = re.sub(r'[^\w]', '', sku)
            
            condition_map = {"New": "1000", "Used": "3000"}
            condition_id = condition_map.get("Used", "3000")

            # Create eBay row - using "Draft" as Action and including image URL
            ebay_row = {
                "Action(SiteID=US|Country=US|Currency=USD|Version=1193|CC=UTF-8)": "Draft",
                "Custom label (SKU)": sku,
                "Category ID": category_id,
                "Title": title,
                "UPC": "",
                "Price": f"{ebay_price:.2f}",
                "Quantity": "1",
                "Item photo URL": image_url,
                "Condition ID": condition_id,
                "Description": title,
                "C:Artist": artist,
            }
            ebay_rows.append(ebay_row)
        
        return ebay_rows

class ImageBBHandler:
    def __init__(self, api_key):
        self.api_key = api_key
        self.upload_url = "https://api.imgbb.com/1/upload"

    def upload_from_file(self, file_path):
        with open(file_path, "rb") as f:
            files = {"image": f}
            data = {"key": self.api_key}
            resp = requests.post(self.upload_url, files=files, data=data)
            resp.raise_for_status()
            return resp.json()["data"]["url"]

class ImageFormatter:
    """
    Handles resizing and compressing images for eBay upload
    to reduce memory usage while keeping quality usable.
    """
    def __init__(self, max_width=800, max_height=800, quality=85):
        self.max_width = max_width
        self.max_height = max_height
        self.quality = quality

    def format_image(self, image_path, save_path=None):
        """
        Resizes and compresses the image at image_path.
        If save_path is provided, saves the formatted image to that path.
        Returns a BytesIO buffer if save_path is None.
        """
        img = Image.open(image_path)
        img = img.convert("RGB")  # Ensure consistent format

        # Resize maintaining aspect ratio
        img.thumbnail((self.max_width, self.max_height))

        # Save to a BytesIO buffer to control compression
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=self.quality, optimize=True)
        buffer.seek(0)

        if save_path:
            with open(save_path, "wb") as f:
                f.write(buffer.read())
            return save_path
        else:
            return buffer

class SKUGenerator:
    def __init__(self, max_length=30):
        self.max_length = max_length

    def generate(self, title, category):
        base_sku = f"{category[:3]}_{title.replace(' ', '_')}"
        safe_sku = re.sub(r'[^\w]', '', base_sku)
        return safe_sku[:self.max_length]

class PriceHandler:
    EBAY_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    EBAY_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

    def __init__(self, artist, title, client_id, client_secret, category_id, exclude_foreign, condition="Used", verbose=False):
        self.artist = artist
        self.title = title
        self.client_id = client_id
        self.client_secret = client_secret
        self.verbose = verbose

        if not str(category_id).isdigit():
            raise ValueError(f"Invalid eBay category ID: {category_id}. Must be numeric.")
        self.category_id = category_id

        self.exclude_foreign = exclude_foreign
        self.condition = condition
        self.token = None
        self.token_expiry = 0
        
        # Check if shipping cost is set
        import streamlit as st
        if "my_shipping_cost" not in st.session_state or st.session_state.my_shipping_cost <= 0:
            raise ValueError("Shipping cost must be set in the sidebar parameters before searching eBay")
            
        self.get_access_token()

    def get_access_token(self):
        if self.token and time.time() < self.token_expiry:
            return self.token

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"}

        resp = requests.post(self.EBAY_TOKEN_URL, headers=headers, data=data, auth=(self.client_id, self.client_secret))
        resp.raise_for_status()
        token_data = resp.json()
        self.token = token_data["access_token"]
        self.token_expiry = time.time() + token_data["expires_in"] - 60
        
        return self.token

    def search_items(self, limit=50, filename_base: str = None):
        headers = {"Authorization": f"Bearer {self.get_access_token()}"}
        query = f"{self.artist} {self.title}".strip()
        params = {"q": query, "limit": limit, "category_ids": self.category_id}

        # Store search request data for verbose mode
        request_data = {
            'url': self.EBAY_SEARCH_URL,
            'headers': {k: '***' if 'Authorization' in k else v for k, v in headers.items()},
            'params': params
        }

        # Save request payload if filename_base provided
        if filename_base:
            self._save_payload(f"{filename_base}_ebay_request.json", request_data)

        resp = requests.get(self.EBAY_SEARCH_URL, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        
        # Save search response data for verbose mode
        if filename_base:
            self._save_payload(f"{filename_base}_ebay_response.json", data)
            
        return data.get("itemSummaries", [])

    def _save_payload(self, filename, data):
        """Save payload data to JSON file"""
        payloads_folder = Path("payloads")
        payloads_folder.mkdir(parents=True, exist_ok=True)
        file_path = payloads_folder / filename
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Saved payload: {file_path}")  # Debug output
        except Exception as e:
            print(f"Error saving payload {filename}: {e}")

    def get_all_competitors(self, default_shipping, filename_base: str = None):
        items = self.search_items(limit=50, filename_base=filename_base)
        competitors = []

        for item in items:
            try:
                marketplace_id = item.get("listingMarketplaceId")
                if self.exclude_foreign and marketplace_id and marketplace_id != "EBAY_US":
                    continue

                price_data = item.get("price", {})
                if "value" in price_data:
                    price = float(price_data["value"])
                elif "__value__" in price_data:
                    price = float(price_data["__value__"])
                else:
                    continue

                shipping_info = item.get("shippingOptions", [])
                if shipping_info:
                    ship_type = shipping_info[0].get("shippingCostType", "N/A")
                    ship_cost_data = shipping_info[0].get("shippingCost", {})

                    if ship_type == "CALCULATED":
                        shipping = "CALC"
                        compete_val = price
                    elif ship_type.upper() == "FREE":
                        shipping = "FREE"
                        compete_val = price - default_shipping
                    elif ship_type.upper() == "FIXED":
                        try:
                            shipping_cost_value = float(ship_cost_data.get("value", default_shipping))
                        except (ValueError, TypeError):
                            shipping_cost_value = default_shipping

                        if shipping_cost_value == 0.0:
                            shipping = "FREE"
                            compete_val = price - default_shipping
                        else:
                            shipping = shipping_cost_value
                            compete_val = price + shipping - default_shipping
                    else:
                        shipping = "CALC"
                        compete_val = price
                else:
                    shipping = "CALC"
                    compete_val = price

                url = item.get("itemWebUrl", "#")
                thumbnail = item.get("thumbnailImages", [{}])[0].get("imageUrl", "")

                competitors.append({
                    "title": item.get("title", "Unknown"),
                    "price": price,
                    "shipping": shipping,
                    "url": url,
                    "thumbnail": thumbnail,
                    "compete": compete_val,
                    "condition": item.get("condition", "Unknown")
                })

            except Exception:
                continue

        competitors.sort(key=lambda x: x["compete"])
        return competitors