import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime
from pytz import timezone
import traceback

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

def student_exists(student_id):
    cursor.execute("SELECT id FROM student WHERE id = %s", (student_id,))
    return cursor.fetchone() is not None

def check_all_tables_for_student_id(student_id):
    """Check all tables for any record with this student_id"""
    tables_to_check = ["student", "meals", "penalty", "health_issues"]
    results = {}
    
    for table in tables_to_check:
        cursor.execute(f"SELECT * FROM {table} WHERE student_id = %s", (student_id,))
        results[table] = cursor.fetchall()
    
    return results

def force_cleanup_student_id(student_id):
    """Force delete any record with this student_id from all tables"""
    try:
        cursor.execute("DELETE FROM meals WHERE student_id = %s", (student_id,))
        cursor.execute("DELETE FROM health_issues WHERE student_id = %s", (student_id,))
        cursor.execute("DELETE FROM penalty WHERE student_id = %s", (student_id,))
        cursor.execute("DELETE FROM student WHERE id = %s", (student_id,))
        conn.commit()
        return True
    except mysql.connector.Error as err:
        conn.rollback()
        st.error(f"Error in force cleanup: {err}")
        return False

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
        # Debug section - Check for any hidden records
        with st.expander("🔧 Database Diagnostic Tools", expanded=True):
            st.warning("⚠️ Use these tools to diagnose and fix database issues")
            
            debug_id = st.number_input("Enter Student ID to Diagnose", step=1, min_value=1, key="debug_id")
            
            if st.button("Run Full Diagnostic"):
                if debug_id:
                    st.write(f"### Diagnostic Report for Student ID: {debug_id}")
                    
                    # Check all tables
                    results = check_all_tables_for_student_id(debug_id)
                    
                    found_any = False
                    for table, records in results.items():
                        if records:
                            found_any = True
                            st.error(f"❌ Found {len(records)} record(s) in {table} table:")
                            st.dataframe(pd.DataFrame(records))
                        else:
                            st.success(f"✓ No records found in {table} table")
                    
                    if not found_any:
                        st.success(f"✅ No records found for Student ID {debug_id} anywhere in the database!")
                        st.info("You should be able to add this student without any issues.")
                    
                    # Show the actual error that would occur
                    st.markdown("### Test Insertion")
                    if st.button("Test What Would Happen on Insert"):
                        try:
                            # Try a test insert with rollback
                            cursor.execute("START TRANSACTION")
                            cursor.execute(
                                "INSERT INTO student (id, student_Name, contact, room_id) VALUES (%s, %s, %s, %s)",
                                (debug_id, "TEST_USER", "0000000000", 1)
                            )
                            cursor.execute("ROLLBACK")
                            st.success("✅ Test insert would succeed! No conflicts found.")
                        except mysql.connector.IntegrityError as e:
                            st.error(f"❌ Test insert failed with error: {e}")
                            st.code(traceback.format_exc())
            
            st.markdown("---")
            
            if st.button("Force Cleanup Student ID (Use if diagnostic shows records)"):
                if debug_id:
                    if force_cleanup_student_id(debug_id):
                        st.success(f"✅ Force cleanup completed for Student ID {debug_id}")
                        st.rerun()
        
        st.markdown("### 🔥 Delete Student")
        delete_id = st.number_input("Enter Student ID to Delete", step=1, min_value=1, format="%d", key="delete_id")
        
        if st.button("Delete Student", type="secondary"):
            if delete_id:
                if student_exists(delete_id):
                    try:
                        cursor.execute("SELECT room_id FROM student WHERE id = %s", (delete_id,))
                        result = cursor.fetchone()
                        room_id = result["room_id"]
                        
                        cursor.execute("DELETE FROM meals WHERE student_id = %s", (delete_id,))
                        cursor.execute("DELETE FROM health_issues WHERE student_id = %s", (delete_id,))
                        cursor.execute("DELETE FROM penalty WHERE student_id = %s", (delete_id,))
                        cursor.execute("DELETE FROM student WHERE id = %s", (delete_id,))
                        update_room_occupancy(room_id)
                        conn.commit()
                        st.success(f"✅ Student ID {delete_id} deleted successfully!")
                        st.rerun()
                    except mysql.connector.Error as err:
                        conn.rollback()
                        st.error(f"❌ Error deleting: {err}")
                else:
                    st.warning(f"⚠️ Student ID {delete_id} not found in student table.")
                    
                    # Check if there are orphaned records
                    results = check_all_tables_for_student_id(delete_id)
                    has_orphans = any(len(records) > 0 for records in results.values())
                    
                    if has_orphans:
                        st.error("⚠️ Found orphaned records! Use the Diagnostic Tools above to clean them.")

        st.markdown("---")
        
        # Add student
        st.markdown("### ✨ Add Student")
        with st.expander("➕ Add New Student", expanded=False):
            sid = st.number_input("Student ID", step=1, min_value=1, format="%d", key="add_sid")
            name = st.text_input("Student Name", key="add_name")
            contact = st.text_input("Contact Number", key="add_contact")
            
            room_list = get_available_rooms()
            if room_list:
                available_rooms = [r for r in room_list if r['capacity'] - r['current_occupancy'] > 0]
                
                if available_rooms:
                    room_display = [f"Room {r['id']} (Free: {r['capacity'] - r['current_occupancy']} slots)" for r in available_rooms]
                    room_choice = st.selectbox("Select Room", room_display)
                    selected_room = available_rooms[room_display.index(room_choice)]
                    room_id = selected_room['id']
                    
                    meal_type = st.selectbox("Meal Type", ["A", "B"])
                    weekday = st.selectbox("Weekday", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
                    health_desc = st.text_area("Health Description (Optional)")
                    prescription = st.text_input("Prescription (Optional)")
                    guardian = st.text_input("Guardian Contact (Optional)")
                    
                    if st.button("Add Student", type="primary", key="add_student_btn"):
                        # Validation
                        if not sid:
                            st.error("❌ Student ID is required")
                        elif not name:
                            st.error("❌ Student Name is required")
                        elif not contact:
                            st.error("❌ Contact Number is required")
                        else:
                            # Double check if student exists before insert
                            if student_exists(sid):
                                st.error(f"❌ Student ID {sid} already exists!")
                                # Show where it exists
                                results = check_all_tables_for_student_id(sid)
                                for table, records in results.items():
                                    if records:
                                        st.write(f"Found in {table}:")
                                        st.dataframe(pd.DataFrame(records))
                            else:
                                try:
                                    # Log the attempt
                                    st.info(f"Attempting to add student ID: {sid}, Name: {name}, Room: {room_id}")
                                    
                                    # Insert student
                                    cursor.execute(
                                        "INSERT INTO student (id, student_Name, contact, room_id) VALUES (%s, %s, %s, %s)",
                                        (sid, name, contact, room_id)
                                    )
                                    st.success("✓ Student inserted")
                                    
                                    # Insert meal preference
                                    cursor.execute(
                                        "INSERT INTO meals (student_id, meal_type, weekday) VALUES (%s, %s, %s)",
                                        (sid, meal_type, weekday)
                                    )
                                    st.success("✓ Meal preference inserted")
                                    
                                    # Insert penalty record
                                    cursor.execute(
                                        "INSERT INTO penalty (student_id, total_points, last_updated) VALUES (%s, %s, %s)",
                                        (sid, 0, now)
                                    )
                                    st.success("✓ Penalty record inserted")
                                    
                                    # Insert health issues if provided
                                    if health_desc or prescription or guardian:
                                        cursor.execute(
                                            "INSERT INTO health_issues (student_id, description, prescription, guardian_contact) VALUES (%s, %s, %s, %s)",
                                            (sid, health_desc if health_desc else None, 
                                             prescription if prescription else None, 
                                             guardian if guardian else None)
                                        )
                                        st.success("✓ Health record inserted")
                                    
                                    update_room_occupancy(room_id)
                                    conn.commit()
                                    st.success(f"✅ Student {name} (ID: {sid}) added successfully!")
                                    st.balloons()
                                    st.rerun()
                                    
                                except mysql.connector.IntegrityError as err:
                                    conn.rollback()
                                    st.error(f"❌ Integrity Error: {err}")
                                    st.code(f"Full error details:\n{traceback.format_exc()}")
                                    
                                    # Show what might be causing the issue
                                    st.markdown("### Troubleshooting:")
                                    st.write("Check if any of these already exist:")
                                    results = check_all_tables_for_student_id(sid)
                                    for table, records in results.items():
                                        if records:
                                            st.write(f"- {table}: Has records")
                                        else:
                                            st.write(f"- {table}: No records")
                                    
                                except mysql.connector.Error as err:
                                    conn.rollback()
                                    st.error(f"❌ Database Error: {err}")
                                    st.code(traceback.format_exc())
                else:
                    st.error("❌ No rooms with available space!")
            else:
                st.error("❌ No rooms found!")

cursor.close()
conn.close()
