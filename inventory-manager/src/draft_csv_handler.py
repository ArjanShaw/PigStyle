import streamlit as st
from pathlib import Path
import io
import os
import time
import requests
import json
import re
import csv
from PIL import Image
from dotenv import load_dotenv
from typing import Dict, Optional, List

# --- Load environment variables ---
load_dotenv()

IMAGEBB_API_KEY = os.getenv("IMAGEBB_API_KEY")
DISCOGS_USER_TOKEN = os.getenv("DISCOGS_USER_TOKEN")
EBAY_CLIENT_ID = os.getenv("EBAY_CLIENT_ID")  
EBAY_CLIENT_SECRET = os.getenv("EBAY_CLIENT_SECRET")  

# --- Configuration ---
st.set_page_config(layout="wide")
IMAGE_FOLDER = Path("images")
IMAGE_FOLDER.mkdir(parents=True, exist_ok=True)

CATEGORY_MAP = {
    "Vinyl": "176985",
    "CDs": "176984",
    "Cassettes": "176983"
}

# --- Handler Classes ---

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
            return
        self.rows.append(clean_row)

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
    
    def search_price_range(self, query: str):
        try:
            # Clean and prepare search query
            search_query = self._prepare_search_query(query)
            
            # First try to get specific release ID if it's a URL
            release_id = self._extract_release_id(query)
            if release_id:
                return self._get_release_pricing(release_id, search_query)
            
            # Try marketplace search for listings
            return self._search_marketplace_listings(search_query)
            
        except Exception as e:
            return self._create_error_response(search_query, str(e))
    
    def _search_marketplace_listings(self, query: str):
        # Search for listings (items for sale)
        params = {
            'q': query,
            'type': 'release',
            'per_page': 100,
            'currency': 'USD'
        }
        
        response = requests.get(
            f"{self.base_url}/database/search",
            params=params,
            headers=self.headers,
            timeout=15
        )
        
        if response.status_code != 200:
            raise Exception(f"API returned status {response.status_code}")
        
        data = response.json()
        
        # Extract prices from results that have them
        prices = []
        listings_with_prices = 0
        
        for result in data.get('results', []):
            price = self._extract_price_from_result(result)
            if price is not None:
                prices.append(price)
                listings_with_prices += 1
        
        if prices:
            return self._calculate_pricing_stats(prices, listings_with_prices, len(data.get('results', [])), query, 'marketplace')
        else:
            return self._get_popular_releases_pricing(data.get('results', []), query)
    
    def _get_popular_releases_pricing(self, results, query: str):
        prices = []
        releases_checked = 0
        
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
            except Exception:
                continue
        
        if prices:
            return self._calculate_pricing_stats(prices, len(prices), len(results), query, 'release_stats')
        else:
            return self._create_no_results_response(len(results), query)
    
    def _get_release_stats(self, release_id: str):
        try:
            response = requests.get(
                f"{self.base_url}/releases/{release_id}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        
        return None
    
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
    
    def _get_release_pricing(self, release_id: str, query: str):
        try:
            release_data = self._get_release_stats(release_id)
            if not release_data:
                return self._create_no_results_response(0, query)
            
            price = self._extract_price_from_release(release_data)
            if price is not None:
                return self._calculate_pricing_stats([price], 1, 1, query, 'specific_release')
            else:
                return self._create_no_results_response(1, query)
                
        except Exception as e:
            return self._create_no_results_response(0, query)
    
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
            'result_count': total_results,
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
            'result_count': total_results,
            'url': self._generate_marketplace_url(query),
            'listings_with_prices': 0,
            'prices_found': 0,
            'search_type': 'no_prices',
            'success': False
        }
    
    def _create_error_response(self, query: str, error: str):
        return {
            'median_price': None,
            'lowest_price': None,
            'highest_price': None,
            'result_count': 0,
            'url': self._generate_marketplace_url(query),
            'listings_with_prices': 0,
            'prices_found': 0,
            'search_type': 'error',
            'error': error,
            'success': False
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

    def __init__(self, artist, title, client_id, client_secret, category_id, exclude_foreign, condition="Used"):
        self.artist = artist
        self.title = title
        self.client_id = client_id
        self.client_secret = client_secret

        if not str(category_id).isdigit():
            raise ValueError(f"Invalid eBay category ID: {category_id}. Must be numeric.")
        self.category_id = category_id

        self.exclude_foreign = exclude_foreign
        self.condition = condition
        self.token = None
        self.token_expiry = 0
        self.get_access_token()

        self.payloads_folder = Path("payloads")
        self.payloads_folder.mkdir(parents=True, exist_ok=True)

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

    def search_items(self, limit=50):
        headers = {"Authorization": f"Bearer {self.get_access_token()}"}
        query = f"{self.artist} {self.title}".strip()
        params = {"q": query, "limit": limit, "category_ids": self.category_id}

        resp = requests.get(self.EBAY_SEARCH_URL, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json().get("itemSummaries", [])

    def get_all_competitors(self, default_shipping):
        items = self.search_items(limit=50)
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

class DiscogsUI:
    def __init__(self, discogs_handler, ebay_client_id, ebay_client_secret):
        self.discogs_handler = discogs_handler
        self.ebay_client_id = ebay_client_id
        self.ebay_client_secret = ebay_client_secret
        if "item_cards" not in st.session_state:
            st.session_state.item_cards = [self._create_empty_card()]

    def render(self):
        if not self.discogs_handler or not getattr(self.discogs_handler, "user_token", None):
            self._render_error_message()
            return

        for i, card in enumerate(st.session_state.item_cards):
            self._render_item_card(i, card)
            if i < len(st.session_state.item_cards) - 1:
                st.markdown("---")

        if st.button("➕ Add New Item", use_container_width=True):
            # Save current card to CSV before adding new one
            self._save_current_card_to_csv()
            st.session_state.item_cards.append(self._create_empty_card())
            st.rerun()

    def _create_empty_card(self):
        return {
            "discogs_input": "",
            "your_price": "",
            "camera_images": [],
            "camera_key_idx": 0,
            "discogs_category": "Vinyl",
            "search_results": None,
            "ebay_prices": [],
            "add_to_inventory": False,
            "post_to_ebay": False,
            "saved_to_csv": False  # Track if this card has been saved
        }

    def _render_item_card(self, card_index, card):
        # Remove border styling
        st.markdown("""
        <style>
        .small-camera {
            max-width: 300px;
        }
        .small-camera .stCamera {
            max-width: 300px;
        }
        </style>
        """, unsafe_allow_html=True)
        
        st.text_input(
            "🔍 Search Discogs / eBay",
            value=card["discogs_input"],
            placeholder="Enter artist and title...",
            key=f"discogs_input_{card_index}",
            on_change=self._update_card_field,
            args=(card_index, "discogs_input", f"discogs_input_{card_index}")
        )

        st.selectbox(
            "Category",
            options=list(CATEGORY_MAP.keys()),
            index=list(CATEGORY_MAP.keys()).index(card.get("discogs_category", "Vinyl")),
            key=f"category_{card_index}",
            on_change=self._update_card_field,
            args=(card_index, "discogs_category", f"category_{card_index}")
        )

        if st.button("🔍 Search", key=f"search_btn_{card_index}", use_container_width=True):
            self._search_discogs_and_ebay(card_index)

        if card.get("search_results"):
            left, right = st.columns([2, 2])
            with left:
                self._render_discogs_data(card_index, card)
            with right:
                self._render_ebay_data(card_index, card)
            
            # Your Price field moved under the eBay/Discogs info
            st.text_input(
                "💲 Your Price",
                value=card.get("your_price", ""),
                placeholder="0.00",
                key=f"your_price_{card_index}",
                on_change=self._update_card_field,
                args=(card_index, "your_price", f"your_price_{card_index}")
            )

            # Panel with two checkboxes
            st.subheader("📦 Listing Options")
            col1, col2 = st.columns(2)
            with col1:
                add_to_inventory = st.checkbox(
                    "Add to Inventory",
                    value=card.get("add_to_inventory", False),
                    key=f"add_to_inventory_{card_index}",
                    on_change=self._update_card_field,
                    args=(card_index, "add_to_inventory", f"add_to_inventory_{card_index}")
                )
            with col2:
                post_to_ebay = st.checkbox(
                    "Post to eBay",
                    value=card.get("post_to_ebay", False),
                    key=f"post_to_ebay_{card_index}",
                    on_change=self._update_card_field,
                    args=(card_index, "post_to_ebay", f"post_to_ebay_{card_index}")
                )

            # Only show photos section if at least one checkbox is checked
            if add_to_inventory or post_to_ebay:
                self._render_photos_section(card_index, card)

    def _search_discogs_and_ebay(self, card_index):
        card = st.session_state.item_cards[card_index]
        if not card.get("discogs_input"):
            st.warning("Please enter a search term first")
            return

        category_id = CATEGORY_MAP.get(card.get("discogs_category", "Vinyl"), "176985")

        try:
            price_data = self.discogs_handler.search_price_range(card["discogs_input"])
            st.session_state.item_cards[card_index]["search_results"] = price_data
        except Exception as e:
            st.error(f"Discogs search failed: {e}")
            return

        try:
            handler = PriceHandler(
                artist=card["discogs_input"],
                title="",
                client_id=self.ebay_client_id,
                client_secret=self.ebay_client_secret,
                category_id=category_id,
                exclude_foreign=st.session_state.exclude_foreign,
                condition="Used"
            )
            competitors = handler.get_all_competitors(st.session_state.my_shipping_cost)
            st.session_state.item_cards[card_index]["ebay_prices"] = competitors
        except Exception as e:
            st.error(f"eBay search failed: {e}")
            return

        st.rerun()

    def _render_discogs_data(self, card_index, card):
        price_data = card.get("search_results")
        if not price_data or price_data.get("median_price") is None:
            st.warning("No Discogs pricing data available")
            return

        st.subheader("🎵 Discogs Data")
        st.info(f"""
**💰 Price Range:** ${price_data.get('lowest_price')} - ${price_data.get('highest_price')}
**🎯 Median Price:** ${price_data.get('median_price')}
**📈 Market Data:**
- Listings with prices: {price_data.get('listings_with_prices')}
- Total results: {price_data.get('result_count')}
""")

    def _render_ebay_data(self, card_index, card):
        competitors = card.get("ebay_prices", [])
        if not competitors:
            st.info("No eBay competitor data available")
            return

        st.subheader("🛒 eBay Data")
        table_html = "<style>table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:4px}</style>"
        table_html += "<table><tr><th>Thumb</th><th>Title</th><th>Price</th><th>Shipping</th><th>Condition</th><th>Compete</th></tr>"
        for item in sorted(competitors, key=lambda x: x["compete"]):
            full_title = item["title"].replace("|", " ")
            truncated = full_title[:30]+"..." if len(full_title)>30 else full_title
            title_html = f"<abbr title='{full_title}'>{truncated}</abbr>"
            price_html = f"${item['price']:.2f}"
            if item["shipping"]=="CALC": shipping_html="CALC"
            elif item["shipping"]=="FREE": shipping_html="FREE"
            else: shipping_html=f"${float(item['shipping']):.2f}"
            compete_html = f"${item['compete']:.2f}"
            thumb_html = f"<a href='{item['url']}' target='_blank'><img src='{item['thumbnail']}' width='50'></a>" if item.get("thumbnail") else "N/A"
            condition_html = item.get("condition", "Unknown")
            table_html += f"<tr><td>{thumb_html}</td><td>{title_html}</td><td>{price_html}</td><td>{shipping_html}</td><td>{condition_html}</td><td>{compete_html}</td></tr>"
        table_html += "</table>"
        st.components.v1.html(table_html, height=300, scrolling=True)

    def _update_card_field(self, card_index, field, key):
        st.session_state.item_cards[card_index][field] = st.session_state[key]

    def _render_photos_section(self, card_index, card):
        st.subheader("📸 Photos")
        
        # Create two columns: left for camera, right for existing photos
        cam_col, photos_col = st.columns([1, 2])
        
        with cam_col:
            st.markdown('<div class="small-camera">', unsafe_allow_html=True)
            camera_image = st.camera_input(
                "Take a picture",
                key=f"camera_{card_index}_{card['camera_key_idx']}"
            )
            st.markdown('</div>', unsafe_allow_html=True)
            
            if camera_image:
                image_bytes = camera_image.getvalue()
                # Always add new photo without clearing
                st.session_state.item_cards[card_index]["camera_images"].append(image_bytes)
                st.session_state.item_cards[card_index]["camera_key_idx"] += 1
                st.rerun()
        
        with photos_col:
            if card["camera_images"]:
                st.write(f"**{len(card['camera_images'])} photo(s) added**")
                
                # Display photos in a grid (side by side)
                photos = card["camera_images"]
                cols_per_row = 2  # Adjust based on your preference
                
                for i in range(0, len(photos), cols_per_row):
                    cols = st.columns(cols_per_row)
                    for j in range(cols_per_row):
                        if i + j < len(photos):
                            with cols[j]:
                                img = Image.open(io.BytesIO(photos[i + j]))
                                st.image(img, use_container_width=True, caption=f"Photo {i + j + 1}")
                
                # Clear photos button
                if st.button("🗑️ Clear All Photos", key=f"clear_photos_{card_index}", use_container_width=True):
                    st.session_state.item_cards[card_index]["camera_images"] = []
                    st.session_state.item_cards[card_index]["camera_key_idx"] = 0
                    st.rerun()
            else:
                st.info("No photos yet. Take a picture using the camera.")

    def _save_current_card_to_csv(self):
        """Save the current card (last one in the list) to CSV"""
        if len(st.session_state.item_cards) > 0:
            current_card = st.session_state.item_cards[-1]
            
            # Only save if we have required data
            title = current_card.get("discogs_input", "").strip()
            try:
                your_price = float(current_card.get("your_price") or 0)
            except ValueError:
                your_price = 0
            category = current_card.get("discogs_category", "Vinyl")
            
            # Check if we have the minimum required data
            if not title or your_price <= 0:
                st.warning("Please fill in title and price before adding new item")
                return

            # Upload all photos to ImageBB and get URLs
            img_urls = []
            for p_idx, image_bytes in enumerate(current_card.get("camera_images", [])):
                # Save image temporarily
                file_path = IMAGE_FOLDER / f"discogs_{len(st.session_state.item_cards)-1}_{p_idx}.jpg"
                with open(file_path, "wb") as f:
                    f.write(image_bytes)
                
                # Format the image
                formatter.format_image(file_path, save_path=file_path)
                
                # Upload to ImageBB
                try:
                    img_url = imagebb_handler.upload_from_file(file_path)
                    img_urls.append(img_url)
                    st.success(f"✅ Photo {p_idx+1} uploaded successfully")
                except Exception as e:
                    st.warning(f"Image upload failed for photo {p_idx+1}: {e}")

            if not img_urls:
                img_urls = [""]

            # Generate SKU and other fields
            sku = sku_generator.generate(title, category)
            artist = ""
            if category == "Vinyl" and "-" in title:
                artist = title.split("-")[0].strip()

            condition_map = {"New": "1000", "Used": "3000"}
            condition_id = condition_map.get("Used", "3000")

            # Create row data
            row = {
                "Action(SiteID=US|Country=US|Currency=USD|Version=1193|CC=UTF-8)": "Add",
                "Custom label (SKU)": sku,
                "Category ID": CATEGORY_MAP.get(category, "176985"),
                "Title": title,
                "UPC": "",
                "Price": f"{your_price:.2f}",
                "Quantity": "1",
                "Item photo URL": ",".join(img_urls),
                "Condition ID": condition_id,
                "Description": title,
                "C:Artist": artist,
            }
            
            # Add to CSV handler and save
            csv_handler.add_row(row)
            csv_handler.save_csv()
            
            # Mark card as saved
            st.session_state.item_cards[-1]["saved_to_csv"] = True
            
            st.success(f"✅ Item '{title}' added to CSV with {len(img_urls)} photos")

    def _render_error_message(self):
        st.error("Discogs API token not found. Please set DISCOGS_USER_TOKEN in your environment variables.")

# --- Session state defaults ---
if "csv_handler" not in st.session_state:
    st.session_state.csv_handler = DraftCSVHandler()
if "imagebb_handler" not in st.session_state:
    st.session_state.imagebb_handler = ImageBBHandler(IMAGEBB_API_KEY)

if "my_shipping_cost" not in st.session_state:
    st.session_state.my_shipping_cost = 5.72
if "exclude_foreign" not in st.session_state:
    st.session_state.exclude_foreign = True
if "verbose_mode" not in st.session_state:
    st.session_state.verbose_mode = False

# --- Initialize main components ---
csv_handler = st.session_state.csv_handler
imagebb_handler = st.session_state.imagebb_handler
formatter = ImageFormatter(max_width=800, max_height=800, quality=85)
sku_generator = SKUGenerator(max_length=30)
discogs_handler = DiscogsHandler(DISCOGS_USER_TOKEN) if DISCOGS_USER_TOKEN else None
discogs_ui = DiscogsUI(discogs_handler, EBAY_CLIENT_ID, EBAY_CLIENT_SECRET) if discogs_handler else None

# --- Sidebar: Parameters & CSV Export ---
with st.sidebar:
    st.header("⚙️ Settings & Export")

    with st.expander("📋 Parameters", expanded=False):
        st.session_state.my_shipping_cost = st.number_input(
            "Shipping ($)",
            min_value=0.0,
            value=st.session_state.my_shipping_cost,
            step=0.01,
            format="%.2f",
            key="shipping_input"
        )
        st.session_state.exclude_foreign = st.checkbox(
            "Exclude items from other eBay marketplaces",
            value=st.session_state.exclude_foreign,
            key="exclude_foreign_checkbox"
        )
        st.session_state.verbose_mode = st.checkbox(
            "Verbose Mode (show raw API responses)",
            value=st.session_state.verbose_mode,
            key="verbose_checkbox"
        )

    with st.expander("📤 CSV Export", expanded=False):
        if st.button("📄 Generate & Download eBay Draft CSV", use_container_width=True):
            csv_buffer = io.StringIO()
            csv_handler.save_csv(file_obj=csv_buffer)
            csv_bytes = io.BytesIO(csv_buffer.getvalue().encode("utf-8"))

            st.download_button(
                label="⬇️ Download eBay Draft CSV",
                data=csv_bytes,
                file_name="ebay_drafts.csv",
                mime="text/csv",
                use_container_width=True
            )

# --- Main page ---
if discogs_ui:
    discogs_ui.render()
else:
    st.error("Discogs integration not available. Please check your Discogs API token.")