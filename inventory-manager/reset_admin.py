#!/usr/bin/env python3
import sqlite3
import hashlib
import secrets

def reset_admin():
    db_path = "data/records.db"
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Disable foreign keys
    cursor.execute("PRAGMA foreign_keys = OFF")
    
    try:
        # Clear user_sessions and audit_log tables first
        cursor.execute("DELETE FROM user_sessions")
        cursor.execute("DELETE FROM audit_log")
        
        # Clear consignor_id from records
        cursor.execute("UPDATE records SET consignor_id = NULL")
        
        # Delete all users
        cursor.execute("DELETE FROM users")
        
        # Create admin user with plain text password that will be hashed properly
        username = "admin"
        password = "admin123"
        email = "admin@pigstylerecords.com"
        
        # Generate proper hash using the same method as auth_manager
        salt = secrets.token_hex(16)
        password_hash = f"{salt}${hashlib.sha256((salt + password).encode()).hexdigest()}"
        
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, role, full_name, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, email, password_hash, 'admin', 'System Administrator', 1))
        
        conn.commit()
        print("✅ Admin user created successfully!")
        print(f"Username: {username}")
        print(f"Password: {password}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        cursor.execute("PRAGMA foreign_keys = ON")
        conn.close()

if __name__ == "__main__":
    reset_admin()