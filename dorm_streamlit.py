import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime
from pytz import timezone

# --- DATABASE CONNECTION ---
conn = mysql.connector.connect(
    host=st.secrets["mysql"]["host"],
    user=st.secrets["mysql"]["user"],
    password=st.secrets["mysql"]["password"],
    database=st.secrets["mysql"]["database"],
    port=st.secrets["mysql"]["port"],
    ssl_ca=st.secrets["mysql"]["ssl_ca"]
)
cursor = conn.cursor(dictionary=True)

# Set MySQL session timezone to EEST (UTC+3)
cursor.execute("SET SESSION time_zone = '+03:00';")

st.title("Student Dorm Management")

# --- VIEW TABLES ---
st.subheader("📋 View Any Table")
cursor.execute("SHOW TABLES")
tables = [row[f'Tables_in_{st.secrets["mysql"]["database"]}'] for row in cursor.fetchall()]
# Ensure only valid tables are shown (case-sensitive)
valid_tables = ["Building", "room", "student", "MaintenanceRequest", "Penalty", "Meals", "health_issues"]
tables = [t for t in tables if t in valid_tables]
selected_table = st.selectbox("Select a table to view:", tables)

if st.button("Show Table"):
    cursor.execute(f"SELECT * FROM {selected_table}")
    rows = cursor.fetchall()
    if rows:
        st.write(pd.DataFrame(rows))
    else:
        st.info("No data found.")

# Define EEST timezone
eest = timezone('Europe/Tallinn')  # EEST is used in Tallinn, Estonia

# --- TABLE-SPECIFIC OPERATIONS ---
if selected_table == "student":
    # --- ADD STUDENT (Reverted to provided code with Penalty and optional health info) ---
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
                    else:
                        st.error("Room does not exist.")

    # --- DELETE STUDENT ---
    st.subheader("🗑️ Delete Student")
    del_id = st.number_input("Enter Student ID to Delete", step=1, min_value=1)
    if st.button("Delete Student"):
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
                st.warning("Student and related records deleted. Room occupancy updated.")
            except mysql.connector.Error as e:
                conn.rollback()
                st.error(f"Error deleting student: {e}")
        else:
            st.error("Student ID not found.")

    # --- SEARCH & EDIT ---
    st.subheader("🔍 Search Student")
    search_id = st.number_input("Search Student by ID", step=1, key="search", min_value=1)
    if st.button("Search"):
        cursor.execute("SELECT * FROM student WHERE id = %s", (search_id,))
        student = cursor.fetchone()
        if student:
            st.json(student)

            st.subheader("✏️ Change Meal")
            weekday = st.selectbox("Weekday", ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"])
            meal_type = st.selectbox("Meal Type", ["A", "B"], key="meal_update")
            if st.button("Update Meal"):
                cursor.execute("REPLACE INTO Meals (student_id, meal_type, weekday) VALUES (%s, %s, %s)",
                              (search_id, meal_type, weekday))
                conn.commit()
                st.success("Meal updated!")

            st.subheader("🏥 Health Issue")
            cursor.execute("SELECT * FROM health_issues WHERE student_id = %s", (search_id,))
            health = cursor.fetchone()
            if health:
                desc = st.text_area("Description", health['description'])
                prescription = st.text_input("Prescription", health['prescription'])
                guardian = st.text_input("Guardian Contact", health['guardian_contact'])
                if st.button("Update Health Issue"):
                    cursor.execute("""
                        UPDATE health_issues 
                        SET description=%s, prescription=%s, guardian_contact=%s 
                        WHERE student_id=%s
                    """, (desc, prescription, guardian, search_id))
                    conn.commit()
                    st.success("Health issue updated!")
            else:
                st.info("No health issue found. Add new below:")
                with st.form("add_health_form"):
                    desc = st.text_area("Description")
                    prescription = st.text_input("Prescription")
                    guardian = st.text_input("Guardian Contact")
                    if st.form_submit_button("Insert Health Issue"):
                        if not desc or not prescription or not guardian:
                            st.error("All health fields are required.")
                        elif len(guardian) != 11 or not guardian.isdigit():
                            st.error("Guardian contact must be exactly 11 digits.")
                        else:
                            cursor.execute("INSERT INTO health_issues VALUES (%s, %s, %s, %s)",
                                          (search_id, desc, prescription, guardian))
                            conn.commit()
                            st.success("Health issue added!")
        else:
            st.error("Student not found.")

elif selected_table == "MaintenanceRequest":
    # --- ADD MAINTENANCE REQUEST ---
    with st.expander("➕ Add Maintenance Request"):
        with st.form("add_maintenance_form"):
            request_id = st.number_input("Request ID", step=1, min_value=1)
            room_id = st.number_input("Room ID", step=1, min_value=1)
            description = st.text_area("Description")
            status = st.selectbox("Status", ["Pending", "In Progress", "Resolved"])
            submitted = st.form_submit_button("Add Request")

            if submitted:
                cursor.execute("INSERT INTO MaintenanceRequest (id, statues, room_id, description) VALUES (%s, %s, %s, %s)",
                              (request_id, status, room_id, description))
                conn.commit()
                st.success("Maintenance request added.")

    # --- UPDATE MAINTENANCE REQUEST ---
    st.subheader("✏️ Update Maintenance Request")
    with st.form("update_maintenance_form"):
        update_request_id = st.number_input("Request ID to Update", step=1, min_value=1)
        new_status = st.selectbox("New Status", ["Pending", "In Progress", "Resolved"], key="update_status")
        new_description = st.text_area("New Description", key="update_desc")
        update_submitted = st.form_submit_button("Update Request")

        if update_submitted:
            cursor.execute("SELECT id FROM MaintenanceRequest WHERE id = %s", (update_request_id,))
            if cursor.fetchone():
                cursor.execute("""
                    UPDATE MaintenanceRequest 
                    SET statues=%s, description=%s 
                    WHERE id=%s
                """, (new_status, new_description, update_request_id))
                conn.commit()
                st.success("Maintenance request updated.")
            else:
                st.error("Request ID not found.")

    # --- DELETE MAINTENANCE REQUEST ---
    st.subheader("🗑️ Delete Maintenance Request")
    del_request_id = st.number_input("Enter Request ID to Delete", step=1, min_value=1)
    if st.button("Delete Request"):
        cursor.execute("DELETE FROM MaintenanceRequest WHERE id = %s", (del_request_id,))
        if cursor.rowcount > 0:
            conn.commit()
            st.warning("Maintenance request deleted.")
        else:
            st.error("Request ID not found.")

elif selected_table == "Penalty":
    # --- UPDATE PENALTY ---
    st.subheader("✏️ Update Penalty Points")
    student_id = st.number_input("Student ID", step=1, min_value=1)
    points = st.number_input("Total Points", step=1, min_value=0)
    if st.button("Update Penalty"):
        cursor.execute("SELECT id FROM student WHERE id = %s", (student_id,))
        if cursor.fetchone():
            cursor.execute("REPLACE INTO Penalty (student_id, total_points, last_updated) VALUES (%s, %s, %s)",
                          (student_id, points, datetime.now(eest)))
            conn.commit()
            st.success("Penalty points and timestamp updated.")
        else:
            st.error("Student ID not found.")

# --- CLOSE DB ---
cursor.close()
conn.close()
