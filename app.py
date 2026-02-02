import streamlit as st
import pandas as pd
import re
import pytesseract
from pdf2image import convert_from_bytes

st.set_page_config(page_title="Selfridges PO (PSM6 Fix)", layout="wide")
st.title("Selfridges PO Converter (Layout Fix)")
st.info("Applying 'Single Block' extraction mode to fix column misalignment.")

uploaded_file = st.file_uploader("Upload Selfridges PO PDF", type="pdf")

if uploaded_file is not None:
    try:
        # 1. Convert PDF to Images (300 DPI for clarity)
        images = convert_from_bytes(uploaded_file.read(), dpi=300)
        
        all_text_content = ""
        
        # 2. Configure OCR to force Left-to-Right reading
        # --psm 6 assumes a single uniform block of text. 
        # This stops it from reading columns top-to-bottom.
        custom_config = r'--psm 6'
        
        for i, image in enumerate(images):
            # Convert to grayscale
            gray_image = image.convert('L')
            
            # Extract with the specific config
            page_text = pytesseract.image_to_string(gray_image, config=custom_config)
            all_text_content += page_text + "\n"

        # Show the user the fixed layout
        with st.expander("Check Raw Text (Should now be aligned Left-to-Right)"):
            st.text(all_text_content)

        # 3. Parse the data
        extracted_data = []
        lines = all_text_content.split('\n')
        
        for i, line in enumerate(lines):
            clean_line = line.strip()
            if not clean_line: continue

            # Fix OCR common errors
            line_fixed = clean_line.replace('l', '1').replace('O', '0').replace('o', '0')

            # Look for the Line Item pattern:
            # Starts with a Line Number (1-3 digits) -> Space -> SKU -> ... -> Two Prices at end
            
            # Regex Explanation:
            # ^(\d{1,3})       = Start with 1-3 digits (Line Num)
            # \s+              = Space
            # ([A-Z0-9-]+)     = SKU (Letters, numbers, dashes)
            # .*               = Anything in middle (Qty, etc)
            # (\d+\.\d{2})     = Unit Cost (18.44)
            # \s+              = Space
            # (\d{1,3}(?:,\d{3})*\.\d{2})$ = Line Cost (442.56)
            
            match = re.search(r"^(\d{1,3})\s+([A-Z0-9-]+).*\s+(\d+\.\d{2})\s+(\d{1,3}(?:,\d{3})*\.\d{2})$", line_fixed)
            
            if match:
                line_num = match.group(1)
                sku = match.group(2)
                unit_cost = match.group(3)
                line_cost = match.group(4)
                
                # Qty is the number right before the unit cost in the middle section
                # We grab the text between SKU and Unit Cost
                # "L-WH...   EA 1 24   18.44"
                middle_section = line_fixed.split(sku)[1].split(unit_cost)[0]
                
                # Find the last number in that middle section
                qty_candidates = re.findall(r"\d+", middle_section)
                qty = qty_candidates[-1] if qty_candidates else ""

                # ----------------------------------------
                # FIND DESCRIPTION & EAN (Look at next 5 lines)
                # ----------------------------------------
                description = ""
                ean = ""
                
                next_lines = lines[i+1 : i+6]
                for nl in next_lines:
                    nl_clean = nl.strip()
                    if not nl_clean: continue
                    
                    # Stop if we hit the next line item (starts with Line Number 8, 9, 10...)
                    if re.match(r"^\d+\s+[A-Z]", nl_clean):
                        break

                    # EAN Finder
                    ean_match = re.search(r"(\d{12,14})", nl_clean)
                    if ean_match:
                        ean = ean_match.group(1)
                    
                    # Description Finder
                    # It's usually the line that isn't the EAN and isn't a page header
                    elif "EAN" not in nl_clean and "PAGE" not in nl_clean and "CONTINUATION" not in nl_clean:
                        # Avoid capturing garbage like "UN PKSZ QTY" header
                        if "VENDOR PRODUCT" not in nl_clean and not description:
                             description = nl_clean

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
            
            # Sort numerically by Line
            df['Line'] = pd.to_numeric(df['Line'], errors='coerce')
            df = df.sort_values('Line')

            st.success(f"Success! Found {len(df)} items.")
            st.dataframe(df)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, "Selfridges_PO_Fixed.csv", "text/csv")
        else:
            st.error("No items found.")
            with st.expander("Debug Text"):
                st.text(all_text_content)
                
    except Exception as e:
        st.error(f"Error: {str(e)}")
