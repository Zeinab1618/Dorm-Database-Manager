import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime
from pytz import timezone

# Connect to MySQL
conn = mysql.connector.connect(
    host=st.secrets["mysql"]["host"],
    user=st.secrets["mysql"]["user"],
    password=st.secrets["mysql"]["password"],
    database=st.secrets["mysql"]["database"],
    port=st.secrets["mysql"]["port"],
    ssl_ca=st.secrets["mysql"]["ssl_ca"]
)
cursor = conn.cursor(dictionary=True)

st.title("🏢 Dormitory Database Management System")

# ---------------------- Utilities ----------------------
def load_table(table_name):
    cursor.execute(f"SELECT * FROM {table_name}")
    return pd.DataFrame(cursor.fetchall())

def update_room_occupancy(room_id):
    cursor.execute("SELECT COUNT(*) AS count FROM student WHERE room_id = %s", (room_id,))
    count = cursor.fetchone()["count"]
    cursor.execute("UPDATE room SET current_occupancy = %s WHERE id = %s", (count, room_id))
    conn.commit()

def get_available_rooms():
    cursor.execute("SELECT id, capacity, current_occupancy FROM room")
    return cursor.fetchall()

# Egypt timezone setup
egypt = timezone("Africa/Cairo")
now = datetime.now(egypt)

# ---------------------- Table Choice ----------------------
all_tables = ["Select", "student", "Penalty", "MaintenanceRequest", "Meals", "room", "Building", "health_issues"]
table_choice = st.selectbox("Select Table to View", all_tables)

if table_choice != "Select":
    st.subheader(f"{table_choice} Table")
    if st.button("🔄 Reload Table"):
        st.dataframe(load_table(table_choice))
    else:
        st.dataframe(load_table(table_choice))

