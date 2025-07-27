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
selected_table = st.selectbox("Select a table to view:", tables, key="view_table_select")

if st.button("Show Table", key="show_table_button"):
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
            student_id = st.number_input("Student ID", step=1, min_value=1, key="add_student_id")
            student_name = st.text_input("Name", key="add_student_name")
            contact = st.text_input("Contact (11 digits)", key="add_student_contact")
            room_id = st.number_input("Room ID", step=1, min_value=1, key="add_room_id")
            
            st.subheader("Meal Information")
            weekday = st.selectbox("Weekday for Meal", ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], key="add_meal_weekday")
            meal_type = st.selectbox("Meal Type", ["A", "B"], key="add_meal_type")
            
            st.subheader("Health Information (Optional)")
            add_health_info = st.checkbox("Add Health Information", key="add_health_check")
            health_desc = st.text_area("Health Description", disabled=not add_health_info, key="add_health_desc")
            prescription = st.text_input("Prescription", disabled=not add_health_info, key="add_health_prescription")
            guardian_contact = st.text_input("Guardian Contact (11 digits)", disabled=not add_health_info, key="add_health_guardian")
            
            submitted = st.form_submit_button("Add Student", key="add_student_submit")

            if submitted:
                if len(contact) != 11 or not contact.isdigit():
                    st.error("Contact must be exactly 11 digits.")
                elif add_health_info and (not health_desc or not prescription or not guardian_contact):
                    st.error("All health fields are required if health information is added.")
                elif add_health_info and (len(guardian_contact) != 11 or not guardian_contact.isdigit()):
                    st.error("Guardian contact must be exactly 11 digits.")
                else:
                    cursor.execute("SELECT capacity, current_occupancy FROM room WHERE id = %s", (int(room_id),))
                    room = cursor.fetchone()
                    if room:
                        if room["current_occupancy"] >= room["capacity"]:
                            st.error("Room is full.")
                        else:
                            try:
                                # Insert student
                                cursor.execute("INSERT INTO student (id, student_Name, contact, room_id) VALUES (%s, %s, %s, %s)",
                                              (int(student_id), student_name, contact, int(room_id)))
                                
                                # Insert meal using ON DUPLICATE KEY UPDATE
                                cursor.execute("""
                                    INSERT INTO Meals (student_id, meal_type, weekday)
                                    VALUES (%s, %s, %s)
                                    ON DUPLICATE KEY UPDATE meal_type = VALUES(meal_type)
                                """, (int(student_id), meal_type, weekday))
                                
                                # Insert health issue if provided
                                if add_health_info:
                                    cursor.execute("INSERT INTO health_issues (student_id, description, prescription, guardian_contact) VALUES (%s, %s, %s, %s)",
                                                  (int(student_id), health_desc, prescription, guardian_contact))
                                
                                # Insert penalty record
                                cursor.execute("INSERT INTO Penalty (student_id, total_points, last_updated) VALUES (%s, %s, %s)",
                                              (int(student_id), 0, datetime.now(eest)))
                                
                                # Update room occupancy
                                cursor.execute("""
                                    UPDATE room 
                                    SET current_occupancy = (
                                        SELECT COUNT(*) FROM student WHERE room_id = %s
                                    )
                                    WHERE id = %s
                                """, (int(room_id), int(room_id)))
                                
                                conn.commit()
                                st.success("Student added successfully!")
                            except mysql.connector.Error as e:
                                conn.rollback()
                                st.error(f"Database Error: {e}")
                    else:
                        st.error("Room does not exist.")

    # --- SEARCH & EDIT STUDENT ---
    st.subheader("🔍 Search Student")
    search_id = st.number_input("Search Student by ID", step=1, min_value=1, value=1, key="search_student_id")
    
    if st.button("Search", key="search_button"):
        try:
            # Get student info
            cursor.execute("SELECT * FROM student WHERE id = %s", (int(search_id),))
            student = cursor.fetchone()
            
            if student:
                st.subheader("Student Information")
                st.json(student)
                
                # --- MEAL MANAGEMENT ---
                st.subheader("Update Meal Preference")
                # Fetch all meal preferences for the student
                cursor.execute("SELECT meal_type, weekday FROM Meals WHERE student_id = %s", (int(search_id),))
                meals = cursor.fetchall()
                
                if meals:
                    st.write("Current Meal Preferences:")
                    st.dataframe(pd.DataFrame(meals))
                else:
                    st.info("No meal preferences found for this student.")
                
                with st.form("update_meal_form_unique"):
                    st.write("Update or Add Meal Preference")
                    weekday_update = st.selectbox("Weekday to Update",
                                                   ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                                                   key="meal_weekday")
                    meal_update = st.selectbox("New Meal Type", ["A", "B"], key="meal_type")
                    
                    # ✅
                    meal_submitted = st.form_submit_button("Submit Meal Update", key="submit_meal_update")
                
                    if meal_submitted:
                        try:
                            student_id = int(search_id)
                            cursor.execute("""
                                INSERT INTO Meals (student_id, weekday, meal_type)
                                VALUES (%s, %s, %s)
                                ON DUPLICATE KEY UPDATE meal_type = VALUES(meal_type)
                            """, (student_id, weekday_update, meal_update))
                            conn.commit()
                            st.success("Meal preference updated successfully")
                            st.experimental_rerun()
                        except mysql.connector.Error as e:
                            conn.rollback()
                            st.error(f"Error updating meal: {e}")

                
                # --- HEALTH INFORMATION ---
                st.subheader("🏥 Health Information")
                cursor.execute("SELECT * FROM health_issues WHERE student_id = %s", (int(search_id),))
                health = cursor.fetchone()
                
                if health:
                    with st.form("health_form"):
                        st.write("Current Health Information")
                        desc = st.text_area("Description", health['description'], key="health_desc")
                        prescription = st.text_input("Prescription", health['prescription'], key="health_prescription")
                        guardian = st.text_input("Guardian Contact", health['guardian_contact'], key="health_guardian")
                        
                        if st.form_submit_button("Update Health Info", key="health_submit"):
                            try:
                                cursor.execute("""
                                    UPDATE health_issues 
                                    SET description=%s, prescription=%s, guardian_contact=%s
                                    WHERE student_id=%s
                                """, (desc, prescription, guardian, int(search_id)))
                                conn.commit()
                                st.success("Health information updated!")
                            except mysql.connector.Error as e:
                                conn.rollback()
                                st.error(f"Error updating health info: {e}")
                else:
                    st.info("No health information found.")
                    with st.form("add_health_form"):
                        st.write("Add Health Information")
                        desc = st.text_area("Description", key="add_health_desc")
                        prescription = st.text_input("Prescription", key="add_health_prescription")
                        guardian = st.text_input("Guardian Contact (11 digits)", key="add_health_guardian")
                        
                        if st.form_submit_button("Add Health Info", key="add_health_submit"):
                            if len(guardian) != 11 or not guardian.isdigit():
                                st.error("Guardian contact must be exactly 11 digits.")
                            else:
                                try:
                                    cursor.execute("""
                                        INSERT INTO health_issues 
                                        (student_id, description, prescription, guardian_contact)
                                        VALUES (%s, %s, %s, %s)
                                    """, (int(search_id), desc, prescription, guardian))
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
    del_id = st.number_input("Enter Student ID to Delete", step=1, min_value=1, value=1, key="delete_student_id")
    
    if st.button("Delete Student", key="delete_button"):
        try:
            cursor.execute("SELECT room_id FROM student WHERE id = %s", (int(del_id),))
            room_data = cursor.fetchone()
            
            if room_data:
                room_id = room_data["room_id"]
                
                # Delete all related records
                cursor.execute("DELETE FROM Meals WHERE student_id = %s", (int(del_id),))
                cursor.execute("DELETE FROM health_issues WHERE student_id = %s", (int(del_id),))
                cursor.execute("DELETE FROM Penalty WHERE student_id = %s", (int(del_id),))
                cursor.execute("DELETE FROM student WHERE id = %s", (int(del_id),))
                
                # Update room occupancy
                cursor.execute("""
                    UPDATE room 
                    SET current_occupancy = (
                        SELECT COUNT(*) FROM student WHERE room_id = %s
                    )
                    WHERE id = %s
                """, (int(room_id), int(room_id)))
                
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
