import pandas as pd

# Load CSVs
revise = pd.read_csv("/home/arjan-ubuntu/Downloads/eBay-edit-price-quantity-template-2025-10-16-11260725431.csv", skiprows=1)
draft = pd.read_csv("/home/arjan-ubuntu/Downloads/merged_ebay.csv", skiprows=1)

# Standardize SKU column
revise.rename(columns={"Custom label (SKU)": "SKU"}, inplace=True)
draft.rename(columns={"Custom label (SKU)": "SKU"}, inplace=True)

# Merge draft and revise on SKU, preferring draft data
merged = pd.merge(draft, revise[['SKU', 'Start price', 'Available quantity']], 
                  on='SKU', how='outer', suffixes=('_draft', '_revise'))

# Update Price and Quantity: prefer revise if present
merged['Price'] = merged['Start price'].combine_first(merged['Price'])
merged['Quantity'] = merged['Available quantity'].combine_first(merged['Quantity'])

# Drop temporary columns
merged.drop(columns=['Start price', 'Available quantity'], inplace=True)

# Remove exact duplicates (keeping the first occurrence)
merged = merged.drop_duplicates(subset=['SKU'])

# Save final CSV
merged.to_csv("merged_ebay.csv", index=False)
