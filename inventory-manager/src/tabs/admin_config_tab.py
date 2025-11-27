import streamlit as st
import pandas as pd
from datetime import datetime

class AdminConfigTab:
    def __init__(self):
        pass
    
    def render(self):
        st.header("⚙️ Admin Configuration")
        
        # Check if user is admin
        user = st.session_state.get('user', {})
        if user.get('role') != 'admin':
            st.error("❌ Access denied. Administrator privileges required to view configuration.")
            return
        
        # Main configuration interface
        col1, col2 = st.columns([2, 1])
        
        with col1:
            self._render_config_editor()
        
        with col2:
            self._render_config_help()
    
    def _render_config_editor(self):
        """Render the configuration editor"""
        st.subheader("Configuration Values")
        
        # Get all current configuration
        config_data = self._get_all_config_values()
        
        if not config_data:
            st.info("No configuration values found.")
            return
        
        # Create editable dataframe
        config_df = pd.DataFrame(config_data)
        
        # Display current values
        st.write("**Current Configuration:**")
        
        edited_df = st.data_editor(
            config_df,
            column_config={
                "config_key": st.column_config.TextColumn("Key", disabled=True),
                "config_value": st.column_config.TextColumn("Value"),
                "description": st.column_config.TextColumn("Description", disabled=True),
                "updated_at": st.column_config.TextColumn("Last Updated", disabled=True)
            },
            hide_index=True,
            use_container_width=True,
            key="config_editor"
        )
        
        # Save changes
        if not edited_df.equals(config_df):
            changes_made = False
            for _, row in edited_df.iterrows():
                original_row = config_df[config_df['config_key'] == row['config_key']].iloc[0]
                if original_row['config_value'] != row['config_value']:
                    success = st.session_state.db_manager.set_config_value(
                        row['config_key'], 
                        row['config_value']
                    )
                    if success:
                        changes_made = True
                        st.success(f"✅ Updated {row['config_key']}")
                    else:
                        st.error(f"❌ Failed to update {row['config_key']}")
            
            if changes_made:
                st.rerun()
        
        # Add new configuration key
        st.subheader("Add New Configuration")
        with st.form("add_config_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_key = st.text_input("Configuration Key", placeholder="e.g., NEW_SETTING")
            with col2:
                new_value = st.text_input("Configuration Value", placeholder="e.g., 100")
            
            new_description = st.text_area("Description", placeholder="What does this setting control?")
            
            if st.form_submit_button("➕ Add Configuration", use_container_width=True):
                if new_key and new_value:
                    success = st.session_state.db_manager.set_config_value(new_key, new_value)
                    if success:
                        st.success(f"✅ Added configuration key: {new_key}")
                        st.rerun()
                    else:
                        st.error(f"❌ Failed to add configuration key: {new_key}")
                else:
                    st.error("Please provide both key and value")
    
    def _render_config_help(self):
        """Render configuration help and descriptions"""
        st.subheader("Configuration Help")
        
        config_descriptions = {
            'SHIPPING_COST': 'Default shipping cost for eBay price calculations ($)',
            'MIN_STORE_PRICE': 'Minimum price for any record in the store ($)',
            'STORE_PRICE_LOWEST_MULTIPLIER': 'Multiplier for lowest price when calculating store price',
            'STORE_PRICE_ESTIMATED_MULTIPLIER': 'Multiplier for estimated price when calculating store price',
            'STORE_PRICE_MINIMUM': 'Absolute minimum store price regardless of calculations ($)',
            'DEFAULT_COMMISSION_RATE': 'Default commission rate for new consignment records (0.0-1.0)',
            'DEFAULT_STORE_RETURN_DAYS': 'Default number of days before unsold consignment records are returned',
            'CUSTOMER_RETURN_DAYS': 'Number of days before sold consignment records can be paid out',
            'CONSIGNOR_PICKUP_DAYS': 'Number of days consignors have to pick up returned records',
            'STORE_CAPACITY': 'Maximum number of records the store can hold'
        }
        
        for key, description in config_descriptions.items():
            with st.expander(f"**{key}**", expanded=False):
                st.write(description)
        
        st.subheader("Quick Actions")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Reset to Defaults", use_container_width=True):
                self._reset_to_defaults()
        
        with col2:
            if st.button("📊 Export Config", use_container_width=True):
                self._export_config()
    
    def _get_all_config_values(self):
        """Get all configuration values from database"""
        try:
            conn = st.session_state.db_manager._get_connection()
            df = pd.read_sql('''
                SELECT config_key, config_value, updated_at 
                FROM app_config 
                ORDER BY config_key
            ''', conn)
            conn.close()
            
            # Add descriptions
            descriptions = {
                'SHIPPING_COST': 'Default eBay shipping cost',
                'MIN_STORE_PRICE': 'Minimum store price',
                'STORE_PRICE_LOWEST_MULTIPLIER': 'Lowest price multiplier',
                'STORE_PRICE_ESTIMATED_MULTIPLIER': 'Estimated price multiplier',
                'STORE_PRICE_MINIMUM': 'Absolute minimum price',
                'DEFAULT_COMMISSION_RATE': 'Default commission rate',
                'DEFAULT_STORE_RETURN_DAYS': 'Default return days',
                'CUSTOMER_RETURN_DAYS': 'Customer return period',
                'CONSIGNOR_PICKUP_DAYS': 'Consignor pickup period',
                'STORE_CAPACITY': 'Store capacity limit'
            }
            
            config_data = []
            for _, row in df.iterrows():
                config_data.append({
                    'config_key': row['config_key'],
                    'config_value': row['config_value'],
                    'description': descriptions.get(row['config_key'], 'No description'),
                    'updated_at': row['updated_at'][:16] if row['updated_at'] else 'Unknown'
                })
            
            return config_data
            
        except Exception as e:
            st.error(f"Error loading configuration: {e}")
            return []
    
    def _reset_to_defaults(self):
        """Reset configuration to default values"""
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
        
        updated_count = 0
        for config_key, config_value in default_configs:
            success = st.session_state.db_manager.set_config_value(config_key, config_value)
            if success:
                updated_count += 1
        
        if updated_count > 0:
            st.success(f"✅ Reset {updated_count} configuration values to defaults!")
            st.rerun()
        else:
            st.error("❌ Failed to reset configuration values")
    
    def _export_config(self):
        """Export configuration to CSV"""
        try:
            config_data = self._get_all_config_values()
            if config_data:
                df = pd.DataFrame(config_data)
                csv_data = df.to_csv(index=False)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"pigstyle_config_export_{timestamp}.csv"
                
                st.download_button(
                    label="📥 Download Configuration CSV",
                    data=csv_data,
                    file_name=filename,
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.warning("No configuration data to export")
                
        except Exception as e:
            st.error(f"Error exporting configuration: {e}")