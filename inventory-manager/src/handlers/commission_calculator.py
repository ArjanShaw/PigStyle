"""
Commission Calculator for Consignment System
Handles dynamic commission rates based on store capacity and store credit bonuses
"""
import streamlit as st
import math

class CommissionCalculator:
    def __init__(self, db_manager):
        self.db_manager = db_manager
    
    def get_current_commission_rate(self, user_id=None):
        """
        Calculate current commission rate based on store capacity
        Returns rate as decimal (0.10 for 10%)
        """
        try:
            # Get store capacity from config
            store_capacity = self._get_config_int('STORE_CAPACITY')
            
            # Get current inventory count
            records_df = self.db_manager.get_all_records()
            total_inventory = len(records_df) if not records_df.empty else 0
            
            # Calculate fill fraction
            fill_fraction = total_inventory / store_capacity if store_capacity > 0 else 0
            
            # Get commission parameters
            min_rate = self._get_config_int('COMMISSION_MIN_RATE') / 100.0
            min_capacity = self._get_config_int('COMMISSION_MIN_CAPACITY') / 100.0
            max_rate = self._get_config_int('COMMISSION_MAX_RATE') / 100.0
            max_capacity = self._get_config_int('COMMISSION_MAX_CAPACITY') / 100.0
            
            # Calculate commission rate
            if fill_fraction < min_capacity:
                return min_rate
            elif fill_fraction <= max_capacity:
                # Linear interpolation between min and max rates
                slope = (max_rate - min_rate) / (max_capacity - min_capacity)
                return min_rate + slope * (fill_fraction - min_capacity)
            else:
                return max_rate
                
        except Exception as e:
            st.error(f"Error calculating commission rate: {e}")
            return 0.10  # Default fallback
    
    def calculate_commission_with_bonus(self, base_rate, store_credit_option=False):
        """
        Apply store credit bonus if selected
        Returns adjusted commission rate
        """
        if store_credit_option:
            bonus_percentage = self._get_config_int('COMMISSION_STORE_CREDIT_BONUS') / 100.0
            return base_rate + bonus_percentage
        return base_rate
    
    def calculate_consignor_payout(self, sale_price, commission_rate, store_credit_option=False):
        """
        Calculate consignor payout after commission
        """
        adjusted_rate = self.calculate_commission_with_bonus(commission_rate, store_credit_option)
        store_commission = sale_price * adjusted_rate
        consignor_payout = sale_price - store_commission
        
        return {
            'sale_price': sale_price,
            'commission_rate': adjusted_rate,
            'store_commission': round(store_commission, 2),
            'consignor_payout': round(consignor_payout, 2),
            'store_credit_option': store_credit_option,
            'bonus_applied': store_credit_option
        }
    
    def get_consignment_period_info(self, start_date):
        """
        Calculate consignment period dates and current phase
        """
        from datetime import datetime, timedelta
        
        total_days = self._get_config_int('CONSIGNMENT_TOTAL_DAYS')
        full_price_days = self._get_config_int('CONSIGNMENT_FULL_PRICE_DAYS')
        discount_days = self._get_config_int('CONSIGNMENT_DISCOUNT_DAYS')
        
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        full_price_end = start_date + timedelta(days=full_price_days)
        discount_end = start_date + timedelta(days=total_days)
        today = datetime.now().date()
        
        days_in_full_price = (today - start_date).days if today <= full_price_end else full_price_days
        days_in_discount = max(0, (today - full_price_end).days) if today > full_price_end else 0
        days_remaining = max(0, (discount_end - today).days)
        
        current_phase = "full_price" if today <= full_price_end else "discount"
        
        return {
            'start_date': start_date,
            'full_price_end': full_price_end,
            'discount_end': discount_end,
            'current_phase': current_phase,
            'days_in_full_price': days_in_full_price,
            'days_in_discount': days_in_discount,
            'days_remaining': days_remaining,
            'total_days': total_days,
            'discount_percentage': self._get_config_int('DISCOUNT_PERCENTAGE')
        }
    
    def check_price_validity(self, user_price, advised_price):
        """
        Validate user price against advised price with maximum ratio
        """
        max_ratio = self._get_config_float('MAX_PRICE_TO_ADV_RATIO')
        max_allowed = advised_price * max_ratio
        
        is_valid = user_price <= max_allowed
        max_allowed_price = round(max_allowed, 2)
        
        return {
            'is_valid': is_valid,
            'user_price': user_price,
            'advised_price': advised_price,
            'max_allowed_price': max_allowed_price,
            'max_ratio': max_ratio,
            'reason': 'Price exceeds maximum allowed ratio' if not is_valid else 'Price is valid'
        }
    
    def check_payout_eligibility(self, user_id, balance):
        """
        Check if user can request payout
        """
        try:
            user_info = self.db_manager.get_user_by_id(user_id)
            if user_info is None or user_info.empty:
                return False, "User not found"
            
            # Check minimum amount
            min_amount = self._get_config_float('PAYOUT_MINIMUM_AMOUNT')
            if balance < min_amount:
                return False, f"Balance (${balance:.2f}) below minimum ${min_amount}"
            
            # Check frequency
            payout_frequency = self._get_config_int('PAYOUT_FREQUENCY_DAYS')
            last_payout = user_info.get('last_payout_date')
            
            if last_payout and pd.notna(last_payout):
                from datetime import datetime, timedelta
                last_date = datetime.strptime(str(last_payout), '%Y-%m-%d').date()
                min_next_date = last_date + timedelta(days=payout_frequency)
                today = datetime.now().date()
                
                if today < min_next_date:
                    days_left = (min_next_date - today).days
                    return False, f"Next payout available in {days_left} days"
            
            return True, "Eligible for payout"
            
        except Exception as e:
            return False, f"Error checking eligibility: {str(e)}"
    
    def _get_config_int(self, key):
        """Get config value as integer"""
        value = self.db_manager.get_config_value(key, '0')
        try:
            return int(float(value))
        except:
            return 0
    
    def _get_config_float(self, key):
        """Get config value as float"""
        value = self.db_manager.get_config_value(key, '0')
        try:
            return float(value)
        except:
            return 0.0