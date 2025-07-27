import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime
from pytz import timezone

conn = mysql.connector.connect(
    host=st.secrets["mysql"]["host"],
    user=st.secrets["mysql"]["user"],
    password=st.secrets["mysql"]["password"],
    database=st.secrets["mysql"]["database"]
)
cursor = conn.cursor()

st.title("Dorm Database Management")

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
            meal_choice = st.selectbox("Meal Choice", ["A", "B"])
            weekday = st.selectbox("Weekday", ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
            prescription = st.text_area("Prescription")
            description = st.text_area("Health Issue Description")
            if st.button("Submit Student"):
                cursor.execute("INSERT INTO student (name, room_id, phone_number) VALUES (%s, %s, %s)", (name, room_id, phone_number))
                conn.commit()
                cursor.execute("SELECT student_id FROM student WHERE name = %s AND room_id = %s ORDER BY student_id DESC LIMIT 1", (name, room_id))
                student_id = cursor.fetchone()[0]
                cursor.execute("REPLACE INTO Meals (student_id, weekday, meal_choice) VALUES (%s, %s, %s)", (student_id, weekday, meal_choice))
                conn.commit()
                cursor.execute("INSERT INTO health_issues (student_id, prescription, description) VALUES (%s, %s, %s)", (student_id, prescription, description))
                conn.commit()
                now = datetime.now(timezone('Africa/Cairo')).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("INSERT INTO penalty (student_id, total_points, last_update) VALUES (%s, %s, %s)", (student_id, 0, now))
                conn.commit()
                cursor.execute("UPDATE room SET occupancy = occupancy + 1 WHERE room_id = %s", (room_id,))
                conn.commit()
                st.success("Student added successfully")

        st.subheader("Search Student")
        search_id = st.text_input("Enter Student ID to Search")
        if search_id:
            student_query = pd.read_sql(f"SELECT * FROM student WHERE student_id = {search_id}", conn)
            st.dataframe(student_query)

            st.subheader("Update Meal Choice")
            weekday_update = st.selectbox("Weekday to Update", ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], key="update")
            meal_update = st.selectbox("New Meal Choice", ["A", "B"], key="meal")
            if st.button("Submit Meal Update"):
                cursor.execute("SELECT * FROM Meals WHERE student_id = %s AND weekday = %s", (search_id, weekday_update))
                if cursor.fetchone():
                    cursor.execute("UPDATE Meals SET meal_choice = %s WHERE student_id = %s AND weekday = %s", (meal_update, search_id, weekday_update))
                else:
                    cursor.execute("INSERT INTO Meals (student_id, weekday, meal_choice) VALUES (%s, %s, %s)",(search_id, weekday_update, meal_update))
                conn.commit()
                st.success("Meal updated successfully")
                                   
            st.subheader("Update Health Issue")
            new_prescription = st.text_area("New Prescription")
            new_description = st.text_area("New Description")
            if st.button("Submit Health Update"):
                cursor.execute("UPDATE health_issues SET prescription = %s, description = %s WHERE student_id = %s", (new_prescription, new_description, search_id))
                conn.commit()
                st.success("Health issue updated successfully")

            if st.button("Delete Student"):
                cursor.execute("SELECT room_id FROM student WHERE student_id = %s", (search_id,))
                room_id = cursor.fetchone()[0]
                cursor.execute("DELETE FROM Meals WHERE student_id = %s", (search_id,))
                cursor.execute("DELETE FROM health_issues WHERE student_id = %s", (search_id,))
                cursor.execute("DELETE FROM penalty WHERE student_id = %s", (search_id,))
                cursor.execute("DELETE FROM student WHERE student_id = %s", (search_id,))
                conn.commit()
                cursor.execute("UPDATE room SET occupancy = occupancy - 1 WHERE room_id = %s", (room_id,))
                conn.commit()
                st.success("Student deleted successfully")

    elif table == "penalty":
        st.subheader("Add Penalty")
        student_id = st.text_input("Student ID")
        total_points = st.number_input("Total Points", step=1)
        if st.button("Submit Penalty"):
            now = datetime.now(timezone('Africa/Cairo')).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("INSERT INTO penalty (student_id, total_points, last_update) VALUES (%s, %s, %s)", (student_id, total_points, now))
            conn.commit()
            st.success("Penalty added successfully")

        st.subheader("Update Total Points")
        penalty_id = st.text_input("Penalty ID to Update")
        updated_points = st.number_input("New Total Points", step=1, key="penalty")
        if st.button("Submit Penalty Update"):
            now = datetime.now(timezone('Africa/Cairo')).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("UPDATE penalty SET total_points = %s, last_update = %s WHERE penalty_id = %s", (updated_points, now, penalty_id))
            conn.commit()
            st.success("Penalty updated successfully")

    elif table in ["maintenance_requests", "health_issues"]:
        st.subheader("Update Record")
        row_id = st.text_input("Enter ID to Update")
        col_name = st.text_input("Enter Column Name to Update")
        new_val = st.text_input("Enter New Value")
        if st.button("Submit Update"):
            cursor.execute(f"UPDATE {table} SET {col_name} = %s WHERE {table}_id = %s", (new_val, row_id))
            conn.commit()
            st.success("Update successful")

cursor.close()
conn.close()
