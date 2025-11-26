import streamlit as st
import hashlib
import secrets
import sqlite3
import time
from datetime import datetime, timedelta
import re
from typing import Optional, Dict, Any
import os

class AuthManager:
    def __init__(self, db_path: str = "data/auth.db"):
        self.db_path = db_path
        self._init_auth_database()
    
    def _init_auth_database(self):
        """Initialize authentication database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table - simplified with only admin and consignor roles
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
        
        # Sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Audit log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                description TEXT,
                ip_address TEXT,
                user_agent TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create default admin user if none exists
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        if cursor.fetchone()[0] == 0:
            default_password = self._hash_password("admin123")
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, role, full_name)
                VALUES (?, ?, ?, ?, ?)
            ''', ('admin', 'admin@pigstylerecords.com', default_password, 'admin', 'System Administrator'))
        
        conn.commit()
        conn.close()
    
    def _hash_password(self, password: str) -> str:
        """Hash password using SHA-256 with salt"""
        salt = secrets.token_hex(16)
        return f"{salt}${hashlib.sha256((salt + password).encode()).hexdigest()}"
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        try:
            salt, hash_value = password_hash.split('$')
            return hashlib.sha256((salt + password).encode()).hexdigest() == hash_value
        except:
            return False
    
    def _validate_email(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def _validate_password_strength(self, password: str) -> tuple[bool, str]:
        """Validate password strength"""
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        if not re.search(r'[0-9]', password):
            return False, "Password must contain at least one number"
        return True, "Password is strong"
    
    def create_user(self, username: str, email: str, password: str, role: str = "consignor", full_name: str = "", phone: str = "", address: str = "") -> tuple[bool, str]:
        """Create a new user account"""
        # Validate inputs
        if not username or not email or not password:
            return False, "All fields are required"
        
        if not self._validate_email(email):
            return False, "Invalid email format"
        
        is_strong, message = self._validate_password_strength(password)
        if not is_strong:
            return False, message
        
        # Check if username or email already exists
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
        if cursor.fetchone():
            conn.close()
            return False, "Username or email already exists"
        
        # Create user
        password_hash = self._hash_password(password)
        try:
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, role, full_name, phone, address)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (username, email, password_hash, role, full_name, phone, address))
            
            user_id = cursor.lastrowid
            
            # Log the action
            cursor.execute('''
                INSERT INTO audit_log (user_id, action, description)
                VALUES (?, ?, ?)
            ''', (user_id, 'USER_CREATED', f'User {username} created with role {role}'))
            
            conn.commit()
            conn.close()
            return True, "User created successfully"
            
        except Exception as e:
            conn.close()
            return False, f"Error creating user: {str(e)}"
    
    def authenticate_user(self, username: str, password: str, ip_address: str = "", user_agent: str = "") -> tuple[bool, str, Optional[Dict]]:
        """Authenticate user and create session"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get user data
        cursor.execute('''
            SELECT id, username, email, password_hash, role, full_name, is_active, 
                   failed_attempts, locked_until 
            FROM users WHERE username = ? OR email = ?
        ''', (username, username))
        
        user_data = cursor.fetchone()
        
        if not user_data:
            conn.close()
            return False, "Invalid username or password", None
        
        user_id, db_username, email, password_hash, role, full_name, is_active, failed_attempts, locked_until = user_data
        
        # Check if account is locked
        if locked_until and datetime.fromisoformat(locked_until) > datetime.now():
            conn.close()
            return False, "Account temporarily locked due to too many failed attempts", None
        
        # Check if account is active
        if not is_active:
            conn.close()
            return False, "Account is deactivated", None
        
        # Verify password
        if self._verify_password(password, password_hash):
            # Successful login - reset failed attempts and update last login
            cursor.execute('''
                UPDATE users 
                SET failed_attempts = 0, locked_until = NULL, last_login = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (user_id,))
            
            # Create session
            session_token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(hours=24)
            
            cursor.execute('''
                INSERT INTO user_sessions (user_id, session_token, expires_at, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, session_token, expires_at, ip_address, user_agent))
            
            # Log successful login
            cursor.execute('''
                INSERT INTO audit_log (user_id, action, description, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, 'LOGIN_SUCCESS', 'User logged in successfully', ip_address, user_agent))
            
            conn.commit()
            conn.close()
            
            user_info = {
                'id': user_id,
                'username': db_username,
                'email': email,
                'role': role,
                'full_name': full_name,
                'session_token': session_token
            }
            
            return True, "Login successful", user_info
        else:
            # Failed login - increment failed attempts
            failed_attempts += 1
            if failed_attempts >= 5:
                locked_until = datetime.now() + timedelta(minutes=30)
                cursor.execute('''
                    UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?
                ''', (failed_attempts, locked_until, user_id))
                message = "Account locked for 30 minutes due to too many failed attempts"
            else:
                cursor.execute('UPDATE users SET failed_attempts = ? WHERE id = ?', (failed_attempts, user_id))
                message = f"Invalid password. {5 - failed_attempts} attempts remaining"
            
            # Log failed attempt
            cursor.execute('''
                INSERT INTO audit_log (user_id, action, description, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, 'LOGIN_FAILED', f'Failed login attempt {failed_attempts}', ip_address, user_agent))
            
            conn.commit()
            conn.close()
            return False, message, None
    
    def validate_session(self, session_token: str) -> tuple[bool, Optional[Dict]]:
        """Validate session token and return user info"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT us.user_id, us.expires_at, u.username, u.email, u.role, u.full_name, u.is_active
            FROM user_sessions us
            JOIN users u ON us.user_id = u.id
            WHERE us.session_token = ? AND us.expires_at > CURRENT_TIMESTAMP AND u.is_active = 1
        ''', (session_token,))
        
        session_data = cursor.fetchone()
        
        if not session_data:
            conn.close()
            return False, None
        
        user_id, expires_at, username, email, role, full_name, is_active = session_data
        
        # Update last activity
        cursor.execute('''
            UPDATE user_sessions SET last_activity = CURRENT_TIMESTAMP WHERE session_token = ?
        ''', (session_token,))
        
        conn.commit()
        conn.close()
        
        user_info = {
            'id': user_id,
            'username': username,
            'email': email,
            'role': role,
            'full_name': full_name
        }
        
        return True, user_info
    
    def logout_user(self, session_token: str):
        """Invalidate user session"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get user ID for logging
        cursor.execute('SELECT user_id FROM user_sessions WHERE session_token = ?', (session_token,))
        result = cursor.fetchone()
        
        if result:
            user_id = result[0]
            # Log logout
            cursor.execute('''
                INSERT INTO audit_log (user_id, action, description)
                VALUES (?, ?, ?)
            ''', (user_id, 'LOGOUT', 'User logged out'))
        
        # Delete session
        cursor.execute('DELETE FROM user_sessions WHERE session_token = ?', (session_token,))
        conn.commit()
        conn.close()
    
    def change_password(self, user_id: int, current_password: str, new_password: str) -> tuple[bool, str]:
        """Change user password"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get current password hash
        cursor.execute('SELECT password_hash FROM users WHERE id = ?', (user_id,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return False, "User not found"
        
        current_password_hash = result[0]
        
        # Verify current password
        if not self._verify_password(current_password, current_password_hash):
            conn.close()
            return False, "Current password is incorrect"
        
        # Validate new password strength
        is_strong, message = self._validate_password_strength(new_password)
        if not is_strong:
            conn.close()
            return False, f"New password is weak: {message}"
        
        # Hash and update new password
        new_password_hash = self._hash_password(new_password)
        
        try:
            cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_password_hash, user_id))
            
            # Log the password change
            cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
            username = cursor.fetchone()[0]
            
            cursor.execute('''
                INSERT INTO audit_log (user_id, action, description)
                VALUES (?, ?, ?)
            ''', (user_id, 'PASSWORD_CHANGE', 'User changed password'))
            
            conn.commit()
            conn.close()
            return True, "Password changed successfully"
            
        except Exception as e:
            conn.close()
            return False, f"Error changing password: {str(e)}"
    
    def reset_password(self, admin_user_id: int, target_user_id: int, new_password: str) -> tuple[bool, str]:
        """Admin reset user password (admin only)"""
        # Validate new password strength
        is_strong, message = self._validate_password_strength(new_password)
        if not is_strong:
            return False, f"New password is weak: {message}"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Hash and update new password
            new_password_hash = self._hash_password(new_password)
            cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_password_hash, target_user_id))
            
            # Log the action
            cursor.execute('SELECT username FROM users WHERE id = ?', (target_user_id,))
            target_username = cursor.fetchone()[0]
            
            cursor.execute('''
                INSERT INTO audit_log (user_id, action, description)
                VALUES (?, ?, ?)
            ''', (admin_user_id, 'PASSWORD_RESET', f'Admin reset password for user {target_username}'))
            
            conn.commit()
            conn.close()
            return True, "Password reset successfully"
            
        except Exception as e:
            conn.close()
            return False, f"Error resetting password: {str(e)}"
    
    def get_all_users(self):
        """Get all users (admin only)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, username, email, role, full_name, phone, address, is_active, created_at, last_login
            FROM users ORDER BY username
        ''')
        
        users = cursor.fetchall()
        conn.close()
        
        return users
    
    def update_user_role(self, user_id: int, new_role: str, admin_id: int) -> tuple[bool, str]:
        """Update user role (admin only)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
            
            # Log the action
            cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
            username = cursor.fetchone()[0]
            
            cursor.execute('''
                INSERT INTO audit_log (user_id, action, description)
                VALUES (?, ?, ?)
            ''', (admin_id, 'ROLE_CHANGE', f'Changed role for {username} to {new_role}'))
            
            conn.commit()
            conn.close()
            return True, "User role updated successfully"
            
        except Exception as e:
            conn.close()
            return False, f"Error updating user role: {str(e)}"
    
    def get_audit_log(self, limit: int = 100):
        """Get audit log entries (admin only)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT al.timestamp, u.username, al.action, al.description, al.ip_address
            FROM audit_log al
            LEFT JOIN users u ON al.user_id = u.id
            ORDER BY al.timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        logs = cursor.fetchall()
        conn.close()
        
        return logs