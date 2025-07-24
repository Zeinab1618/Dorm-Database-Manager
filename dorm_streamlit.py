import streamlit as st
import mysql.connector
import pandas as pd
import datetime

# --- DB CONNECTION ---
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

# --- VIEW TABLE ---
st.subheader("📋 View Any Table")
cursor.execute("SHOW TABLES")
tables = [row[f'Tables_in_{st.secrets["mysql"]["database"]}'] for row in cursor.fetchall()]
tables = [t for t in tables if t.lower() not in ("meal", "building")]  # remove invalid names
selected_table = st.selectbox("Select a table to view:", tables)

if st.button("Show Table"):
    cursor.execute(f"SELECT * FROM {selected_table}")
    rows = cursor.fetchall()
    if rows:
        st.write(pd.DataFrame(rows))
    else:
        st.info("No data found.")

# --- DYNAMIC OPERATIONS ---
if selected_table:
    st.markdown("---")
    if selected_table.lower() == "student":

        with st.expander("➕ Add New Student"):
            with st.form("add_student_form"):
                student_id = st.number_input("Student ID", step=1)
                student_name = st.text_input("Name")
                contact = st.text_input("Contact (11 digits)")
                room_id = st.number_input("Room ID", step=1)
                weekday = st.selectbox("Weekday for Meal", ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"])
                meal_choice = st.selectbox("Meal Choice", ["A", "B"])

                # Optional Health Issue Fields
                add_health = st.checkbox("Add Health Issue Info")
                if add_health:
                    description = st.text_area("Health Description")
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
                                    # Insert Student
                                    cursor.execute("INSERT INTO student (id, student_Name, contact, room_id) VALUES (%s, %s, %s, %s)",
                                                   (student_id, student_name, contact, room_id))
                                    conn.commit()

                                    # Add Meal
                                    cursor.execute("REPLACE INTO Meals (student_id, meal_type, weekday) VALUES (%s, %s, %s)",
                                                   (student_id, meal_choice, weekday))
                                    conn.commit()

                                    # Add Penalty
                                    cursor.execute("INSERT INTO Penalty (student_id, total_points, last_updated) VALUES (%s, 0, %s)",
                                                   (student_id, datetime.datetime.now()))
                                    conn.commit()

                                    # Optional: Add Health
                                    if add_health:
                                        cursor.execute("INSERT INTO health_issues VALUES (%s, %s, %s, %s)",
                                                       (student_id, description, prescription, guardian_contact))
                                        conn.commit()

                                    # Update Room Occupancy
                                    cursor.execute("""
                                        UPDATE room 
                                        SET current_occupancy = (
                                            SELECT COUNT(*) FROM student WHERE room_id = %s
                                        )
                                        WHERE id = %s
                                    """, (room_id, room_id))
                                    conn.commit()

                                    st.success("Student added with related info!")
                                except mysql.connector.Error as e:
                                    conn.rollback()
                                    st.error(f"MySQL Error: {e}")
                        else:
                            st.error("Room does not exist.")

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

                    st.warning("Student deleted with related records.")
                except mysql.connector.Error as e:
                    conn.rollback()
                    st.error(f"Error deleting student: {e}")
            else:
                st.error("Student not found.")

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

    elif selected_table.lower() == "penalty":
        st.subheader("➕ Add New Penalty")
        with st.form("add_penalty"):
            sid = st.number_input("Student ID", step=1)
            points = st.number_input("Total Points", step=1)
            submit_pen = st.form_submit_button("Insert")
            if submit_pen:
                now = datetime.datetime.now()
                try:
                    cursor.execute("INSERT INTO Penalty (student_id, total_points, last_updated) VALUES (%s, %s, %s)",
                                   (sid, points, now))
                    conn.commit()
                    st.success("Penalty inserted.")
                except:
                    conn.rollback()
                    st.error("Insert failed.")

        st.subheader("✏️ Update Penalty Points")
        with st.form("update_penalty"):
            sid = st.number_input("Student ID to Update", step=1, key="penalty_update")
            new_points = st.number_input("New Total Points", step=1)
            update_btn = st.form_submit_button("Update Penalty")
            if update_btn:
                now = datetime.datetime.now()
                cursor.execute("UPDATE Penalty SET total_points=%s, last_updated=%s WHERE student_id=%s",
                               (new_points, now, sid))
                conn.commit()
                st.success("Penalty updated.")

    elif selected_table.lower() in ("maintenance_requests", "health_issues"):
        st.subheader("✏️ Update Record")
        cursor.execute(f"SELECT * FROM {selected_table}")
        rows = cursor.fetchall()
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df)
            record_id = st.number_input("Enter Student ID to Edit", step=1)
            if st.button("Load Record"):
                cursor.execute(f"SELECT * FROM {selected_table} WHERE student_id = %s", (record_id,))
                data = cursor.fetchone()
                if data:
                    new_data = {}
                    for key in data:
                        if key != "student_id":
                            new_data[key] = st.text_input(f"{key}", value=data[key])
                    if st.button("Update Record"):
                        update_query = f"UPDATE {selected_table} SET " + ", ".join(
                            f"{key} = %s" for key in new_data.keys()) + " WHERE student_id = %s"
                        values = list(new_data.values()) + [record_id]
                        cursor.execute(update_query, values)
                        conn.commit()
                        st.success("Record updated.")
                else:
                    st.warning("ID not found.")

# --- CLOSE DB ---
cursor.close()
conn.close()
