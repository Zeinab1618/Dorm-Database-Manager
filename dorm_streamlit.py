import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime
from pytz import timezone

# ---------------------- DB CONNECTION ----------------------
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

if 'search_id' not in st.session_state:
    st.session_state['search_id'] = None
if 'selected_table' not in st.session_state:
    st.session_state['selected_table'] = None

# ---------------------- Utilities ----------------------
VALID_TABLES = [
    "student",
    "penalty",
    "maintenancerequest",
    "meals",
    "room",
    "building",
    "health_issues"
]

# Create formatted table names with proper display names
FORMATTED_TABLES = [
    "Student",
    "Penalty",
    "Maintenancerequest",
    "Meals", 
    "Room",
    "Building",
    "Health issues"
]

# Create mapping between formatted names and original names
TABLE_MAPPING = dict(zip(FORMATTED_TABLES, VALID_TABLES))

def load_table(table_name):
    if table_name not in VALID_TABLES:
        return pd.DataFrame()
    try:
        cursor.execute(f"SELECT * FROM {table_name}")
        return pd.DataFrame(cursor.fetchall())
    except mysql.connector.Error as err:
        st.error(f"Error loading table: {err}")
        return pd.DataFrame()

def update_room_occupancy(room_id):
    cursor.execute("SELECT COUNT(*) AS count FROM student WHERE room_id = %s", (room_id,))
    count = cursor.fetchone()["count"]
    cursor.execute("UPDATE room SET current_occupancy = %s WHERE id = %s", (count, room_id))
    conn.commit()

def get_available_rooms():
    cursor.execute("SELECT id, capacity, current_occupancy FROM room")
    return cursor.fetchall()

egypt = timezone("Africa/Cairo")
now = datetime.now(egypt)

# ---------------------- Table Choice ---------------------- 
# Use index to set placeholder
table_options = FORMATTED_TABLES
table_choice_formatted = st.selectbox(
    "Select Table to View", 
    table_options,
    index=None,
    placeholder="Choose a table..."
)

# Only show table data if a valid table is selected
if table_choice_formatted:
    # Convert formatted name back to original table name
    table_choice = TABLE_MAPPING[table_choice_formatted]
    st.session_state['selected_table'] = table_choice
    
    st.subheader(f"{table_choice_formatted} Table") 
    st.dataframe(load_table(table_choice))
    
    # ---------------------- STUDENT TABLE ----------------------
    if table_choice == "student":
        st.markdown("### 🔥 Delete Student")
        delete_id = st.number_input("Enter Student ID to Delete", step=1, format="%d")
        
        if st.button("Delete Student"):
            cursor.execute("SELECT room_id FROM student WHERE id = %s", (delete_id,))
            result = cursor.fetchone()
            if result:
                room_id = result["room_id"]
                cursor.execute("DELETE FROM meals WHERE student_id = %s", (delete_id,))
                cursor.execute("DELETE FROM health_issues WHERE student_id = %s", (delete_id,))
                cursor.execute("DELETE FROM penalty WHERE student_id = %s", (delete_id,))
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
                st.warning("❌ This room is full.")

            meal_type = st.selectbox("Meal Type", ["A", "B"])
            weekday = st.selectbox("Weekday", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
            health_desc = st.text_area("Health Description")
            prescription = st.text_input("Prescription")
            guardian = st.text_input("Guardian Contact")

            if st.button("Add Student"):
                if free_slots <= 0:
                    st.error("Room is full!")
                else:
                    cursor.execute(
                        "INSERT INTO student (id, student_Name, contact, room_id) VALUES (%s, %s, %s, %s)",
                        (sid, name, contact, room_id)
                    )
                    cursor.execute(
                        "INSERT INTO meals (student_id, meal_type, weekday) VALUES (%s, %s, %s)",
                        (sid, meal_type, weekday)
                    )
                    cursor.execute(
                        "INSERT INTO penalty (student_id, last_updated) VALUES (%s, %s)",
                        (sid, now)
                    )
                    if health_desc:
                        cursor.execute(
                            "INSERT INTO health_issues (student_id, description, prescription, guardian_contact) VALUES (%s, %s, %s, %s)",
                            (sid, health_desc, prescription, guardian)
                        )
                    update_room_occupancy(room_id)
                    conn.commit()
                    st.success("Student added.")

    # ---------------------- PENALTY ----------------------
    elif table_choice == "penalty":
        st.markdown("### ✏️ Update Penalty")
        pid = st.number_input("Student ID", step=1)

        if st.button("Search Penalty Record"):
            cursor.execute("SELECT * FROM penalty WHERE student_id = %s", (pid,))
            penalty = cursor.fetchone()

            if penalty:
                st.write(penalty)
                points = st.number_input("New Points", value=penalty["total_points"])
                if st.button("Update Penalty"):
                    cursor.execute(
                        "UPDATE penalty SET total_points = %s, last_updated = %s WHERE student_id = %s",
                        (points, now, pid)
                    )
                    conn.commit()
                    st.success("Updated.")
            else:
                st.warning("Not found.")

    # ---------------------- MAINTENANCE ----------------------
    elif table_choice == "maintenancerequest":
        st.markdown("### ➕ Add Maintenance Request")

        desc = st.text_area("Description")
        stat = st.selectbox("Status", ['Pending', 'In Progress', 'Resolved'])
        rid = st.number_input("Request ID", step=1)
        room_id = st.number_input("Room ID", step=1)

        if st.button("Add Request"):
            cursor.execute(
                "INSERT INTO maintenancerequest (id, room_id, description, statues) VALUES (%s, %s, %s, %s)",
                (rid, room_id, desc, stat)
            )
            conn.commit()
            st.success("Added.")

cursor.close()
conn.close()
