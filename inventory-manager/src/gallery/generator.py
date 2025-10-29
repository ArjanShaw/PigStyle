import json
import threading
import time
import os
from pathlib import Path
import pandas as pd

class GalleryJSONManager:
    def __init__(self, db_manager, web_base_path="../../web/public"):
        self.db_manager = db_manager
        self.web_base_path = Path(web_base_path)
        self.json_path = self.web_base_path / "gallery-data.json"
        self.temp_path = self.web_base_path / "gallery-data.json.tmp"
        self.backup_path = self.web_base_path / "gallery-data.json.backup"
        self._rebuild_lock = threading.Lock()
        self._last_rebuild_time = 0
        self._rebuild_in_progress = False
        
    def trigger_rebuild(self, async_mode=True):
        """Trigger a JSON rebuild, optionally in background thread"""
        if async_mode:
            # Start rebuild in background thread
            thread = threading.Thread(target=self._rebuild_in_thread, daemon=True)
            thread.start()
            return True
        else:
            # Synchronous rebuild
            return self._perform_rebuild()
    
    def _rebuild_in_thread(self):
        """Wrapper to run rebuild in thread with proper error handling"""
        try:
            self._perform_rebuild()
        except Exception as e:
            print(f"Background JSON rebuild failed: {e}")
    
    def _perform_rebuild(self):
        """Perform the actual JSON rebuild with locking"""
        # Acquire lock to prevent concurrent rebuilds
        if not self._rebuild_lock.acquire(blocking=False):
            print("JSON rebuild already in progress, skipping...")
            return False
        
        try:
            self._rebuild_in_progress = True
            start_time = time.time()
            
            print("Starting gallery JSON rebuild...")
            
            # Get all records from database
            records = self._fetch_all_records()
            
            # Build JSON structure
            json_data = self._build_json_structure(records)
            
            # Write to file
            success = self._write_json_file(json_data)
            
            if success:
                duration = time.time() - start_time
                print(f"Gallery JSON rebuild completed in {duration:.2f}s - {len(records)} records")
            else:
                print("Gallery JSON rebuild failed")
                
            return success
            
        except Exception as e:
            print(f"Gallery JSON rebuild error: {e}")
            return False
        finally:
            self._rebuild_in_progress = False
            self._rebuild_lock.release()
    
    def _fetch_all_records(self):
        """Fetch all records efficiently with a single query"""
        conn = self.db_manager._get_connection()
        
        # Single optimized query for all needed fields
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
        """Build the complete JSON structure"""
        return {
            "meta": {
                "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "total_records": len(records),
                "format_version": "2.0"
            },
            "records": records
        }
    
    def _write_json_file(self, json_data):
        """Write JSON data to file with atomic safety"""
        try:
            # Ensure web directory exists
            self.web_base_path.mkdir(parents=True, exist_ok=True)
            
            # Write to temporary file first
            with open(self.temp_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            
            # Backup existing file if it exists
            if self.json_path.exists():
                if self.backup_path.exists():
                    self.backup_path.unlink()  # Remove old backup
                self.json_path.rename(self.backup_path)
            
            # Atomic rename from temp to final
            self.temp_path.rename(self.json_path)
            
            return True
            
        except Exception as e:
            print(f"Error writing JSON file: {e}")
            
            # Restore from backup if current write failed
            self._restore_from_backup()
            return False
    
    def _restore_from_backup(self):
        """Restore from backup if available"""
        try:
            if self.backup_path.exists() and not self.json_path.exists():
                self.backup_path.rename(self.json_path)
                print("Restored gallery JSON from backup")
        except Exception as e:
            print(f"Error restoring from backup: {e}")
    
    def get_rebuild_status(self):
        """Get current rebuild status"""
        return {
            "in_progress": self._rebuild_in_progress,
            "last_rebuild_time": self._last_rebuild_time
        }