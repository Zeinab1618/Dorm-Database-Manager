import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime
from pytz import timezone
import time

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

# Add custom CSS to fix cursor on dropdown
st.markdown("""
    <style>
    /* Make the selectbox dropdown arrow show pointer cursor */
    .stSelectbox [data-baseweb="select"] {
        cursor: pointer;
    }
    .stSelectbox [data-baseweb="select"] * {
        cursor: pointer;
    }
    /* For the dropdown arrow specifically */
    .stSelectbox svg {
        cursor: pointer;
    }
    /* For the entire selectbox container */
    div[data-testid="stSelectbox"] {
        cursor: pointer;
    }
    div[data-testid="stSelectbox"] * {
        cursor: pointer;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'current_table' not in st.session_state:
    st.session_state.current_table = None

# ---------------------- Utilities ----------------------
# Define table display names with proper formatting
TABLE_NAMES = {
    "student": "📚 Student",
    "penalty": "⚠️ Penalty",
    "maintenancerequest": "🔧 Maintenance Request",
    "meals": "🍽️ Meals",
    "room": "🚪 Room",
    "building": "🏢 Building",
    "health_issues": "🏥 Health Issues"
}

def load_table(table_name):
    if table_name not in TABLE_NAMES:
        return pd.DataFrame()
    try:
        cursor.execute(f"SELECT * FROM {table_name}")
        data = cursor.fetchall()
        if data:
            return pd.DataFrame(data)
        else:
            return pd.DataFrame()
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

def student_exists(student_id):
    cursor.execute("SELECT id FROM student WHERE id = %s", (student_id,))
    return cursor.fetchone() is not None

def contact_exists(contact):
    cursor.execute("SELECT contact FROM student WHERE contact = %s", (contact,))
    return cursor.fetchone() is not None

egypt = timezone("Africa/Cairo")
now = datetime.now(egypt)

# ---------------------- Table Selection ---------------------- 
# Create list of options for dropdown
table_options = list(TABLE_NAMES.values())

# Use index=None to make it a true placeholder (not selectable)
selected_display = st.selectbox(
    "Select Table to View", 
    table_options,
    index=None,
    placeholder="Choose a table...",
    key="table_selector"
)

# Update current table based on selection
if selected_display:
    for table_key, table_display in TABLE_NAMES.items():
        if table_display == selected_display:
            st.session_state.current_table = table_key
            break
else:
    st.session_state.current_table = None

# Display content based on selected table
if st.session_state.current_table:
    table_choice = st.session_state.current_table
    selected_display_name = TABLE_NAMES[table_choice]
    
    # Display table data
    df = load_table(table_choice)
    st.subheader(f"{selected_display_name} Table")
    
    if not df.empty:
        st.dataframe(df)
    else:
        st.info("No data found in this table")
    
    # ---------------------- STUDENT TABLE ----------------------
    if table_choice == "student":
        st.markdown("---")
        st.markdown("### 🔥 Delete Student")
        delete_id = st.number_input("Enter Student ID to Delete", step=1, min_value=1, format="%d", key="delete_id")
        
        if st.button("Delete Student", type="secondary"):
            if delete_id:
                if student_exists(delete_id):
                    try:
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
                            st.success(f"✅ Student ID {delete_id} deleted successfully!")
                            time.sleep(1)
                            st.rerun()
                    except mysql.connector.Error as err:
                        conn.rollback()
                        st.error(f"❌ Error deleting: {err}")
                else:
                    st.warning(f"⚠️ Student ID {delete_id} not found")

        st.markdown("---")
        
        # Add student
        st.markdown("### ✨ Add Student")
        with st.expander("➕ Add New Student", expanded=False):
            cursor.execute("SELECT COUNT(*) as count FROM room")
            room_count = cursor.fetchone()['count']
            
            if room_count == 0:
                st.error("❌ No rooms available! Please add rooms to the 'room' table first.")
            else:
                sid = st.number_input("Student ID", step=1, min_value=1, format="%d", key="add_sid")
                name = st.text_input("Student Name", key="add_name")
                contact = st.text_input("Contact Number (11 digits)", key="add_contact", max_chars=11)
                
                if contact and len(contact) == 11:
                    if contact_exists(contact):
                        st.error("❌ This contact number is already registered!")
                    else:
                        st.success("✓ Contact number is available")
                elif contact:
                    st.warning("Contact number must be 11 digits")
                
                room_list = get_available_rooms()
                if room_list:
                    available_rooms = [r for r in room_list if r['capacity'] - r['current_occupancy'] > 0]
                    
                    if not available_rooms:
                        st.error("❌ No rooms with available space! All rooms are full.")
                    else:
                        room_display = [f"Room {r['id']} (Free: {r['capacity'] - r['current_occupancy']} slots)" for r in available_rooms]
                        room_choice = st.selectbox("Select Room", room_display)
                        selected_index = room_display.index(room_choice)
                        selected_room = available_rooms[selected_index]
                        room_id = selected_room['id']
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            meal_type = st.selectbox("Meal Type", ["A", "B"])
                            weekday = st.selectbox("Weekday", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
                        with col2:
                            health_desc = st.text_area("Health Description (Optional)")
                            prescription = st.text_input("Prescription (Optional)")
                            guardian_contact = st.text_input("Guardian Contact (11 digits, required if health issues)", max_chars=11, key="guardian")
                        
                        if st.button("Add Student", type="primary", key="add_student_btn"):
                            errors = []
                            if not sid:
                                errors.append("Student ID is required")
                            elif student_exists(sid):
                                errors.append(f"Student ID {sid} already exists")
                            
                            if not name:
                                errors.append("Student Name is required")
                            
                            if not contact:
                                errors.append("Contact Number is required")
                            elif len(contact) != 11:
                                errors.append("Contact number must be exactly 11 digits")
                            elif contact_exists(contact):
                                errors.append("This contact number is already registered")
                            
                            if health_desc or prescription or guardian_contact:
                                if not guardian_contact:
                                    errors.append("Guardian Contact is required when adding health issues")
                                elif len(guardian_contact) != 11:
                                    errors.append("Guardian contact must be exactly 11 digits")
                            
                            if errors:
                                for error in errors:
                                    st.error(f"❌ {error}")
                            else:
                                try:
                                    cursor.execute(
                                        "INSERT INTO student (id, student_Name, contact, room_id) VALUES (%s, %s, %s, %s)",
                                        (sid, name, contact, room_id)
                                    )
                                    
                                    cursor.execute(
                                        "INSERT INTO meals (student_id, meal_type, weekday) VALUES (%s, %s, %s)",
                                        (sid, meal_type, weekday)
                                    )
                                    
                                    cursor.execute(
                                        "INSERT INTO penalty (student_id, total_points, last_updated) VALUES (%s, %s, %s)",
                                        (sid, 0, now)
                                    )
                                    
                                    if health_desc or prescription or guardian_contact:
                                        cursor.execute(
                                            "INSERT INTO health_issues (student_id, description, prescription, guardian_contact) VALUES (%s, %s, %s, %s)",
                                            (sid, health_desc if health_desc else None, 
                                             prescription if prescription else None, 
                                             guardian_contact)
                                        )
                                    
                                    update_room_occupancy(room_id)
                                    conn.commit()
                                    st.success(f"✅ Student {name} (ID: {sid}) added successfully!")
                                    st.balloons()
                                    time.sleep(2)
                                    st.rerun()
                                    
                                except mysql.connector.IntegrityError as err:
                                    conn.rollback()
                                    error_msg = str(err)
                                    if "Duplicate entry" in error_msg:
                                        if "contact" in error_msg:
                                            st.error("❌ This contact number is already registered!")
                                        else:
                                            st.error("❌ Student ID already exists!")
                                    else:
                                        st.error(f"❌ Database error: {err}")
                                        
                                except mysql.connector.Error as err:
                                    conn.rollback()
                                    st.error(f"❌ Database error: {err}")

    # ---------------------- PENALTY ----------------------
    elif table_choice == "penalty":
        st.markdown("---")
        st.markdown("### ✏️ Update Penalty Points")
        pid = st.number_input("Student ID", step=1, min_value=1, key="penalty_sid")

        if st.button("Search Penalty Record"):
            try:
                cursor.execute("SELECT * FROM penalty WHERE student_id = %s", (pid,))
                penalty = cursor.fetchone()

                if penalty:
                    st.success(f"Found penalty record for Student ID: {pid}")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Total Points", penalty["total_points"])
                    with col2:
                        st.metric("Last Updated", penalty["last_updated"])
                    
                    points = st.number_input("New Points", value=penalty["total_points"], step=1, min_value=0)
                    if st.button("Update Penalty", type="primary"):
                        cursor.execute(
                            "UPDATE penalty SET total_points = %s, last_updated = %s WHERE student_id = %s",
                            (points, now, pid)
                        )
                        conn.commit()
                        st.success("✅ Penalty points updated successfully!")
                        st.rerun()
                else:
                    st.warning(f"⚠️ No penalty record found for Student ID: {pid}")
            except mysql.connector.Error as err:
                st.error(f"Error searching penalty: {err}")

    # ---------------------- MAINTENANCE REQUEST ----------------------
    elif table_choice == "maintenancerequest":
        st.markdown("---")
        st.markdown("### ➕ Add Maintenance Request")
        
        col1, col2 = st.columns(2)
        with col1:
            rid = st.number_input("Request ID", step=1, min_value=1)
            room_id = st.number_input("Room ID", step=1, min_value=1)
        with col2:
            desc = st.text_area("Description")
            stat = st.selectbox("Status", ['Pending', 'In Progress', 'Resolved'])

        if st.button("Add Request", type="primary"):
            if not rid:
                st.error("❌ Request ID is required")
            elif not room_id:
                st.error("❌ Room ID is required")
            elif not desc:
                st.error("❌ Description is required")
            else:
                try:
                    cursor.execute(
                        "INSERT INTO maintenancerequest (id, room_id, description, statues) VALUES (%s, %s, %s, %s)",
                        (rid, room_id, desc, stat)
                    )
                    conn.commit()
                    st.success("✅ Maintenance request added successfully!")
                    st.rerun()
                except mysql.connector.IntegrityError as err:
                    conn.rollback()
                    if "Duplicate entry" in str(err):
                        st.error(f"❌ Request ID {rid} already exists!")
                    elif "foreign key" in str(err):
                        st.error(f"❌ Room ID {room_id} does not exist!")
                    else:
                        st.error(f"❌ Database error: {err}")
                except mysql.connector.Error as err:
                    conn.rollback()
                    st.error(f"❌ Error adding request: {err}")

    # ---------------------- MEALS ----------------------
    elif table_choice == "meals":
        st.markdown("---")
        st.markdown("### 📝 Meal Preferences")
        
        with st.expander("➕ Add Meal Preference", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                student_id = st.number_input("Student ID", step=1, min_value=1, key="meal_student_id")
                meal_type = st.selectbox("Meal Type", ["A", "B"], key="meal_type")
            with col2:
                weekday = st.selectbox("Weekday", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], key="meal_weekday")
            
            if st.button("Add Meal Preference"):
                if not student_exists(student_id):
                    st.error(f"❌ Student ID {student_id} does not exist!")
                else:
                    try:
                        cursor.execute(
                            "INSERT INTO meals (student_id, meal_type, weekday) VALUES (%s, %s, %s)",
                            (student_id, meal_type, weekday)
                        )
                        conn.commit()
                        st.success("✅ Meal preference added successfully!")
                        st.rerun()
                    except mysql.connector.IntegrityError:
                        st.error("❌ This student already has a meal preference for this weekday!")
                    except mysql.connector.Error as err:
                        st.error(f"❌ Error: {err}")

    # ---------------------- ROOM ----------------------
    elif table_choice == "room":
        st.markdown("---")
        st.markdown("### ➕ Add New Room")
        with st.expander("➕ Add Room", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                room_id = st.number_input("Room ID", step=1, min_value=1)
                floor = st.number_input("Floor", step=1, min_value=1)
            with col2:
                building_id = st.number_input("Building ID", step=1, min_value=1)
                capacity = st.number_input("Capacity", step=1, min_value=1)
            
            if st.button("Add Room"):
                try:
                    cursor.execute(
                        "INSERT INTO room (id, floor, building_id, capacity, current_occupancy) VALUES (%s, %s, %s, %s, %s)",
                        (room_id, floor, building_id, capacity, 0)
                    )
                    conn.commit()
                    st.success("✅ Room added successfully!")
                    st.rerun()
                except mysql.connector.IntegrityError as err:
                    if "Duplicate entry" in str(err):
                        st.error(f"❌ Room ID {room_id} already exists!")
                    elif "foreign key" in str(err):
                        st.error(f"❌ Building ID {building_id} does not exist!")
                    else:
                        st.error(f"❌ Error: {err}")

    # ---------------------- BUILDING ----------------------
    elif table_choice == "building":
        st.markdown("---")
        st.markdown("### ➕ Add New Building")
        with st.expander("➕ Add Building", expanded=True):
            building_id = st.number_input("Building ID", step=1, min_value=1)
            building_name = st.text_input("Building Name")
            
            if st.button("Add Building"):
                try:
                    cursor.execute(
                        "INSERT INTO building (id, building_name) VALUES (%s, %s)",
                        (building_id, building_name)
                    )
                    conn.commit()
                    st.success("✅ Building added successfully!")
                    st.rerun()
                except mysql.connector.IntegrityError as err:
                    if "Duplicate entry" in str(err):
                        st.error(f"❌ Building ID {building_id} already exists!")
                    else:
                        st.error(f"❌ Error: {err}")

    # ---------------------- HEALTH ISSUES ----------------------
    elif table_choice == "health_issues":
        st.markdown("---")
        st.markdown("### 🏥 Health Issues Management")
        
        with st.expander("➕ Add/Update Health Issues", expanded=True):
            student_id = st.number_input("Student ID", step=1, min_value=1, key="health_student_id")
            
            if student_id:
                if student_exists(student_id):
                    cursor.execute("SELECT student_Name FROM student WHERE id = %s", (student_id,))
                    student = cursor.fetchone()
                    st.info(f"👤 Student: {student['student_Name']}")
                    
                    cursor.execute("SELECT * FROM health_issues WHERE student_id = %s", (student_id,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        st.warning("⚠️ This student already has a health record. Updating existing record.")
                        default_desc = existing['description'] if existing['description'] else ""
                        default_prescription = existing['prescription'] if existing['prescription'] else ""
                        default_guardian = existing['guardian_contact']
                    else:
                        st.info("📝 This student has no health record yet. Adding new record.")
                        default_desc = ""
                        default_prescription = ""
                        default_guardian = ""
                    
                    health_desc = st.text_area("Health Description", value=default_desc, height=100)
                    prescription = st.text_input("Prescription", value=default_prescription)
                    guardian_contact = st.text_input("Guardian Contact (11 digits)", value=default_guardian, max_chars=11)
                    
                    if st.button("💾 Save Health Record", key="save_health"):
                        if not guardian_contact:
                            st.error("❌ Guardian Contact is required!")
                        elif len(guardian_contact) != 11:
                            st.error("❌ Guardian contact must be exactly 11 digits!")
                        else:
                            try:
                                if existing:
                                    cursor.execute(
                                        "UPDATE health_issues SET description = %s, prescription = %s, guardian_contact = %s WHERE student_id = %s",
                                        (health_desc if health_desc else None, 
                                         prescription if prescription else None, 
                                         guardian_contact, 
                                         student_id)
                                    )
                                else:
                                    cursor.execute(
                                        "INSERT INTO health_issues (student_id, description, prescription, guardian_contact) VALUES (%s, %s, %s, %s)",
                                        (student_id, 
                                         health_desc if health_desc else None, 
                                         prescription if prescription else None, 
                                         guardian_contact)
                                    )
                                conn.commit()
                                st.success("✅ Health record saved successfully!")
                                time.sleep(1)
                                st.rerun()
                            except mysql.connector.Error as err:
                                conn.rollback()
                                st.error(f"❌ Error saving health record: {err}")
                else:
                    st.error(f"❌ Student ID {student_id} does not exist!")

cursor.close()
conn.close()
