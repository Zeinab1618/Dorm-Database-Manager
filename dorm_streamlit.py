import streamlit as st
import mysql.connector
import pandas as pd

conn = mysql.connector.connect(
    host=st.secrets["mysql"]["host"],
    user=st.secrets["mysql"]["user"],
    password=st.secrets["mysql"]["password"],
    database=st.secrets["mysql"]["database"],
    port=st.secrets["mysql"]["port"],
    ssl_ca=st.secrets["mysql"]["ssl_ca"]
)
cursor = conn.cursor(dictionary=True)

st.title("Dormitory Management System")

menu = st.sidebar.radio("Select a Page", ["Students", "Maintenance Requests", "All Tables"])

if menu == "Students":
    st.header("Student Information")

    cursor.execute("SELECT * FROM student")
    students = cursor.fetchall()
    df = pd.DataFrame(students)
    st.dataframe(df)

    with st.expander("Add New Student"):
        sid = st.number_input("Student ID", step=1)
        name = st.text_input("Student Name")
        contact = st.text_input("Contact")
        room_id = st.number_input("Room ID", step=1)
        if st.button("Insert Student"):
            cursor.execute("INSERT INTO student VALUES (%s, %s, %s, %s)", (sid, name, contact, room_id))
            conn.commit()
            st.success("Student added!")

    del_id = st.number_input("Delete Student by ID", step=1)
    if st.button("Delete Student"):
        cursor.execute("DELETE FROM student WHERE id = %s", (del_id,))
        conn.commit()
        st.warning("Student deleted!")

    search_id = st.number_input("Search Student by ID", step=1, key="search")
    if st.button("Search"):
        cursor.execute("SELECT * FROM student WHERE id = %s", (search_id,))
        student = cursor.fetchone()
        if student:
            st.json(student)

            st.subheader("Change Meal")
            weekday = st.selectbox("Weekday", ["Sunday","Monday","Tuesday","Wednesday","Thursday"])
            meal_type = st.selectbox("Meal Type", ["A", "B"])
            if st.button("Update Meal"):
                cursor.execute("REPLACE INTO Meals (student_id, meal_type, weekday) VALUES (%s, %s, %s)", (search_id, meal_type, weekday))
                conn.commit()
                st.success("Meal updated!")

            st.subheader("Health Issue")
            cursor.execute("SELECT * FROM health_issues WHERE student_id = %s", (search_id,))
            health = cursor.fetchone()
            if health:
                desc = st.text_area("Description", health['description'])
                prescription = st.text_input("Prescription", health['prescription'])
                guardian = st.text_input("Guardian Contact", health['guardian_contact'])
                if st.button("Update Health Issue"):
                    cursor.execute("""
                        UPDATE health_issues SET description=%s, prescription=%s, guardian_contact=%s
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
                    cursor.execute("INSERT INTO health_issues VALUES (%s, %s, %s, %s)", (search_id, desc, prescription, guardian))
                    conn.commit()
                    st.success("Health issue added!")
        else:
            st.error("Student not found")

elif menu == "Maintenance Requests":
    st.header("Maintenance Requests")

    cursor.execute("SELECT * FROM MaintenanceRequest")
    maintenance = cursor.fetchall()
    df = pd.DataFrame(maintenance)
    st.dataframe(df)

    with st.expander("Add/Edit Request"):
        mid = st.number_input("Request ID", step=1)
        status = st.selectbox("Status", ["Pending", "In Progress", "Resolved"])
        room_id = st.number_input("Room ID", step=1, key="maint")
        description = st.text_area("Description")
        if st.button("Save Maintenance Request"):
            cursor.execute("REPLACE INTO MaintenanceRequest (id, statues, room_id, description) VALUES (%s, %s, %s, %s)", (mid, status, room_id, description))
            conn.commit()
            st.success("Saved!")

elif menu == "All Tables":
    st.header("View Any Table")

    allowed_tables = [
        "student", "room", "Building", "Meals",
        "Penalty", "MaintenanceRequest", "health_issues"
    ]
    selected_table = st.selectbox("Choose a table to view:", allowed_tables)

    if selected_table:
        try:
            cursor.execute(f"SELECT * FROM {selected_table}")
            data = cursor.fetchall()
            if data:
                df = pd.DataFrame(data)
                st.dataframe(df)
            else:
                st.info("No data found.")
        except Exception as e:
            st.error(f"Error: {e}")

cursor.close()
conn.close()

