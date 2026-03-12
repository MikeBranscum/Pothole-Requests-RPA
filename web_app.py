import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime

# Streamlit page config must be the first st command
st.set_page_config(page_title="Rabine America", layout="wide")

# --- DATABASE SETUP & PRICING ENGINE ---
def setup_database():
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE tbl_Baseline_Tiers (Tier_ID INTEGER PRIMARY KEY, Scope_Name TEXT, Base_Price_Per_SF REAL)''')
    cursor.execute("INSERT INTO tbl_Baseline_Tiers VALUES (1, 'Cut & Patch (Price Per SF)', 28.50)")
    
    cursor.execute('''CREATE TABLE tbl_State_Labor (State_ID TEXT PRIMARY KEY, State_Name TEXT, Labor_CCI REAL, Has_Winter_Shutdown BOOLEAN)''')
    states_data = [
        ('AL', 'Alabama', 0.85, 0), ('AK', 'Alaska', 1.30, 1), ('AZ', 'Arizona', 0.97, 0), ('AR', 'Arkansas', 0.83, 0), 
        ('CA', 'California', 1.32, 0), ('CO', 'Colorado', 1.05, 1), ('CT', 'Connecticut', 1.25, 1), ('DE', 'Delaware', 1.08, 1), 
        ('FL', 'Florida', 0.88, 0), ('GA', 'Georgia', 0.95, 0), ('HI', 'Hawaii', 1.45, 0), ('ID', 'Idaho', 0.96, 1),
        ('IL', 'Illinois', 1.18, 1), ('IN', 'Indiana', 1.01, 1), ('IA', 'Iowa', 0.98, 1), ('KS', 'Kansas', 0.94, 1), 
        ('KY', 'Kentucky', 0.92, 1), ('LA', 'Louisiana', 0.87, 0), ('ME', 'Maine', 1.02, 1), ('MD', 'Maryland', 1.10, 1), 
        ('MA', 'Massachusetts', 1.28, 1), ('MI', 'Michigan', 1.12, 1), ('MN', 'Minnesota', 1.15, 1), ('MS', 'Mississippi', 0.82, 0),
        ('MO', 'Missouri', 0.99, 1), ('MT', 'Montana', 0.95, 1), ('NE', 'Nebraska', 0.94, 1), ('NV', 'Nevada', 1.10, 0), 
        ('NH', 'New Hampshire', 1.08, 1), ('NJ', 'New Jersey', 1.30, 1), ('NM', 'New Mexico', 0.93, 0), ('NY', 'New York', 1.35, 1), 
        ('NC', 'North Carolina', 0.90, 0), ('ND', 'North Dakota', 0.96, 1), ('OH', 'Ohio', 1.02, 1), ('OK', 'Oklahoma', 0.88, 0),
        ('OR', 'Oregon', 1.15, 1), ('PA', 'Pennsylvania', 1.14, 1), ('RI', 'Rhode Island', 1.20, 1), ('SC', 'South Carolina', 0.85, 0), 
        ('SD', 'South Dakota', 0.90, 1), ('TN', 'Tennessee', 0.89, 0), ('TX', 'Texas', 0.92, 0), ('UT', 'Utah', 0.98, 1), 
        ('VT', 'Vermont', 1.03, 1), ('VA', 'Virginia', 1.01, 1), ('WA', 'Washington', 1.22, 1), ('WV', 'West Virginia', 0.91, 1),
        ('WI', 'Wisconsin', 1.11, 1), ('WY', 'Wyoming', 0.95, 1)
    ]
    cursor.executemany("INSERT INTO tbl_State_Labor VALUES (?, ?, ?, ?)", states_data)
    
    cursor.execute('''CREATE TABLE tbl_Macro_Trend (Trend_ID INTEGER PRIMARY KEY, Year_Quarter TEXT, Oil_Freight_Multiplier REAL, Is_Active BOOLEAN)''')
    cursor.execute("INSERT INTO tbl_Macro_Trend VALUES (202601, 'Q1_2026', 1.08, 1)")
    
    cursor.execute('''CREATE TABLE tbl_Seasonal_Rules (Season_ID INTEGER PRIMARY KEY, Season_Name TEXT, Material_Multiplier REAL)''')
    cursor.executemany("INSERT INTO tbl_Seasonal_Rules VALUES (?, ?, ?)", [(1, 'Hot Mix Open', 1.00), (2, 'Winter/Plant Closed', 1.15)])
    
    cursor.execute('''CREATE TABLE tbl_State_Seasonality (Mapping_ID INTEGER PRIMARY KEY AUTOINCREMENT, State_ID TEXT, Month_Num INTEGER, Season_ID INTEGER)''')
    cursor.execute("SELECT State_ID, Has_Winter_Shutdown FROM tbl_State_Labor")
    for row in cursor.fetchall():
        state_id, has_winter = row[0], row[1]
        for month in range(1, 13):
            season = 2 if (has_winter and month in [1, 2, 3, 4, 11, 12]) else 1
            cursor.execute("INSERT INTO tbl_State_Seasonality (State_ID, Month_Num, Season_ID) VALUES (?, ?, ?)", (state_id, month, season))

    conn.commit()
    return conn

def calculate_price_per_sf(conn, state_id, month_num):
    cursor = conn.cursor()
    query = '''
        SELECT b.Base_Price_Per_SF, l.Labor_CCI, m.Oil_Freight_Multiplier, r.Material_Multiplier
        FROM tbl_Baseline_Tiers b
        JOIN tbl_State_Labor l ON l.State_ID = ?
        JOIN tbl_State_Seasonality ss ON ss.State_ID = l.State_ID AND ss.Month_Num = ?
        JOIN tbl_Seasonal_Rules r ON r.Season_ID = ss.Season_ID
        CROSS JOIN tbl_Macro_Trend m WHERE m.Is_Active = 1 AND b.Tier_ID = 1
    '''
    cursor.execute(query, (state_id, month_num))
    result = cursor.fetchone()
    if result:
        base, labor, macro, season = result
        return round(base * labor * macro * season, 2)
    return None

# --- WEB INTERFACE ---
st.title("🚧 Pothole Request")
st.markdown("Submit maintenance requests below. Pricing is automatically generated based on regional indices and material availability.")

# 1. Manager Contact Info (Symmetrical 2-Column Layout)
st.subheader("Manager Contact Info")
col1, col2 = st.columns(2)
with col1:
    requested_by = st.text_input("Requested By:")
with col2:
    email = st.text_input("Email:")

# 2. Locations Grid
st.subheader("Maintenance Locations")
st.markdown("Add your locations below. Click the **+** icon at the bottom of the table to add more rows.")

if 'locations_df' not in st.session_state:
    # Set the starting dataframe with an index of 1 for proper auto-numbering
    df = pd.DataFrame(columns=["Street", "City", "State", "Zip_Code", "Priority"])
    df.loc[1] = ["", "", "IL", "", "Moderate"]
    st.session_state.locations_df = df

state_list = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"]

edited_df = st.data_editor(
    st.session_state.locations_df, 
    num_rows="dynamic", 
    use_container_width=True,
    column_config={
        "State": st.column_config.SelectboxColumn("State", options=state_list, required=True),
        "Priority": st.column_config.SelectboxColumn("Priority", options=["Moderate", "HIGH"], required=True, default="Moderate")
    }
)

# 3. Submission & Processing
if st.button("Submit & Generate Pricing", type="primary"):
    if not requested_by or not email:
        st.error("Please fill out both the 'Requested By' and 'Email' fields.")
    elif edited_df["Street"].replace("", pd.NA).dropna().empty:
        st.error("Please provide at least one valid street address.")
    else:
        active_db = setup_database()
        current_month = datetime.now().month
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        results = []
        for index, row in edited_df.iterrows():
            street = str(row["Street"]).strip()
            if street and street != "nan":
                city = str(row["City"]).strip()
                state = str(row["State"]).strip()
                zip_code = str(row["Zip_Code"]).strip()
                priority = str(row["Priority"]).strip()
                
                final_price = calculate_price_per_sf(active_db, state, current_month)
                
                if final_price:
                    results.append({
                        "Timestamp": timestamp, 
                        "Requested_By": requested_by,
                        "Email": email, 
                        "Street": street,
                        "City": city, 
                        "State": state, 
                        "Zip": zip_code, 
                        "Priority": priority,
                        "Final_Price_Per_SF": final_price
                    })
        
        active_db.close()
        
        if results:
            results_df = pd.DataFrame(results)
            # We use a new filename to avoid conflicts with the old 3-column CSV format
            filename = "Rabine_Priced_Requests.csv" 
            
            # Append to CSV
            if os.path.isfile(filename):
                results_df.to_csv(filename, mode='a', header=False, index=False)
            else:
                results_df.to_csv(filename, index=False)
                
            st.success("Request priced and logged successfully!")
            st.balloons() 

# 4. Data Viewer
st.divider()
st.subheader("Internal Bid Log")
if os.path.isfile("Rabine_Priced_Requests.csv"):
    log_df = pd.read_csv("Rabine_Priced_Requests.csv")
    st.dataframe(log_df, use_container_width=True)
else:
    st.info("No requests have been logged yet.")