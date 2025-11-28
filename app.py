import streamlit as st
import pandas as pd
import re
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image

st.set_page_config(page_title="Selfridges PO (HD OCR)", layout="wide")
st.title("Selfridges PO Converter (High-Def OCR)")
st.info("Scanning at 300 DPI for maximum accuracy. This takes a few seconds per page.")

uploaded_file = st.file_uploader("Upload Selfridges PO PDF", type="pdf")

if uploaded_file is not None:
    try:
        # 1. CONVERT PDF TO IMAGES AT 300 DPI (Crucial for Page 2 and EANs)
        # ------------------------------------------------------------------
        images = convert_from_bytes(uploaded_file.read(), dpi=300)
        
        all_text_content = ""
        
        # 2. EXTRACT TEXT FROM EACH PAGE
        # ------------------------------------------------------------------
        progress_bar = st.progress(0)
        
        for i, image in enumerate(images):
            progress_bar.progress((i + 1) / len(images), text=f"Processing Page {i+1}...")
            
            # Convert to grayscale to improve text contrast
            gray_image = image.convert('L')
            
            # Extract text
            page_text = pytesseract.image_to_string(gray_image)
            all_text_content += page_text + "\n"

        # 3. PARSE THE TEXT
        # ------------------------------------------------------------------
        extracted_data = []
        lines = all_text_content.split('\n')
        
        for i, line in enumerate(lines):
            clean_line = line.strip()
            if not clean_line: continue

            # Common OCR Fixes (replace letters that look like numbers)
            # This helps fix prices like 18.44 appearing as l8.44
            line_fixed = clean_line.replace('l', '1').replace('O', '0').replace('o', '0')

            # PATTERN: Look for lines ending with TWO decimal numbers
            # Example: "24    18.44    442.56"
            # Regex captures: (Unit Cost) (Space) (Total Cost) (End of Line)
            cost_match = re.search(r"(\d+\.\d{2})\s+(\d{1,3}(?:,\d{3})*\.\d{2})$", line_fixed)
            
            if cost_match:
                line_cost = cost_match.group(2)
                unit_cost = cost_match.group(1)
                
                # Get everything before the costs
                remaining = clean_line[:cost_match.start()].strip()
                parts = remaining.split()
                
                # We need at least 2 parts (SKU and Qty)
                if len(parts) >= 2:
                    qty_candidate = parts[-1]
                    # Filter purely for digits (removes 'PC' or 'EA' noise if attached)
                    qty = ''.join(filter(str.isdigit, qty_candidate))
                    
                    if not qty: continue 

                    # Identify Line Number and SKU
                    line_num = ""
                    sku = ""
                    
                    # Heuristic: Line Number is usually 1-3 digits at the start
                    if parts[0].isdigit() and len(parts[0]) <= 3:
                        line_num = parts[0]
                        if len(parts) > 1:
                            sku = parts[1]
                    else:
                        # If Line number is missing/merged, assume first part is SKU
                        sku = parts[0]

                    # -------------------------------------------------------
                    # FIND DESCRIPTION & EAN (Look at next 6 lines)
                    # -------------------------------------------------------
                    description = ""
                    ean = ""
                    
                    # Look ahead up to 6 lines (generous buffer)
                    next_lines = lines[i+1 : i+7]
                    
                    for nl in next_lines:
                        nl_stripped = nl.strip()
                        if not nl_stripped: continue
                        
                        # Stop searching if we hit the next product (starts with digit, ends with price)
                        if re.match(r"^\d+", nl_stripped) and re.search(r"\d+\.\d{2}$", nl_stripped):
                            break
                        
                        # EAN FINDER:
                        # Look for any 12 to 14 digit number anywhere in these lines
                        # We do NOT require the word "EAN" to be present, as OCR often misses it.
                        ean_candidates = re.findall(r"\b(\d{12,14})\b", nl_stripped)
                        if ean_candidates:
                            ean = ean_candidates[0] # Take the first valid barcode found
                        
                        # DESCRIPTION FINDER:
                        # If it's not an EAN line and not a page header, it's likely the description
                        elif "CONTINUATION" not in nl_stripped and "PAGE:" not in nl_stripped:
                             if not description:
                                 description = nl_stripped

                    extracted_data.append({
                        "Line": line_num,
                        "Vendor Product Number": sku,
                        "Description": description,
                        "EAN No": ean,
                        "Qty": qty,
                        "Unit Cost": unit_cost,
                        "Line Cost": line_cost
                    })

        # 4. OUTPUT
        # ------------------------------------------------------------------
        if extracted_data:
            df = pd.DataFrame(extracted_data)
            
            # Sort by Line Number just in case they were read out of order
            # (Convert to numeric first for sorting)
            try:
                df['Line'] = pd.to_numeric(df['Line'])
                df = df.sort_values('Line')
            except:
                pass # If line numbers aren't clean, skip sorting

            st.success(f"Success! Found {len(df)} items.")
            st.dataframe(df)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, "Selfridges_PO_Final.csv", "text/csv")
        else:
            st.error("No items found. Please check the 'Raw Text' below.")
            with st.expander("Show Raw OCR Text for Debugging"):
                st.text(all_text_content)
            
    except Exception as e:
        st.error(f"Error: {str(e)}")
