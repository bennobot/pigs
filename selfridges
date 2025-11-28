import streamlit as st
import pdfplumber
import pandas as pd
import re

st.title("Purchase Order to CSV Converter")
st.write("Upload a Selfridges PO PDF to convert it to a CSV file.")

uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file is not None:
    all_data = []
    with pdfplumber.open(uploaded_file) as pdf:
        # Regex to find line items (starts with a number, then text)
        line_pattern = re.compile(r'^(\d+)\s+(L-WH|WHT)\w+') 
        
        for page in pdf.pages:
            text = page.extract_text()
            lines = text.split('\n')
            
            # Simple logic to grab the table data (This needs tuning based on exact layout consistency)
            # A more robust way uses extract_table() if the PDF lines are perfect
            # For this example, we will use the table extraction method
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # Filter for rows that look like data (First column is a number)
                    if row[0] and row[0].isdigit():
                        # Clean up newlines in description
                        clean_row = [str(item).replace('\n', ' ') if item else '' for item in row]
                        all_data.append(clean_row)

    if all_data:
        # Define columns based on your specific PO format
        columns = ["Line", "Product Number", "Description", "EAN", "Qty", "Unit Cost", "Line Cost"]
        
        # Adjust column count if table extraction read differently
        # Sometimes extra blank columns appear
        if len(all_data[0]) > len(columns):
             all_data = [row[:len(columns)] for row in all_data]
             
        df = pd.DataFrame(all_data, columns=columns)
        
        st.success("Extraction Complete!")
        st.dataframe(df) # Show preview

        # Create download button
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="converted_po.csv",
            mime="text/csv",
        )
    else:
        st.error("Could not extract tabular data. The PDF format might vary.")
