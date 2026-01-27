from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.units import inch

# Full path to your TTF font
font_path = "/home/arjan-ubuntu/Documents/keep-on-truckin/KEEPT___.TTF"

# Register the font
pdfmetrics.registerFont(TTFont("KeepOnTruckin", font_path))

# Output PDF
output_file = "/home/arjan-ubuntu/Documents/psychedelic_words_custom.pdf"

# List of words
words = [
    "Loveland's Coolest Record Store"
]

# Desired font height: 6 inches
font_size = 6 * 72  # 432 points
horizontal_margin = 72  # 1 inch
vertical_margin = 72    # 1 inch

# Create canvas
c = canvas.Canvas(output_file)

# Function to add a word page
def add_word_page(word, font_size=432, subscript_text=None, subscript_size=36):
    # Measure text width
    text_width = pdfmetrics.stringWidth(word, "KeepOnTruckin", font_size)
    
    # Custom page width = text width + horizontal margins
    page_width = text_width + 2 * horizontal_margin
    
    # Adjust page height if there's subscript
    if subscript_text:
        subscript_width = pdfmetrics.stringWidth(subscript_text, "KeepOnTruckin", subscript_size)
        page_height = font_size + 2 * vertical_margin + subscript_size
    else:
        page_height = font_size + 2 * vertical_margin
    
    # Set page size dynamically
    c.setPageSize((page_width, page_height))
    
    # Draw the main word centered
    x = (page_width - text_width) / 2
    y = (page_height - font_size) / 2
    c.setFont("KeepOnTruckin", font_size)
    # ADD THIS LINE TO SET RED COLOR (RGB values: 1,0,0 = pure red)
    c.setFillColorRGB(1, 0, 0)  # Makes the text red
    c.drawString(x, y, word)
    
    # Draw subscript if provided
    if subscript_text:
        subscript_x = (page_width - subscript_width) / 2
        subscript_y = y - subscript_size - 10  # 10 points below main text
        c.setFont("KeepOnTruckin", subscript_size)
        # Also set red for subscript if you want it red too
        c.setFillColorRGB(1, 0, 0)  # Makes the subscript text red
        c.drawString(subscript_x, subscript_y, subscript_text)
    
    c.showPage()

# Add all the original words
for word in words:
    add_word_page(word)

c.save()
print(f"PDF created: {output_file}")