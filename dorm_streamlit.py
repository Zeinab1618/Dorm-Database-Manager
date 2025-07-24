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
tables = [t for t in tables if t.lower() not in ("meal", "building")]
selected_table = st.selectbox("📋 Select a table to view:", tables)

if selected_table:
    cursor.execute(f"SELECT * FROM {selected_table}")
    rows = cursor.fetchall()
    st.subheader(f"📄 {selected_table} Table Data")
    st.dataframe(pd.DataFrame(rows))

    # --- STUDENT TABLE OPERATIONS ---
    if selected_table == "student":
        with st.expander("➕ Add Student"):
            with st.form("add_student_form"):
                student_id = st.number_input("Student ID", step=1)
                student_name = st.text_input("Name")
                contact = st.text_input("Contact (11 digits)")
                room_id = st.number_input("Room ID", step=1)
                weekday = st.selectbox("Meal Weekday", ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"])
                meal_choice = st.selectbox("Meal Choice", ["A", "B"])

                # Health Issue
                st.markdown("**Health Issue (Optional)**")
                description = st.text_area("Description")
                prescription = st.text_input("Prescription")
                guardian_contact = st.text_input("Guardian Contact")

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
                                    conn.commit()

                                    cursor.execute("REPLACE INTO Meals (student_id, meal_type, weekday) VALUES (%s, %s, %s)",
                                                   (student_id, meal_choice, weekday))
                                    conn.commit()

                                    cursor.execute("UPDATE room SET current_occupancy = (SELECT COUNT(*) FROM student WHERE room_id = %s) WHERE id = %s",
                                                   (room_id, room_id))
                                    conn.commit()

                                    cursor.execute("INSERT INTO penalty (student_id, total_points, time_of_penalty) VALUES (%s, %s, %s)",
                                                   (student_id, 0, datetime.now()))
                                    conn.commit()

                                    if description or prescription or guardian_contact:
                                        cursor.execute("INSERT INTO health_issues (student_id, description, prescription, guardian_contact) VALUES (%s, %s, %s, %s)",
                                                       (student_id, description, prescription, guardian_contact))
                                        conn.commit()

                                    st.success("Student, meal, penalty, and optional health issue added successfully.")
                                except mysql.connector.Error as e:
                                    conn.rollback()
                                    st.error(f"MySQL Error: {e}")
                        else:
                            st.error("Room does not exist.")

        st.subheader("🗑️ Delete Student")
        del_id = st.number_input("Student ID to Delete", step=1)
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
                    conn.commit()

                    cursor.execute("UPDATE room SET current_occupancy = (SELECT COUNT(*) FROM student WHERE room_id = %s) WHERE id = %s",
                                   (room_id, room_id))
                    conn.commit()
                    st.success("Student and related records deleted.")
                except mysql.connector.Error as e:
                    conn.rollback()
                    st.error(f"Error deleting student: {e}")
            else:
                st.error("Student ID not found.")

        st.subheader("🔍 Search Student")
        search_id = st.number_input("Enter Student ID to Search", step=1, key="search")
        if st.button("Search Student"):
            cursor.execute("SELECT * FROM student WHERE id = %s", (search_id,))
            student = cursor.fetchone()
            if student:
                st.json(student)

                st.subheader("✏️ Update Meal")
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
                        cursor.execute("""UPDATE health_issues 
                                          SET description=%s, prescription=%s, guardian_contact=%s 
                                          WHERE student_id=%s""",
                                       (desc, prescription, guardian, search_id))
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

    # --- PENALTY TABLE OPERATIONS ---
    elif selected_table == "penalty":
        st.subheader("➕ Add Penalty")
        sid = st.number_input("Student ID", step=1)
        points = st.number_input("Total Points", step=1)
        if st.button("Add Penalty"):
            try:
                cursor.execute("INSERT INTO penalty (student_id, total_points, time_of_penalty) VALUES (%s, %s, %s)",
                               (sid, points, datetime.now()))
                conn.commit()
                st.success("Penalty added!")
            except mysql.connector.Error as e:
                st.error(f"MySQL Error: {e}")

        st.subheader("✏️ Update Total Points Only")
        update_id = st.number_input("Penalty Student ID to Update", step=1, key="update_penalty")
        new_points = st.number_input("New Total Points", step=1, key="new_points")
        if st.button("Update Penalty"):
            try:
                cursor.execute("UPDATE penalty SET total_points=%s, time_of_penalty=%s WHERE student_id=%s",
                               (new_points, datetime.now(), update_id))
                conn.commit()
                st.success("Penalty updated.")
            except mysql.connector.Error as e:
                st.error(f"MySQL Error: {e}")

    # --- MAINTENANCE & HEALTH ISSUES UPDATE ---
    elif selected_table in ["maintenance_requests", "health_issues"]:
        st.subheader("✏️ Update Record (Not Student ID)")
        cursor.execute(f"SELECT * FROM {selected_table}")
        records = cursor.fetchall()
        if records:
            record_df = pd.DataFrame(records)
            editable_id = st.selectbox("Select Record to Update", record_df.iloc[:, 0].tolist())
            editable = next((r for r in records if r[list(r.keys())[0]] == editable_id), None)
            if editable:
                update_data = {}
                for key, val in editable.items():
                    if key == "student_id":
                        continue  # don't allow updating student_id
                    new_val = st.text_input(f"{key}", value=str(val))
                    update_data[key] = new_val
                if st.button("Update Record"):
                    set_clause = ", ".join([f"{k} = %s" for k in update_data.keys()])
                    values = list(update_data.values()) + [editable_id]
                    pk_col = list(editable.keys())[0]
                    try:
                        cursor.execute(f"UPDATE {selected_table} SET {set_clause} WHERE {pk_col} = %s", values)
                        conn.commit()
                        st.success(f"{selected_table} record updated.")
                    except mysql.connector.Error as e:
                        st.error(f"MySQL Error: {e}")
else:
    st.warning("Please select a table to view.")

# --- CLOSE CONNECTION ---
cursor.close()
conn.close()
