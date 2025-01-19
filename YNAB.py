import streamlit as st
import numpy as np
import pandas as pd

from datetime import datetime



# Hardcoded column mappings for each file type
COLUMN_MAPPINGS = {
    "Swedbank (csv)": {
        "Date": "Transaktionsdag",
        "Payee": "Beskrivning",
        "Memo": None,  # Empty field
        "Amount": "Belopp"
    },
    "Coop Mastercard (xls & xlsx)": {
        "Date": "Datum",
        "Payee": "Detaljer",
        "Memo": None,  # Empty field
        "Amount": "Fakturabelopp"
    }
}

def parse_transaction_file(file, file_type):
    try:
        if file_type == "Swedbank (csv)":
            # Read CSV file with windows-1252 encoding, skipping 1 row
            df = pd.read_csv(file, encoding="windows-1252", skiprows=1)
        elif file_type == "Coop Mastercard (xls & xlsx)":
            # Read Excel (.xlsx or .xls) file, skipping 2 rows
            df = pd.read_excel(file, skiprows=2)
        else:
            st.error("Unsupported file type!")
            return None
        return df
    except Exception as e:
        st.error(f"Error reading file {file.name}: {str(e)}")
        return None

def apply_mappings(df, mappings):
    # Create a new DataFrame with the YNAB format
    ynab_df = pd.DataFrame()
    
    for ynab_col, source_col in mappings.items():
        if source_col:
            # Only map if the source column exists
            if source_col in df.columns:
                ynab_df[ynab_col] = df[source_col]
            else:
                st.warning(f"Column {source_col} not found in the data!")
                ynab_df[ynab_col] = ""  # For unmapped columns like Memo
        else:
            ynab_df[ynab_col] = ""  # For unmapped columns like Memo
    
    # Split "Amount" into "Inflow" and "Outflow"
    ynab_df['Inflow'] = ynab_df['Amount'].apply(lambda x: round(x, 2) if x > 0 else 0)
    ynab_df['Outflow'] = ynab_df['Amount'].apply(lambda x: round(-x, 2) if x < 0 else 0)
    ynab_df = ynab_df.drop(columns=['Amount'])  # Drop the original Amount column
    return ynab_df

def calculate_kpis(df):
    # Calculate Total Inflow and Outflow using the 'Inflow' and 'Outflow' columns
    total_inflow = df['Inflow'].sum()
    total_outflow = df['Outflow'].sum()

    return total_inflow, total_outflow

def top_payees_count(df):
    # Get the top payees (most frequent payees by transaction count, considering only outflows)
    df_outflows = df[df['Outflow'] > 0]
    return df_outflows['Payee'].value_counts().head(5)

def top_payees_amount(df):
    # Get the top payees by accumulated amount spent (outflows only)
    df_outflows = df[df['Outflow'] > 0]
    payee_totals = df_outflows.groupby('Payee')['Outflow'].sum().sort_values(ascending=False)
    # Format to 2 decimal places
    payee_totals = payee_totals.apply(lambda x: round(x, 2))
    return payee_totals.head(5)

def average_outflow(df):
    # Calculate the average outflow amount, considering only outflows
    outflows = df[df['Outflow'] > 0]
    return outflows['Outflow'].mean() if not outflows.empty else 0


st.set_page_config(
    page_title="YNAB Converter",
    page_icon="💰",
)

# App title
st.title("YNAB Converter")

st.write(
    "Upload your transaction files and process them into a simplified YNAB-compatible format (Date, Payee, Memo, Inflow, Outflow)."
)

# Select file type with labeled options
file_type = st.selectbox(
    "Select your file type:",
    ["Coop Mastercard (xls & xlsx)", "Swedbank (csv)"]
)

# File uploader for multiple files
uploaded_files = st.file_uploader(
    f"Upload your {file_type.split(' ')[0]} files:",
    accept_multiple_files=True,
    type=["csv"] if file_type == "Swedbank (csv)" else ["xls", "xlsx"]
)

