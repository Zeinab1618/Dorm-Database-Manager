import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime
from pytz import timezone

# --- DATABASE CONNECTION ---
try:
    conn = mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"],
        port=st.secrets["mysql"]["port"],
        ssl_ca=st.secrets["mysql"]["ssl_ca"]
    )
    cursor = conn.cursor(dictionary=True)
except mysql.connector.Error as e:
    st.error(f"Database connection failed: {e}")
    st.stop()

# Set MySQL session timezone to EEST (UTC+3)
try:
    cursor.execute("SET SESSION time_zone = '+03:00';")
except mysql.connector.Error as e:
    st.error(f"Failed to set session timezone: {e}")
    cursor.close()
    conn.close()
    st.stop()

st.title("Student Dorm Management")

# --- VIEW TABLES ---
st.subheader("📋 View Any Table")
try:
    cursor.execute("SHOW TABLES")
    tables = [row[f'Tables_in_{st.secrets["mysql"]["database"]}'] for row in cursor.fetchall()]
    # Ensure only valid tables are shown (case-sensitive)
    valid_tables = ["Building", "room", "student", "MaintenanceRequest", "Penalty", "Meals", "health_issues"]
    tables = [t for t in tables if t in valid_tables]
    selected_table = st.selectbox("Select a table to view:", tables)
except mysql.connector.Error as e:
    st.error(f"Error fetching tables: {e}")
    cursor.close()
    conn.close()
    st.stop()

if st.button("Show Table"):
    try:
        cursor.execute(f"SELECT * FROM {selected_table}")
        rows = cursor.fetchall()
        if rows:
            st.write(pd.DataFrame(rows))
        else:
            st.info("No data found.")
    except mysql.connector.Error as e:
        st.error(f"Error fetching table data: {e}")

# Define EEST timezone
eest = timezone('Europe/Tallinn')  # EEST is used in Tallinn, Estonia

# --- TABLE-SPECIFIC OPERATIONS ---
if selected_table == "student":
    # --- ADD STUDENT (Reverted to provided code with modifications for Penalty and optional health info) ---
    with st.expander("➕ Add New Student"):
        with st.form("add_student_form"):
            student_id = st.number_input("Student ID", step=1, min_value=1)
            student_name = st.text_input("Name")
            contact = st.text_input("Contact (11 digits)")
            room_id = st.number_input("Room ID", step=1, min_value=1)
            
            # Mandatory Meal Information
            st.subheader("Meal Information")
            weekday = st.selectbox("Weekday for Meal", ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"])
            meal_choice = st.selectbox("Meal Choice", ["A", "B"])
            
            # Optional Health Information
            st.subheader("Health Information (Optional)")
            add_health_info = st.checkbox("Add Health Information")
            health_desc = st.text_area("Health Description", disabled=not add_health_info)
            prescription = st.text_input("Prescription", disabled=not add_health_info)
            guardian_contact = st.text_input("Guardian Contact (11 digits)", disabled=not add_health_info)
            
            submitted = st.form_submit_button("Add Student")

            if submitted:
                if len(contact) != 11 or not contact.isdigit():
                    st.error("Contact must be exactly 11 digits.")
                elif add_health_info and (not health_desc or not prescription or not guardian_contact):
                    st.error("All health fields are required if health information is added.")
                elif add_health_info and (len(guardian_contact) != 11 or not guardian_contact.isdigit()):
                    st.error("Guardian contact must be exactly 11 digits.")
                else:
                    try:
                        cursor.execute("SELECT capacity, current_occupancy FROM room WHERE id = %s", (room_id,))
                        room = cursor.fetchone()
                        if room:
                            if room["current_occupancy"] >= room["capacity"]:
                                st.error("Room is full.")
                            else:
                                try:
                                    # Insert student
                                    cursor.execute("INSERT INTO student (id, student_Name, contact, room_id) VALUES (%s, %s, %s, %s)",
                                                  (student_id, student_name, contact, room_id))
                                    
                                    # Insert meal
                                    cursor.execute("REPLACE INTO Meals (student_id, meal_type, weekday) VALUES (%s, %s, %s)",
                                                  (student_id, meal_choice, weekday))
                                    
                                    # Insert health issue if provided
                                    if add_health_info:
                                        cursor.execute("INSERT INTO health_issues (student_id, description, prescription, guardian_contact) VALUES (%s, %s, %s, %s)",
                                                      (student_id, health_desc, prescription, guardian_contact))
                                    
                                    # Insert penalty record with 0 points and EEST timestamp
                                    cursor.execute("INSERT INTO Penalty (student_id, total_points, last_updated) VALUES (%s, %s, %s)",
                                                  (student_id, 0, datetime.now(eest)))
                                    
                                    # Update room occupancy
                                    cursor.execute("""
                                        UPDATE room 
                                        SET current_occupancy = (
                                            SELECT COUNT(*) FROM student WHERE room_id = %s
                                        )
                                        WHERE id = %s
                                    """, (room_id, room_id))
                                    
                                    conn.commit()
                                    st.success("Student, meal, and penalty information added. Health info added if provided. Room occupancy updated.")
                                except mysql.connector.Error as e:
                                    conn.rollback()
                                    st.error(f"MySQL Error: {e}")
                                    if "Duplicate entry" in str(e):
                                        if "student.PRIMARY" in str(e):
                                            st.error("Student ID already exists.")
                                        elif "student.contact" in str(e):
                                            st.error("Contact number already exists.")
                                        elif "Meals.PRIMARY" in str(e):
                                            st.error("Meal record for this student and weekday already exists.")
                                        elif "health_issues.PRIMARY" in str(e):
                                            st.error("Health issue record for this student already exists.")
                        else:
                            st.error("Room does not exist.")
                    except mysql.connector.Error as e:
                        st.error(f"Error checking room: {e}")

    # --- DELETE STUDENT ---
    st.subheader("🗑️ Delete Student")
    del_id = st.number_input("Enter Student ID to Delete", step=1, min_value=1)
    if st.button("Delete Student"):
        try:
            cursor.execute("SELECT room_id FROM student WHERE id = %s", (del_id,))
            room_data = cursor.fetchone()
            if room_data:
                try:
                    room_id = room_data["room_id"]
                    cursor.execute("DELETE FROM Meals WHERE student_id = %s", (del_id,))
                    cursor.execute("DELETE FROM health_issues WHERE student_id = %s", (del_id,))
                    cursor.execute("DELETE FROM Penalty WHERE student_id = %s", (del_id,))
                    cursor.execute("DELETE FROM student WHERE id = %s", (del_id,))
                    
                    # Update room occupancy
                    cursor.execute("""
                        UPDATE room 
                        SET current_occupancy = (
                            SELECT COUNT(*) FROM student WHERE room_id = %s
                        )
                        WHERE id = %s
                    """, (room_id, room_id))
                    
                    conn.commit()
