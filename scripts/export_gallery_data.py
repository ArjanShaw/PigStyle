#!/usr/bin/env python3
"""
Export database records to JSON for the web gallery
"""
import sys
import os
import json
import sqlite3
from pathlib import Path

def export_gallery_data():
    """Export all records to JSON format for the web gallery"""
    
    # Database paths to try
    db_paths = [
        "data/records.db"
    ]
    
    # Find the first existing database
    db_path = None
    for path in db_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("❌ No database file found")
        return False
    
    print(f"📁 Using database: {db_path}")
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if records_with_genres view exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='records_with_genres'")
        view_exists = cursor.fetchone()
        
        if view_exists:
            # Use the view that includes genre names
            print("✅ Using records_with_genres view")
            cursor.execute("""
                SELECT artist, title, genre, store_price, image_url, youtube_url 
                FROM records_with_genres 
                ORDER BY artist, title
            """)
        else:
            # Fallback to basic records table (without genre)
            print("⚠️  Using records table (no genre available)")
            cursor.execute("""
                SELECT artist, title, NULL as genre, store_price, image_url, youtube_url 
                FROM records 
                ORDER BY artist, title
            """)
        
        records = cursor.fetchall()
        print(f"📊 Found {len(records)} records")
        
        # Convert to gallery format - only essential fields
        gallery_data = []
        for record in records:
            artist, title, genre, store_price, image_url, youtube_url = record
            
            # Format price
            if store_price and store_price > 0:
                price_display = f"${store_price:.2f}"
            else:
                price_display = "Price TBD"
            
            gallery_data.append({
                'artist': artist or 'Unknown Artist',
                'title': title or 'Unknown Title', 
                'genre': genre or 'Unknown Genre',
                'price': price_display,
                'image': image_url or 'images/default-record.jpg',
                'youtube_url': youtube_url or ''  # Include YouTube URL
            })
        
        # Create web/public directory if it doesn't exist
        web_public_dir = Path("web/public")
        web_public_dir.mkdir(parents=True, exist_ok=True)
        
        # Write JSON file
        output_file = web_public_dir / "gallery-data.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(gallery_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Exported {len(gallery_data)} records to {output_file}")
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error exporting data: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    export_gallery_data()