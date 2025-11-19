import sqlite3
import pandas as pd
from datetime import datetime
import os

class DataManager:
    def __init__(self, db_path="data/records.db"):
        self.db_path = db_path
        self._init_db()
    
    def _get_connection(self):
        """Create connection to SQLite database"""
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        return sqlite3.connect(self.db_path)
    
    def _init_db(self):
        """Initialize database tables"""
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    amount REAL NOT NULL,
                    type TEXT NOT NULL CHECK(type IN ('Income', 'Expense')),
                    category TEXT NOT NULL,
                    description TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
    
    def add_transaction(self, amount, transaction_type, category, description=""):
        """Add a new transaction"""
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO transactions (amount, type, category, description)
                VALUES (?, ?, ?, ?)
            ''', (amount, transaction_type, category, description))
            conn.commit()
    
    def get_all_transactions(self):
        """Get all transactions"""
        with self._get_connection() as conn:
            return pd.read_sql('''
                SELECT * FROM transactions 
                ORDER BY timestamp DESC
            ''', conn)
    
    def get_categories(self, transaction_type):
        """Get available categories for a transaction type"""
        categories = {
            'Income': ['Salary', 'Freelance', 'Investment', 'Gift', 'Other'],
            'Expense': ['Food', 'Transport', 'Entertainment', 'Bills', 'Shopping', 'Healthcare', 'Other']
        }
        return categories.get(transaction_type, [])
    
    def get_transactions_by_date_range(self, start_date, end_date):
        """Get transactions within a date range"""
        with self._get_connection() as conn:
            return pd.read_sql('''
                SELECT * FROM transactions 
                WHERE date(timestamp) BETWEEN ? AND ?
                ORDER BY timestamp DESC
            ''', conn, params=(start_date, end_date))
    
    def delete_transaction(self, transaction_id):
        """Delete a transaction by ID"""
        with self._get_connection() as conn:
            conn.execute('DELETE FROM transactions WHERE id = ?', (transaction_id,))
            conn.commit()