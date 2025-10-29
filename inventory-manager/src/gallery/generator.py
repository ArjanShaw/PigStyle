import json
import threading
import time
import os
from pathlib import Path
import pandas as pd
import math

class GalleryJSONManager:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
        # The web server directory
        web_server_paths = [
            Path("/var/www/html"),
            Path("/var/www/pigstylerecords.com/public_html"),
            Path("/var/www/pigstylerecords.com/html"),
            Path("/srv/www/pigstylerecords.com/public_html"),
            Path("/home/pigstyle/public_html"),
            Path("/home/pigstyle/www"),
            Path("/home/pigstyle/web"),
            Path("/mount/src/pigstyle/web/public"),
            Path("./web/public"),
        ]
        
        # Find the correct web server directory
        self.web_base_path = None
        for path in web_server_paths:
            if path.exists():
                catalog_path = path / "catalog.html"
                if catalog_path.exists():
                    self.web_base_path = path
                    print(f"✅ Found web directory: {path}")
                    print(f"✅ Catalog.html exists at: {catalog_path}")
                    break
        
        # If no directory found, use a fallback
        if self.web_base_path is None:
            self.web_base_path = Path("/tmp/pigstyle_web_fallback")
            self.web_base_path.mkdir(parents=True, exist_ok=True)
            print(f"⚠️  WARNING: Using fallback directory: {self.web_base_path}")
        
        self.json_path = self.web_base_path / "gallery-data.json"
        self.temp_path = self.web_base_path / "gallery-data.json.tmp"
        
        print(f"🎯 JSON will be saved to: {self.json_path}")
        
        self._rebuild_lock = threading.Lock()
        self._last_rebuild_time = 0
        self._rebuild_in_progress = False
        
    def trigger_rebuild(self, async_mode=True):
        """Trigger a JSON rebuild, optionally in background thread"""
        if async_mode:
            thread = threading.Thread(target=self._rebuild_in_thread, daemon=True)
            thread.start()
            return True
        else:
            return self._perform_rebuild()
    
    def _rebuild_in_thread(self):
        self._perform_rebuild()
    
    def _perform_rebuild(self):
        if not self._rebuild_lock.acquire(blocking=False):
            print("JSON rebuild already in progress, skipping...")
            return False
        
        try:
            self._rebuild_in_progress = True
            start_time = time.time()
            
            print(f"🎯 Starting gallery JSON rebuild to: {self.json_path}")
            
            # Ensure directory exists
            self.web_base_path.mkdir(parents=True, exist_ok=True)
            
            if not os.access(self.web_base_path, os.W_OK):
                raise Exception(f"Directory not writable: {self.web_base_path}")
            
            # Get all records from database
            records = self._fetch_all_records()
            print(f"📊 Fetched {len(records)} records from database")
            
            # Build JSON structure
            json_data = self._build_json_structure(records)
            
            # Write to file
            success = self._write_json_file(json_data)
            
            if success:
                duration = time.time() - start_time
                print(f"✅ Gallery JSON rebuild completed in {duration:.2f}s - {len(records)} records")
                self._last_rebuild_time = time.time()
                
                # Verify the file was created
                if self.json_path.exists():
                    file_size = self.json_path.stat().st_size
                    print(f"📄 JSON file created: {file_size} bytes")
                    
                    # Check if catalog.html can access it
                    catalog_path = self.web_base_path / "catalog.html"
                    if catalog_path.exists():
                        print(f"🌐 Website should now see the JSON at: https://pigstylerecords.com/gallery-data.json")
                    else:
                        print(f"⚠️  Warning: catalog.html not found in {self.web_base_path}")
                else:
                    print("❌ WARNING: JSON file was not created!")
                    
            else:
                print("❌ Gallery JSON rebuild failed")
                
            return success
            
        except Exception as e:
            print(f"❌ Gallery JSON rebuild error: {e}")
            import traceback
            print(f"📋 Traceback: {traceback.format_exc()}")
            return False
        finally:
            self._rebuild_in_progress = False
            self._rebuild_lock.release()
    
    def _fetch_all_records(self):
        conn = self.db_manager._get_connection()
        
        query = """
        SELECT 
            id, artist, title, image_url, genre, barcode,
            store_price, file_at, youtube_url, catalog_number,
            format, condition
        FROM records_with_genres 
        ORDER BY id
        """
        
        df = pd.read_sql(query, conn)
        conn.close()
        
        return df.to_dict('records')
    
    def _build_json_structure(self, records):
        # Clean the records data to replace NaN with null
        cleaned_records = []
        for record in records:
            cleaned_record = {}
            for key, value in record.items():
                # Replace NaN, None, and other invalid values with null
                if value is None or (isinstance(value, float) and math.isnan(value)):
                    cleaned_record[key] = None
                else:
                    cleaned_record[key] = value
            cleaned_records.append(cleaned_record)
        
        return {
            "meta": {
                "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "total_records": len(cleaned_records),
                "format_version": "2.0"
            },
            "records": cleaned_records
        }
    
    def _write_json_file(self, json_data):
        # Write to temporary file first
        with open(self.temp_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        # Atomic rename from temp to final
        self.temp_path.rename(self.json_path)
        
        return True
    
    def get_rebuild_status(self):
        return {
            "in_progress": self._rebuild_in_progress,
            "last_rebuild_time": self._last_rebuild_time
        }
    
    def get_json_path(self):
        return str(self.json_path)
    
    def get_web_directory(self):
        return str(self.web_base_path)