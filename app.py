import streamlit as st
import pandas as pd
import re
import pytesseract
from pdf2image import convert_from_bytes

st.set_page_config(page_title="Selfridges PO (OCR - MultiPage)", layout="wide")
st.title("Selfridges PO Converter (OCR - MultiPage Fix)")

uploaded_file = st.file_uploader("Upload Selfridges PO PDF", type="pdf")

if uploaded_file is not None:
    try:
        # Reset file pointer to be safe
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        
        # Convert PDF to Images
        # We explicitly ask for all pages
        images = convert_from_bytes(file_bytes)
        
        st.info(f"PDF Loaded. Detected {len(images)} pages.")
        
        all_text_content = ""
        
        # Extract text from EACH page
        progress_bar = st.progress(0)
        for i, image in enumerate(images):
            status_text = f"Scanning Page {i+1} of {len(images)}..."
            progress_bar.progress((i + 1) / len(images), text=status_text)
            
            # Extract text
            page_text = pytesseract.image_to_string(image)
            
            # Add a marker so we know where pages end in the raw text (for debugging)
            all_text_content += f"\n--- PAGE {i+1} START ---\n"
            all_text_content += page_text
            all_text_content += f"\n--- PAGE {i+1} END ---\n"

        # Debug: Show the user exactly what was read from ALL pages
        with st.expander("View Raw OCR Text (Check if Page 2 data is here)"):
            st.text(all_text_content)

        extracted_data = []
        lines = all_text_content.split('\n')
        
        for i, line in enumerate(lines):
            clean_line = line.strip()
            if not clean_line: continue

            # OCR Fixes: 0 vs O, l vs 1
            clean_line_fixed = clean_line.replace('O', '0').replace('l', '1')

            # Regex: Look for lines ending in two prices (Unit Cost and Line Cost)
            # Matches: 18.44 442.56
            cost_match = re.search(r"(\d+\.\d{2})\s+(\d{1,3}(?:,\d{3})*\.\d{2})$", clean_line_fixed)
            
            if cost_match:
                line_cost = cost_match.group(2)
                unit_cost = cost_match.group(1)
                
                # Get text before the costs
                remaining = clean_line[:cost_match.start()].strip()
                parts = remaining.split()
                
                # Needs to be at least "LineNum SKU Qty" (3 parts) 
                # or just "SKU Qty" if line number is merged
                if len(parts) >= 2:
                    qty_candidate = parts[-1]
                    # Clean non-digits from Qty (OCR noise)
                    qty = ''.join(filter(str.isdigit, qty_candidate))
                    
                    if not qty: continue 

                    # Attempt to find Line Number and SKU
                    line_num = ""
                    sku = ""
                    
                    # Heuristic: If first part is small number (1-3 digits), it's Line Number
                    if parts[0].isdigit() and len(parts[0]) <= 3:
                        line_num = parts[0]
                        if len(parts) > 1:
                            sku = parts[1]
                    else:
                        # Maybe Line number is missing or merged? Take first part as SKU
                        sku = parts[0]

                    # Description & EAN Lookahead
                    description = ""
                    ean = ""
                    
                    # Look at next 5 lines
                    next_lines = lines[i+1 : i+6]
                    for nl in next_lines:
                        # Skip page markers
                        if "--- PAGE" in nl: continue
                        
                        # Stop if we hit a new item line (starts with digit, ends with price)
                        if re.match(r"^\d+", nl.strip()) and re.search(r"\d+\.\d{2}$", nl.strip()):
                            break
                            
                        if "EAN" in nl:
                             ean_match = re.search(r"(\d{12,14})", nl)
                             if ean_match: ean = ean_match.group(1)
                        elif "WHITEBOX" in nl.upper() or "MARTINI" in nl.upper() or "NO COLOUR" in nl.upper():
                             if not description: description = nl.strip()
                    
                    extracted_data.append({
                        "Line": line_num,
                        "Vendor Product Number": sku,
                        "Description": description,
                        "EAN No": ean,
                        "Qty": qty,
                        "Unit Cost": unit_cost,
                        "Line Cost": line_cost
                    })

        if extracted_data:
            df = pd.DataFrame(extracted_data)
            st.success(f"Success! Found {len(df)} items across {len(images)} pages.")
            st.dataframe(df)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, "Selfridges_PO.csv", "text/csv")
        else:
            st.error("No items found.")
            
    except Exception as e:
        st.error(f"Error: {str(e)}")
