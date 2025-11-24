import sqlite3
import pandas as pd
import os
from datetime import datetime

class DatabaseManager:
    """Handles all database operations for Discogs data"""
    
    def __init__(self, db_path=None, gallery_json_manager=None):
        # Use provided path or get from config
        if db_path is None:
            from config import AppConfig
            config = AppConfig()
            db_path = config.get_database_path()
        
        self.db_path = db_path
        self.gallery_json_manager = gallery_json_manager
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with required tables and triggers"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Records table - with consignment columns
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artist TEXT NOT NULL,
                title TEXT NOT NULL,
                barcode TEXT,
                genre_id INTEGER,
                file_at TEXT,
                image_url TEXT,
                discogs_suggested_price REAL,
                catalog_number TEXT,
                format TEXT,
                condition TEXT,
                store_price REAL,
                ebay_sell_at REAL,
                youtube_url TEXT,
                date_added DATE,
                date_sold DATE,
                date_returned DATE,
                date_picked_up DATE,
                date_paid DATE,
                consignment_session_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (genre_id) REFERENCES genres (id),
                FOREIGN KEY (consignment_session_id) REFERENCES consignment_sessions (id)
            )
        ''')
        
        # Consignors table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS consignors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                address TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Consignment sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS consignment_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consignor_id INTEGER NOT NULL,
                session_date DATE DEFAULT CURRENT_DATE,
                commission_rate REAL NOT NULL,
                store_return_days INTEGER NOT NULL,
                session_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (consignor_id) REFERENCES consignors (id)
            )
        ''')
        
        # Add columns if they don't exist (without DEFAULT for date_added)
        columns_to_add = [
            ('store_price', 'REAL'),
            ('genre_id', 'INTEGER'),
            ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
            ('youtube_url', 'TEXT'),
            ('ebay_sell_at', 'REAL'),
            ('discogs_suggested_price', 'REAL'),
            ('date_added', 'DATE'),
            ('date_sold', 'DATE'),
            ('date_returned', 'DATE'),
            ('date_picked_up', 'DATE'),
            ('date_paid', 'DATE'),
            ('consignment_session_id', 'INTEGER')
        ]
        
        for column_name, column_type in columns_to_add:
            try:
                cursor.execute(f"ALTER TABLE records ADD COLUMN {column_name} {column_type}")
            except sqlite3.OperationalError:
                pass
        
        # Set default date_added for existing records that don't have it
        cursor.execute('''
            UPDATE records SET date_added = date(created_at) 
            WHERE date_added IS NULL
        ''')
        
        # Genre domain table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS genres (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                genre_name TEXT UNIQUE NOT NULL,
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
        
        # Voter tracking table for streaming votes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS voter_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id INTEGER NOT NULL,
                voter_hash TEXT NOT NULL,
                vote_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(record_id, voter_hash),
                FOREIGN KEY (record_id) REFERENCES records (id)
            )
        ''')
        
        # Create triggers
        self._create_triggers(cursor, conn)
        
        # Insert default configuration
        default_configs = [
            ('SHIPPING_COST', '5.72'),
            ('MIN_STORE_PRICE', '1.99'),
            ('STORE_PRICE_LOWEST_MULTIPLIER', '1.1'),
            ('STORE_PRICE_ESTIMATED_MULTIPLIER', '0.9'),
            ('STORE_PRICE_MINIMUM', '4.99'),
            ('DEFAULT_COMMISSION_RATE', '0.50'),
            ('DEFAULT_STORE_RETURN_DAYS', '90'),
            ('CUSTOMER_RETURN_DAYS', '30'),
            ('CONSIGNOR_PICKUP_DAYS', '30')
        ]
        
        for config_key, config_value in default_configs:
            cursor.execute('''
                INSERT OR IGNORE INTO app_config (config_key, config_value)
                VALUES (?, ?)
            ''', (config_key, config_value))
        
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
    
    def _get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def save_record(self, result_data):
        """Save record to database using correct column names"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Set date_added to current date if not provided
        date_added = result_data.get('date_added')
        if date_added is None:
            date_added = datetime.now().date()
        
        cursor.execute('''
            INSERT INTO records 
            (artist, title, barcode, genre_id, image_url,
             discogs_suggested_price,
             catalog_number, format, condition, file_at, store_price, ebay_sell_at, youtube_url,
             date_added, consignment_session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            result_data.get('artist', result_data.get('discogs_artist', '')),
            result_data.get('title', result_data.get('discogs_title', '')),
            result_data.get('barcode', ''),
            result_data.get('genre_id'),
            result_data.get('image_url', ''),
            result_data.get('discogs_suggested_price'),
            result_data.get('catalog_number', ''),
            result_data.get('format', ''),
            result_data.get('condition', ''),
            result_data.get('file_at', ''),
            result_data.get('store_price'),
            result_data.get('ebay_sell_at'),
            result_data.get('youtube_url'),
            date_added,
            result_data.get('consignment_session_id')
        ))
        
        conn.commit()
        record_id = cursor.lastrowid
        conn.close()
        return record_id
    
    # Vote management methods
    def record_vote(self, record_id, voter_hash, vote_type):
        """Record a vote for a record"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Use INSERT OR REPLACE to handle vote changes
            cursor.execute('''
                INSERT OR REPLACE INTO voter_tracking (record_id, voter_hash, vote_type)
                VALUES (?, ?, ?)
            ''', (record_id, voter_hash, vote_type))
            
            conn.commit()
            success = True
        except Exception as e:
            print(f"Error recording vote: {e}")
            success = False
        finally:
            conn.close()
            
        return success
    
    def get_vote_counts(self, record_id=None):
        """Get vote counts for all records or a specific record"""
        conn = self._get_connection()
        
        if record_id:
            # Get votes for specific record
            query = '''
                SELECT 
                    record_id,
                    SUM(CASE WHEN vote_type = 'upvote' THEN 1 ELSE 0 END) as upvotes,
                    SUM(CASE WHEN vote_type = 'downvote' THEN 1 ELSE 0 END) as downvotes
                FROM voter_tracking 
                WHERE record_id = ?
                GROUP BY record_id
            '''
            df = pd.read_sql(query, conn, params=(record_id,))
        else:
            # Get votes for all records
            query = '''
                SELECT 
                    record_id,
                    SUM(CASE WHEN vote_type = 'upvote' THEN 1 ELSE 0 END) as upvotes,
                    SUM(CASE WHEN vote_type = 'downvote' THEN 1 ELSE 0 END) as downvotes
                FROM voter_tracking 
                GROUP BY record_id
            '''
            df = pd.read_sql(query, conn)
        
        conn.close()
        
        # Convert to dictionary for easy access
        vote_counts = {}
        for _, row in df.iterrows():
            vote_counts[row['record_id']] = {
                'upvotes': int(row['upvotes']),
                'downvotes': int(row['downvotes'])
            }
            
        return vote_counts
    
    def get_user_vote(self, record_id, voter_hash):
        """Get a user's vote for a specific record"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT vote_type FROM voter_tracking 
            WHERE record_id = ? AND voter_hash = ?
        ''', (record_id, voter_hash))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    # Consignor management methods
    def get_all_consignors(self):
        """Get all consignors"""
        conn = self._get_connection()
        df = pd.read_sql('SELECT * FROM consignors ORDER BY name', conn)
        conn.close()
        return df
    
    def get_consignor_by_id(self, consignor_id):
        """Get consignor by ID"""
        conn = self._get_connection()
        df = pd.read_sql('SELECT * FROM consignors WHERE id = ?', conn, params=(consignor_id,))
        conn.close()
        return df.iloc[0] if len(df) > 0 else None
    
    def add_consignor(self, name, email=None, phone=None, address=None, notes=None):
        """Add a new consignor"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO consignors (name, email, phone, address, notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, email, phone, address, notes))
        
        conn.commit()
        consignor_id = cursor.lastrowid
        conn.close()
        return consignor_id
    
    def update_consignor(self, consignor_id, updates):
        """Update a consignor"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        set_clause = []
        values = []
        for field, value in updates.items():
            set_clause.append(f"{field} = ?")
            values.append(value)
        
        values.append(consignor_id)
        query = f"UPDATE consignors SET {', '.join(set_clause)} WHERE id = ?"
        cursor.execute(query, values)
        
        conn.commit()
        conn.close()
        return True
    
    # Consignment session management methods
    def get_all_consignment_sessions(self):
        """Get all consignment sessions with consignor info"""
        conn = self._get_connection()
        df = pd.read_sql('''
            SELECT cs.*, c.name as consignor_name
            FROM consignment_sessions cs
            JOIN consignors c ON cs.consignor_id = c.id
            ORDER BY cs.session_date DESC
        ''', conn)
        conn.close()
        return df
    
    def get_consignment_session_by_id(self, session_id):
        """Get consignment session by ID"""
        conn = self._get_connection()
        df = pd.read_sql('''
            SELECT cs.*, c.name as consignor_name
            FROM consignment_sessions cs
            JOIN consignors c ON cs.consignor_id = c.id
            WHERE cs.id = ?
        ''', conn, params=(session_id,))
        conn.close()
        return df.iloc[0] if len(df) > 0 else None
    
    def get_sessions_by_consignor(self, consignor_id):
        """Get all sessions for a consignor"""
        conn = self._get_connection()
        df = pd.read_sql('''
            SELECT cs.*, c.name as consignor_name
            FROM consignment_sessions cs
            JOIN consignors c ON cs.consignor_id = c.id
            WHERE cs.consignor_id = ?
            ORDER BY cs.session_date DESC
        ''', conn, params=(consignor_id,))
        conn.close()
        return df
    
    def add_consignment_session(self, consignor_id, session_date=None, commission_rate=None, store_return_days=None, session_notes=None):
        """Add a new consignment session"""
        if session_date is None:
            session_date = datetime.now().date()
        
        if commission_rate is None:
            commission_rate = float(self.get_config_value('DEFAULT_COMMISSION_RATE', '0.50'))
        
        if store_return_days is None:
            store_return_days = int(self.get_config_value('DEFAULT_STORE_RETURN_DAYS', '90'))
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO consignment_sessions (consignor_id, session_date, commission_rate, store_return_days, session_notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (consignor_id, session_date, commission_rate, store_return_days, session_notes))
        
        conn.commit()
        session_id = cursor.lastrowid
        conn.close()
        return session_id
    
    # Consignment record queries
    def get_consignment_records_ready_for_payment(self, consignor_id=None):
        """Get consignment records ready for payment (passed customer return period)"""
        customer_return_days = int(self.get_config_value('CUSTOMER_RETURN_DAYS', '30'))
        
        query = '''
            SELECT r.*, cs.commission_rate, c.name as consignor_name
            FROM records r
            JOIN consignment_sessions cs ON r.consignment_session_id = cs.id
            JOIN consignors c ON cs.consignor_id = c.id
            WHERE r.date_sold IS NOT NULL
            AND r.date_paid IS NULL
            AND r.date_sold < date('now', '-' || ? || ' days')
        '''
        
        params = [customer_return_days]
        
        if consignor_id:
            query += ' AND cs.consignor_id = ?'
            params.append(consignor_id)
        
        query += ' ORDER BY r.date_sold'
        
        conn = self._get_connection()
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        return df
    
    def get_consignment_records_ready_for_pickup(self, consignor_id=None):
        """Get consignment records ready for pickup (past store return deadline)"""
        query = '''
            SELECT r.*, cs.store_return_days, c.name as consignor_name
            FROM records r
            JOIN consignment_sessions cs ON r.consignment_session_id = cs.id
            JOIN consignors c ON cs.consignor_id = c.id
            WHERE r.date_sold IS NULL
            AND r.date_returned IS NOT NULL
            AND r.date_picked_up IS NULL
        '''
        
        params = []
        
        if consignor_id:
            query += ' AND cs.consignor_id = ?'
            params.append(consignor_id)
        
        query += ' ORDER BY r.date_returned'
        
        conn = self._get_connection()
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        return df
    
    def get_overdue_pickups(self):
        """Get consignment records that are overdue for pickup"""
        consignor_pickup_days = int(self.get_config_value('CONSIGNOR_PICKUP_DAYS', '30'))
        
        conn = self._get_connection()
        df = pd.read_sql('''
            SELECT r.*, cs.store_return_days, c.name as consignor_name
            FROM records r
            JOIN consignment_sessions cs ON r.consignment_session_id = cs.id
            JOIN consignors c ON cs.consignor_id = c.id
            WHERE r.date_sold IS NULL
            AND r.date_returned IS NOT NULL
            AND r.date_picked_up IS NULL
            AND r.date_returned < date('now', '-' || ? || ' days')
            ORDER BY r.date_returned
        ''', conn, params=(consignor_pickup_days,))
        conn.close()
        return df
    
    def mark_records_for_return(self):
        """Mark consignment records as ready for pickup when past store return deadline"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE records 
            SET date_returned = CURRENT_DATE
            WHERE consignment_session_id IS NOT NULL
            AND date_sold IS NULL
            AND date_returned IS NULL
            AND date_added < (
                SELECT date('now', '-' || cs.store_return_days || ' days')
                FROM consignment_sessions cs
                WHERE cs.id = records.consignment_session_id
            )
        ''')
        
        updated_count = cursor.rowcount
        conn.commit()
        conn.close()
        return updated_count
    
    def mark_abandoned_records_as_store_owned(self):
        """Mark abandoned consignment records as store property"""
        consignor_pickup_days = int(self.get_config_value('CONSIGNOR_PICKUP_DAYS', '30'))
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE records 
            SET consignment_session_id = NULL,
                date_returned = NULL,
                date_picked_up = CURRENT_DATE
            WHERE date_sold IS NULL
            AND date_returned IS NOT NULL
            AND date_picked_up IS NULL
            AND date_returned < date('now', '-' || ? || ' days')
        ''', (consignor_pickup_days,))
        
        updated_count = cursor.rowcount
        conn.commit()
        conn.close()
        return updated_count
    
    def get_record_by_id(self, record_id):
        """Get a record by ID"""
        conn = self._get_connection()
        df = pd.read_sql('''
            SELECT r.*, g.genre_name as genre
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            WHERE r.id = ?
        ''', conn, params=(record_id,))
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
        
        # Trigger JSON rebuild after successful deletion
        if success and self.gallery_json_manager:
            self.gallery_json_manager.trigger_rebuild(async_mode=True)
            
        return success
    
    def get_all_records(self):
        """Get all records from database"""
        conn = self._get_connection()
        df = pd.read_sql('''
            SELECT r.*, g.genre_name as genre
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            ORDER BY r.created_at DESC
        ''', conn)
        conn.close()
        return df
    
    def get_recent_records(self, limit=100):
        """Get recent records"""
        conn = self._get_connection()
        df = pd.read_sql(f'''
            SELECT r.*, g.genre_name as genre
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            ORDER BY r.created_at DESC LIMIT {limit}
        ''', conn)
        conn.close()
        return df
    
    def get_database_stats(self):
        """Get database statistics"""
        conn = self._get_connection()
        
        # Use COALESCE to handle NULL values and ensure we get 0 instead of None
        records_count = pd.read_sql('SELECT COALESCE(COUNT(*), 0) as count FROM records', conn).iloc[0]['count']
        consignors_count = pd.read_sql('SELECT COALESCE(COUNT(*), 0) as count FROM consignors', conn).iloc[0]['count']
        sessions_count = pd.read_sql('SELECT COALESCE(COUNT(*), 0) as count FROM consignment_sessions', conn).iloc[0]['count']
        
        # For latest timestamps, handle case where tables are empty
        latest_record_df = pd.read_sql('SELECT MAX(created_at) as latest FROM records', conn)
        latest_record = latest_record_df.iloc[0]['latest'] if not latest_record_df.empty and latest_record_df.iloc[0]['latest'] is not None else "None"
        
        conn.close()
        
        return {
            'records_count': int(records_count),
            'consignors_count': int(consignors_count),
            'sessions_count': int(sessions_count),
            'latest_record': latest_record,
            'db_path': self.db_path
        }
    
    # Genre management methods
    def get_all_genres(self):
        """Get all available genres"""
        conn = self._get_connection()
        df = pd.read_sql('SELECT * FROM genres ORDER BY genre_name', conn)
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
                LEFT JOIN genres g ON r.genre_id = g.id
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
                LEFT JOIN genres g ON r.genre_id = g.id
                ORDER BY r.artist
            '''
            df = pd.read_sql(query, conn)
        
        conn.close()
        return df
    
    def get_artists_without_genres(self):
        """Get artists that don't have genres assigned yet"""
        conn = self._get_connection()
        df = pd.read_sql('''
            SELECT DISTINCT artist as artist_name
            FROM records 
            WHERE genre_id IS NULL
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
        """Delete a genre"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM genres WHERE id = ?', (genre_id,))
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
            SELECT g.genre_name, r.genre_id
            FROM records r
            JOIN genres g ON r.genre_id = g.id
            WHERE r.artist = ?
            GROUP BY r.genre_id
            ORDER BY COUNT(*) DESC
            LIMIT 1
        ''', conn, params=(artist_name,))
        conn.close()
        return df.iloc[0] if len(df) > 0 else None
    
    def get_genre_statistics(self):
        """Get statistics about genres and records"""
        conn = self._get_connection()
        
        df = pd.read_sql('''
            SELECT 
                g.genre_name,
                COUNT(r.id) as record_count
            FROM genres g
            LEFT JOIN records r ON g.id = r.genre_id
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
        cursor.execute('DELETE FROM genres')
        cursor.execute('DELETE FROM consignment_sessions')
        cursor.execute('DELETE FROM consignors')
        conn.commit()
        conn.close()
    
    def search_records(self, search_term):
        """Search for records by search term"""
        conn = self._get_connection()
        df = pd.read_sql(
            'SELECT r.*, g.genre_name as genre FROM records r LEFT JOIN genres g ON r.genre_id = g.id WHERE r.artist LIKE ? OR r.title LIKE ? ORDER BY r.created_at DESC',
            conn,
            params=(f'%{search_term}%', f'%{search_term}%')
        )
        conn.close()
        return df
    
    def get_record_by_barcode(self, barcode):
        """Get a record by barcode"""
        conn = self._get_connection()
        df = pd.read_sql(
            'SELECT r.*, g.genre_name as genre FROM records r LEFT JOIN genres g ON r.genre_id = g.id WHERE r.barcode = ?',
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