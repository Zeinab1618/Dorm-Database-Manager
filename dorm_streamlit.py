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
eest = timezone('Europe/Tallinn')

# --- TABLE-SPECIFIC OPERATIONS ---
if selected_table == "student":
    # --- ADD STUDENT ---
    with st.expander("➕ Add New Student"):
        with st.form("add_student_form"):
            student_id = st.number_input("Student ID", step=1, min_value=1)
            student_name = st.text_input("Name")
            contact = st.text_input("Contact (11 digits)")
            room_id = st.number_input("Room ID", step=1, min_value=1)
            
            st.subheader("Meal Information")
            weekday = st.selectbox("Weekday for Meal", ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"])
            meal_type = st.selectbox("Meal Type", ["A", "B"])
            
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
                                
                                # Insert meal using ON DUPLICATE KEY UPDATE
                                cursor.execute("""
                                    INSERT INTO Meals (student_id, meal_type, weekday)
                                    VALUES (%s, %s, %s)
                                    ON DUPLICATE KEY UPDATE meal_type = VALUES(meal_type)
                                """, (student_id, meal_type, weekday))
                                
                                # Insert health issue if provided
                                if add_health_info:
                                    cursor.execute("INSERT INTO health_issues (student_id, description, prescription, guardian_contact) VALUES (%s, %s, %s, %s)",
                                                  (student_id, health_desc, prescription, guardian_contact))
                                
                                # Insert penalty record
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
                                st.success("Student added successfully!")
                            except mysql.connector.Error as e:
                                conn.rollback()
                                st.error(f"Database Error: {e}")
                    else:
                        st.error("Room does not exist.")

    # --- SEARCH & EDIT STUDENT ---
    st.subheader("🔍 Search Student")
    search_id = st.number_input("Search Student by ID", step=1, key="search", min_value=1)
    
    if st.button("Search"):
        try:
            # Get student info
            cursor.execute("SELECT * FROM student WHERE id = %s", (search_id,))
            student = cursor.fetchone()
            
            if student:
                st.json(student)
                
                st.subheader("✏️ Change Meal")
                # Fetch current meal info if available
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
                            # Check if a meal record exists for the student and weekday
                            cursor.execute("SELECT COUNT(*) as count FROM Meals WHERE student_id = %s AND weekday = %s", 
                                          (search_id, weekday))
                            meal_exists = cursor.fetchone()['count'] > 0

                            if meal_exists:
                                # Update existing meal record
                                cursor.execute("""
                                    UPDATE Meals 
                                    SET meal_type = %s
                                    WHERE student_id = %s AND weekday = %s
                                """, (meal_type, search_id, weekday))
                                conn.commit()
                                st.success(f"Meal updated for {weekday} to meal type {meal_type}!")
                            else:
                                # Insert new meal record since no existing record was found
                                cursor.execute("""
                                    INSERT INTO Meals (student_id, weekday, meal_type)
                                    VALUES (%s, %s, %s)
                                """, (search_id, weekday, meal_type))
                                conn.commit()
                                st.success(f"Meal preference added for {weekday} with meal type {meal_type}!")
                            st.experimental_rerun()
                        except mysql.connector.Error as e:
                            conn.rollback()
                            st.error(f"Error updating meal: {e}")

                # --- HEALTH INFORMATION ---
                st.subheader("🏥 Health Information")
                cursor.execute("SELECT * FROM health_issues WHERE student_id = %s", (search_id,))
                health = cursor.fetchone()
                
                if health:
                    with st.form("health_form"):
                        st.write("Current Health Information")
                        desc = st.text_area("Description", health['description'])
                        prescription = st.text_input("Prescription", health['prescription'])
                        guardian = st.text_input("Guardian Contact", health['guardian_contact'])
                        
                        if st.form_submit_button("Update Health Info"):
                            try:
                                cursor.execute("""
                                    UPDATE health_issues 
                                    SET description=%s, prescription=%s, guardian_contact=%s
                                    WHERE student_id=%s
                                """, (desc, prescription, guardian, search_id))
                                conn.commit()
                                st.success("Health information updated!")
                            except mysql.connector.Error as e:
                                conn.rollback()
                                st.error(f"Error updating health info: {e}")
                else:
                    st.info("No health information found.")
                    with st.form("add_health_form"):
                        st.write("Add Health Information")
                        desc = st.text_area("Description")
                        prescription = st.text_input("Prescription")
                        guardian = st.text_input("Guardian Contact (11 digits)")
                        
                        if st.form_submit_button("Add Health Info"):
                            if len(guardian) != 11 or not guardian.isdigit():
                                st.error("Guardian contact must be exactly 11 digits.")
                            else:
                                try:
                                    cursor.execute("""
                                        INSERT INTO health_issues 
                                        (student_id, description, prescription, guardian_contact)
                                        VALUES (%s, %s, %s, %s)
                                    """, (search_id, desc, prescription, guardian))
                                    conn.commit()
                                    st.success("Health information added!")
                                except mysql.connector.Error as e:
                                    conn.rollback()
                                    st.error(f"Error adding health info: {e}")
            
            else:
                st.error("Student not found.")
        
        except mysql.connector.Error as e:
            st.error(f"Database Error: {e}")

    # --- DELETE STUDENT ---
    st.subheader("🗑️ Delete Student")
    del_id = st.number_input("Enter Student ID to Delete", step=1, min_value=1)
    
    if st.button("Delete Student"):
        try:
            cursor.execute("SELECT room_id FROM student WHERE id = %s", (del_id,))
            room_data = cursor.fetchone()
            
            if room_data:
                room_id = room_data["room_id"]
                
                # Delete all related records
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
                st.success("Student and all related records deleted successfully!")
            else:
                st.error("Student not found.")
        
        except mysql.connector.Error as e:
            conn.rollback()
            st.error(f"Error deleting student: {e}")

# --- CLOSE DB CONNECTION ---
cursor.close()
conn.close()
