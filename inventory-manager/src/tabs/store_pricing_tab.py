import streamlit as st
import pandas as pd
import time
import math

class StorePricingTab:
    def __init__(self):
        pass
    
    def render(self):
        st.header("🏪 Store Pricing")
        
        # Store Pricing Configuration
        with st.expander("⚙️ Store Pricing Configuration", expanded=True):
            self._render_pricing_configuration()
            
        # Store Pricing Strategy
        with st.expander("💰 Store Pricing Strategy", expanded=True):
            st.write("""
            **Store Price Calculation:**
            ```
            Store Price = MAX(
                Selected Discogs Condition Price × Estimated Multiplier,
                Minimum Price
            )
            ```
            Then rounded to nearest .49 or .99 price point.
            
            **Note:** Discogs provides suggested prices for each condition grade.
            The selected condition price is multiplied by the estimated multiplier
            to determine the store price.
            """)
            
            # Test record input
            st.subheader("Test Single Record")
            col1, col2 = st.columns([1, 1])
            with col1:
                test_record_id = st.text_input("Record ID for testing:", placeholder="Enter record ID", key="store_test_record_id")
            
            # Store pricing action buttons
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🏪 Update Store Price", width='stretch', help="Calculate store price using current configuration"):
                    if test_record_id and test_record_id.strip():
                        self._calculate_single_store_price(test_record_id.strip())
                    else:
                        self._calculate_all_store_prices()

    def _render_pricing_configuration(self):
        """Render store pricing configuration settings"""
        try:
            col1, col2 = st.columns(2)
            
            with col1:
                estimated_multiplier = st.number_input(
                    "Estimated Price Multiplier", 
                    min_value=0.5,
                    max_value=1.5,
                    value=self._get_config_value('STORE_PRICE_ESTIMATED_MULTIPLIER'),
                    step=0.05,
                    help="Multiply selected Discogs condition price by this factor"
                )
                st.session_state.db_manager.set_config_value('STORE_PRICE_ESTIMATED_MULTIPLIER', str(estimated_multiplier))
            
            with col2:
                minimum_price = st.number_input(
                    "Minimum Store Price",
                    min_value=0.0,
                    max_value=50.0,
                    value=self._get_config_value('STORE_PRICE_MINIMUM'),
                    step=0.5,
                    help="Minimum price for any record"
                )
                st.session_state.db_manager.set_config_value('STORE_PRICE_MINIMUM', str(minimum_price))
            
            # Show current configuration
            st.info(f"""
            **Current Configuration:**
            - Selected Condition Price × {estimated_multiplier}
            - Minimum Price: ${minimum_price:.2f}
            """)
            
        except ValueError as e:
            st.error(f"❌ Configuration Error: {e}")
            st.warning("Please go to Admin Config tab to set up configuration values.")

    def _get_config_value(self, config_key):
        """Get config value and throw exception if not found"""
        value = st.session_state.db_manager.get_config_value(config_key, None)
        if value is None:
            raise ValueError(f"Configuration key '{config_key}' not found in app_config table")
        try:
            return float(value)
        except ValueError:
            raise ValueError(f"Configuration key '{config_key}' has invalid value: '{value}'. Must be a number.")

    def _calculate_all_store_prices(self):
        """Calculate store prices for all inventory records using current configuration"""
        try:
            # Get configuration values
            estimated_multiplier = self._get_config_value('STORE_PRICE_ESTIMATED_MULTIPLIER')
            minimum_price = self._get_config_value('STORE_PRICE_MINIMUM')
            
            updated_count = self._update_all_store_prices(estimated_multiplier, minimum_price)
            
            if updated_count > 0:
                st.session_state.records_updated += 1
                st.rerun()
                
        except ValueError as e:
            st.error(f"❌ Cannot calculate store prices: {e}")

    def _calculate_single_store_price(self, record_id):
        """Calculate store price for a single record using current configuration"""
        try:
            # Get configuration values
            estimated_multiplier = self._get_config_value('STORE_PRICE_ESTIMATED_MULTIPLIER')
            minimum_price = self._get_config_value('STORE_PRICE_MINIMUM')
            
            updated_count = self._update_single_store_price(record_id, estimated_multiplier, minimum_price)
            
            if updated_count > 0:
                st.session_state.records_updated += 1
                st.rerun()
                
        except ValueError as e:
            st.error(f"❌ Cannot calculate store price: {e}")

    def _update_all_store_prices(self, estimated_multiplier, minimum_price):
        """Update store prices for all inventory records using current configuration"""
        # Get all records using API
        records_df = st.session_state.db_manager.get_all_records()
        
        if records_df.empty:
            st.info("No records found to update")
            return 0
        
        updated_count = 0
        failed_count = 0
        progress_bar = st.progress(0)
        status_text = st.empty()
        results_container = st.container()
        
        with results_container:
            st.subheader("Store Price Update Progress")
            results_placeholder = st.empty()
        
        results = []
        
        for i, (_, record) in enumerate(records_df.iterrows()):
            artist = record.get('artist', '')
            title = record.get('title', '')
            record_id = record.get('id')
            discogs_suggested_price = record.get('discogs_suggested_price')
            
            status_text.text(f"Updating {i+1}/{len(records_df)}: {artist} - {title}")
            
            # Calculate store price using current configuration
            store_price = self._calculate_store_price(
                discogs_suggested_price, 
                estimated_multiplier, 
                minimum_price
            )
            
            # Update the store_price field
            success = st.session_state.db_manager.update_record(record_id, {'store_price': store_price})
            if success:
                updated_count += 1
                if discogs_suggested_price:
                    price_info = f"Discogs: ${discogs_suggested_price:.2f}×{estimated_multiplier}=${discogs_suggested_price * estimated_multiplier:.2f}"
                else:
                    price_info = "no Discogs data"
                results.append(f"✅ {artist} - {title}: {price_info} → ${store_price:.2f}")
            else:
                failed_count += 1
                results.append(f"❌ {artist} - {title}: Database update failed")
            
            # Update progress
            progress_bar.progress((i + 1) / len(records_df))
            
            # Update results display every 5 records or at the end
            if (i + 1) % 5 == 0 or (i + 1) == len(records_df):
                with results_placeholder:
                    # Show last 10 results
                    display_results = results[-10:] if len(results) > 10 else results
                    for result in display_results:
                        st.write(result)
        
        status_text.empty()
        progress_bar.empty()
        
        # Show final summary
        with results_container:
            st.success(f"✅ Store price update completed!")
            st.write(f"**Results:** {updated_count} updated, {failed_count} failed")
            
        return updated_count

    def _update_single_store_price(self, record_id, estimated_multiplier, minimum_price):
        """Update store price for a single record using current configuration"""
        # Get single record using API
        record = st.session_state.db_manager.get_record_by_id(record_id)
        if record is None:
            st.error(f"Record ID {record_id} not found")
            return 0
        
        artist = record.get('artist', '')
        title = record.get('title', '')
        discogs_suggested_price = record.get('discogs_suggested_price')
        
        # Calculate store price using current configuration
        store_price = self._calculate_store_price(
            discogs_suggested_price, 
            estimated_multiplier, 
            minimum_price
        )
        
        # Update the store_price field
        success = st.session_state.db_manager.update_record(record_id, {'store_price': store_price})
        if success:
            if discogs_suggested_price:
                price_info = f"Discogs: ${discogs_suggested_price:.2f}×{estimated_multiplier}=${discogs_suggested_price * estimated_multiplier:.2f}"
            else:
                price_info = "no Discogs data"
            st.success(f"✅ Updated store price for {artist} - {title}: {price_info} → ${store_price:.2f}")
            return 1
        else:
            st.error(f"❌ Database update failed for {artist} - {title}")
            return 0

    def _calculate_store_price(self, discogs_suggested_price, estimated_multiplier, minimum_price):
        """Use the consolidated calculation function from RecordOperationsHandler"""
        # Import and use the consolidated function
        from handlers.record_operations_handler import RecordOperationsHandler
        
        # Create a temporary instance to use the calculation method
        # Note: This could be refactored to make calculate_store_price a static method
        temp_handler = RecordOperationsHandler()
        
        # Set the parameters in session state for the calculation function to access
        st.session_state.db_manager.set_config_value('STORE_PRICE_ESTIMATED_MULTIPLIER', str(estimated_multiplier))
        st.session_state.db_manager.set_config_value('STORE_PRICE_MINIMUM', str(minimum_price))
        
        # Use the consolidated calculation function
        return temp_handler.calculate_store_price(discogs_suggested_price)

    def _round_to_49_or_99(self, price):
        """Round to nearest .49 or .99"""
        if price <= 0:
            return 0.0
        
        base_price = math.floor(price)
        decimal_part = price - base_price
        
        if decimal_part < 0.25:
            return base_price + 0.49
        elif decimal_part < 0.75:
            return base_price + 0.49
        else:
            return base_price + 0.99