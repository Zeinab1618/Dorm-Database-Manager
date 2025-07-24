import streamlit as st
import mysql.connector
import pandas as pd

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
st.subheader("📋 View Any Table")
cursor.execute("SHOW TABLES")
tables = [row[f'Tables_in_{st.secrets["mysql"]["database"]}'] for row in cursor.fetchall()]
# Remove invalid/non-existent ones if they're somehow present
tables = [t for t in tables if t.lower() not in ("meal", "building")]
selected_table = st.selectbox("Select a table to view:", tables)

if st.button("Show Table"):
    cursor.execute(f"SELECT * FROM {selected_table}")
    rows = cursor.fetchall()
    if rows:
        st.write(pd.DataFrame(rows))
    else:
        st.info("No data found.")

# --- ADD STUDENT ---
with st.expander("➕ Add New Student"):
    with st.form("add_student_form"):
        student_id = st.number_input("Student ID", step=1)
        student_name = st.text_input("Name")
        contact = st.text_input("Contact (11 digits)")
        room_id = st.number_input("Room ID", step=1)
        weekday = st.selectbox("Weekday for Meal", ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"])
        meal_choice = st.selectbox("Meal Choice", ["A", "B"])
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

                            cursor.execute("""
                                UPDATE room 
                                SET current_occupancy = (
                                    SELECT COUNT(*) FROM student WHERE room_id = %s
                                )
                                WHERE id = %s
                            """, (room_id, room_id))
                            conn.commit()

                            st.success("Student and meal added. Room occupancy updated.")
                        except mysql.connector.Error as e:
                            conn.rollback()
                            st.error(f"MySQL Error: {e}")
                else:
                    st.error("Room does not exist.")

# --- DELETE STUDENT ---
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

# --- SEARCH & EDIT ---
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

# --- CLOSE DB ---
cursor.close()
conn.close()
