import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime
from pytz import timezone

# Database connection with error handling
try:
    conn = mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"],
        port=st.secrets["mysql"]["port"],
        ssl_ca=st.secrets["mysql"]["ssl_ca"],
        connect_timeout=5
    )
    cursor = conn.cursor()
except mysql.connector.Error as e:
    st.error(f"Database connection failed: {e}")
    st.stop()

st.title("Dorm Database Management")

# Get tables list
cursor.execute("SHOW TABLES")
tables = [table[0] for table in cursor.fetchall() if table[0] not in ('Meal', 'building')]
table = st.selectbox("Select Table", ["None"] + tables)

if table != "None":
    df = pd.read_sql(f"SELECT * FROM {table}", conn)
    st.dataframe(df)

    if table == "student":
        with st.expander("Add Student"):
            name = st.text_input("Name")
            room_id = st.text_input("Room ID")
            phone_number = st.text_input("Phone Number")
            meal_type = st.selectbox("Meal Type", ["A", "B"])
            weekday = st.selectbox("Weekday", ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
            prescription = st.text_area("Prescription")
            description = st.text_area("Health Issue Description")
            guardian_contact = st.text_input("Guardian Contact")
            
            if st.button("Submit Student"):
                try:
                    
                    cursor.execute("INSERT INTO student (student_Name, contact, room_id) VALUES (%s, %s, %s)", 
                                  (name, phone_number, room_id))
                    student_id = cursor.lastrowid
                    
                    
                    cursor.execute("INSERT INTO Meals (student_id, meal_type, weekday) VALUES (%s, %s, %s)", 
                                 (student_id, meal_type, weekday))
                    
                   
                    cursor.execute("INSERT INTO health_issues (student_id, description, prescription, guardian_contact) VALUES (%s, %s, %s, %s)", 
                                 (student_id, description, prescription, guardian_contact))
                    
                    
                    now = datetime.now(timezone('Africa/Cairo')).strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute("INSERT INTO Penalty (student_id, total_points, last_updated) VALUES (%s, %s, %s)", 
                                 (student_id, 0, now))
                    
                    
                    cursor.execute("UPDATE room SET current_occupancy = current_occupancy + 1 WHERE id = %s", (room_id,))
                    
                    conn.commit()
                    st.success("Student added successfully")
                except mysql.connector.Error as e:
                    conn.rollback()
                    st.error(f"Error adding student: {e}")

        st.subheader("Search Student")
        search_id = st.text_input("Enter Student ID to Search")
        if search_id:
            try:
                student_query = pd.read_sql(f"SELECT * FROM student WHERE id = {search_id}", conn)
                st.dataframe(student_query)

                st.subheader("Update Meal Preference")
                weekday_update = st.selectbox("Weekday to Update", 
                                           ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], 
                                           key="update")
                meal_update = st.selectbox("New Meal Type", ["A", "B"], key="meal")
                
                if st.button("Submit Meal Update"):
                    try:
                        
                        cursor.execute("""
                            INSERT INTO Meals (student_id, weekday, meal_type)
                            VALUES (%s, %s, %s)
                            ON DUPLICATE KEY UPDATE meal_type = VALUES(meal_type)
                        """, (search_id, weekday_update, meal_update))
                        conn.commit()
                        st.success("Meal preference updated successfully")
                        st.experimental_rerun()
                    except mysql.connector.Error as e:
                        conn.rollback()
                        st.error(f"Error updating meal: {e}")

                st.subheader("Update Health Issue")
                new_prescription = st.text_area("New Prescription")
                new_description = st.text_area("New Description")
                new_guardian = st.text_input("New Guardian Contact")
                
                if st.button("Submit Health Update"):
                    try:
                        cursor.execute("""
                            UPDATE health_issues 
                            SET prescription = %s, description = %s, guardian_contact = %s
                            WHERE student_id = %s
                        """, (new_prescription, new_description, new_guardian, search_id))
                        conn.commit()
                        st.success("Health issue updated successfully")
                    except mysql.connector.Error as e:
                        conn.rollback()
                        st.error(f"Error updating health record: {e}")

                if st.button("Delete Student"):
                    try:
                        cursor.execute("SELECT room_id FROM student WHERE id = %s", (search_id,))
                        room_id = cursor.fetchone()[0]
                        
                       
                        cursor.execute("DELETE FROM Meals WHERE student_id = %s", (search_id,))
                        cursor.execute("DELETE FROM health_issues WHERE student_id = %s", (search_id,))
                        cursor.execute("DELETE FROM Penalty WHERE student_id = %s", (search_id,))
                        cursor.execute("DELETE FROM student WHERE id = %s", (search_id,))
                        
                        
                        cursor.execute("UPDATE room SET current_occupancy = current_occupancy - 1 WHERE id = %s", (room_id,))
                        
                        conn.commit()
                        st.success("Student deleted successfully")
                        st.experimental_rerun()
                    except mysql.connector.Error as e:
                        conn.rollback()
                        st.error(f"Error deleting student: {e}")
            except:
                st.warning("Invalid Student ID")

    elif table == "penalty":
        st.subheader("Add Penalty")
        student_id = st.text_input("Student ID")
        total_points = st.number_input("Total Points", min_value=0, step=1)
        
        if st.button("Submit Penalty"):
            try:
                now = datetime.now(timezone('Africa/Cairo')).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("""
                    INSERT INTO Penalty (student_id, total_points, last_updated)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE total_points = VALUES(total_points), last_updated = VALUES(last_updated)
                """, (student_id, total_points, now))
                conn.commit()
                st.success("Penalty added/updated successfully")
            except mysql.connector.Error as e:
                conn.rollback()
                st.error(f"Error updating penalty: {e}")

    elif table in ["maintenance_requests", "health_issues"]:
        st.subheader("Update Record")
        row_id = st.text_input("Enter ID to Update")
        col_name = st.text_input("Enter Column Name to Update")
        new_val = st.text_input("Enter New Value")
        
        if st.button("Submit Update"):
            try:
                cursor.execute(f"UPDATE {table} SET {col_name} = %s WHERE id = %s", (new_val, row_id))
                conn.commit()
                st.success("Update successful")
            except mysql.connector.Error as e:
                conn.rollback()
                st.error(f"Error updating record: {e}")

cursor.close()
conn.close()
