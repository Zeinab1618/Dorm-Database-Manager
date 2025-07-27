import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime
from pytz import timezone

st.set_page_config(page_title="Dorm Database Manager", layout="centered")

# Database connection
def get_connection():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"],
    )

# Load table
def load_table(table_name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM `{table_name}`")
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    return pd.DataFrame(rows, columns=columns)

# Get current time in Egypt
egypt = timezone("Africa/Cairo")
now = datetime.now(egypt)

# ---------------------- Table Choice ----------------------
all_tables = ["Select", "student", "penalty", "MaintenanceRequest", "Meals", "room", "Building", "health_issues"]
table_choice = st.selectbox("Select Table to View", all_tables)

if table_choice != "Select":
    st.subheader(f"{table_choice} Table")
    if st.button("🔄 Reload Table"):
        st.dataframe(load_table(table_choice))
    else:
        st.dataframe(load_table(table_choice))

# --------------- Operations for student table ---------------
if table_choice == "student":
    # Delete student
    st.markdown("### 🔥 Delete Student")
    with st.expander("🗑️ Delete Student"):
        student_id = st.number_input("Student ID to Delete", step=1)
        if st.button("Delete"):
            conn = get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM student WHERE student_id = %s", (student_id,))
                conn.commit()
                st.success("Student deleted successfully.")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                conn.close()

    # Add student
    st.markdown("### ✨ Add Student")
    with st.expander("➕ Add Student"):
        sid = st.number_input("Student ID", step=1)
        name = st.text_input("Student Name")
        contact = st.text_input("Contact Number")
        room_id = st.number_input("Room ID", step=1)
        weekday = st.selectbox("Weekday", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
        meal_choice = st.selectbox("Meal Choice", ["A", "B"])
        presc = st.text_input("Prescription")
        descr = st.text_input("Description")
        if st.button("Add Student"):
            conn = get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO student (student_id, name, contact_number, room_id) VALUES (%s, %s, %s, %s)", (sid, name, contact, room_id))
                cursor.execute("REPLACE INTO Meals (student_id, weekday, meal_choice) VALUES (%s, %s, %s)", (sid, weekday, meal_choice))
                cursor.execute("INSERT INTO health_issues (student_id, prescription, description) VALUES (%s, %s, %s)", (sid, presc, descr))
                cursor.execute("INSERT INTO penalty (student_id, total_points, last_updated) VALUES (%s, %s, %s)", (sid, 0, now))
                # Update room occupancy
                cursor.execute("UPDATE room SET current_occupancy = (SELECT COUNT(*) FROM student WHERE room_id = %s) WHERE room_id = %s", (room_id, room_id))
                conn.commit()
                st.success("Student added successfully.")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                conn.close()

# ---------------- Operations for penalty table ----------------
elif table_choice == "penalty":
    st.markdown("### 🛠️ Update Penalty Points")
    with st.expander("✏️ Edit Total Points"):
        student_id = st.number_input("Student ID", step=1, key="penalty_id")
        new_points = st.number_input("New Total Points", step=1)
        if st.button("Update Penalty"):
            conn = get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("UPDATE penalty SET total_points = %s, last_updated = %s WHERE student_id = %s", (new_points, now, student_id))
                conn.commit()
                st.success("Penalty updated successfully.")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                conn.close()

# ----------- Update MaintenanceRequest or health_issues ---------
elif table_choice in ["MaintenanceRequest", "health_issues"]:
    st.markdown(f"### 🧾 Update {table_choice}")
    with st.expander("✏️ Edit Row"):
        student_id = st.number_input("Student ID", step=1, key="update_id")
        col1 = st.text_input("Column to Update (exclude student_id)")
        new_val = st.text_input("New Value")
        if st.button("Update Row"):
            conn = get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(f"UPDATE {table_choice} SET {col1} = %s WHERE student_id = %s", (new_val, student_id))
                conn.commit()
                st.success(f"{table_choice} updated successfully.")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                conn.close()
