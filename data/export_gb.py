#!/usr/bin/env python3
"""
Extract receipts from SQLite 'expenses' table:
- Saves each receipt BLOB to an image file (JPG, PNG, or PDF)
- Creates a new table 'expense_receipts' with:
  description, amount, created_at, file_path
- Adds the readable date (MM-DD) to the filename
"""

import sqlite3
import os
import re
from datetime import datetime

# === CONFIGURATION ===
DB_FILE = "records.db"          # your SQLite database file
OUTPUT_DIR = "receipts"         # folder to store extracted files
NEW_TABLE = "expense_receipts"

# === HELPER FUNCTIONS ===

def detect_file_extension(blob):
    """Detect file type from first bytes of BLOB."""
    if blob.startswith(b'\xFF\xD8'):
        return "jpg"
    elif blob.startswith(b'\x89PNG'):
        return "png"
    elif blob.startswith(b'%PDF'):
        return "pdf"
    else:
        return "bin"

def sanitize_filename(text):
    """Make filename safe for filesystem."""
    return re.sub(r'[^A-Za-z0-9 _-]', '_', text).strip()

def format_date_for_filename(date_str):
    """Extract and format date as MM-DD for filename."""
    if not date_str:
        return "unknown"
    try:
        # Try multiple date formats
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(date_str[:10], fmt)
                return dt.strftime("%m-%d")
            except ValueError:
                continue
        # If parsing fails, fallback to substring of numbers
        m = re.search(r'(\d{4})[-/](\d{2})[-/](\d{2})', date_str)
        if m:
            return f"{m.group(2)}-{m.group(3)}"
    except Exception:
        pass
    return "unknown"

# === MAIN ===
def extract_receipts():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # Read expenses table
    cur.execute("SELECT rowid, description, amount, receipt_image, created_at FROM expenses")
    rows = cur.fetchall()

    # Create new table if not exists
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {NEW_TABLE} (
            id INTEGER PRIMARY KEY,
            description TEXT,
            amount REAL,
            created_at TEXT,
            file_path TEXT
        )
    """)
    conn.commit()

    for rowid, description, amount, receipt_blob, created_at in rows:
        if not receipt_blob:
            continue

        ext = detect_file_extension(receipt_blob)
        safe_desc = sanitize_filename(description)[:30]
        safe_date = format_date_for_filename(created_at)
        filename = f"{rowid}_{safe_desc}_{safe_date}.{ext}"
        filepath = os.path.join(OUTPUT_DIR, filename)

        # Write file
        with open(filepath, "wb") as f:
            f.write(receipt_blob)

        # Insert record into new table
        cur.execute(f"""
            INSERT INTO {NEW_TABLE} (description, amount, created_at, file_path)
            VALUES (?, ?, ?, ?)
        """, (description, amount, created_at, filepath))

        print(f"Saved {filepath}")

    conn.commit()
    conn.close()

    print("\n✅ Extraction complete.")
    print(f"Receipts saved to: {os.path.abspath(OUTPUT_DIR)}")
    print(f"Linked records saved in table: {NEW_TABLE}")

if __name__ == "__main__":
    extract_receipts()
