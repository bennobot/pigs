import streamlit as st
import pdfplumber
import pandas as pd
import re

st.title("Selfridges PO to CSV Converter")

# File uploader
uploaded_file = st.file_uploader("Upload Selfridges PO PDF", type="pdf")

if uploaded_file is not None:
    extracted_data = []
    
    with pdfplumber.open(uploaded_file) as pdf:
        # Combine text from all pages into one big list of lines
        all_text = ""
        for page in pdf.pages:
            extracted_text = page.extract_text()
            if extracted_text:
                all_text += extracted_text + "\n"
        
        lines = all_text.split('\n')
        
        # Regex to find the start of a line item.
        # It looks for: Start of line -> Number -> Space -> SKU (Letters/Numbers)
        # Example: "1 L-WHBOCLCO..."
        item_start_pattern = re.compile(r"^\s*(\d+)\s+([A-Z0-9-]+)")
        
        for i, line in enumerate(lines):
            match = item_start_pattern.match(line)
            
            # If we find a line starting with a number and SKU
            if match:
                line_num = match.group(1)
                sku = match.group(2)
                
                # Extract the numbers at the end of the line (Qty, Unit Cost, Total Cost)
                # We look for decimal numbers or integers at the end of the string
                # Example end of line: "... 24 18.44 442.56"
                numbers = re.findall(r"(\d+(?:\.\d{2})?)", line)
                
                # We expect at least 3 numbers at the end (Qty, Unit Cost, Line Cost)
                if len(numbers) >= 3:
                    line_cost = numbers[-1]
                    unit_cost = numbers[-2]
                    qty = numbers[-3]
                    
                    # -----------------------------------------------
                    # GET DESCRIPTION (Usually the NEXT line)
                    # -----------------------------------------------
                    description = ""
                    if i + 1 < len(lines):
                        # The description is on the line immediately following the SKU line
                        description_line = lines[i+1].strip()
                        # Verify it's not a new item or an EAN line
                        if "EAN NO" not in description_line and not item_start_pattern.match(description_line):
                            description = description_line

                    # -----------------------------------------------
                    # GET EAN (Usually 2 lines down, containing "EAN NO")
                    # -----------------------------------------------
                    ean = ""
                    # Check line i+1 (if desc was short) or i+2
                    check_range = lines[i+1:i+4] # Look at next 3 lines just to be safe
                    for subline in check_range:
                        if "EAN NO" in subline:
                            # Extract just the digits from the EAN line
                            ean_match = re.search(r"EAN NO:\s*(\d+)", subline)
                            if ean_match:
                                ean = ean_match.group(1)
                            break

                    extracted_data.append({
                        "Line": line_num,
                        "Vendor Product Number": sku,
                        "Description": description,
                        "EAN No": ean,
                        "Qty": qty,
                        "Unit Cost (GBP)": unit_cost,
                        "Line Cost (GBP)": line_cost
                    })

    # Output results
    if extracted_data:
        df = pd.DataFrame(extracted_data)
        
        # Show a preview on screen
        st.success(f"Successfully extracted {len(df)} line items.")
        st.dataframe(df)
        
        # Create CSV download
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="Selfridges_PO_Converted.csv",
            mime="text/csv",
        )
    else:
        st.error("No line items found. Please ensure this is a standard Selfridges PO.")
