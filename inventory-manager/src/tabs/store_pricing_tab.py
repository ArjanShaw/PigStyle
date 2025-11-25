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
        col1, col2 = st.columns(2)
        
        with col1:
            estimated_multiplier = st.number_input(
                "Estimated Price Multiplier", 
                min_value=0.5,
                max_value=1.5,
                value=float(st.session_state.db_manager.get_config_value('STORE_PRICE_ESTIMATED_MULTIPLIER', '0.9')),
                step=0.05,
                help="Multiply selected Discogs condition price by this factor"
            )
            st.session_state.db_manager.set_config_value('STORE_PRICE_ESTIMATED_MULTIPLIER', str(estimated_multiplier))
        
        with col2:
            minimum_price = st.number_input(
                "Minimum Store Price",
                min_value=0.0,
                max_value=50.0,
                value=float(st.session_state.db_manager.get_config_value('STORE_PRICE_MINIMUM', '4.99')),
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

    def _calculate_all_store_prices(self):
        """Calculate store prices for all inventory records using current configuration"""
        updated_count = self._update_all_store_prices()
        
        if updated_count > 0:
            st.session_state.records_updated += 1
            start_time = time.time()
            st.rerun()
            duration = time.time() - start_time

    def _calculate_single_store_price(self, record_id):
        """Calculate store price for a single record using current configuration"""
        updated_count = self._update_single_store_price(record_id)
        
        if updated_count > 0:
            st.session_state.records_updated += 1
            start_time = time.time()
            st.rerun()
            duration = time.time() - start_time

    def _update_all_store_prices(self):
        """Update store prices for all inventory records using current configuration"""
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql('SELECT * FROM records_with_genres', conn)
        conn.close()
        
        # Get current configuration
        estimated_multiplier = float(st.session_state.db_manager.get_config_value('STORE_PRICE_ESTIMATED_MULTIPLIER', '0.9'))
        minimum_price = float(st.session_state.db_manager.get_config_value('STORE_PRICE_MINIMUM', '4.99'))
        
        updated_count = 0
        failed_count = 0
        progress_bar = st.progress(0)
        status_text = st.empty()
        results_container = st.container()
        
        with results_container:
            st.subheader("Store Price Update Progress")
            results_placeholder = st.empty()
        
        results = []
        
        for i, (_, record) in enumerate(df.iterrows()):
            artist = record.get('artist', '')
            title = record.get('title', '')
            record_id = record.get('id')
            discogs_suggested_price = record.get('discogs_suggested_price')
            
            status_text.text(f"Updating {i+1}/{len(df)}: {artist} - {title}")
            
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
            progress_bar.progress((i + 1) / len(df))
            
            # Update results display every 5 records or at the end
            if (i + 1) % 5 == 0 or (i + 1) == len(df):
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

    def _update_single_store_price(self, record_id):
        """Update store price for a single record using current configuration"""
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql('SELECT * FROM records_with_genres WHERE id = ?', conn, params=(record_id,))
        conn.close()
        
        if len(df) == 0:
            st.error(f"Record ID {record_id} not found")
            return 0
        
        # Get current configuration
        estimated_multiplier = float(st.session_state.db_manager.get_config_value('STORE_PRICE_ESTIMATED_MULTIPLIER', '0.9'))
        minimum_price = float(st.session_state.db_manager.get_config_value('STORE_PRICE_MINIMUM', '4.99'))
        
        record = df.iloc[0]
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
        """Calculate store price using the current formula"""
        candidates = []
        
        if discogs_suggested_price and discogs_suggested_price > 0:
            # Use the selected Discogs condition price with the estimated multiplier
            candidates.append(discogs_suggested_price * estimated_multiplier)
        
        if candidates:
            raw_price = max(candidates)
            raw_price = max(raw_price, minimum_price)
        else:
            raw_price = minimum_price
        
        # Round to nearest .49 or .99
        store_price = self._round_to_49_or_99(raw_price)
        
        return store_price

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