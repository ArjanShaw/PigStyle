import sqlite3
import pandas as pd
import os
from datetime import datetime
import requests
import tempfile

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
        
        # Always download database from GitHub - never use local copy
        self._download_database_from_github()
        
        self._init_database()
    
    def _download_database_from_github(self):
        """Download database from GitHub - never use local copy"""
        github_db_url = "https://github.com/ArjanShaw/PigStyle/raw/main/data/records.db"
        
        try:
            print("Downloading database from GitHub...")
            response = requests.get(github_db_url, timeout=30)
            if response.status_code == 200:
                # Write to temporary file first
                with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as temp_file:
                    temp_file.write(response.content)
                    temp_path = temp_file.name
                
                # Replace local database
                if os.path.exists(self.db_path):
                    os.remove(self.db_path)
                os.rename(temp_path, self.db_path)
                print("✅ Database downloaded successfully from GitHub")
            else:
                raise Exception(f"Failed to download database: HTTP {response.status_code}")
        except Exception as e:
            # Remove any existing local database to ensure consistency
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
            raise Exception(f"Could not download database from GitHub: {e}")
    
    def _init_database(self):
        """Initialize SQLite database with required tables and triggers"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Records table - with consignment columns and compilation
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
                consignor_id INTEGER,
                commission_rate REAL,
                store_return_days INTEGER,
                compilation BOOLEAN DEFAULT FALSE,
                payment_requested DATE,
                pickup_confirmed DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (genre_id) REFERENCES genres (id),
                FOREIGN KEY (consignor_id) REFERENCES users (id)
            )
        ''')
        
        # Users table (replaces consignors table)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'consignor',
                full_name TEXT,
                phone TEXT,
                address TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                failed_attempts INTEGER DEFAULT 0,
                locked_until TIMESTAMP
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
            ('consignor_id', 'INTEGER'),
            ('commission_rate', 'REAL'),
            ('store_return_days', 'INTEGER'),
            ('compilation', 'BOOLEAN DEFAULT FALSE'),
            ('payment_requested', 'DATE'),
            ('pickup_confirmed', 'DATE')
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
            ('CONSIGNOR_PICKUP_DAYS', '30'),
            ('STORE_CAPACITY', '1000')
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
        # Trigger for file_at when artist, genre_id, or compilation changes
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS update_file_at
            AFTER UPDATE OF artist, genre_id, compilation ON records
            FOR EACH ROW
            WHEN (NEW.artist IS NOT NULL AND NEW.genre_id IS NOT NULL)
            BEGIN
                UPDATE records 
                SET file_at = (
                    SELECT 
                        CASE 
                            WHEN NEW.compilation = TRUE THEN
                                'Comp(' || 
                                CASE 
                                    WHEN UPPER(SUBSTR(g.genre_name, 1, 1)) BETWEEN 'A' AND 'Z' THEN
                                        UPPER(SUBSTR(g.genre_name, 1, 1))
                                    ELSE '?'
                                END || ')'
                            ELSE
                                g.genre_name || '(' || 
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
                        END
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
                    SELECT 
                        CASE 
                            WHEN NEW.compilation = TRUE THEN
                                'Comp(' || 
                                CASE 
                                    WHEN UPPER(SUBSTR(g.genre_name, 1, 1)) BETWEEN 'A' AND 'Z' THEN
                                        UPPER(SUBSTR(g.genre_name, 1, 1))
                                    ELSE '?'
                                END || ')'
                            ELSE
                                g.genre_name || '(' || 
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
                        END
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
             date_added, consignor_id, commission_rate, store_return_days, compilation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            result_data.get('consignor_id'),
            result_data.get('commission_rate'),
            result_data.get('store_return_days'),
            result_data.get('compilation', False)
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
    
    # User management methods (replacing consignor methods)
    def get_all_users(self):
        """Get all users"""
        conn = self._get_connection()
        df = pd.read_sql('SELECT * FROM users ORDER BY username', conn)
        conn.close()
        return df
    
    def get_user_by_id(self, user_id):
        """Get user by ID"""
        conn = self._get_connection()
        df = pd.read_sql('SELECT * FROM users WHERE id = ?', conn, params=(user_id,))
        conn.close()
        return df.iloc[0] if len(df) > 0 else None

    def get_consignor_by_user_id(self, user_id):
        """Get user by user ID (replaces get_consignor_by_user_id)"""
        conn = self._get_connection()
        df = pd.read_sql('SELECT * FROM users WHERE id = ?', conn, params=(user_id,))
        conn.close()
        return df.iloc[0] if len(df) > 0 else None
    
    def add_user(self, username, email, password_hash, role='consignor', full_name=None, phone=None, address=None):
        """Add a new user (replaces add_consignor)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, role, full_name, phone, address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (username, email, password_hash, role, full_name, phone, address))
        
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id
    
    def update_user(self, user_id, updates):
        """Update a user (replaces update_consignor)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        set_clause = []
        values = []
        for field, value in updates.items():
            set_clause.append(f"{field} = ?")
            values.append(value)
        
        values.append(user_id)
        query = f"UPDATE users SET {', '.join(set_clause)} WHERE id = ?"
        cursor.execute(query, values)
        
        conn.commit()
        conn.close()
        return True
    
    # Consignment record queries (updated to use users table)
    def get_consignment_records_ready_for_payment(self, user_id=None):
        """Get consignment records ready for payment (passed customer return period)"""
        customer_return_days = int(self.get_config_value('CUSTOMER_RETURN_DAYS', '30'))
        
        query = '''
            SELECT r.*, u.username as consignor_name, u.full_name, r.commission_rate
            FROM records r
            LEFT JOIN users u ON r.consignor_id = u.id
            WHERE r.date_sold IS NOT NULL
            AND r.date_paid IS NULL
            AND r.consignor_id IS NOT NULL
            AND r.date_sold < date('now', '-' || ? || ' days')
        '''
        
        params = [customer_return_days]
        
        if user_id:
            query += ' AND r.consignor_id = ?'
            params.append(user_id)
        
        query += ' ORDER BY r.date_sold'
        
        conn = self._get_connection()
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        return df

    def get_user_consignment_records_ready_for_payment(self, user_id):
        """Get consignment records ready for payment for a specific user"""
        customer_return_days = int(self.get_config_value('CUSTOMER_RETURN_DAYS', '30'))
        
        conn = self._get_connection()
        df = pd.read_sql('''
            SELECT r.*, u.username as consignor_name, u.full_name, r.commission_rate
            FROM records r
            LEFT JOIN users u ON r.consignor_id = u.id
            WHERE r.date_sold IS NOT NULL
            AND r.date_paid IS NULL
            AND r.consignor_id IS NOT NULL
            AND r.date_sold < date('now', '-' || ? || ' days')
            AND u.id = ?
            ORDER BY r.date_sold
        ''', conn, params=(customer_return_days, user_id))
        conn.close()
        return df
    
    def get_consignment_records_ready_for_pickup(self, user_id=None):
        """Get consignment records ready for pickup (past store return deadline)"""
        query = '''
            SELECT r.*, u.username as consignor_name, u.full_name, r.store_return_days
            FROM records r
            LEFT JOIN users u ON r.consignor_id = u.id
            WHERE r.date_sold IS NULL
            AND r.date_returned IS NOT NULL
            AND r.date_picked_up IS NULL
            AND r.consignor_id IS NOT NULL
        '''
        
        params = []
        
        if user_id:
            query += ' AND r.consignor_id = ?'
            params.append(user_id)
        
        query += ' ORDER BY r.date_returned'
        
        conn = self._get_connection()
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        return df

    def get_user_consignment_records_ready_for_pickup(self, user_id):
        """Get consignment records ready for pickup for a specific user"""
        conn = self._get_connection()
        df = pd.read_sql('''
            SELECT r.*, u.username as consignor_name, u.full_name, r.store_return_days
            FROM records r
            LEFT JOIN users u ON r.consignor_id = u.id
            WHERE r.date_sold IS NULL
            AND r.date_returned IS NOT NULL
            AND r.date_picked_up IS NULL
            AND r.consignor_id IS NOT NULL
            AND u.id = ?
            ORDER BY r.date_returned
        ''', conn, params=(user_id,))
        conn.close()
        return df
    
    def get_overdue_pickups(self):
        """Get consignment records that are overdue for pickup"""
        consignor_pickup_days = int(self.get_config_value('CONSIGNOR_PICKUP_DAYS', '30'))
        
        conn = self._get_connection()
        df = pd.read_sql('''
            SELECT r.*, u.username as consignor_name, u.full_name, r.store_return_days
            FROM records r
            LEFT JOIN users u ON r.consignor_id = u.id
            WHERE r.date_sold IS NULL
            AND r.date_returned IS NOT NULL
            AND r.date_picked_up IS NULL
            AND r.consignor_id IS NOT NULL
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
            WHERE consignor_id IS NOT NULL
            AND date_sold IS NULL
            AND date_returned IS NULL
            AND date_added < date('now', '-' || store_return_days || ' days')
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
            SET consignor_id = NULL,
                commission_rate = NULL,
                store_return_days = NULL,
                date_returned = NULL,
                date_picked_up = CURRENT_DATE
            WHERE date_sold IS NULL
            AND date_returned IS NOT NULL
            AND date_picked_up IS NULL
            AND consignor_id IS NOT NULL
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
            SELECT r.*, g.genre_name as genre, u.username as consignor_name, u.full_name
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            LEFT JOIN users u ON r.consignor_id = u.id
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
            SELECT r.*, g.genre_name as genre, u.username as consignor_name, u.full_name
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            LEFT JOIN users u ON r.consignor_id = u.id
            ORDER BY r.created_at DESC
        ''', conn)
        conn.close()
        return df

    def get_user_records(self, user_id):
        """Get records for a specific user (consignor)"""
        conn = self._get_connection()
        df = pd.read_sql('''
            SELECT r.*, g.genre_name as genre, u.username as consignor_name, u.full_name
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            LEFT JOIN users u ON r.consignor_id = u.id
            WHERE u.id = ?
            ORDER BY r.created_at DESC
        ''', conn, params=(user_id,))
        conn.close()
        return df
    
    def get_recent_records(self, limit=100):
        """Get recent records"""
        conn = self._get_connection()
        df = pd.read_sql(f'''
            SELECT r.*, g.genre_name as genre, u.username as consignor_name, u.full_name
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            LEFT JOIN users u ON r.consignor_id = u.id
            ORDER BY r.created_at DESC LIMIT {limit}
        ''', conn)
        conn.close()
        return df
    
    def get_database_stats(self):
        """Get database statistics"""
        conn = self._get_connection()
        
        # Use COALESCE to handle NULL values and ensure we get 0 instead of None
        records_count = pd.read_sql('SELECT COALESCE(COUNT(*), 0) as count FROM records', conn).iloc[0]['count']
        users_count = pd.read_sql('SELECT COALESCE(COUNT(*), 0) as count FROM users', conn).iloc[0]['count']
        
        # For latest timestamps, handle case where tables are empty
        latest_record_df = pd.read_sql('SELECT MAX(created_at) as latest FROM records', conn)
        latest_record = latest_record_df.iloc[0]['latest'] if not latest_record_df.empty and latest_record_df.iloc[0]['latest'] is not None else "None"
        
        conn.close()
        
        return {
            'records_count': int(records_count),
            'users_count': int(users_count),
            'latest_record': latest_record,
            'db_path': self.db_path
        }

    def get_user_database_stats(self, user_id):
        """Get database statistics for a specific user"""
        conn = self._get_connection()
        
        # Get records count for user
        records_count_df = pd.read_sql('''
            SELECT COALESCE(COUNT(*), 0) as count 
            FROM records r
            LEFT JOIN users u ON r.consignor_id = u.id
            WHERE u.id = ?
        ''', conn, params=(user_id,))
        records_count = records_count_df.iloc[0]['count']
        
        conn.close()
        
        return {
            'records_count': int(records_count),
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
        cursor.execute('DELETE FROM users')
        conn.commit()
        conn.close()
    
    def search_records(self, search_term):
        """Search for records by search term"""
        conn = self._get_connection()
        df = pd.read_sql(
            'SELECT r.*, g.genre_name as genre, u.username as consignor_name, u.full_name FROM records r LEFT JOIN genres g ON r.genre_id = g.id LEFT JOIN users u ON r.consignor_id = u.id WHERE r.artist LIKE ? OR r.title LIKE ? ORDER BY r.created_at DESC',
            conn,
            params=(f'%{search_term}%', f'%{search_term}%')
        )
        conn.close()
        return df
    
    def get_record_by_barcode(self, barcode):
        """Get a record by barcode"""
        conn = self._get_connection()
        df = pd.read_sql(
            'SELECT r.*, g.genre_name as genre, u.username as consignor_name, u.full_name FROM records r LEFT JOIN genres g ON r.genre_id = g.id LEFT JOIN users u ON r.consignor_id = u.id WHERE r.barcode = ?',
            conn,
            params=(barcode,)
        )
        conn.close()
        return df.iloc[0] if len(df) > 0 else None
    
    def update_file_at_for_all_records(self):
        """Update file_at column for all records with genre(file_at) format"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, artist, genre_id, compilation FROM records')
        records = cursor.fetchall()
        
        updated_count = 0
        for record in records:
            record_id = record[0]
            artist = record[1]
            genre_id = record[2]
            compilation = record[3]
            
            if genre_id:
                cursor.execute('SELECT genre_name FROM genres WHERE id = ?', (genre_id,))
                genre_result = cursor.fetchone()
                genre = genre_result[0] if genre_result else 'Unknown'
            else:
                genre = 'Unknown'
                
            file_at_value = self._calculate_file_at(artist, genre, compilation)
            
            cursor.execute('UPDATE records SET file_at = ? WHERE id = ?', (file_at_value, record_id))
            updated_count += 1
        
        conn.commit()
        conn.close()
        return updated_count
    
    def _calculate_file_at(self, artist, genre, compilation):
        """Calculate file_at value for an artist"""
        if not artist or not genre:
            return "?"
        
        if compilation:
            # For compilations: Comp(first_letter_of_genre)
            genre_first_char = genre[0].upper() if genre and genre[0].isalpha() else "?"
            return f"Comp({genre_first_char})"
        else:
            # For regular records: genre(first_letter_of_artist)
            artist_clean = artist.strip().lower()
            
            if artist_clean.startswith('the '):
                artist_clean = artist_clean[4:]
            
            if artist_clean and artist_clean[0].isdigit():
                number_words = {
                    '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
                    '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine'
                }
                first_char = artist_clean[0]
                file_at_letter = number_words.get(first_char, '?')[0].upper()
            elif artist_clean and artist_clean[0].isalpha():
                file_at_letter = artist_clean[0].upper()
            else:
                file_at_letter = "?"
            
            return f"{genre}({file_at_letter})"

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