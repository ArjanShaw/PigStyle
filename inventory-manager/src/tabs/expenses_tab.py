import streamlit as st
import pandas as pd
from datetime import datetime
import io

class ExpensesTab:
    def __init__(self):
        pass
    
    def render(self):
        st.header("💰 Expenses")
        
        tab1, tab2 = st.tabs(["➕ Add Expense", "📋 View Expenses"])
        
        with tab1:
            self._render_add_expense()
        
        with tab2:
            self._render_view_expenses()

    def _render_add_expense(self):
        """Render the add expense form"""
        st.subheader("Add New Expense")
        
        with st.form(key="expense_form"):
            description = st.text_input(
                "Description",
                placeholder="Enter expense description..."
            )
            
            amount = st.number_input(
                "Amount",
                min_value=0.0,
                step=0.01,
                format="%.2f",
                help="Enter the expense amount"
            )
            
            # Camera input for receipt photo
            st.write("**Receipt Photo:**")
            camera_input = st.camera_input(
                "Take a photo of the receipt",
                help="Use your camera to take a photo of the receipt"
            )
            
            # File uploader as fallback
            receipt_upload = st.file_uploader(
                "Or upload receipt photo",
                type=['jpg', 'jpeg', 'png'],
                help="Upload a photo of the receipt"
            )
            
            submitted = st.form_submit_button("Save Expense", use_container_width=True)
            
            if submitted:
                if not description:
                    st.error("Please enter a description")
                    return
                
                if amount <= 0:
                    st.error("Please enter a valid amount")
                    return
                
                try:
                    # Use camera input if available, otherwise use file upload
                    receipt_bytes = None
                    if camera_input is not None:
                        receipt_bytes = camera_input.getvalue()
                    elif receipt_upload is not None:
                        receipt_bytes = receipt_upload.getvalue()
                    
                    # Save to database
                    expense_id = st.session_state.db_manager.save_expense(description, amount, receipt_bytes)
                    
                    if expense_id:
                        st.success(f"✅ Expense saved! Amount: ${amount:.2f}")
                        st.rerun()
                    else:
                        st.error("Failed to save expense")
                        
                except Exception as e:
                    st.error(f"Error saving expense: {e}")

    def _render_view_expenses(self):
        """Render the expenses list"""
        st.subheader("Expense History")
        
        try:
            expenses = st.session_state.db_manager.get_all_expenses()
            
            if len(expenses) > 0:
                # Calculate total
                total_amount = expenses['amount'].sum()
                
                # Display summary
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Expenses", f"${total_amount:.2f}")
                with col2:
                    st.metric("Number of Expenses", len(expenses))
                
                # Prepare display data
                display_data = []
                for _, expense in expenses.iterrows():
                    display_data.append({
                        'Date': expense.get('created_at', '')[:16],
                        'Description': expense.get('description', ''),
                        'Amount': f"${expense.get('amount', 0):.2f}",
                        'Receipt': "📷" if expense.get('receipt_image') else "❌"
                    })
                
                display_df = pd.DataFrame(display_data)
                
                # Configure columns
                column_config = {
                    'Date': st.column_config.TextColumn('Date', width='small'),
                    'Description': st.column_config.TextColumn('Description', width='medium'),
                    'Amount': st.column_config.TextColumn('Amount', width='small'),
                    'Receipt': st.column_config.TextColumn('Receipt', width='small'),
                }
                
                st.dataframe(
                    display_df,
                    column_config=column_config,
                    use_container_width=True,
                    hide_index=True
                )
                
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