if uploaded_files:
    all_transactions = []

    # Parse and process each uploaded file
    for file in uploaded_files:
        st.write(f"Processing {file.name}...")
        transactions = parse_transaction_file(file, file_type)
        if transactions is not None:
            # Apply the hardcoded column mappings
            mapped_transactions = apply_mappings(transactions, COLUMN_MAPPINGS[file_type])
            all_transactions.append(mapped_transactions)

    if all_transactions:
        # Combine all transactions into a single DataFrame
        combined_df = pd.concat(all_transactions, ignore_index=True)

        # Ensure 'Date' column is in datetime format
        combined_df['Date'] = pd.to_datetime(combined_df['Date'], errors='coerce')

        # Sort the data by the 'Date' column in ascending order
        combined_df = combined_df.sort_values(by='Date', ascending=True)

        # Reset the index and start it from 1 (instead of 0)
        combined_df = combined_df.reset_index(drop=True)
        combined_df.index = combined_df.index + 1

        # Show Summary Dashboard in a grid layout (KPI Cards)
        st.subheader("Summary Dashboard")

        # Calculate and display Total Inflow, Outflow
        total_inflow, total_outflow = calculate_kpis(combined_df)

        # Create a grid layout for KPIs
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Transactions", len(combined_df))
        
        with col2:
            st.metric("Total Inflow (SEK)", f"SEK {total_inflow:,.2f}")
        
        with col3:
            st.metric("Total Outflow (SEK)", f"SEK {total_outflow:,.2f}")

        # Average Outflow Transaction Amount
        avg_outflow = average_outflow(combined_df)
        st.metric("Avg Outflow Amount (SEK)", f"SEK {avg_outflow:,.2f}")

        # Top Payees (by Transaction Count) - side-by-side
        col1, col2 = st.columns(2)

        with col1:
            top_payees_count_list = top_payees_count(combined_df)
            st.subheader("Top Payees (Count)")
            st.write(top_payees_count_list)

        with col2:
            top_payees_amount_list = top_payees_amount(combined_df)
            st.subheader("Top Payees (Amount)")
            st.write(top_payees_amount_list)

        # Date Range (Only showing the date without time)
        date_range = f"{combined_df['Date'].min().strftime('%Y-%m-%d')} to {combined_df['Date'].max().strftime('%Y-%m-%d')}"
        st.metric("Date Range", date_range)

        # Editable DataFrame for the YNAB output (use st.data_editor())
        st.subheader("Edit YNAB Output")
        
        # Add a checkbox to exclude rows from the final export
        combined_df['Remove'] = False  # Add a column for the checkbox

        # Set cells with 0 for Inflow and Outflow to empty
        combined_df['Inflow'] = combined_df['Inflow'].apply(lambda x: "" if x == 0 else f"{x:.2f}")
        combined_df['Outflow'] = combined_df['Outflow'].apply(lambda x: "" if x == 0 else f"{x:.2f}")

        # Configure column types for st.data_editor
        column_config = {
            'Remove': st.column_config.CheckboxColumn('Exclude'),
            'Date': st.column_config.DateColumn(),
            'Payee': st.column_config.TextColumn(),
            'Memo': st.column_config.TextColumn(),
            'Inflow': st.column_config.NumberColumn(format="%.2f"),
            'Outflow': st.column_config.NumberColumn(format="%.2f")
        }

        # Using st.data_editor() to display the editable dataframe, sorted by Date
        edited_df = st.data_editor(
            combined_df, 
            use_container_width=True,
            column_config=column_config
        )

        # Filter out rows marked for removal
        final_df = edited_df[edited_df['Remove'] == False].drop(columns=['Remove'])

        # Convert 'Date' column back to string format (if necessary) for export
        final_df['Date'] = final_df['Date'].dt.strftime('%Y-%m-%d')

        # Create the dynamic filename with transaction count and timestamp
        transaction_count = len(final_df)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ynab_import_{transaction_count}_{timestamp}.csv"

        # Create a download link for the generated CSV
        ynab_csv = final_df.to_csv(index=False)

        st.download_button(
            label="Download YNAB CSV",
            data=ynab_csv,
            file_name=filename,
            mime="text/csv"
        )
