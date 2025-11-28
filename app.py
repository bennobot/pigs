import streamlit as st
import pandas as pd
import re
import pytesseract
from pdf2image import convert_from_bytes
from io import BytesIO

st.set_page_config(page_title="Selfridges PO (OCR)")
st.title("Selfridges PO Converter (OCR Method)")
st.info("This method reads the PDF as an image (like a scanner). It may take 10-20 seconds.")

uploaded_file = st.file_uploader("Upload Selfridges PO PDF", type="pdf")

if uploaded_file is not None:
    try:
        # Convert PDF to Images (One image per page)
        images = convert_from_bytes(uploaded_file.read())
        
        all_text_content = ""
        extracted_data = []

        # Extract text from images using Tesseract OCR
        progress_bar = st.progress(0)
        for i, image in enumerate(images):
            # Update progress
            progress_bar.progress((i + 1) / len(images))
            # Extract text
            text = pytesseract.image_to_string(image)
            all_text_content += text + "\n"

        # Show raw text for validation
        with st.expander("Show OCR Extracted Text"):
            st.text(all_text_content)

        # Process the text line by line
        lines = all_text_content.split('\n')
        
        for i, line in enumerate(lines):
            clean_line = line.strip()
            if not clean_line: continue

            # Regex: Look for lines ending in two prices (e.g., "18.44 442.56")
            # OCR sometimes confuses dots with commas or spaces, so we are flexible
            # Looking for: Number -> Space -> Number -> End of line
            # We also replace common OCR glitches (like 'O' instead of '0')
            
            clean_line_fixed = clean_line.replace('O', '0').replace('l', '1') # Basic OCR fixes
            
            # Pattern: (Float) space (Float) at end of string
            cost_match = re.search(r"(\d+\.\d{2})\s+(\d{1,3}(?:,\d{3})*\.\d{2})$", clean_line_fixed)
            
            if cost_match:
                line_cost = cost_match.group(2)
                unit_cost = cost_match.group(1)
                
                # Get everything before the costs
                remaining = clean_line[:cost_match.start()].strip()
                parts = remaining.split()
                
                if len(parts) >= 2:
                    qty = parts[-1]
                    # Filter out non-digits from qty (OCR noise)
                    qty = ''.join(filter(str.isdigit, qty))
                    
                    if not qty: continue # Skip if qty became empty

                    # SKU / Line
                    # Assuming first part is Line Num, Second is SKU
                    line_num = parts[0]
                    sku = parts[1] if len(parts) > 1 else ""

                    # Description & EAN Search (Look ahead)
                    description = ""
                    ean = ""
                    
                    # Look at next 4 lines
                    next_lines = lines[i+1 : i+5]
                    for nl in next_lines:
                        if "EAN" in nl:
                             # Extract digits
                             ean_match = re.search(r"(\d{12,14})", nl)
                             if ean_match: ean = ean_match.group(1)
                        elif "WHITEBOX" in nl.upper() or "MARTINI" in nl.upper():
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
            st.success(f"OCR Successful! Found {len(df)} items.")
            st.dataframe(df)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, "Selfridges_PO.csv", "text/csv")
        else:
            st.error("No items found. The image quality might be too low or the layout is unique.")
            
    except Exception as e:
        st.error(f"Error: {str(e)}")
        st.write("Ensure 'poppler-utils' and 'tesseract-ocr' are in packages.txt")