# ---------------------- STUDENT TABLE ----------------------
if table_choice == "student":

    # Delete student
    st.markdown("### 🔥 Delete Student")
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
            st.success("Student and related records deleted.")
        else:
            st.warning("Student ID not found.")

    # Add student
    st.markdown("### ✨ Add Student")
    with st.expander("➕ Add Student"):
        sid = st.number_input("Student ID", step=1)
        name = st.text_input("Student Name")
        contact = st.text_input("Contact Number")

        room_list = get_available_rooms()
        room_display = [f"Room {r['id']} (Free: {r['capacity'] - r['current_occupancy']})" for r in room_list]
        room_choice = st.selectbox("Select Room", room_display)
        selected_room = room_list[room_display.index(room_choice)]
        room_id = selected_room['id']
        free_slots = selected_room['capacity'] - selected_room['current_occupancy']

        if free_slots <= 0:
            st.warning("❌ This room is full. Choose a different room.")

        meal_type = st.selectbox("Meal Type", ["A", "B"])
        weekday = st.selectbox("Weekday", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
        health_desc = st.text_area("Health Description (Optional)")
        prescription = st.text_input("Prescription (Optional)")
        guardian = st.text_input("Guardian Contact (Optional)")

        if st.button("Add Student"):
            if free_slots <= 0:
                st.error("Room is full! Cannot add student.")
            else:
                cursor.execute("INSERT INTO student (id, student_Name, contact, room_id) VALUES (%s, %s, %s, %s)", (sid, name, contact, room_id))
                cursor.execute("INSERT INTO Meals (student_id, meal_type, weekday) VALUES (%s, %s, %s)", (sid, meal_type, weekday))
                cursor.execute("INSERT INTO Penalty (student_id, last_updated) VALUES (%s, %s)", (sid, now))
                if health_desc and prescription and guardian:
                    cursor.execute("INSERT INTO health_issues (student_id, description, prescription, guardian_contact) VALUES (%s, %s, %s, %s)",
                                (sid, health_desc, prescription, guardian))
                update_room_occupancy(room_id)
                conn.commit()
                st.success("Student added with related data.")

    # Search student
        # Search student
    st.markdown("### 🔍 Search & Update Student Info")
    search_id = st.number_input("Enter Student ID to Search", step=1)
    
    if st.button("Search Student"):
        st.session_state['search_id'] = search_id  # Store the ID in session state
    
    if 'search_id' in st.session_state:
        search_id = st.session_state['search_id']
        cursor.execute("SELECT * FROM student WHERE id = %s", (search_id,))
        student = cursor.fetchone()
        
        if student:
            st.write("Student Info", student)

            # MEAL UPDATE SECTION
            cursor.execute("SELECT * FROM Meals WHERE student_id = %s", (search_id,))
            meal = cursor.fetchone()
            
            meal_col, health_col = st.columns(2)
            
            with meal_col:
                st.subheader("Meal Information")
                if meal:
                    new_meal = st.selectbox("Meal Type", ["A", "B"], index=["A", "B"].index(meal["meal_type"]), key="meal_type")
                    new_day = st.selectbox("Weekday", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], 
                                        index=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].index(meal["weekday"]), key="weekday")
                else:
                    new_meal = st.selectbox("Meal Type", ["A", "B"], key="meal_type_new")
                    new_day = st.selectbox("Weekday", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], key="weekday_new")
                
                if st.button("Update Meal", key="update_meal"):
                    cursor.execute("""
                        INSERT INTO Meals (student_id, meal_type, weekday)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE meal_type=VALUES(meal_type), weekday=VALUES(weekday)
                    """, (search_id, new_meal, new_day))
                    conn.commit()
                    st.success("Meal updated successfully!")
                    st.experimental_rerun()

            # HEALTH ISSUES SECTION
            with health_col:
                st.subheader("Health Information")
                cursor.execute("SELECT * FROM health_issues WHERE student_id = %s", (search_id,))
                health = cursor.fetchone()
                
                if health:
                    desc = st.text_area("Health Description", value=health["description"], key="health_desc")
                    pres = st.text_input("Prescription", value=health["prescription"], key="prescription")
                    guardian = st.text_input("Guardian Contact", value=health["guardian_contact"], key="guardian")
                else:
                    desc = st.text_area("Health Description", key="health_desc_new")
                    pres = st.text_input("Prescription", key="prescription_new")
                    guardian = st.text_input("Guardian Contact", key="guardian_new")
                
                if st.button("Update Health Info", key="update_health"):
                    if health:
                        cursor.execute("UPDATE health_issues SET description=%s, prescription=%s, guardian_contact=%s WHERE student_id=%s", 
                                    (desc, pres, guardian, search_id))
                    else:
                        cursor.execute("INSERT INTO health_issues (student_id, description, prescription, guardian_contact) VALUES (%s, %s, %s, %s)",
                                    (search_id, desc, pres, guardian))
                    conn.commit()
                    st.success("Health info updated successfully!")
                    st.experimental_rerun()
        else:
            st.warning("Student not found.")

# ---------------------- PENALTY TABLE ----------------------
elif table_choice == "Penalty":
    st.markdown("### ✏️ Update Penalty")
    pid = st.number_input("Student ID", step=1)
    points = st.number_input("New Total Points", step=1)
    if st.button("Update Penalty"):
        cursor.execute("UPDATE Penalty SET total_points = %s, last_updated = %s WHERE student_id = %s", (points, now, pid))
        conn.commit()
        st.success("Penalty updated.")

# ---------------------- MAINTENANCE TABLE ----------------------
elif table_choice == "MaintenanceRequest":
    st.markdown("### 🛠️ Update Request Status")
    req_id = st.number_input("Maintenance Request ID", step=1)
    new_status = st.selectbox("New Status", ['Pending', 'In Progress', 'Resolved'])
    if st.button("Update Status"):
        cursor.execute("UPDATE MaintenanceRequest SET statues = %s WHERE id = %s", (new_status, req_id))
        conn.commit()
        st.success("Request status updated.")

cursor.close()
conn.close()
