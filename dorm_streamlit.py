import streamlit as st
import mysql.connector
import pandas as pd

# MySQL connection
conn = mysql.connector.connect(
    host=st.secrets["mysql"]["host"],
    user=st.secrets["mysql"]["user"],
    password=st.secrets["mysql"]["password"],
    database=st.secrets["mysql"]["database"],
    port=st.secrets["mysql"]["port"],
    ssl_ca=st.secrets["mysql"]["ssl_ca"]
)
cursor = conn.cursor(dictionary=True)

st.set_page_config(page_title="Dorm System", layout="wide")
tabs = st.tabs(["🏫 Students", "🛠️ Maintenance", "📋 Tables"])

# ---------------- STUDENTS TAB ----------------
with tabs[0]:
    st.header("👨‍🎓 Student Management")
    cursor.execute("SELECT * FROM student")
    students = cursor.fetchall()
    st.dataframe(pd.DataFrame(students), use_container_width=True)

    with st.expander("➕ Add Student"):
        sid = st.number_input("Student ID", step=1)
        name = st.text_input("Name")
        contact = st.text_input("Contact")
        room_id = st.number_input("Room ID", step=1)
        weekday = st.selectbox("Weekday", ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"])
        meal_type = st.selectbox("Meal Type", ["A", "B"])

        if st.button("Add Student"):
            try:
                cursor.execute("INSERT INTO student VALUES (%s, %s, %s, %s)", (sid, name, contact, room_id))
                cursor.execute("REPLACE INTO Meals VALUES (%s, %s, %s)", (sid, meal_type, weekday))
                cursor.execute("""
                    UPDATE room SET current_occupancy = (
                        SELECT COUNT(*) FROM student WHERE room_id = %s
                    ) WHERE id = %s
                """, (room_id, room_id))
                conn.commit()
                st.success("Student and meal added. Room occupancy updated.")
            except Exception as e:
                st.error(f"Error: {e}")

    with st.expander("🗑️ Delete Student"):
        del_id = st.number_input("Student ID to Delete", step=1, key="del")
        if st.button("Delete"):
            cursor.execute("SELECT room_id FROM student WHERE id = %s", (del_id,))
            data = cursor.fetchone()
            if data:
                room_id = data['room_id']
                cursor.execute("DELETE FROM Meals WHERE student_id = %s", (del_id,))
                cursor.execute("DELETE FROM health_issues WHERE student_id = %s", (del_id,))
                cursor.execute("DELETE FROM student WHERE id = %s", (del_id,))
                cursor.execute("""
                    UPDATE room SET current_occupancy = (
                        SELECT COUNT(*) FROM student WHERE room_id = %s
                    ) WHERE id = %s
                """, (room_id, room_id))
                conn.commit()
                st.success("Student deleted and occupancy updated.")
            else:
                st.warning("Student not found.")

    with st.expander("🔍 Search / Edit Student"):
        search_id = st.number_input("Search Student ID", step=1, key="search")
        if st.button("Search"):
            cursor.execute("SELECT * FROM student WHERE id = %s", (search_id,))
            student = cursor.fetchone()
            if student:
                st.json(student)

                st.subheader("🍽️ Update Meal")
                weekday = st.selectbox("Weekday", ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"], key="wd1")
                meal_type = st.selectbox("Meal", ["A", "B"], key="mt1")
                if st.button("Update Meal"):
                    cursor.execute("REPLACE INTO Meals VALUES (%s, %s, %s)", (search_id, meal_type, weekday))
                    conn.commit()
                    st.success("Meal updated")

                st.subheader("🩺 Health Info")
                cursor.execute("SELECT * FROM health_issues WHERE student_id = %s", (search_id,))
                health = cursor.fetchone()
                if health:
                    desc = st.text_area("Description", health['description'])
                    pres = st.text_input("Prescription", health['prescription'])
                    guardian = st.text_input("Guardian", health['guardian_contact'])
                    if st.button("Update Health"):
                        cursor.execute("UPDATE health_issues SET description=%s, prescription=%s, guardian_contact=%s WHERE student_id=%s",
                                       (desc, pres, guardian, search_id))
                        conn.commit()
                        st.success("Updated health issue")
                else:
                    st.info("No health record found. Add new:")
                    desc = st.text_area("Description", key="desc2")
                    pres = st.text_input("Prescription", key="pres2")
                    guardian = st.text_input("Guardian", key="guard2")
                    if st.button("Add Health Issue"):
                        cursor.execute("INSERT INTO health_issues VALUES (%s, %s, %s, %s)",
                                       (search_id, desc, pres, guardian))
                        conn.commit()
                        st.success("Inserted")
            else:
                st.warning("Student not found.")

# ---------------- MAINTENANCE TAB ----------------
with tabs[1]:
    st.header("🔧 Maintenance")
    cursor.execute("SELECT * FROM MaintenanceRequest")
    st.dataframe(pd.DataFrame(cursor.fetchall()), use_container_width=True)

    with st.expander("Add / Edit Request"):
        rid = st.number_input("Request ID", step=1)
        room = st.number_input("Room ID", step=1, key="room_edit")
        status = st.selectbox("Status", ["Pending", "In Progress", "Resolved"])
        desc = st.text_area("Description")
        if st.button("Save Request"):
            cursor.execute("REPLACE INTO MaintenanceRequest VALUES (%s, %s, %s, %s)", (rid, status, room, desc))
            conn.commit()
            st.success("Saved")

# ---------------- TABLES TAB ----------------
with tabs[2]:
    st.header("📋 View Tables")
    tables = ["student", "room", "Building", "Meals", "Penalty", "MaintenanceRequest", "health_issues"]
    tname = st.selectbox("Choose table:", tables)
    cursor.execute(f"SELECT * FROM {tname}")
    st.dataframe(pd.DataFrame(cursor.fetchall()), use_container_width=True)

cursor.close()
conn.close()
