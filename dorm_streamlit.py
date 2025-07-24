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
selected_table = st.selectbox("Select a table to view:", tables)

if st.button("Show Table"):
    cursor.execute(f"SELECT * FROM {selected_table}")
    rows = cursor.fetchall()
    if rows:
        st.write(pd.DataFrame(rows))
    else:
        st.info("No data found.")

# --- ADD STUDENT ---
st.subheader("➕ Add New Student")
with st.form("add_student_form"):
    student_name = st.text_input("Name")
    contact = st.text_input("Contact (11 digits)")
    room_id = st.number_input("Room ID", step=1)
    meal = st.selectbox("Meal Choice", ["A", "B"])
    submitted = st.form_submit_button("Add Student")

    if submitted:
        if len(contact) != 11 or not contact.isdigit():
            st.error("Contact must be exactly 11 digits.")
        else:
            # Check room capacity
            cursor.execute("SELECT capacity, current_occupancy FROM room WHERE id = %s", (room_id,))
            room = cursor.fetchone()
            if room:
                if room["current_occupancy"] >= room["capacity"]:
                    st.error("Room is full.")
                else:
                    try:
                        # Add student
                        cursor.execute("INSERT INTO student (student_Name, contact, room_id) VALUES (%s, %s, %s)",
                                       (student_name, contact, room_id))
                        conn.commit()

                        # Get new student ID
                        student_id = cursor.lastrowid

                        # Add meal
                        cursor.execute("INSERT INTO Meals (student_id, weekday, meal_choice) VALUES (%s, %s, %s)",
                                       (student_id, 'Monday', meal))
                        conn.commit()

                        # Update room occupancy
                        cursor.execute("UPDATE room SET current_occupancy = current_occupancy + 1 WHERE id = %s",
                                       (room_id,))
                        conn.commit()

                        st.success("Student added, meal registered, and room occupancy updated.")
                    except mysql.connector.Error as e:
                        conn.rollback()
                        st.error(f"Error: {e}")
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
            cursor.execute("DELETE FROM Meals WHERE student_id = %s", (del_id,))
            cursor.execute("DELETE FROM health_issues WHERE student_id = %s", (del_id,))
            cursor.execute("DELETE FROM student WHERE id = %s", (del_id,))
            cursor.execute("UPDATE room SET current_occupancy = current_occupancy - 1 WHERE id = %s",
                           (room_data["room_id"],))
            conn.commit()
            st.warning("Student deleted and room occupancy updated.")
        except mysql.connector.Error as e:
            conn.rollback()
            st.error(f"Error deleting student: {e}")
    else:
        st.error("Student ID not found.")

# --- CLOSE CURSOR & CONNECTION ---
cursor.close()
conn.close()
