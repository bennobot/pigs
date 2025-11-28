import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(layout="wide")
st.title("Selfridges PO Converter (Diagnostic Mode)")

uploaded_file = st.file_uploader("Upload Selfridges PO PDF", type="pdf")

if uploaded_file is not None:
    all_text_content = ""
    extracted_data = []

    with pdfplumber.open(uploaded_file) as pdf:
        all_lines = []
        for page in pdf.pages:
            # We use basic extraction first (often safer than layout=True for simple lists)
            text = page.extract_text()
            if text:
                all_text_content += text + "\n"
                all_lines.extend(text.split('\n'))

    # --- SHOW RAW TEXT FOR DEBUGGING ---
    with st.expander("Show Raw PDF Text (Click to Expand)", expanded=False):
        st.text_area("This is exactly what the computer sees:", all_text_content, height=200)

    # --- EXTRACTION LOGIC ---
    for i, line in enumerate(all_lines):
        # Clean the line
        clean_line = line.strip()
        if not clean_line:
            continue

        # Strategy: Find all numbers in the line
        # This matches integers (24) and decimals (18.44) and totals (1,000.00)
        # Regex: Optional comma, optional dot
        numbers_found = re.findall(r'\d+(?:,\d{3})*(?:\.\d+)?', clean_line)

        # A valid data line in your PO typically has at least 5 numbers:
        # 1. Line # (e.g., "1")
        # 2. Pack Size (e.g., "1" or "12")
        # 3. Qty (e.g., "24")
        # 4. Unit Cost (e.g., "18.44")
        # 5. Line Cost (e.g., "442.56")
        
        # We check if line starts with a Line Number and has enough numbers
        if len(numbers_found) >= 4 and clean_line[0].isdigit():
            
            # Extract based on position of numbers (from the right)
            line_cost = numbers_found[-1]
            unit_cost = numbers_found[-2]
            qty = numbers_found[-3]
            
            # The Line Number is likely the very first character/word
            line_num = numbers_found[0]
            
            # SKU is usually the text between Line Number and the Pack Size/Qty
            # This is tricky, so we grab the text between the first space and the "EA" or "UN" markers
            # Or simplified: The second "word" in the line
            parts = clean_line.split()
            sku = parts[1] if len(parts) > 1 else "Unknown"

            # --- DESCRIPTION & EAN LOOKUP ---
            description = ""
            ean = ""
            
            # Look at the next 4 lines
            # Be careful not to go out of bounds
            max_lookahead = min(len(all_lines), i + 5)
            next_lines = all_lines[i+1 : max_lookahead]
            
            for nl in next_lines:
                nl_clean = nl.strip()
                if not nl_clean: continue
                
                # Stop if we hit a new line starting with a number
                if nl_clean[0].isdigit() and len(re.findall(r'\d+', nl_clean)) > 2:
                    break
                
                if "EAN" in nl.upper():
                    ean_match = re.search(r"(\d{12,14})", nl)
                    if ean_match:
                        ean = ean_match.group(1)
                elif "WHITEBOX" in nl.upper() or "MARTINI" in nl.upper() or "NO COLOUR" in nl.upper():
                    # This is likely the description
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
        st.success(f"Success! Found {len(df)} items.")
        st.dataframe(df)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv, "Selfridges_PO.csv", "text/csv")
    else:
        st.error("Still no items found.")
        st.warning("Please copy the content from the 'Show Raw PDF Text' box above and share it, so I can adjust the logic.")
