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
        """Initialize SQLite database with required tables"""
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
                discogs_have INTEGER DEFAULT 0,
                discogs_want INTEGER DEFAULT 0,
                genre TEXT,
                image_url TEXT,
                year TEXT,
                barcode TEXT,
                catalog_number TEXT,
                format TEXT,
                condition TEXT,
                store_price REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
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
                artist_name TEXT NOT NULL,
                genre_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (genre_id) REFERENCES genres (id),
                UNIQUE(artist_name, genre_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
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
             genre, image_url, catalog_number, format, barcode, condition, year, discogs_have, discogs_want)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            result_data.get('artist', result_data.get('discogs_artist', '')),
            result_data.get('title', result_data.get('discogs_title', '')),
            result_data.get('median_price'),
            result_data.get('lowest_price'),
            result_data.get('highest_price'),
            result_data.get('genre', ''),
            result_data.get('image_url', ''),
            result_data.get('catalog_number', ''),
            result_data.get('format', ''),
            result_data.get('barcode', ''),
            result_data.get('condition', ''),
            result_data.get('year', ''),
            result_data.get('discogs_have', 0),
            result_data.get('discogs_want', 0)
        ))
        
        conn.commit()
        conn.close()
        return cursor.lastrowid
    
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
        """Get all records from database"""
        conn = self._get_connection()
        df = pd.read_sql('SELECT * FROM records ORDER BY created_at DESC', conn)
        conn.close()
        return df
    
    def get_all_failed_searches(self):
        """Get all failed searches from database"""
        conn = self._get_connection()
        df = pd.read_sql('SELECT * FROM failed_searches ORDER BY created_at DESC', conn)
        conn.close()
        return df
    
    def get_recent_records(self, limit=100):
        """Get recent records"""
        conn = self._get_connection()
        df = pd.read_sql(f'SELECT * FROM records ORDER BY created_at DESC LIMIT {limit}', conn)
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
            'records_count': int(records_count),  # Ensure it's an integer
            'failed_count': int(failed_count),    # Ensure it's an integer
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
            # Genre already exists
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
            # First remove all artist associations
            cursor.execute('DELETE FROM genre_by_artist WHERE genre_id = ?', (genre_id,))
            # Then delete the genre
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
        
        # First check if genre_by_artist table exists and has data
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='genre_by_artist'")
        genre_table_exists = cursor.fetchone() is not None
        
        if not genre_table_exists:
            # Return empty dataframe if genre tables don't exist
            df = pd.DataFrame(columns=['genre_name', 'record_count', 'artist_count'])
        else:
            # Use the correct query with proper column names
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
        conn.commit()
        conn.close()
    
    def search_records(self, search_term):
        """Search for records by search term"""
        conn = self._get_connection()
        df = pd.read_sql(
            'SELECT * FROM records WHERE artist LIKE ? OR title LIKE ? ORDER BY created_at DESC',
            conn,
            params=(f'%{search_term}%', f'%{search_term}%')
        )
        conn.close()
        return df