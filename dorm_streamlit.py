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

conn.autocommit = True

# Set timezone
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

eest = timezone('Europe/Tallinn')

# --- STUDENT OPERATIONS ---
if selected_table == "student":
    # ADD STUDENT
    with st.expander("➕ Add New Student"):
        with st.form("add_student_form"):
            student_id = st.number_input("Student ID", step=1, min_value=1)
            student_name = st.text_input("Name")
            contact = st.text_input("Contact (11 digits)")
            room_id = st.number_input("Room ID", step=1, min_value=1)

            st.subheader("Meal Information")
            weekday = st.selectbox("Weekday for Meal", ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"])
            meal_choice = st.selectbox("Meal Choice", ["A", "B"])

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
                    st.error("All health fields are required if health info is added.")
                elif add_health_info and (len(guardian_contact) != 11 or not guardian_contact.isdigit()):
                    st.error("Guardian contact must be exactly 11 digits.")
                else:
                    try:
                        cursor.execute("SELECT capacity, current_occupancy FROM room WHERE id = %s", (room_id,))
                        room = cursor.fetchone()
                        if room and room["current_occupancy"] < room["capacity"]:
                            cursor.execute("INSERT INTO student (id, student_Name, contact, room_id) VALUES (%s, %s, %s, %s)",
                                           (student_id, student_name, contact, room_id))

                            cursor.execute("REPLACE INTO Meals (student_id, meal_type, weekday) VALUES (%s, %s, %s)",
                                           (student_id, meal_choice, weekday))

                            if add_health_info:
                                cursor.execute("INSERT INTO health_issues (student_id, description, prescription, guardian_contact) VALUES (%s, %s, %s, %s)",
                                               (student_id, health_desc, prescription, guardian_contact))

                            cursor.execute("INSERT INTO Penalty (student_id, total_points, last_updated) VALUES (%s, %s, %s)",
                                           (student_id, 0, datetime.now(eest)))

                            cursor.execute("""
                                UPDATE room 
                                SET current_occupancy = (
                                    SELECT COUNT(*) FROM student WHERE room_id = %s
                                )
                                WHERE id = %s
                            """, (room_id, room_id))

                            conn.commit()
                            st.success("Student and related data added.")
                        else:
                            st.error("Room is full or does not exist.")
                    except mysql.connector.Error as e:
                        conn.rollback()
                        st.error(f"MySQL Error: {e}")

    # DELETE STUDENT
    st.subheader("🗑️ Delete Student")
    del_id = st.number_input("Enter Student ID to Delete", step=1, min_value=1)
    if st.button("Delete Student"):
        try:
            cursor.execute("SELECT room_id FROM student WHERE id = %s", (del_id,))
            room_data = cursor.fetchone()
            if room_data:
                room_id = room_data["room_id"]
                cursor.execute("DELETE FROM Meals WHERE student_id = %s", (del_id,))
                cursor.execute("DELETE FROM health_issues WHERE student_id = %s", (del_id,))
                cursor.execute("DELETE FROM Penalty WHERE student_id = %s", (del_id,))
                cursor.execute("DELETE FROM student WHERE id = %s", (del_id,))
                cursor.execute("""
                    UPDATE room 
                    SET current_occupancy = (
                        SELECT COUNT(*) FROM student WHERE room_id = %s
                    )
                    WHERE id = %s
                """, (room_id, room_id))
                conn.commit()
                st.warning("Student and related data deleted.")
            else:
                st.error("Student ID not found.")
        except mysql.connector.Error as e:
            conn.rollback()
            st.error(f"Error deleting student: {e}")

    # SEARCH & EDIT STUDENT
    st.subheader("🔍 Search Student")
    search_id = st.number_input("Search Student by ID", step=1, key="search", min_value=1)
    if st.button("Search"):
        try:
            cursor.execute("SELECT * FROM student WHERE id = %s", (search_id,))
            student = cursor.fetchone()
            if student:
                st.json(student)
            else:
                st.error("Student ID not found.")
                st.stop()

            # Update Meal
            st.subheader("✏️ Change Meal")
            cursor.execute("SELECT meal_type, weekday FROM Meals WHERE student_id = %s", (search_id,))
            current_meal = cursor.fetchone()
            current_weekday = current_meal['weekday'] if current_meal else "Sunday"
            current_meal_type = current_meal['meal_type'] if current_meal else "A"

            with st.form("update_meal_form"):
                weekday = st.selectbox("Weekday", ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"],
                                       index=["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"].index(current_weekday))
                meal_type = st.selectbox("Meal Type", ["A", "B"],
                                         index=["A", "B"].index(current_meal_type) if current_meal_type in ["A", "B"] else 0)
                meal_submitted = st.form_submit_button("Update Meal")

                if meal_submitted:
                    try:
                        if weekday != current_weekday:
                            cursor.execute("DELETE FROM Meals WHERE student_id = %s AND weekday = %s", (search_id, current_weekday))

                        cursor.execute("""
                            INSERT INTO Meals (student_id, meal_type, weekday)
                            VALUES (%s, %s, %s)
                            ON DUPLICATE KEY UPDATE meal_type = %s
                        """, (search_id, meal_type, weekday, meal_type))

                        conn.commit()
                        st.success(f"Meal updated for {weekday} to type {meal_type}.")
                    except mysql.connector.Error as e:
                        conn.rollback()
                        st.error(f"Error updating meal: {e}")

            # Health Issue
            st.subheader("🏥 Health Issue")
            cursor.execute("SELECT * FROM health_issues WHERE student_id = %s", (search_id,))
            health = cursor.fetchone()
            if health:
                with st.form("update_health_form"):
                    desc = st.text_area("Description", health['description'])
                    prescription = st.text_input("Prescription", health['prescription'])
                    guardian = st.text_input("Guardian Contact", health['guardian_contact'])
                    health_submitted = st.form_submit_button("Update Health Issue")
                    if health_submitted:
                        try:
                            cursor.execute("""
                                UPDATE health_issues 
                                SET description=%s, prescription=%s, guardian_contact=%s 
                                WHERE student_id=%s
                            """, (desc, prescription, guardian, search_id))
                            conn.commit()
                            st.success("Health issue updated.")
                        except mysql.connector.Error as e:
                            conn.rollback()
                            st.error(f"Error updating health issue: {e}")
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
                            try:
                                cursor.execute("INSERT INTO health_issues VALUES (%s, %s, %s, %s)",
                                               (search_id, desc, prescription, guardian))
                                conn.commit()
                                st.success("Health issue added.")
                            except mysql.connector.Error as e:
                                conn.rollback()
                                st.error(f"Error adding health issue: {e}")
        except mysql.connector.Error as e:
            st.error(f"Error searching student: {e}")

# --- MAINTENANCE REQUESTS ---
elif selected_table == "MaintenanceRequest":
    with st.expander("➕ Add Maintenance Request"):
        with st.form("add_maintenance_form"):
            request_id = st.number_input("Request ID", step=1, min_value=1)
            room_id = st.number_input("Room ID", step=1, min_value=1)
            description = st.text_area("Description")
            status = st.selectbox("Status", ["Pending", "In Progress", "Resolved"])
            submitted = st.form_submit_button("Add Request")
            if submitted:
                try:
                    cursor.execute("INSERT INTO MaintenanceRequest (id, statues, room_id, description) VALUES (%s, %s, %s, %s)",
                                   (request_id, status, room_id, description))
                    conn.commit()
                    st.success("Maintenance request added.")
                except mysql.connector.Error as e:
                    conn.rollback()
                    st.error(f"Error adding maintenance request: {e}")

    st.subheader("✏️ Update Maintenance Request")
    with st.form("update_maintenance_form"):
        update_request_id = st.number_input("Request ID to Update", step=1, min_value=1)
        new_status = st.selectbox("New Status", ["Pending", "In Progress", "Resolved"], key="update_status")
        new_description = st.text_area("New Description", key="update_desc")
        update_submitted = st.form_submit_button("Update Request")
        if update_submitted:
            try:
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
            except mysql.connector.Error as e:
                conn.rollback()
                st.error(f"Error updating maintenance request: {e}")

    st.subheader("🗑️ Delete Maintenance Request")
    del_request_id = st.number_input("Enter Request ID to Delete", step=1, min_value=1)
    if st.button("Delete Request"):
        try:
            cursor.execute("DELETE FROM MaintenanceRequest WHERE id = %s", (del_request_id,))
            if cursor.rowcount > 0:
                conn.commit()
                st.warning("Maintenance request deleted.")
            else:
                st.error("Request ID not found.")
        except mysql.connector.Error as e:
            st.error(f"Error deleting maintenance request: {e}")

# --- PENALTY ---
elif selected_table == "Penalty":
    st.subheader("✏️ Update Penalty Points")
    student_id = st.number_input("Student ID", step=1, min_value=1)
    points = st.number_input("Total Points", step=1, min_value=0)
    if st.button("Update Penalty"):
        try:
            cursor.execute("SELECT id FROM student WHERE id = %s", (student_id,))
            if cursor.fetchone():
                cursor.execute("REPLACE INTO Penalty (student_id, total_points, last_updated) VALUES (%s, %s, %s)",
                               (student_id, points, datetime.now(eest)))
                conn.commit()
                st.success("Penalty points and timestamp updated.")
            else:
                st.error("Student ID not found.")
        except mysql.connector.Error as e:
            conn.rollback()
            st.error(f"Error updating penalty: {e}")

# --- CLOSE DB ---
cursor.close()
conn.close()
