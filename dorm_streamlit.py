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

# --- VIEW TABLES ---
cursor.execute("SHOW TABLES")
tables = [row[f'Tables_in_{st.secrets["mysql"]["database"]}'] for row in cursor.fetchall()]
# Remove invalid/non-existent ones if they're somehow present
tables = [t for t in tables if t.lower() not in ("meal", "building")]

selected_table = st.selectbox("Select a table to view:", [""] + tables)

if selected_table:
    st.subheader(f"📋 {selected_table} Table")
    cursor.execute(f"SELECT * FROM {selected_table}")
    rows = cursor.fetchall()
    if rows:
        st.write(pd.DataFrame(rows))
    else:
        st.info("No data found.")

    # ---------------------------------------------
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

                st.markdown("**Optional Health Issue**")
                has_health_issue = st.checkbox("Add Health Issue")
                if has_health_issue:
                    desc = st.text_area("Description")
                    prescription = st.text_input("Prescription")
                    guardian = st.text_input("Guardian Contact")

                submitted = st.form_submit_button("Add Student")

                if submitted:
                    if len(contact) != 11 or not contact.isdigit():
                        st.error("Contact must be exactly 11 digits.")
                    else:
                        cursor.execute("SELECT capacity, current_occupancy FROM room WHERE id = %s", (room_id,))
                        room = cursor.fetchone()
                        if room:
                            if room["current_occupancy"] >= room["capacity"]:
                                st.error("Room is full.")
                            else:
                                try:
                                    cursor.execute("INSERT INTO student (id, student_Name, contact, room_id) VALUES (%s, %s, %s, %s)",
                                                   (student_id, student_name, contact, room_id))
                                    cursor.execute("REPLACE INTO Meals (student_id, meal_type, weekday) VALUES (%s, %s, %s)",
                                                   (student_id, meal_choice, weekday))
                                    cursor.execute("""
                                        UPDATE room 
                                        SET current_occupancy = (
                                            SELECT COUNT(*) FROM student WHERE room_id = %s
                                        )
                                        WHERE id = %s
                                    """, (room_id, room_id))
                                    cursor.execute("INSERT INTO Penalty (student_id, total_points, penalty_time) VALUES (%s, %s, %s)",
                                                   (student_id, 0, datetime.now()))

                                    if has_health_issue:
                                        cursor.execute("INSERT INTO health_issues VALUES (%s, %s, %s, %s)",
                                                       (student_id, desc, prescription, guardian))

                                    conn.commit()
                                    st.success("Student and meal added. Penalty and health issue recorded. Room occupancy updated.")
                                except mysql.connector.Error as e:
                                    conn.rollback()
                                    st.error(f"MySQL Error: {e}")
                        else:
                            st.error("Room does not exist.")

        st.subheader("🗑️ Delete Student")
        del_id = st.number_input("Enter Student ID to Delete", step=1)
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
                    conn.commit()

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

        st.subheader("🔍 Search Student")
        search_id = st.number_input("Search Student by ID", step=1, key="search")
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
                    desc = st.text_area("Description")
                    prescription = st.text_input("Prescription")
                    guardian = st.text_input("Guardian Contact")
                    if st.button("Insert Health Issue"):
                        cursor.execute("INSERT INTO health_issues VALUES (%s, %s, %s, %s)",
                                       (search_id, desc, prescription, guardian))
                        conn.commit()
                        st.success("Health issue added!")
            else:
                st.error("Student not found.")

    # ---------------------------------------------
    # --- PENALTY OPERATIONS ---
    elif selected_table == "Penalty":
        st.subheader("➕ Add New Penalty")
        with st.form("penalty_form"):
            student_id = st.number_input("Student ID", step=1)
            total_points = st.number_input("Total Points", step=1)
            submitted = st.form_submit_button("Add Penalty")
            if submitted:
                try:
                    now = datetime.now()
                    cursor.execute("INSERT INTO Penalty (student_id, total_points, penalty_time) VALUES (%s, %s, %s)",
                                   (student_id, total_points, now))
                    conn.commit()
                    st.success("Penalty added.")
                except mysql.connector.Error as e:
                    conn.rollback()
                    st.error(f"MySQL Error: {e}")

        st.subheader("✏️ Update Penalty Points")
        with st.form("update_penalty_form"):
            penalty_id = st.number_input("Student ID to Update", step=1)
            new_points = st.number_input("New Total Points", step=1)
            update_btn = st.form_submit_button("Update Points")
            if update_btn:
                now = datetime.now()
                cursor.execute("UPDATE Penalty SET total_points=%s, penalty_time=%s WHERE student_id=%s",
                               (new_points, now, penalty_id))
                conn.commit()
                st.success("Penalty points updated.")

    # ---------------------------------------------
    # --- MAINTENANCE & HEALTH ISSUES UPDATE ---
    elif selected_table in ["maintenance_requests", "health_issues"]:
        st.subheader("✏️ Update Record")
        st.info("Student ID field is not editable.")
        update_id = st.number_input("Enter Student ID", step=1, key="update_id")
        if st.button("Fetch Record"):
            cursor.execute(f"SELECT * FROM {selected_table} WHERE student_id = %s", (update_id,))
            record = cursor.fetchone()
            if record:
                form_data = {}
                with st.form("update_form"):
                    for key, val in record.items():
                        if key == "student_id":
                            st.text_input("Student ID", value=str(val), disabled=True)
                        else:
                            form_data[key] = st.text_input(f"{key}", value=str(val))
                    submitted = st.form_submit_button("Update Record")
                    if submitted:
                        set_clause = ", ".join(f"{k} = %s" for k in form_data)
                        values = list(form_data.values()) + [update_id]
                        cursor.execute(f"UPDATE {selected_table} SET {set_clause} WHERE student_id = %s", values)
                        conn.commit()
                        st.success("Record updated.")
            else:
                st.error("Record not found.")

# --- CLOSE DB ---
cursor.close()
conn.close()
