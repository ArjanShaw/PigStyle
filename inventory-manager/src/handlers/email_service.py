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
    def __init__(self, api_client):
        self.api_client = api_client
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
            # Get user info via API
            user_info = self.api_client.get_user_by_id(user_id)
            if user_info is None:
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
            
            # Log notification in database via API
            # Note: The API endpoint for notifications needs to be implemented
            # For now, just return email_sent status
            
            # Update last notification sent date on record via API
            if record_id:
                self.api_client.update_record(record_id, {
                    'last_notification_sent': datetime.now().date()
                })
            
            return email_sent
            
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")
            return False
    
    def send_discount_warning(self, record_id):
        """
        Send notification that item will be discounted soon
        """
        # Get record via API
        # Note: This would need an API endpoint to get record by ID
        # For now, this is a placeholder
        return False
    
    def send_pickup_reminder(self, record_id):
        """
        Send weekly pickup reminder
        """
        # Get record via API
        # Note: This would need an API endpoint to get record by ID
        # For now, this is a placeholder
        return False
    
    def send_payment_notification(self, user_id, amount, records_count):
        """
        Send payment confirmation
        """
        # Get user info via API
        user_info = self.api_client.get_user_by_id(user_id)
        if user_info is None:
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
            # This would query records needing notifications via API
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