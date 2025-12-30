"""
Handles generation of consignment contracts and batch receipts
"""
import streamlit as st
from datetime import datetime
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import mm, inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
import tempfile

class ContractHandler:
    def __init__(self, api_client):
        self.api_client = api_client
        self.styles = getSampleStyleSheet()
        
    def generate_consignment_contract(self, user_data, batch_data, store_credit_option=False):
        """Generate consignment contract PDF for download"""
        
        # Create temp file for PDF
        temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        output_path = temp_file.name
        temp_file.close()
        
        # Create PDF document
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Build story (content)
        story = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1  # Center
        )
        story.append(Paragraph("PIGSTYLE RECORDS CONSIGNMENT AGREEMENT", title_style))
        story.append(Spacer(1, 20))
        
        # Agreement Details
        details_style = ParagraphStyle(
            'Details',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=6
        )
        
        current_date = datetime.now().strftime('%Y-%m-%d')
        commission_rate = batch_data.get('commission_rate', 0.20) * 100
        
        details = [
            f"<b>Agreement Date:</b> {current_date}",
            f"<b>Consignor ID:</b> {user_data.get('id', '')}",
            f"<b>Consignor Name:</b> {user_data.get('full_name', user_data.get('username', ''))}",
            f"<b>Consignor Email:</b> {user_data.get('email', '')}",
            f"<b>Consignor Phone:</b> {user_data.get('phone', 'Not provided')}",
            f"<b>Store Representative:</b> PigStyle Records",
            f"<b>Batch ID:</b> {batch_data.get('batch_id', 'N/A')}",
            f"<b>Total Items in Batch:</b> {batch_data.get('item_count', 0)}",
            f"<b>Estimated Total Value:</b> ${batch_data.get('total_value', 0):.2f}",
            f"<b>Check-in Date:</b> {current_date}",
            f"<b>Current Commission Rate:</b> {commission_rate:.1f}%",
            f"<b>Store Credit Option:</b> {'Yes (+20% bonus)' if store_credit_option else 'No'}"
        ]
        
        for detail in details:
            story.append(Paragraph(detail, details_style))
        
        story.append(Spacer(1, 30))
        
        # Terms and Conditions
        terms_title = ParagraphStyle(
            'TermsTitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=12
        )
        story.append(Paragraph("TERMS AND CONDITIONS", terms_title))
        
        # Terms content
        terms = self._get_terms_and_conditions()
        for term in terms:
            story.append(Paragraph(term, self.styles['Normal']))
            story.append(Spacer(1, 6))
        
        story.append(Spacer(1, 30))
        
        # Agreement Acceptance
        accept_title = ParagraphStyle(
            'AcceptTitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=12
        )
        story.append(Paragraph("AGREEMENT ACCEPTANCE", accept_title))
        
        acceptance_text = f"""
        I, <b>{user_data.get('full_name', user_data.get('username', ''))}</b>, hereby agree to the terms and conditions outlined above for the consignment of records to PigStyle Records.
        
        I certify that I am the legal owner of all items being consigned.
        
        I understand that I can monitor my sales and inventory status in real-time through the online portal.
        
        I agree to receive email notifications regarding my consignment items.
        """
        
        story.append(Paragraph(acceptance_text, self.styles['Normal']))
        story.append(Spacer(1, 40))
        
        # Signature lines
        sig_data = [
            ["_________________________________________", "_________________________________________"],
            ["Consignor Signature", "Store Representative Signature"],
            [f"Date: {current_date}", f"Date: {current_date}"]
        ]
        
        sig_table = Table(sig_data, colWidths=[3*inch, 3*inch])
        sig_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        story.append(sig_table)
        
        # Build PDF
        doc.build(story)
        
        # Read file back
        with open(output_path, 'rb') as f:
            pdf_data = f.read()
        
        # Clean up temp file
        os.unlink(output_path)
        
        return pdf_data
    
    def generate_batch_receipt(self, user_data, records, commission_rate, store_credit_option=False):
        """Generate thermal printer receipt for batch check-in"""
        
        # Create receipt text (formatted for thermal printer)
        receipt_lines = []
        
        # Header
        receipt_lines.append("═" * 40)
        receipt_lines.append("PIGSTYLE RECORDS RECEIPT".center(40))
        receipt_lines.append("═" * 40)
        
        # Receipt details
        receipt_number = f"PS{datetime.now().strftime('%Y%m%d%H%M%S')}"
        current_date = datetime.now().strftime('%Y-%m-%d')
        current_time = datetime.now().strftime('%H:%M')
        
        receipt_lines.append(f"Receipt #: {receipt_number}")
        receipt_lines.append(f"Date: {current_date}")
        receipt_lines.append(f"Time: {current_time}")
        receipt_lines.append(f"Consignor ID: {user_data.get('id', '')}")
        receipt_lines.append(f"Consignor: {user_data.get('full_name', user_data.get('username', ''))}")
        receipt_lines.append("─" * 40)
        receipt_lines.append("ITEMS ACCEPTED".center(40))
        receipt_lines.append("─" * 40)
        
        # Item list
        total_value = 0
        for i, record in enumerate(records, 1):
            artist = record.get('artist', 'Unknown')[:15]
            title = record.get('title', 'Unknown')[:20]
            price = record.get('store_price', 0)
            catalog = record.get('catalog_number', 'N/A')[:8]
            condition = record.get('condition', 'N/A')
            
            receipt_lines.append(f"{i:2}. {artist} - {title}")
            receipt_lines.append(f"    ${price:>6.2f} | Cat: {catalog} | Cond: {condition}")
            total_value += price
        
        receipt_lines.append("─" * 40)
        receipt_lines.append(f"Total Items: {len(records)}")
        receipt_lines.append(f"Est. Total Value: ${total_value:.2f}")
        receipt_lines.append(f"Commission Rate: {commission_rate*100:.1f}%")
        receipt_lines.append(f"Store Credit Bonus: {'Yes (+20%)' if store_credit_option else 'No'}")
        receipt_lines.append("─" * 40)
        receipt_lines.append("CONSIGNMENT TERMS".center(40))
        receipt_lines.append("─" * 40)
        receipt_lines.append("• 180-day consignment period")
        receipt_lines.append("• 90 days at your price")
        receipt_lines.append("• After 90 days, may discount")
        receipt_lines.append("  up to 50%")
        receipt_lines.append("• Weekly status emails")
        receipt_lines.append("• 30-day pickup for unsold")
        receipt_lines.append("─" * 40)
        receipt_lines.append("Monitor sales at:")
        receipt_lines.append("portal.pigstyle.com")
        receipt_lines.append("Questions:")
        receipt_lines.append("contact@pigstylerecords.com")
        receipt_lines.append("═" * 40)
        
        # Join lines
        receipt_text = "\n".join(receipt_lines)
        
        # Also generate PDF version
        pdf_receipt = self._generate_receipt_pdf(
            user_data, records, receipt_number, 
            commission_rate, store_credit_option
        )
        
        return receipt_text, pdf_receipt, receipt_number
    
    def _generate_receipt_pdf(self, user_data, records, receipt_number, commission_rate, store_credit_option):
        """Generate PDF version of receipt"""
        temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        output_path = temp_file.name
        temp_file.close()
        
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )
        
        story = []
        
        # Header
        header_style = ParagraphStyle(
            'Header',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceAfter=12,
            alignment=1
        )
        story.append(Paragraph("PIGSTYLE RECORDS RECEIPT", header_style))
        
        # Details
        details_style = ParagraphStyle(
            'ReceiptDetails',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=4
        )
        
        current_date = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        details = [
            f"<b>Receipt #:</b> {receipt_number}",
            f"<b>Date:</b> {current_date}",
            f"<b>Consignor ID:</b> {user_data.get('id', '')}",
            f"<b>Consignor:</b> {user_data.get('full_name', user_data.get('username', ''))}",
            f"<b>Commission Rate:</b> {commission_rate*100:.1f}%",
            f"<b>Store Credit Bonus:</b> {'Yes (+20%)' if store_credit_option else 'No'}"
        ]
        
        for detail in details:
            story.append(Paragraph(detail, details_style))
        
        story.append(Spacer(1, 20))
        
        # Item Table
        table_data = [['No.', 'Artist', 'Title', 'Catalog', 'Condition', 'Price']]
        total_value = 0
        
        for i, record in enumerate(records, 1):
            artist = record.get('artist', 'Unknown')
            title = record.get('title', 'Unknown')
            catalog = record.get('catalog_number', 'N/A')
            condition = record.get('condition', 'N/A')
            price = record.get('store_price', 0)
            total_value += price
            
            table_data.append([
                str(i),
                artist[:20],
                title[:25],
                catalog[:10],
                condition,
                f"${price:.2f}"
            ])
        
        # Add total row
        table_data.append(['', '', '', '', 'Total:', f"${total_value:.2f}"])
        
        item_table = Table(table_data, colWidths=[0.5*inch, 1.5*inch, 2*inch, 1*inch, 1*inch, 1*inch])
        item_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (5, 1), (5, -1), 'RIGHT'),
            ('BACKGROUND', (-2, -1), (-1, -1), colors.lightgrey),
            ('FONTNAME', (-2, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        
        story.append(item_table)
        story.append(Spacer(1, 20))
        
        # Terms section
        terms_title = ParagraphStyle(
            'ReceiptTermsTitle',
            parent=self.styles['Heading3'],
            fontSize=12,
            spaceAfter=8
        )
        story.append(Paragraph("Consignment Terms", terms_title))
        
        terms = [
            "• 180-day consignment period total",
            "• 90 days at consignor's set price",
            "• After 90 days, items may be discounted up to 50%",
            "• Weekly email status updates",
            "• 30 days to pick up unsold items after removal",
            "• Items not picked up within 30 days become store property"
        ]
        
        for term in terms:
            story.append(Paragraph(term, self.styles['Normal']))
            story.append(Spacer(1, 4))
        
        story.append(Spacer(1, 20))
        
        # Contact info
        contact_style = ParagraphStyle(
            'Contact',
            parent=self.styles['Normal'],
            fontSize=9,
            alignment=1,
            textColor=colors.grey
        )
        
        contact_info = [
            "Monitor your sales at: portal.pigstyle.com",
            "Questions? contact@pigstylerecords.com",
            "Keep this receipt for your records"
        ]
        
        for info in contact_info:
            story.append(Paragraph(info, contact_style))
        
        # Build PDF
        doc.build(story)
        
        # Read file back
        with open(output_path, 'rb') as f:
            pdf_data = f.read()
        
        # Clean up
        os.unlink(output_path)
        
        return pdf_data
    
    def _get_terms_and_conditions(self):
        """Return list of terms and conditions paragraphs"""
        return [
            "<b>1. Item Eligibility</b>",
            "• Items must be Discogs VG (Very Good) grade or above",
            "• Store accepts only unique records (duplicates will be rejected)",
            "• Singles, counterfeits/bootlegs, or rare/high-value items requiring appraisal may be rejected",
            "• Store reserves right to reject any item deemed unsellable or undesirable",
            "",
            "<b>2. Consignment Period</b>",
            "• 180-day term total",
            "• 90 days at consignor's set price",
            "• After 90 days, items may be discounted up to 50% (with 14-day email notice)",
            "• Consignor may remove items or terminate contract early at any time via online portal",
            "",
            "<b>3. Pricing</b>",
            "• Consignor sets price via online portal",
            "• Maximum allowable price: 130% of advised price (based on Discogs + eBay data)",
            "• Price reductions after 90 days as described above",
            "",
            "<b>4. Commission Structure</b>",
            "• Variable commission based on store inventory capacity:",
            "  * 10% at ≤60% capacity",
            "  * Linearly increasing to 40% at 110% capacity",
            "  * +20% commission bonus for choosing store credit payout",
            "",
            "<b>5. Payment Terms</b>",
            "• Payout available upon request via portal once balance reaches $10.00 minimum",
            "• Maximum payout frequency: once per month",
            "• Payout method: Check / Store Credit",
            "",
            "<b>6. Item Intake Process</b>",
            "• Consignor submits items via online portal first",
            "• Physical inspection required at store before acceptance",
            "• Consignor self-grades items; store verifies during check-in",
            "• Inaccurate grading is grounds for rejection",
            "",
            "<b>7. Unsold Items</b>",
            "• After removal from shelves, consignor has 30 days to pick up items",
            "• Weekly email reminders sent",
            "• Items not picked up within 30 days become store property",
            "",
            "<b>8. Liability</b>",
            "• Store covers: missing items, visible damage missed at intake, burglary, natural disasters, shoplifting",
            "• Consignor responsible for: invisible defects (e.g., skips), assumed pre-existing",
            "• Affected records returned to consignor as unsold",
            "",
            "<b>9. Consignor Responsibilities</b>",
            "• Certify legal ownership of all items",
            "• Keep contact information current",
            "• Pick up unsold/returned items within 30-day deadline",
            "",
            "<b>10. Cleaning Service</b>",
            "• Records should be clean at intake",
            "• Store offers cleaning service at discounted rate (billed separately)",
        ]