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

# Initialize session state for search
if 'search_id' not in st.session_state:
    st.session_state['search_id'] = None

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
    with st.form("add_student_form"):
        sid = st.text_input("Student ID", key="student_id_input")
        if sid and not sid.isdigit():
            st.error("Student ID must contain only numbers (0-9)")
        
        contact = st.text_input("Contact Number", key="contact_input")
        if contact and not contact.isdigit():
            st.error("Contact number must contain only numbers (0-9)")

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

        if st.form_submit_button("Add Student"):
            if not sid or not sid.isdigit():
                st.error("Please enter a valid Student ID (numbers only)")
            elif not contact or not contact.isdigit():
                st.error("Please enter a valid Contact Number (numbers only)")
            elif free_slots <= 0:
                st.error("Room is full! Cannot add student.")
            else:
                sid_int = int(sid)
                contact_str = str(contact)
                
                cursor.execute("INSERT INTO student (id, student_Name, contact, room_id) VALUES (%s, %s, %s, %s)", 
                             (sid_int, name, contact_str, room_id))
                cursor.execute("INSERT INTO Meals (student_id, meal_type, weekday) VALUES (%s, %s, %s)", 
                             (sid_int, meal_type, weekday))
                cursor.execute("INSERT INTO Penalty (student_id, last_updated) VALUES (%s, %s)", 
                             (sid_int, now))
                
                if health_desc or prescription or guardian:
                    cursor.execute("INSERT INTO health_issues (student_id, description, prescription, guardian_contact) VALUES (%s, %s, %s, %s)",
                                (sid_int, health_desc, prescription, guardian))
                
                update_room_occupancy(room_id)
                conn.commit()
                st.success("Student added with related data.")
    # Search student 
    st.markdown("### 🔍 Search & Update Student Info")
    search_id = st.number_input("Enter Student ID to Search", step=1, key="search_input")
    
    if st.button("Search Student"):
        st.session_state['search_id'] = search_id
    
    if st.session_state['search_id'] is not None:
        search_id = st.session_state['search_id']
        cursor.execute("SELECT * FROM student WHERE id = %s", (search_id,))
        student = cursor.fetchone()
        
        if student:
            st.write("Student Info", student)

            # MEAL UPDATE FORM
            with st.form("meal_form"):
                cursor.execute("SELECT * FROM Meals WHERE student_id = %s", (search_id,))
                meal = cursor.fetchone()
                
                st.subheader("Meal Information")
                if meal:
                    new_meal = st.selectbox("Meal Type", ["A", "B"], index=["A", "B"].index(meal["meal_type"]))
                    new_day = st.selectbox("Weekday", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], 
                                        index=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].index(meal["weekday"]))
                else:
                    new_meal = st.selectbox("Meal Type", ["A", "B"])
                    new_day = st.selectbox("Weekday", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
                
                if st.form_submit_button("Update Meal"):
                    cursor.execute("""
                        INSERT INTO Meals (student_id, meal_type, weekday)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE meal_type=VALUES(meal_type), weekday=VALUES(weekday)
                    """, (search_id, new_meal, new_day))
                    conn.commit()
                    st.success("Meal updated successfully!")

            # HEALTH UPDATE FORM
            with st.form("health_form"):
                cursor.execute("SELECT * FROM health_issues WHERE student_id = %s", (search_id,))
                health = cursor.fetchone()
                
                st.subheader("Health Information")
                if health:
                    desc = st.text_area("Health Description", value=health["description"])
                    pres = st.text_input("Prescription", value=health["prescription"])
                    guardian = st.text_input("Guardian Contact", value=health["guardian_contact"])
                else:
                    desc = st.text_area("Health Description")
                    pres = st.text_input("Prescription")
                    guardian = st.text_input("Guardian Contact")
                
                if st.form_submit_button("Update Health Info"):
                    if health:
                        cursor.execute("UPDATE health_issues SET description=%s, prescription=%s, guardian_contact=%s WHERE student_id=%s", 
                                    (desc, pres, guardian, search_id))
                    else:
                        cursor.execute("INSERT INTO health_issues (student_id, description, prescription, guardian_contact) VALUES (%s, %s, %s, %s)",
                                    (search_id, desc, pres, guardian))
                    conn.commit()
                    st.success("Health info updated successfully!")
        else:
            st.warning("Student not found.")

# ---------------------- PENALTY TABLE ----------------------
elif table_choice == "Penalty":
    st.markdown("### ✏️ Update Penalty")
    
    # Initialize session state for penalty
    if 'penalty_id' not in st.session_state:
        st.session_state['penalty_id'] = None
    
    pid = st.number_input("Student ID", step=1, key="penalty_input")
    
    if st.button("Search Penalty Record"):
        st.session_state['penalty_id'] = pid
    
    if st.session_state['penalty_id'] is not None:
        pid = st.session_state['penalty_id']
        cursor.execute("SELECT * FROM Penalty WHERE student_id = %s", (pid,))
        penalty = cursor.fetchone()
        
        if penalty:
            st.write("Current Penalty Info", penalty)
            
            with st.form("penalty_form"):
                points = st.number_input("New Total Points", step=1, value=penalty["total_points"])
                
                if st.form_submit_button("Update Penalty"):
                    cursor.execute("UPDATE Penalty SET total_points = %s, last_updated = %s WHERE student_id = %s", 
                                 (points, now, pid))
                    conn.commit()
                    st.success("Penalty updated successfully!")
        else:
            st.warning("No penalty record found for this student ID.")

# ---------------------- MAINTENANCE TABLE ----------------------
elif table_choice == "MaintenanceRequest":
    # Initialize session states
    if 'search_maintenance_id' not in st.session_state:
        st.session_state.search_maintenance_id = None
    if 'show_not_found' not in st.session_state:
        st.session_state.show_not_found = False

    # Update Request Section
    st.markdown("### 🛠️ Update Request")
    req_id = st.number_input("Maintenance Request ID to Update", step=1, key="update_req_input")
    
    if st.button("Search Request", key="search_req_btn"):
        st.session_state.search_maintenance_id = req_id
        st.session_state.show_not_found = True  # Only show "not found" after search
        
        # Reset not found message if searching again
        cursor.execute("SELECT * FROM MaintenanceRequest WHERE id = %s", (req_id,))
        if cursor.fetchone():
            st.session_state.show_not_found = False

    if st.session_state.search_maintenance_id is not None:
        cursor.execute("SELECT * FROM MaintenanceRequest WHERE id = %s", (st.session_state.search_maintenance_id,))
        request = cursor.fetchone()

        if request:
            with st.form("update_request_form"):
                new_status = st.selectbox("New Status", ['Pending', 'In Progress', 'Resolved'], 
                                        index=['Pending', 'In Progress', 'Resolved'].index(request['statues']))
                new_description = st.text_area("Update Description", value=request['description'])
                
                if st.form_submit_button("Update Request"):
                    cursor.execute("UPDATE MaintenanceRequest SET statues = %s, description = %s WHERE id = %s", 
                                 (new_status, new_description, st.session_state.search_maintenance_id))
                    conn.commit()
                    st.success("Maintenance request updated successfully!")
                    st.session_state.search_maintenance_id = None 
        elif st.session_state.show_not_found:
            st.info("No maintenance request found with that ID.")

    # Add New Request Section
    st.markdown("---")
    st.markdown("### ➕ Add New Maintenance Request")
    
    with st.form("add_request_form"):
        new_desc = st.text_area("Description", key="add_desc")
        new_stat = st.selectbox("Status", ['Pending', 'In Progress', 'Resolved'], key="add_status")
        request_id = st.number_input("Request ID", step=1, key="add_sid")
        room_id = st.number_input("Room ID", step=1, key="add_room_id") 
        
        if st.form_submit_button("Add Request"):
            try:
                cursor.execute("INSERT INTO MaintenanceRequest (id, room_id, description, statues) VALUES (%s, %s, %s, %s)", 
                             (request_id, room_id, new_desc, new_stat))
                conn.commit()
                st.success("New maintenance request added successfully!")
            except mysql.connector.Error as err:
                st.error(f"Error adding request: {err}")

cursor.close()
conn.close()
