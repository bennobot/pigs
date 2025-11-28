import streamlit as st
import pdfplumber
import pandas as pd
import re

st.title("Selfridges PO to CSV Converter (Robust)")

uploaded_file = st.file_uploader("Upload Selfridges PO PDF", type="pdf")

if uploaded_file is not None:
    extracted_data = []
    all_text_debug = "" # To store raw text for debugging
    
    with pdfplumber.open(uploaded_file) as pdf:
        # We iterate through all pages
        lines_list = []
        for page in pdf.pages:
            # layout=True helps keep columns separated by spaces
            text = page.extract_text(layout=True)
            if text:
                all_text_debug += f"--- PAGE {page.page_number} ---\n{text}\n"
                lines_list.extend(text.split('\n'))
        
        # LOGIC: Find lines that look like PO Items
        # A PO line usually ends with: Qty -> Unit Cost -> Total Cost
        # Example: "24    18.44    442.56"
        # We search for lines ending in 2 decimal numbers
        
        for i, line in enumerate(lines_list):
            clean_line = line.strip()
            
            # Skip empty lines
            if not clean_line:
                continue

            # Regex: Look for lines ending with (Float) (Space) (Float)
            # This captures: Unit Cost and Total Cost at the end of the line
            # Example match: "18.44     442.56"
            cost_pattern = re.search(r"(\d+\.\d{2})\s+(\d{1,3}(?:,\d{3})*\.\d{2})$", clean_line)
            
            if cost_pattern:
                line_cost = cost_pattern.group(2)
                unit_cost = cost_pattern.group(1)
                
                # Now we try to find the other parts in the same line
                # Remove the costs we just found to analyze the rest
                remaining_text = clean_line[:cost_pattern.start()].strip()
                
                # The Qty should be the number right before the Unit Cost
                # We split the remaining text by spaces to find the last number
                parts = remaining_text.split()
                if parts and parts[-1].isdigit():
                    qty = parts[-1]
                    # Everything before the Qty is the Product/SKU info
                    # Usually: LineNumber SKU Unit PackSize
                    # But sometimes just: LineNumber SKU
                    
                    # Let's assume the very first part is the Line Number if it's digit
                    line_num = ""
                    sku = ""
                    
                    product_parts = parts[:-1] # Remove Qty
                    
                    if product_parts:
                        if product_parts[0].isdigit():
                            line_num = product_parts[0]
                            # SKU is likely the next chunk
                            if len(product_parts) > 1:
                                sku = product_parts[1]
                        else:
                            # Maybe line number is missing or merged? Just grab first part as SKU
                            sku = product_parts[0]

                    # -----------------------------------------------
                    # GET DESCRIPTION & EAN (Look at lines below)
                    # -----------------------------------------------
                    description = ""
                    ean = ""
                    
                    # Look at the next few lines (up to 4) to find Description and EAN
                    next_lines = lines_list[i+1 : i+5]
                    
                    for nl in next_lines:
                        nl_stripped = nl.strip()
                        if not nl_stripped: continue
                        
                        # Stop if we hit a new line item (starts with a digit and looks like a price line)
                        if re.search(r"\d+\.\d{2}$", nl_stripped) and re.match(r"^\d+", nl_stripped):
                            break
                        
                        if "EAN NO" in nl.upper():
                            # Extract EAN digits
                            ean_match = re.search(r"(\d{12,14})", nl)
                            if ean_match:
                                ean = ean_match.group(1)
                        elif "NO COLOUR" in nl.upper() or "WHITEBOX" in nl.upper() or "MARTINI" in nl.upper():
                            # This is likely the description line
                            description = nl_stripped

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
        st.success(f"Success! Extracted {len(df)} items.")
        st.dataframe(df)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="Selfridges_PO_Converted.csv",
            mime="text/csv",
        )
    else:
        st.error("Still no items found. Check the Debug Information below to see why.")
        
        with st.expander("Show Debug Information (Raw Text)"):
            st.text(all_text_debug)
            st.write("Copy the text above and share it if you need further help.")
