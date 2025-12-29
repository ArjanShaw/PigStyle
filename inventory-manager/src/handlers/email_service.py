"""
Email Service for Consignment System
Handles notifications for discounts, pickups, payments, etc.
"""
import streamlit as st
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime, timedelta
import logging

class EmailService:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        
        # Email configuration (would come from app_config in production)
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.from_email = os.getenv('FROM_EMAIL', 'noreply@pigstylerecords.com')
        self.enabled = bool(self.smtp_username and self.smtp_password)
    
    def send_notification(self, user_id, record_id, notification_type, message):
        """
        Send notification and log it in database
        """
        try:
            # Get user info
            user_info = self.db_manager.get_user_by_id(user_id)
            if user_info is None or user_info.empty:
                self.logger.error(f"User {user_id} not found for notification")
                return False
            
            email = user_info.get('email', '')
            if not email:
                self.logger.error(f"No email for user {user_id}")
                return False
            
            # Send email if enabled
            email_sent = False
            if self.enabled:
                subject = self._get_subject(notification_type)
                email_sent = self._send_email(email, subject, message)
            
            # Log notification in database
            result = self.db_manager._make_request(
                'POST',
                '/notifications',
                json={
                    'user_id': user_id,
                    'record_id': record_id,
                    'notification_type': notification_type,
                    'message': message
                }
            )
            
            # Update last notification sent date on record
            if record_id:
                self.db_manager.update_record(record_id, {
                    'last_notification_sent': datetime.now().date()
                })
            
            return email_sent or result is not None
            
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")
            return False
    
    def send_discount_warning(self, record_id):
        """
        Send notification that item will be discounted soon
        """
        record = self.db_manager.get_record_by_id(record_id)
        if record is None:
            return False
        
        user_id = record.get('consignor_id')
        if not user_id:
            return False
        
        artist = record.get('artist', 'Unknown')
        title = record.get('title', 'Unknown')
        days_left = 7  # Default warning period
        
        message = f"""
        Hello,
        
        Your consigned record "{artist} - {title}" has been on sale for nearly 90 days.
        In {days_left} days, it may be discounted by up to 50% to help with sales.
        
        You can:
        1. Leave it for sale with potential discount
        2. Request to remove it from the store
        
        Please visit your consignment portal to make a decision.
        
        Thank you,
        PigStyle Records Team
        """
        
        return self.send_notification(
            user_id, record_id, 'discount_warning', message
        )
    
    def send_pickup_reminder(self, record_id):
        """
        Send weekly pickup reminder
        """
        record = self.db_manager.get_record_by_id(record_id)
        if record is None:
            return False
        
        user_id = record.get('consignor_id')
        if not user_id:
            return False
        
        artist = record.get('artist', 'Unknown')
        title = record.get('title', 'Unknown')
        
        message = f"""
        Hello,
        
        Your consigned record "{artist} - {title}" is ready for pickup.
        Please pick it up within 30 days or it will become store property.
        
        You can pick up during store hours:
        - Monday-Friday: 10am-6pm
        - Saturday: 11am-4pm
        
        Thank you,
        PigStyle Records Team
        """
        
        return self.send_notification(
            user_id, record_id, 'pickup_reminder', message
        )
    
    def send_payment_notification(self, user_id, amount, records_count):
        """
        Send payment confirmation
        """
        user_info = self.db_manager.get_user_by_id(user_id)
        if user_info is None or user_info.empty:
            return False
        
        message = f"""
        Hello {user_info.get('full_name', 'Consignor')},
        
        Your payment of ${amount:.2f} has been processed for {records_count} sold records.
        
        The payment will be available via your chosen method.
        Store credit bonus has been applied to your commission rate.
        
        You can view detailed breakdown in your consignment portal.
        
        Thank you for consigning with PigStyle Records!
        """
        
        return self.send_notification(
            user_id, None, 'payment_processed', message
        )
    
    def check_and_send_scheduled_notifications(self):
        """
        Check for records needing notifications and send them
        Returns count of notifications sent
        """
        try:
            # Get records approaching discount period (last 7 days of full price)
            from datetime import datetime, timedelta
            
            today = datetime.now().date()
            warning_start = today - timedelta(days=83)  # 90 - 7 days
            
            # This would query records needing discount warnings
            # For now, just return 0 as placeholder
            return 0
            
        except Exception as e:
            self.logger.error(f"Error checking scheduled notifications: {e}")
            return 0
    
    def _send_email(self, to_email, subject, body):
        """
        Actually send email via SMTP
        """
        try:
            if not self.enabled:
                self.logger.info(f"Email service disabled. Would send to {to_email}: {subject}")
                return True  # Return True for logging purposes
            
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            self.logger.info(f"Email sent to {to_email}: {subject}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    def _get_subject(self, notification_type):
        """Get email subject based on notification type"""
        subjects = {
            'discount_warning': 'PigStyle Records: Your Item May Be Discounted Soon',
            'pickup_reminder': 'PigStyle Records: Item Ready for Pickup',
            'payment_processed': 'PigStyle Records: Payment Processed',
            'price_override': 'PigStyle Records: Price Override Request',
            'item_sold': 'PigStyle Records: Your Item Has Sold!',
            'consignment_expired': 'PigStyle Records: Consignment Period Ending'
        }
        return subjects.get(notification_type, 'PigStyle Records Notification')