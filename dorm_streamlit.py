import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime

# Database connection
conn = mysql.connector.connect(
    host=st.secrets["mysql"]["host"],
    user=st.secrets["mysql"]["user"],
    password=st.secrets["mysql"]["password"],
    database=st.secrets["mysql"]["database"]
)
cursor = conn.cursor(dictionary=True)

st.title("🏢 Student Housing Management Dashboard")

# --- Helper to get tables ---
def get_existing_tables():
    cursor.execute("SHOW TABLES")
    return [list(t.values())[0] for t in cursor.fetchall()]

# --- Helper to load selected table ---
def load_table(table):
    cursor.execute(f"SELECT * FROM {table}")
    df = pd.DataFrame(cursor.fetchall())
    st.dataframe(df)

# --- Helper to update room occupancy ---
def update_room_occupancy(room_id):
    cursor.execute("SELECT COUNT(*) as count FROM student WHERE room_id = %s", (room_id,))
    count = cursor.fetchone()["count"]
    cursor.execute("UPDATE room SET current_occupancy = %s WHERE id = %s", (count, room_id))
    conn.commit()

# --- View any table ---
st.subheader("📋 View Any Table")
available_tables = get_existing_tables()
selected_table = st.selectbox("Choose a table", available_tables)

if st.button("📄 Load Table"):
    load_table(selected_table)

# === Student Operations ===
if selected_table == "student":
    st.subheader("➕ Add Student")
    with st.form("add_student_form"):
        sid = st.number_input("Student ID", step=1)
        name = st.text_input("Name")
        contact = st.text_input("Contact")
        room_id = st.number_input("Room ID", step=1)
        weekday = st.selectbox("Weekday", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
        meal_type = st.selectbox("Meal Type", ["A", "B"])
        health_desc = st.text_area("Health Description")
        prescription = st.text_input("Prescription")
        guardian = st.text_input("Guardian Contact")
        submitted = st.form_submit_button("Add Student")

        if submitted:
            cursor.execute("SELECT capacity, current_occupancy FROM room WHERE id = %s", (room_id,))
            room = cursor.fetchone()
            if not room:
                st.error("Room does not exist.")
            elif room["current_occupancy"] >= room["capacity"]:
                st.warning("Room is full. Choose another room.")
            else:
                cursor.execute("INSERT INTO student (id, student_Name, contact, room_id) VALUES (%s, %s, %s, %s)",
                               (sid, name, contact, room_id))
                cursor.execute("INSERT INTO Meals (student_id, meal_type, weekday) VALUES (%s, %s, %s)",
                               (sid, meal_type, weekday))
                cursor.execute("INSERT INTO Penalty (student_id, total_points, time_updated) VALUES (%s, %s, %s)",
                               (sid, 0, datetime.now()))
                if health_desc and prescription:
                    cursor.execute("INSERT INTO health_issues (student_id, description, prescription, guardian_contact) VALUES (%s, %s, %s, %s)",
                                   (sid, health_desc, prescription, guardian))
                update_room_occupancy(room_id)
                conn.commit()
                st.success("Student and related records added!")

    # Delete student
    st.subheader("❌ Delete Student")
    delete_id = st.number_input("Enter Student ID to Delete", step=1, format="%d")
    if st.button("Delete Student"):
        cursor.execute("SELECT room_id FROM student WHERE id = %s", (delete_id,))
        result = cursor.fetchone()
        if result:
            room_id = result["room_id"]
            cursor.execute("DELETE FROM Meals WHERE student_id = %s", (delete_id,))
            cursor.execute("DELETE FROM health_issues WHERE student_id = %s", (delete_id,))
            cursor.execute("DELETE FROM Penalty WHERE student_id = %s", (delete_id,))
            cursor.execute("DELETE FROM student WHERE id = %s", (delete_id,))
            update_room_occupancy(room_id)
            conn.commit()
            st.success("Student and all related data deleted.")
        else:
            st.warning("Student ID not found.")

    # Update meals
    st.subheader("🍽️ Update Student Meal")
    meal_id = st.number_input("Meal Student ID", step=1)
    new_meal = st.selectbox("New Meal Type", ["A", "B"], key="meal_update")
    new_day = st.selectbox("New Weekday", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], key="day_update")
    if st.button("Update Meal"):
        cursor.execute("REPLACE INTO Meals (student_id, meal_type, weekday) VALUES (%s, %s, %s)",
                       (meal_id, new_meal, new_day))
        conn.commit()
        st.success("Meal updated!")

    # Update health issues
    st.subheader("🩺 Update Health Info")
    hid = st.number_input("Student ID (Health)", step=1)
    new_desc = st.text_area("New Description")
    new_presc = st.text_input("New Prescription")
    new_guard = st.text_input("New Guardian Contact")
    if st.button("Update Health Info"):
        cursor.execute("UPDATE health_issues SET description=%s, prescription=%s, guardian_contact=%s WHERE student_id = %s",
                       (new_desc, new_presc, new_guard, hid))
        conn.commit()
        st.success("Health info updated!")

# === Penalty ===
elif selected_table == "penalty":
    st.subheader("📝 Update Penalty Points")
    pid = st.number_input("Student ID", step=1)
    new_pts = st.number_input("New Total Points", step=1)
    if st.button("Update Penalty"):
        cursor.execute("UPDATE Penalty SET total_points = %s, time_updated = %s WHERE student_id = %s",
                       (new_pts, datetime.now(), pid))
        conn.commit()
        st.success("Penalty updated!")

# === Maintenance ===
elif selected_table == "maintenance_requests":
    st.subheader("🛠️ Update Request Status")
    req_id = st.number_input("Request ID", step=1)
    new_status = st.text_input("New Status")
    if st.button("Update Status"):
        cursor.execute("UPDATE maintenance_requests SET request_status = %s WHERE id = %s",
                       (new_status, req_id))
        conn.commit()
        st.success("Maintenance request updated!")
