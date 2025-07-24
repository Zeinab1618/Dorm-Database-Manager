import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime

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

st.title("Student Dorm Management")

# --- VALID TABLES TO SHOW ---
cursor.execute("SHOW TABLES")
raw_tables = [row[f'Tables_in_{st.secrets["mysql"]["database"]}'] for row in cursor.fetchall()]
valid_tables = [t for t in raw_tables if t.lower() not in ["meal", "building"]]
selected_table = st.selectbox("Select a table to view:", valid_tables)

# --- SHOW SELECTED TABLE ---
if st.button("Show Table"):
    cursor.execute(f"SELECT * FROM {selected_table}")
    data = cursor.fetchall()
    st.write(pd.DataFrame(data))

    # --- STUDENT OPERATIONS ---
    if selected_table == "student":
        with st.expander("➕ Add New Student"):
            with st.form("add_student_form"):
                student_id = st.number_input("Student ID", step=1)
                student_name = st.text_input("Name")
                contact = st.text_input("Contact (11 digits)")
                room_id = st.number_input("Room ID", step=1)
                weekday = st.selectbox("Weekday for Meal", ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"])
                meal_choice = st.selectbox("Meal Choice", ["A", "B"])
                submit_add = st.form_submit_button("Add Student")

                if submit_add:
                    if len(contact) != 11 or not contact.isdigit():
                        st.error("Contact must be exactly 11 digits.")
                    else:
                        cursor.execute("SELECT capacity FROM room WHERE id = %s", (room_id,))
                        room = cursor.fetchone()
                        if room:
                            cursor.execute("SELECT COUNT(*) AS cnt FROM student WHERE room_id = %s", (room_id,))
                            count = cursor.fetchone()["cnt"]
                            if count >= room["capacity"]:
                                st.error("Room is full.")
                            else:
                                try:
                                    cursor.execute("INSERT INTO student VALUES (%s, %s, %s, %s)",
                                                   (student_id, student_name, contact, room_id))
                                    cursor.execute("REPLACE INTO Meals VALUES (%s, %s, %s)",
                                                   (student_id, meal_choice, weekday))
                                    cursor.execute("INSERT INTO penalty (student_id, total_points, time) VALUES (%s, %s, %s)",
                                                   (student_id, 0, datetime.now()))
                                    cursor.execute("""
                                        UPDATE room SET current_occupancy = (
                                            SELECT COUNT(*) FROM student WHERE room_id = %s
                                        ) WHERE id = %s
                                    """, (room_id, room_id))
                                    conn.commit()
                                    st.success("Student, meal, and penalty added. Room updated.")
                                except mysql.connector.Error as e:
                                    conn.rollback()
                                    st.error(e)
                        else:
                            st.error("Room not found.")

        st.subheader("🗑️ Delete Student")
        del_id = st.number_input("Enter Student ID to Delete", step=1, key="del")
        if st.button("Delete Student"):
            cursor.execute("SELECT room_id FROM student WHERE id = %s", (del_id,))
            room_data = cursor.fetchone()
            if room_data:
                try:
                    room_id = room_data["room_id"]
                    cursor.execute("DELETE FROM Meals WHERE student_id = %s", (del_id,))
                    cursor.execute("DELETE FROM health_issues WHERE student_id = %s", (del_id,))
                    cursor.execute("DELETE FROM penalty WHERE student_id = %s", (del_id,))
                    cursor.execute("DELETE FROM student WHERE id = %s", (del_id,))
                    cursor.execute("""
                        UPDATE room SET current_occupancy = (
                            SELECT COUNT(*) FROM student WHERE room_id = %s
                        ) WHERE id = %s
                    """, (room_id, room_id))
                    conn.commit()
                    st.success("Deleted student and related records.")
                except mysql.connector.Error as e:
                    conn.rollback()
                    st.error(e)
            else:
                st.error("Student ID not found.")

        st.subheader("🔍 Search Student")
        search_id = st.number_input("Enter ID", key="search")
        if st.button("Search"):
            cursor.execute("SELECT * FROM student WHERE id = %s", (search_id,))
            student = cursor.fetchone()
            if student:
                st.json(student)

                st.subheader("✏️ Change Meal")
                new_day = st.selectbox("Weekday", ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"])
                new_meal = st.selectbox("Meal", ["A", "B"], key="mealup")
                if st.button("Update Meal"):
                    cursor.execute("REPLACE INTO Meals VALUES (%s, %s, %s)", (search_id, new_meal, new_day))
                    conn.commit()
                    st.success("Meal updated.")

                st.subheader("🏥 Health Issue")
                cursor.execute("SELECT * FROM health_issues WHERE student_id = %s", (search_id,))
                health = cursor.fetchone()
                if health:
                    desc = st.text_area("Description", health["description"])
                    pres = st.text_input("Prescription", health["prescription"])
                    guardian = st.text_input("Guardian Contact", health["guardian_contact"])
                    if st.button("Update Health Issue"):
                        cursor.execute("""
                            UPDATE health_issues SET description=%s, prescription=%s, guardian_contact=%s 
                            WHERE student_id=%s
                        """, (desc, pres, guardian, search_id))
                        conn.commit()
                        st.success("Health issue updated.")
                else:
                    st.info("No record found. Add new one below.")
                    desc = st.text_area("Description")
                    pres = st.text_input("Prescription")
                    guardian = st.text_input("Guardian Contact")
                    if st.button("Insert Health Issue"):
                        cursor.execute("INSERT INTO health_issues VALUES (%s, %s, %s, %s)",
                                       (search_id, desc, pres, guardian))
                        conn.commit()
                        st.success("Health issue added.")
            else:
                st.error("Student not found.")

    # --- PENALTY OPERATIONS ---
    elif selected_table == "penalty":
        st.subheader("➕ Add New Penalty")
        with st.form("add_penalty_form"):
            pid = st.number_input("Student ID", step=1, key="pen_add")
            points = st.number_input("Total Points", step=1)
            submit_penalty = st.form_submit_button("Add Penalty")
            if submit_penalty:
                try:
                    cursor.execute("INSERT INTO penalty VALUES (%s, %s, %s)",
                                   (pid, points, datetime.now()))
                    conn.commit()
                    st.success("Penalty added.")
                except mysql.connector.Error as e:
                    st.error(e)

        st.subheader("✏️ Update Penalty Points")
        up_id = st.number_input("Student ID to Update", step=1, key="pen_up")
        new_points = st.number_input("New Total Points", step=1)
        if st.button("Update Penalty"):
            try:
                cursor.execute("UPDATE penalty SET total_points=%s, time=%s WHERE student_id=%s",
                               (new_points, datetime.now(), up_id))
                conn.commit()
                st.success("Penalty updated.")
            except mysql.connector.Error as e:
                st.error(e)

    # --- HEALTH or MAINTENANCE UPDATE ---
    elif selected_table in ["health_issues", "maintenance_requests"]:
        st.subheader("✏️ Update Records")
        st.info("Make sure to enter a valid student ID from the shown table.")
        row_id = st.number_input("Student ID to Update", step=1, key="gen_up")
        col_name = st.text_input("Column to Update (e.g., description)")
        new_val = st.text_input("New Value")
        if st.button("Update Record"):
            if col_name.lower() == "student_id":
                st.error("You can't update the student ID.")
            else:
                try:
                    cursor.execute(f"UPDATE {selected_table} SET {col_name}=%s WHERE student_id=%s", (new_val, row_id))
                    conn.commit()
                    st.success(f"{selected_table} record updated.")
                except mysql.connector.Error as e:
                    st.error(e)

# --- CLOSE CONNECTION ---
cursor.close()
conn.close()
