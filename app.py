import streamlit as st
from pypdf import PdfReader
import pandas as pd
import re

st.title("Selfridges PO Converter (pypdf method)")

uploaded_file = st.file_uploader("Upload Selfridges PO PDF", type="pdf")

if uploaded_file is not None:
    extracted_data = []
    full_text_debug = ""
    
    try:
        reader = PdfReader(uploaded_file)
        
        # Combine text from all pages
        all_lines = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text_debug += text + "\n"
                # pypdf often returns text blocks differently, let's split by newlines
                all_lines.extend(text.split('\n'))
        
        # Debug View
        with st.expander("View Extracted Text"):
            st.text(full_text_debug)

        # Extraction Logic
        for i, line in enumerate(all_lines):
            clean_line = line.strip()
            
            # Find numbers (integers or decimals)
            # This captures 18.44 and 442.56
            numbers = re.findall(r'\d+\.\d{2}', clean_line)
            
            # We look for lines that have at least 2 decimal numbers (Unit Cost, Total Cost)
            if len(numbers) >= 2:
                # The last two decimal numbers are likely Unit Cost and Line Cost
                line_cost = numbers[-1]
                unit_cost = numbers[-2]
                
                # Now we try to find Qty (integer) appearing before the costs
                # We split the line and look for the last digit-only item before the costs
                parts = clean_line.split()
                qty = ""
                
                # Iterate backwards from the end to find the costs and then the Qty
                for part in reversed(parts):
                    if part == line_cost or part == unit_cost:
                        continue
                    if part.isdigit():
                        qty = part
                        break
                
                if qty:
                    # Everything before the Qty is the SKU / Line info
                    # Simple heuristic: Split line by Qty, take the left side
                    left_side = clean_line.split(qty)[0].strip()
                    
                    # Line number is the first word
                    line_parts = left_side.split()
                    line_num = line_parts[0] if line_parts else ""
                    sku = line_parts[1] if len(line_parts) > 1 else ""

                    # Description: Look at the NEXT line
                    description = ""
                    ean = ""
                    if i + 1 < len(all_lines):
                        next_line = all_lines[i+1]
                        if "EAN" in next_line:
                             # Sometimes description is skipped or on same line?
                             pass
                        else:
                             description = next_line.strip()
                    
                    # EAN: Look at next 2-3 lines
                    for nl in all_lines[i+1:i+4]:
                        if "EAN" in nl:
                            ean_match = re.search(r"(\d{12,14})", nl)
                            if ean_match:
                                ean = ean_match.group(1)

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
            st.error("No data found.")
            st.write("If the 'View Extracted Text' box above is empty, your PDF is an image/scan and cannot be read by this tool.")

    except Exception as e:
        st.error(f"An error occurred: {e}")
