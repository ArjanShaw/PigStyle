import streamlit as st
import pandas as pd
from datetime import datetime
import io
from PIL import Image

class ExpensesTab:
    def __init__(self):
        pass
    
    def render(self):
        st.header("💰 Expenses")
        
        tab1, tab2 = st.tabs(["➕ Add Expenses", "📋 View Expenses"])
        
        with tab1:
            self._render_add_expenses()
        
        with tab2:
            self._render_view_expenses()

    def _render_add_expenses(self):
        """Render the add expenses form with individual file management"""
        st.subheader("Add New Expenses")
        
        # Multiple file upload
        st.write("**Receipt Photos:**")
        receipt_uploads = st.file_uploader(
            "Upload receipt photos",
            type=['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'],
            accept_multiple_files=True,
            help="Upload multiple receipt photos from your local filesystem"
        )
        
        if receipt_uploads:
            st.write(f"**Managing {len(receipt_uploads)} receipt(s):**")
            
            # Create a form for each uploaded file
            expense_data = []
            for i, uploaded_file in enumerate(receipt_uploads):
                st.divider()
                col1, col2 = st.columns([1, 3])
                
                with col1:
                    # Display the image with much larger preview
                    st.image(uploaded_file, width=600, caption=f"Receipt {i+1} - {uploaded_file.name}")
                    
                    # Add expandable full-screen view
                    with st.expander("🔍 View Full Size"):
                        # Display at full resolution using container width
                        st.image(uploaded_file, use_container_width=True)
                    
                    if st.button("Remove", key=f"remove_{i}"):
                        receipt_uploads.pop(i)
                        st.rerun()
                
                with col2:
                    # Individual expense details for each receipt
                    st.write(f"**Receipt {i+1}: {uploaded_file.name}**")
                    description = st.text_input(
                        f"Description {i+1}",
                        placeholder="Enter description for this receipt...",
                        key=f"desc_{i}"
                    )
                    amount = st.number_input(
                        f"Amount {i+1}",
                        min_value=None,  # Allow negative values for returns
                        step=0.01,
                        format="%.2f",
                        help="Enter amount for this receipt (negative for returns)",
                        key=f"amount_{i}"
                    )
                    
                    # Store the data for this receipt
                    expense_data.append({
                        'file': uploaded_file,
                        'description': description,
                        'amount': amount
                    })
            
            st.divider()
            
            # Submit all button
            if st.button("💾 Save All Expenses", use_container_width=True):
                # Validate and save all expenses
                saved_count = 0
                errors = []
                
                for i, expense in enumerate(expense_data):
                    if not expense['description']:
                        errors.append(f"Receipt {i+1}: Description is required")
                        continue
                    
                    if expense['amount'] is None:
                        errors.append(f"Receipt {i+1}: Amount is required")
                        continue
                    
                    try:
                        receipt_bytes = expense['file'].getvalue()
                        expense_id = st.session_state.db_manager.save_expense(
                            expense['description'], 
                            expense['amount'], 
                            receipt_bytes
                        )
                        
                        if expense_id:
                            saved_count += 1
                        else:
                            errors.append(f"Receipt {i+1}: Failed to save to database")
                            
                    except Exception as e:
                        errors.append(f"Receipt {i+1}: {str(e)}")
                
                # Show results
                if saved_count > 0:
                    st.success(f"✅ {saved_count} expense(s) saved successfully!")
                
                if errors:
                    for error in errors:
                        st.error(error)
                
                if saved_count > 0:
                    st.rerun()

    def _render_view_expenses(self):
        """Render the expenses list"""
        st.subheader("Expense History")
        
        try:
            expenses = st.session_state.db_manager.get_all_expenses()
            
            if len(expenses) > 0:
                # Calculate total (includes negative amounts for returns)
                total_amount = expenses['amount'].sum()
                
                # Display summary
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Net Expenses", f"${total_amount:.2f}")
                with col2:
                    st.metric("Number of Expenses", len(expenses))
                with col3:
                    receipt_count = expenses[expenses['receipt_image'].notnull()].shape[0]
                    st.metric("Receipts Attached", receipt_count)
                
                # Prepare display data with image previews
                for _, expense in expenses.iterrows():
                    with st.container():
                        col1, col2, col3 = st.columns([1, 3, 1])
                        
                        with col1:
                            if expense.get('receipt_image'):
                                # Display receipt image with expandable view
                                try:
                                    # Convert blob back to image for display
                                    image_data = expense['receipt_image']
                                    if image_data:
                                        image = Image.open(io.BytesIO(image_data))
                                        st.image(image, width=400, caption="Receipt")
                                        
                                        # Full size expandable view
                                        with st.expander("🔍 View Full Receipt"):
                                            st.image(image, use_container_width=True)
                                except Exception as e:
                                    st.write("📷 (Image unavailable)")
                            else:
                                st.write("❌ No receipt")
                        
                        with col2:
                            amount = expense.get('amount', 0)
                            amount_color = "red" if amount < 0 else "black"
                            st.write(f"**{expense.get('description', 'No description')}**")
                            st.write(f"**Amount:** <span style='color:{amount_color}'>${amount:.2f}</span>", unsafe_allow_html=True)
                            st.write(f"**Date:** {expense.get('created_at', '')[:16]}")
                        
                        with col3:
                            st.write(f"**ID:** {expense.get('id', '')}")
                        
                        st.divider()
                
                # Export button
                if st.button("📊 Export CSV", use_container_width=True):
                    self._export_expenses(expenses)
                
            else:
                st.info("No expenses recorded yet. Add your first expense above!")
                
        except Exception as e:
            st.error(f"Error loading expenses: {e}")

    def _export_expenses(self, expenses):
        """Export expenses to CSV"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"expenses_export_{timestamp}.csv"
            
            # Create clean export data
            export_data = expenses[['created_at', 'description', 'amount']].copy()
            export_data.columns = ['Date', 'Description', 'Amount']
            export_data['Date'] = export_data['Date'].str[:16]
            
            csv_data = export_data.to_csv(index=False)
            
            st.download_button(
                label="⬇️ Download Expenses CSV",
                data=csv_data,
                file_name=filename,
                mime="text/csv",
                key="download_expenses"
            )
            
            st.success(f"✅ Export ready! {len(expenses)} expenses.")
            
        except Exception as e:
            st.error(f"Error exporting expenses: {e}")