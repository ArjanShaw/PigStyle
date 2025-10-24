import csv
import io
import time
import re
import requests
import json
from pathlib import Path
from PIL import Image
from typing import Dict, List, Optional

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

class DiscogsHandler:
    def __init__(self, user_token: str):
        self.user_token = user_token
        self.base_url = "https://api.discogs.com"
        self.headers = {
            "User-Agent": "eBayListingTool/1.0",
            "Authorization": f"Discogs token={self.user_token}"
        }
    
    def search_multiple_results(self, query: str, filename_base: str = None):
        """Search Discogs and return multiple results for user selection"""
        # Search for listings (items for sale)
        params = {
            'q': query,
            'type': 'release',
            'per_page': 50,  # Get more results for selection
            'currency': 'USD'
        }
        
        # Store request data for verbose mode
        request_data = {
            'url': f"{self.base_url}/database/search",
            'headers': {k: '***' if 'Authorization' in k else v for k, v in self.headers.items()},
            'params': params
        }
        
        # Save request payload if filename_base provided
        if filename_base:
            self._save_payload(f"{filename_base}_discogs_search_request.json", request_data)
        
        response = requests.get(
            f"{self.base_url}/database/search",
            params=params,
            headers=self.headers,
            timeout=15
        )
        
        if response.status_code != 200:
            raise Exception(f"Discogs API returned status {response.status_code}: {response.text}")
        
        data = response.json()
        
        # Save response payload if filename_base provided
        if filename_base:
            self._save_payload(f"{filename_base}_discogs_search_response.json", data)
        
        return data
    
    def get_release_pricing(self, release_id: str, query: str, filename_base: str = None):
        """Get pricing information for a specific release"""
        # First get release details
        release_data = self._get_release_stats(release_id)
        if not release_data:
            return self._create_no_results_response(0, query)
        
        # Then get marketplace listings for this specific release
        params = {
            'release_id': release_id,
            'per_page': 100,
            'currency': 'USD'
        }
        
        response = requests.get(
            f"{self.base_url}/marketplace/listings",
            params=params,
            headers=self.headers,
            timeout=15
        )
        
        if response.status_code != 200:
            # Fallback to using release stats if marketplace search fails
            price = self._extract_price_from_release(release_data)
            image_url = self._extract_image_from_release(release_data)
            
            if price is not None:
                result = self._calculate_pricing_stats([price], 1, 1, query, 'release_stats')
                result['image_url'] = image_url
                result['release_data'] = release_data
                return result
            else:
                result = self._create_no_results_response(1, query)
                result['image_url'] = image_url
                result['release_data'] = release_data
                return result
        
        listings_data = response.json()
        
        # Save response payload if filename_base provided
        if filename_base:
            self._save_payload(f"{filename_base}_discogs_listings_response.json", listings_data)
        
        # Extract prices from listings
        prices = []
        for listing in listings_data.get('listings', []):
            price_str = listing.get('price', {}).get('value')
            if price_str:
                price = self._parse_price(price_str)
                if price is not None:
                    prices.append(price)
        
        image_url = self._extract_image_from_release(release_data)
        
        if prices:
            result = self._calculate_pricing_stats(prices, len(prices), len(listings_data.get('listings', [])), query, 'marketplace')
            result['image_url'] = image_url
            result['release_data'] = release_data
            return result
        else:
            # Fallback to release stats
            price = self._extract_price_from_release(release_data)
            if price is not None:
                result = self._calculate_pricing_stats([price], 1, 1, query, 'release_stats')
                result['image_url'] = image_url
                result['release_data'] = release_data
                return result
            else:
                result = self._create_no_results_response(len(listings_data.get('listings', [])), query)
                result['image_url'] = image_url
                result['release_data'] = release_data
                return result

    def search_price_range(self, query: str, filename_base: str = None):
        # Clean and prepare search query
        search_query = self._prepare_search_query(query)
        
        # First try to get specific release ID if it's a URL
        release_id = self._extract_release_id(query)
        if release_id:
            return self._get_release_pricing(release_id, search_query, filename_base)
        
        # Try marketplace search for listings
        return self._search_marketplace_listings(search_query, filename_base)
    
    def _search_marketplace_listings(self, query: str, filename_base: str = None):
        # Search for listings (items for sale)
        params = {
            'q': query,
            'type': 'release',
            'per_page': 100,
            'currency': 'USD'
        }
        
        # Store request data for verbose mode
        request_data = {
            'url': f"{self.base_url}/database/search",
            'headers': {k: '***' if 'Authorization' in k else v for k, v in self.headers.items()},
            'params': params
        }
        
        # Save request payload if filename_base provided
        if filename_base:
            self._save_payload(f"{filename_base}_discogs_request.json", request_data)
        
        response = requests.get(
            f"{self.base_url}/database/search",
            params=params,
            headers=self.headers,
            timeout=15
        )
        
        if response.status_code != 200:
            raise Exception(f"Discogs API returned status {response.status_code}: {response.text}")
        
        data = response.json()
        
        # Save response payload if filename_base provided
        if filename_base:
            self._save_payload(f"{filename_base}_discogs_response.json", data)
        
        # Extract artist and title from first result if available
        artist = "Unknown Artist"
        title = "Unknown Title"
        genre = "Unknown"
        image_url = ""
        
        if data.get('results'):
            first_result = data['results'][0]
            
            # Extract artist - try different fields
            if first_result.get('artist'):
                artist = first_result['artist']
            elif first_result.get('artists') and first_result['artists']:
                artist = first_result['artists'][0].get('name', 'Unknown Artist')
            
            # Extract title and split artist-title if needed
            if first_result.get('title'):
                title_text = first_result['title']
                # If title contains " - ", split it into artist and title
                if ' - ' in title_text:
                    parts = title_text.split(' - ', 1)
                    if artist == "Unknown Artist":
                        artist = parts[0].strip()
                    title = parts[1].strip()
                else:
                    title = title_text
            
            # Extract genre
            if first_result.get('genre'):
                genre = first_result.get('genre', ['Unknown'])[0] if first_result.get('genre') else "Unknown"
            
            # Extract image URL
            image_url = self._extract_image_from_result(first_result)
        
        # Extract prices from results that have them
        prices = []
        listings_with_prices = 0
        
        for result in data.get('results', []):
            price = self._extract_price_from_result(result)
            if price is not None:
                prices.append(price)
                listings_with_prices += 1
        
        if prices:
            result = self._calculate_pricing_stats(prices, listings_with_prices, len(data.get('results', [])), query, 'marketplace')
            result['artist'] = artist
            result['title'] = title
            result['genre'] = genre
            result['image_url'] = image_url
            result['release_data'] = data.get('results', [{}])[0] if data.get('results') else {}
            return result
        else:
            result = self._get_popular_releases_pricing(data.get('results', []), query)
            result['artist'] = artist
            result['title'] = title
            result['genre'] = genre
            result['image_url'] = image_url
            result['release_data'] = data.get('results', [{}])[0] if data.get('results') else {}
            return result

    def _extract_image_from_result(self, result):
        """Extract image URL from Discogs result"""
        # Try different possible image fields in order of preference
        image_fields = [
            result.get('cover_image'),
            result.get('thumb'),
            result.get('images', [{}])[0].get('uri'),
            result.get('images', [{}])[0].get('uri150'),
            result.get('resource_url')
        ]
        
        for image_field in image_fields:
            if image_field and isinstance(image_field, str) and image_field.startswith('http'):
                return image_field
        
        return ""

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
    
    def _get_popular_releases_pricing(self, results, query: str):
        prices = []
        releases_checked = 0
        image_url = ""
        
        # Check first 5 most relevant results
        for result in results[:5]:
            release_id = result.get('id')
            if not release_id:
                continue
                
            try:
                release_data = self._get_release_stats(str(release_id))
                if release_data:
                    price = self._extract_price_from_release(release_data)
                    if price is not None:
                        prices.append(price)
                        releases_checked += 1
                        # Get image from the first successful release
                        if not image_url:
                            image_url = self._extract_image_from_release(release_data)
            except Exception as e:
                print(f"Error getting release {release_id}: {e}")
                continue
        
        if prices:
            result = self._calculate_pricing_stats(prices, len(prices), len(results), query, 'release_stats')
            result['image_url'] = image_url
            return result
        else:
            result = self._create_no_results_response(len(results), query)
            result['image_url'] = image_url
            return result
    
    def _extract_image_from_release(self, release_data):
        """Extract image URL from release data"""
        # Try different possible image fields
        image_fields = [
            release_data.get('images', [{}])[0].get('uri'),
            release_data.get('images', [{}])[0].get('uri150'),
            release_data.get('thumb'),
            release_data.get('cover_image')
        ]
        
        for image_field in image_fields:
            if image_field and isinstance(image_field, str) and image_field.startswith('http'):
                return image_field
        
        return ""
    
    def _get_release_stats(self, release_id: str):
        response = requests.get(
            f"{self.base_url}/releases/{release_id}",
            headers=self.headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get release {release_id}: {response.status_code}")
    
    def _extract_price_from_release(self, release_data):
        price_fields = [
            release_data.get('lowest_price'),
            release_data.get('estimated_price'),
        ]
        
        for price_str in price_fields:
            if price_str:
                price = self._parse_price(price_str)
                if price is not None:
                    return price
        
        return None
    
    def _extract_price_from_result(self, result):
        price_fields = [
            result.get('lowest_price'),
            result.get('price'), 
            result.get('formatted_price'),
            result.get('estimated_price'),
        ]
        
        for price_str in price_fields:
            if price_str:
                price = self._parse_price(price_str)
                if price is not None:
                    return price
        
        return None
    
    def _get_release_pricing_old(self, release_id: str, query: str, filename_base: str = None):
        release_data = self._get_release_stats(release_id)
        if not release_data:
            return self._create_no_results_response(0, query)
        
        price = self._extract_price_from_release(release_data)
        image_url = self._extract_image_from_release(release_data)
        
        if price is not None:
            result = self._calculate_pricing_stats([price], 1, 1, query, 'specific_release')
            result['image_url'] = image_url
            result['release_data'] = release_data
            return result
        else:
            result = self._create_no_results_response(1, query)
            result['image_url'] = image_url
            result['release_data'] = release_data
            return result
    
    def _calculate_pricing_stats(self, prices, listings_with_prices: int, total_results: int, query: str, search_type: str):
        sorted_prices = sorted(prices)
        n = len(sorted_prices)
        
        # Calculate median
        if n % 2 == 1:
            median = sorted_prices[n//2]
        else:
            median = (sorted_prices[n//2 - 1] + sorted_prices[n//2]) / 2
        
        return {
            'median_price': round(median, 2),
            'lowest_price': min(prices),
            'highest_price': max(prices),
            'url': self._generate_marketplace_url(query),
            'currency': 'USD',
            'listings_with_prices': listings_with_prices,
            'prices_found': len(prices),
            'search_type': search_type,
            'success': True
        }
    
    def _create_no_results_response(self, total_results: int, query: str):
        return {
            'median_price': None,
            'lowest_price': None,
            'highest_price': None,
            'url': self._generate_marketplace_url(query),
            'listings_with_prices': 0,
            'prices_found': 0,
            'search_type': 'no_prices',
            'success': False,
            'error': 'No pricing data found'
        }
    
    def _extract_release_id(self, query: str):
        if 'discogs.com' in query.lower():
            match = re.search(r'discogs\.com/(?:release|sell/item)/(\d+)', query)
            if match:
                return match.group(1)
        return None
    
    def _prepare_search_query(self, query: str):
        if 'discogs.com' in query.lower():
            match = re.search(r'discogs\.com/.*/([^/?]+)', query)
            if match:
                return match.group(1).replace('-', ' ')
        return query.strip()
    
    def _parse_price(self, price_str):
        try:
            if not price_str:
                return None
            
            cleaned = re.sub(r'[^\d.,]', '', str(price_str))
            
            if not cleaned:
                return None
            
            if ',' in cleaned and '.' in cleaned:
                cleaned = cleaned.replace(',', '')
            elif ',' in cleaned:
                parts = cleaned.split(',')
                if len(parts) == 2 and len(parts[1]) <= 2:
                    cleaned = cleaned.replace(',', '.')
                else:
                    cleaned = cleaned.replace(',', '')
            
            cleaned = re.sub(r'[^\d.]', '', cleaned)
            
            if cleaned:
                price_float = float(cleaned)
                if 0.1 <= price_float <= 10000:
                    return round(price_float, 2)
            return None
        except (ValueError, TypeError):
            return None
    
    def _generate_marketplace_url(self, query: str):
        encoded_query = requests.utils.quote(query)
        return f"https://www.discogs.com/sell/list?q={encoded_query}&currency=USD"

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