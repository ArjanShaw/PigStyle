import sqlite3
import pandas as pd
import os
from datetime import datetime

class DatabaseManager:
    """Handles all database operations for Discogs data"""
    
    def __init__(self, db_path=None):
        self.db_path = db_path or os.getenv('DATABASE_PATH', 'discogs_data.db')
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with required tables and triggers"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Records table - using the actual column names from your schema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artist TEXT NOT NULL,
                title TEXT NOT NULL,
                discogs_median_price REAL,
                discogs_lowest_price REAL,
                discogs_highest_price REAL,
                ebay_median_price REAL,
                ebay_lowest_price REAL,
                ebay_highest_price REAL,
                ebay_count INTEGER,
                ebay_sell_at REAL,
                ebay_low_shipping REAL,
                ebay_low_url TEXT,
                genre_id INTEGER NOT NULL,
                image_url TEXT,
                year TEXT,
                barcode TEXT,
                catalog_number TEXT,
                format TEXT,
                condition TEXT,
                store_price REAL,
                file_at TEXT,
                status TEXT DEFAULT 'inventory',
                price_tag_printed BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                discogs_genre TEXT,
                FOREIGN KEY (genre_id) REFERENCES genres (id)
            )
        ''')
        
        # Add columns if they don't exist
        columns_to_add = [
            ('ebay_count', 'INTEGER'),
            ('ebay_sell_at', 'REAL'),
            ('ebay_low_shipping', 'REAL'),
            ('ebay_low_url', 'TEXT'),
            ('store_price', 'REAL'),
            ('genre_id', 'INTEGER NOT NULL'),
            ('status', 'TEXT DEFAULT "inventory"'),
            ('price_tag_printed', 'BOOLEAN DEFAULT 0'),
            ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
            ('discogs_genre', 'TEXT')
        ]
        
        for column_name, column_type in columns_to_add:
            try:
                cursor.execute(f"ALTER TABLE records ADD COLUMN {column_name} {column_type}")
            except sqlite3.OperationalError:
                pass
        
        # Remove price column if it exists
        try:
            cursor.execute("ALTER TABLE records DROP COLUMN price")
        except sqlite3.OperationalError:
            pass
        
        # Failed searches table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS failed_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_term TEXT NOT NULL,
                error_details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Genre domain table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS genres (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                genre_name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Genre by artist cross-reference table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS genre_by_artist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artist_name TEXT UNIQUE NOT NULL,
                genre_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (genre_id) REFERENCES genres (id)
            )
        ''')
        
        # Expenses table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                receipt_image BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Configuration table for settings like eBay cutoff price
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS app_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key TEXT UNIQUE NOT NULL,
                config_value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create view for records with genre names
        cursor.execute('''
            CREATE VIEW IF NOT EXISTS records_with_genres AS
            SELECT 
                r.*,
                g.genre_name as genre
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
        ''')
        
        # Create triggers
        self._create_triggers(cursor, conn)
        
        # Insert default SHIPPING_COST configuration
        cursor.execute('''
            INSERT OR IGNORE INTO app_config (config_key, config_value)
            VALUES ('SHIPPING_COST', '5.72')
        ''')
        
        # Insert default MIN_STORE_PRICE configuration
        cursor.execute('''
            INSERT OR IGNORE INTO app_config (config_key, config_value)
            VALUES ('MIN_STORE_PRICE', '1.99')
        ''')
        
        conn.commit()
        conn.close()
    
    def _create_triggers(self, cursor, conn):
        """Create all database triggers"""
        # Trigger for file_at when artist or genre_id changes
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS update_file_at
            AFTER UPDATE OF artist, genre_id ON records
            FOR EACH ROW
            WHEN (NEW.artist IS NOT NULL AND NEW.genre_id IS NOT NULL)
            BEGIN
                UPDATE records 
                SET file_at = (
                    SELECT COALESCE(g.genre_name, 'Unknown') || '(' || 
                        CASE 
                            WHEN UPPER(SUBSTR(REPLACE(NEW.artist, 'The ', ''), 1, 1)) BETWEEN '0' AND '9' THEN
                                CASE SUBSTR(REPLACE(NEW.artist, 'The ', ''), 1, 1)
                                    WHEN '0' THEN 'Z' WHEN '1' THEN 'O' WHEN '2' THEN 'T' 
                                    WHEN '3' THEN 'T' WHEN '4' THEN 'F' WHEN '5' THEN 'F' 
                                    WHEN '6' THEN 'S' WHEN '7' THEN 'S' WHEN '8' THEN 'E' 
                                    WHEN '9' THEN 'N' ELSE '?' END
                            WHEN UPPER(SUBSTR(REPLACE(NEW.artist, 'The ', ''), 1, 1)) BETWEEN 'A' AND 'Z' THEN
                                UPPER(SUBSTR(REPLACE(NEW.artist, 'The ', ''), 1, 1))
                            ELSE '?'
                        END || ')'
                    FROM genres g WHERE g.id = NEW.genre_id
                )
                WHERE id = NEW.id;
            END
        ''')
        
        # Trigger for file_at when new record is inserted
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS update_file_at_on_insert
            AFTER INSERT ON records
            FOR EACH ROW
            WHEN (NEW.artist IS NOT NULL AND NEW.genre_id IS NOT NULL)
            BEGIN
                UPDATE records 
                SET file_at = (
                    SELECT COALESCE(g.genre_name, 'Unknown') || '(' || 
                        CASE 
                            WHEN UPPER(SUBSTR(REPLACE(NEW.artist, 'The ', ''), 1, 1)) BETWEEN '0' AND '9' THEN
                                CASE SUBSTR(REPLACE(NEW.artist, 'The ', ''), 1, 1)
                                    WHEN '0' THEN 'Z' WHEN '1' THEN 'O' WHEN '2' THEN 'T' 
                                    WHEN '3' THEN 'T' WHEN '4' THEN 'F' WHEN '5' THEN 'F' 
                                    WHEN '6' THEN 'S' WHEN '7' THEN 'S' WHEN '8' THEN 'E' 
                                    WHEN '9' THEN 'N' ELSE '?' END
                            WHEN UPPER(SUBSTR(REPLACE(NEW.artist, 'The ', ''), 1, 1)) BETWEEN 'A' AND 'Z' THEN
                                UPPER(SUBSTR(REPLACE(NEW.artist, 'The ', ''), 1, 1))
                            ELSE '?'
                        END || ')'
                    FROM genres g WHERE g.id = NEW.genre_id
                )
                WHERE id = NEW.id;
            END
        ''')
        
        # Trigger for barcode generation when new record is inserted
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS generate_barcode_on_insert
            AFTER INSERT ON records
            FOR EACH ROW
            WHEN (NEW.barcode IS NULL OR NEW.barcode = '')
            BEGIN
                UPDATE records 
                SET barcode = (
                    SELECT COALESCE(MAX(CAST(barcode AS INTEGER)), 100000) + 1 
                    FROM records 
                    WHERE barcode GLOB '[0-9]*'
                )
                WHERE id = NEW.id;
            END
        ''')
        
        # Remove store_price triggers since we don't calculate automatically anymore
        try:
            cursor.execute('DROP TRIGGER IF EXISTS calculate_store_price')
            cursor.execute('DROP TRIGGER IF EXISTS calculate_store_price_on_insert')
        except:
            pass
    
    def _get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def save_record(self, result_data):
        """Save record to database using correct column names"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO records 
            (artist, title, discogs_median_price, discogs_lowest_price, discogs_highest_price,
             ebay_median_price, ebay_lowest_price, ebay_highest_price, ebay_count, ebay_sell_at, ebay_low_shipping, ebay_low_url,
             genre_id, image_url, catalog_number, format, barcode, condition, year, file_at, status, price_tag_printed, store_price, discogs_genre)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            result_data.get('artist', result_data.get('discogs_artist', '')),
            result_data.get('title', result_data.get('discogs_title', '')),
            result_data.get('discogs_median_price'),
            result_data.get('discogs_lowest_price'),
            result_data.get('discogs_highest_price'),
            result_data.get('ebay_median_price'),
            result_data.get('ebay_lowest_price'),
            result_data.get('ebay_highest_price'),
            result_data.get('ebay_count'),
            result_data.get('ebay_sell_at'),
            result_data.get('ebay_low_shipping'),
            result_data.get('ebay_low_url', ''),
            result_data.get('genre_id'),
            result_data.get('image_url', ''),
            result_data.get('catalog_number', ''),
            result_data.get('format', ''),
            result_data.get('barcode', ''),
            result_data.get('condition', ''),
            result_data.get('year', ''),
            result_data.get('file_at', ''),
            result_data.get('status', 'inventory'),
            0,  # price_tag_printed starts as False
            result_data.get('store_price'),
            result_data.get('discogs_genre')
        ))
        
        conn.commit()
        record_id = cursor.lastrowid
        conn.close()
        return record_id
    
    def get_record_by_id(self, record_id):
        """Get a record by ID using the view"""
        conn = self._get_connection()
        df = pd.read_sql(
            'SELECT * FROM records_with_genres WHERE id = ?',
            conn,
            params=(record_id,)
        )
        conn.close()
        return df.iloc[0] if len(df) > 0 else None
    
    def update_record(self, record_id, updates):
        """Update a record"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Build update query
        set_clause = []
        values = []
        for field, value in updates.items():
            set_clause.append(f"{field} = ?")
            values.append(value)
        
        # Add updated_at timestamp
        set_clause.append("updated_at = CURRENT_TIMESTAMP")
        
        values.append(record_id)
        
        query = f"UPDATE records SET {', '.join(set_clause)} WHERE id = ?"
        cursor.execute(query, values)
        
        conn.commit()
        conn.close()
        return True
    
    def delete_record(self, record_id):
        """Delete a record from the database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM records WHERE id = ?', (record_id,))
        
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    
    def mark_price_tags_printed(self, record_ids):
        """Mark price tags as printed for given record IDs"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        placeholders = ','.join(['?'] * len(record_ids))
        cursor.execute(f'UPDATE records SET price_tag_printed = 1 WHERE id IN ({placeholders})', record_ids)
        
        conn.commit()
        conn.close()
        return True
    
    def save_expense(self, description, amount, receipt_image=None):
        """Save expense to database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO expenses (description, amount, receipt_image)
            VALUES (?, ?, ?)
        ''', (description, amount, receipt_image))
        
        conn.commit()
        expense_id = cursor.lastrowid
        conn.close()
        return expense_id
    
    def get_all_expenses(self):
        """Get all expenses from database"""
        conn = self._get_connection()
        df = pd.read_sql('SELECT * FROM expenses ORDER BY created_at DESC', conn)
        conn.close()
        return df
    
    def save_failed_search(self, search_term, error_details):
        """Save failed search to database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO failed_searches (search_term, error_details)
            VALUES (?, ?)
        ''', (search_term, error_details))
        
        conn.commit()
        conn.close()
        return cursor.lastrowid
    
    def get_all_records(self):
        """Get all records from database using the view"""
        conn = self._get_connection()
        df = pd.read_sql('SELECT * FROM records_with_genres ORDER BY created_at DESC', conn)
        conn.close()
        return df
    
    def get_all_failed_searches(self):
        """Get all failed searches from database"""
        conn = self._get_connection()
        df = pd.read_sql('SELECT * FROM failed_searches ORDER BY created_at DESC', conn)
        conn.close()
        return df
    
    def get_recent_records(self, limit=100):
        """Get recent records using the view"""
        conn = self._get_connection()
        df = pd.read_sql(f'SELECT * FROM records_with_genres ORDER BY created_at DESC LIMIT {limit}', conn)
        conn.close()
        return df
    
    def get_recent_failed_searches(self, limit=100):
        """Get recent failed searches"""
        conn = self._get_connection()
        df = pd.read_sql(f'SELECT * FROM failed_searches ORDER BY created_at DESC LIMIT {limit}', conn)
        conn.close()
        return df
    
    def get_database_stats(self):
        """Get database statistics"""
        conn = self._get_connection()
        
        # Use COALESCE to handle NULL values and ensure we get 0 instead of None
        records_count = pd.read_sql('SELECT COALESCE(COUNT(*), 0) as count FROM records', conn).iloc[0]['count']
        failed_count = pd.read_sql('SELECT COALESCE(COUNT(*), 0) as count FROM failed_searches', conn).iloc[0]['count']
        
        # For latest timestamps, handle case where tables are empty
        latest_record_df = pd.read_sql('SELECT MAX(created_at) as latest FROM records', conn)
        latest_record = latest_record_df.iloc[0]['latest'] if not latest_record_df.empty and latest_record_df.iloc[0]['latest'] is not None else "None"
        
        latest_failed_df = pd.read_sql('SELECT MAX(created_at) as latest FROM failed_searches', conn)
        latest_failed = latest_failed_df.iloc[0]['latest'] if not latest_failed_df.empty and latest_failed_df.iloc[0]['latest'] is not None else "None"
        
        conn.close()
        
        return {
            'records_count': int(records_count),
            'failed_count': int(failed_count),
            'latest_record': latest_record,
            'latest_failed': latest_failed,
            'db_path': self.db_path
        }
    
    # Genre management methods
    def get_all_genres(self):
        """Get all available genres"""
        conn = self._get_connection()
        df = pd.read_sql('SELECT * FROM genres ORDER BY genre_name', conn)
        conn.close()
        return df
    
    def get_artists_with_genres(self):
        """Get all artists with their assigned genres"""
        conn = self._get_connection()
        df = pd.read_sql('''
            SELECT 
                gba.artist_name,
                g.genre_name,
                gba.genre_id,
                gba.id as mapping_id
            FROM genre_by_artist gba
            JOIN genres g ON gba.genre_id = g.id
            ORDER BY gba.artist_name
        ''', conn)
        conn.close()
        return df
    
    def get_all_artists_with_genres(self, search_term=None):
        """Get all artists from records and their assigned genres (including unassigned)"""
        conn = self._get_connection()
        
        if search_term:
            query = '''
                SELECT DISTINCT 
                    r.artist as artist_name,
                    g.genre_name
                FROM records r
                LEFT JOIN genre_by_artist gba ON r.artist = gba.artist_name
                LEFT JOIN genres g ON gba.genre_id = g.id
                WHERE r.artist LIKE ?
                ORDER BY r.artist
            '''
            df = pd.read_sql(query, conn, params=(f'%{search_term}%',))
        else:
            query = '''
                SELECT DISTINCT 
                    r.artist as artist_name,
                    g.genre_name
                FROM records r
                LEFT JOIN genre_by_artist gba ON r.artist = gba.artist_name
                LEFT JOIN genres g ON gba.genre_id = g.id
                ORDER BY r.artist
            '''
            df = pd.read_sql(query, conn)
        
        conn.close()
        return df
    
    def search_artists_with_genres(self, search_term):
        """Search artists with genres by artist name"""
        conn = self._get_connection()
        df = pd.read_sql('''
            SELECT 
                gba.artist_name,
                g.genre_name,
                gba.genre_id,
                gba.id as mapping_id
            FROM genre_by_artist gba
            JOIN genres g ON gba.genre_id = g.id
            WHERE gba.artist_name LIKE ?
            ORDER BY gba.artist_name
        ''', conn, params=(f'%{search_term}%',))
        conn.close()
        return df
    
    def get_artists_without_genres(self):
        """Get artists that don't have genres assigned yet"""
        conn = self._get_connection()
        df = pd.read_sql('''
            SELECT DISTINCT artist as artist_name
            FROM records 
            WHERE artist NOT IN (SELECT artist_name FROM genre_by_artist)
            ORDER BY artist
        ''', conn)
        conn.close()
        return df
    
    def add_genre(self, genre_name):
        """Add a new genre"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('INSERT INTO genres (genre_name) VALUES (?)', (genre_name,))
            conn.commit()
            genre_id = cursor.lastrowid
            success = True
        except sqlite3.IntegrityError:
            genre_id = None
            success = False
        finally:
            conn.close()
            
        return success, genre_id
    
    def delete_genre(self, genre_id):
        """Delete a genre and remove all artist associations"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM genre_by_artist WHERE genre_id = ?', (genre_id,))
            cursor.execute('DELETE FROM genres WHERE id = ?', (genre_id,))
            conn.commit()
            success = True
        except Exception as e:
            success = False
        finally:
            conn.close()
            
        return success
    
    def assign_genre_to_artist(self, artist_name, genre_id):
        """Assign a genre to an artist"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO genre_by_artist (artist_name, genre_id)
                VALUES (?, ?)
            ''', (artist_name, genre_id))
            conn.commit()
            success = True
        except Exception as e:
            success = False
        finally:
            conn.close()
            
        return success
    
    def remove_genre_from_artist(self, artist_name, genre_id):
        """Remove a genre assignment from an artist"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                DELETE FROM genre_by_artist 
                WHERE artist_name = ? AND genre_id = ?
            ''', (artist_name, genre_id))
            conn.commit()
            success = True
        except Exception as e:
            success = False
        finally:
            conn.close()
            
        return success
    
    def remove_genre_from_artist_by_name(self, artist_name):
        """Remove all genre assignments from an artist by name"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                DELETE FROM genre_by_artist 
                WHERE artist_name = ?
            ''', (artist_name,))
            conn.commit()
            success = True
        except Exception as e:
            success = False
        finally:
            conn.close()
            
        return success
    
    def get_artist_genre(self, artist_name):
        """Get the genre assigned to an artist"""
        conn = self._get_connection()
        df = pd.read_sql('''
            SELECT g.genre_name, g.id as genre_id
            FROM genre_by_artist gba
            JOIN genres g ON gba.genre_id = g.id
            WHERE gba.artist_name = ?
        ''', conn, params=(artist_name,))
        conn.close()
        return df.iloc[0] if len(df) > 0 else None
    
    def get_genre_statistics(self):
        """Get statistics about genres and records"""
        conn = self._get_connection()
        
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='genre_by_artist'")
        genre_table_exists = cursor.fetchone() is not None
        
        if not genre_table_exists:
            df = pd.DataFrame(columns=['genre_name', 'record_count', 'artist_count'])
        else:
            df = pd.read_sql('''
                SELECT 
                    g.genre_name,
                    COUNT(r.id) as record_count,
                    COUNT(DISTINCT gba.artist_name) as artist_count
                FROM genres g
                LEFT JOIN genre_by_artist gba ON g.id = gba.genre_id
                LEFT JOIN records r ON gba.artist_name = r.artist
                GROUP BY g.id, g.genre_name
                ORDER BY record_count DESC
            ''', conn)
        
        conn.close()
        return df
    
    def clear_database(self):
        """Clear all data from database (use with caution!)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM records')
        cursor.execute('DELETE FROM failed_searches')
        cursor.execute('DELETE FROM genre_by_artist')
        cursor.execute('DELETE FROM genres')
        cursor.execute('DELETE FROM expenses')
        conn.commit()
        conn.close()
    
    def search_records(self, search_term):
        """Search for records by search term using the view"""
        conn = self._get_connection()
        df = pd.read_sql(
            'SELECT * FROM records_with_genres WHERE artist LIKE ? OR title LIKE ? ORDER BY created_at DESC',
            conn,
            params=(f'%{search_term}%', f'%{search_term}%')
        )
        conn.close()
        return df
    
    def get_record_by_barcode(self, barcode):
        """Get a record by barcode using the view"""
        conn = self._get_connection()
        df = pd.read_sql(
            'SELECT * FROM records_with_genres WHERE barcode = ?',
            conn,
            params=(barcode,)
        )
        conn.close()
        return df.iloc[0] if len(df) > 0 else None
    
    def update_file_at_for_all_records(self):
        """Update file_at column for all records with genre(file_at) format"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, artist, genre_id FROM records')
        records = cursor.fetchall()
        
        updated_count = 0
        for record in records:
            record_id = record[0]
            artist = record[1]
            genre_id = record[2]
            
            if genre_id:
                cursor.execute('SELECT genre_name FROM genres WHERE id = ?', (genre_id,))
                genre_result = cursor.fetchone()
                genre = genre_result[0] if genre_result else 'Unknown'
            else:
                genre = 'Unknown'
                
            file_at_letter = self._calculate_file_at(artist)
            file_at_value = f"{genre}({file_at_letter})"
            
            cursor.execute('UPDATE records SET file_at = ? WHERE id = ?', (file_at_value, record_id))
            updated_count += 1
        
        conn.commit()
        conn.close()
        return updated_count
    
    def _calculate_file_at(self, artist):
        """Calculate file_at value for an artist"""
        if not artist:
            return "?"
        
        artist_clean = artist.strip().lower()
        
        if artist_clean.startswith('the '):
            artist_clean = artist_clean[4:]
        
        if artist_clean and artist_clean[0].isdigit():
            number_words = {
                '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
                '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine'
            }
            first_char = artist_clean[0]
            return number_words.get(first_char, '?')[0].upper()
        
        if artist_clean and artist_clean[0].isalpha():
            return artist_clean[0].upper()
        
        return "?"

    # Configuration methods
    def get_config_value(self, config_key, default=None):
        """Get configuration value from app_config table"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT config_value FROM app_config WHERE config_key = ?', (config_key,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0]
        return default
    
    def set_config_value(self, config_key, config_value):
        """Set configuration value in app_config table"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO app_config (config_key, config_value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (config_key, config_value))
        
        conn.commit()
        conn.close()
        return True