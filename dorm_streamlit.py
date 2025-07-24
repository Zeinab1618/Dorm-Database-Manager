import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime
from pytz import timezone

# --- DATABASE CONNECTION ---
conn = mysql.connector.connect(
    host=st.secrets["mysql"]["host"],
    user=st.secrets["mysql"]["user"],
    password=st.secrets["mysql"]["password"],
    database=st.secrets["mysql"]["database"]
)
cursor = conn.cursor(dictionary=True)

st.title("🏢 Dorm Management System")

# Get available tables
cursor.execute("SHOW TABLES")
tables = [row[f'Tables_in_{st.secrets["mysql"]["database"]}'] for row in cursor.fetchall()]
exclude_tables = ["Meal", "building"]
tables = [t for t in tables if t not in exclude_tables]

selected_table = st.selectbox("Select a Table", [""] + tables)

if selected_table:
    st.subheader(f"📋 {selected_table.capitalize()} Table")
    cursor.execute(f"SELECT * FROM {selected_table}")
    rows = cursor.fetchall()
    df = pd.DataFrame(rows)
    st.dataframe(df)

    # Student Table Operations
    if selected_table == "student":
        st.markdown("### ➕ Add Student")
        with st.expander("Add New Student"):
            new_name = st.text_input("Student Name")
            new_contact = st.text_input("Contact")
            new_room_id = st.number_input("Room ID", step=1, format="%d")
            health_prescription = st.text_input("Prescription")
            health_description = st.text_input("Description")
            if st.button("Add Student"):
                cursor.execute("INSERT INTO student (student_Name, contact, room_id) VALUES (%s, %s, %s)",
                               (new_name, new_contact, new_room_id))
                conn.commit()
                student_id = cursor.lastrowid

                # Insert health issue if provided
                if health_prescription or health_description:
                    cursor.execute("INSERT INTO health_issues (student_id, prescription, description) VALUES (%s, %s, %s)",
                                   (student_id, health_prescription, health_description))
                    conn.commit()

                # Insert default penalty
                cairo_time = datetime.now(timezone("Africa/Cairo")).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT INTO penalty (student_id, total_points, last_update_time) VALUES (%s, %s, %s)",
                               (student_id, 0, cairo_time))
                conn.commit()
                st.success("Student and health info added successfully.")

        # Delete student
        st.markdown("### ❌ Delete Student")
        del_id = st.number_input("Student ID to Delete", step=1, format="%d")
        if st.button("Delete Student"):
            cursor.execute("DELETE FROM student WHERE id = %s", (del_id,))
            conn.commit()
            st.success("Student deleted.")

        # Search and update
        st.markdown("### 🔍 Search Student by ID")
        student_id = st.number_input("Search Student by ID", step=1, format="%d", key="search_id")
        if st.button("Search"):
            cursor.execute("SELECT * FROM student WHERE id = %s", (student_id,))
            student = cursor.fetchone()
            if student:
                st.json(student)

                # Meal update
                st.markdown("### 📝 Change Meal")
                selected_weekday = st.selectbox("Weekday", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
                selected_meal = st.selectbox("Meal Type", ["A", "B"])
                if st.button("Update Meal"):
                    try:
                        cursor.execute("""
                            REPLACE INTO Meals (student_id, weekday, meal_type)
                            VALUES (%s, %s, %s)
                        """, (student_id, selected_weekday, selected_meal))
                        conn.commit()
                        st.success("Meal updated successfully.")
                    except Exception as e:
                        st.error(f"Failed to update meal: {e}")

                # Health Issue update
                st.markdown("### 💊 Update Health Issue")
                cursor.execute("SELECT * FROM health_issues WHERE student_id = %s", (student_id,))
                issue = cursor.fetchone()

                prescription = st.text_input("Prescription", value=issue["prescription"] if issue else "")
                description = st.text_input("Description", value=issue["description"] if issue else "")
                if st.button("Update Health Issue"):
                    if issue:
                        cursor.execute("""
                            UPDATE health_issues
                            SET prescription = %s, description = %s
                            WHERE student_id = %s
                        """, (prescription, description, student_id))
                    else:
                        cursor.execute("""
                            INSERT INTO health_issues (student_id, prescription, description)
                            VALUES (%s, %s, %s)
                        """, (student_id, prescription, description))
                    conn.commit()
                    st.success("Health issue updated.")

    # Penalty Table Operations
    elif selected_table == "penalty":
        st.markdown("### ✏️ Update Penalty Points")
        penalty_id = st.number_input("Penalty Student ID", step=1, format="%d")
        new_points = st.number_input("New Total Points", step=1)
        if st.button("Update Penalty"):
            time_now = datetime.now(timezone("Africa/Cairo")).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                UPDATE penalty
                SET total_points = %s, last_update_time = %s
                WHERE student_id = %s
            """, (new_points, time_now, penalty_id))
            conn.commit()
            st.success("Penalty updated.")

    # Maintenance and Health Tables
    elif selected_table in ["maintenance_requests", "health_issues"]:
        st.markdown(f"### ✏️ Update {selected_table.replace('_', ' ').capitalize()}")
        columns = df.columns.tolist()
        selected_id = st.number_input(f"{selected_table} ID", step=1)
        selected_column = st.selectbox("Field to Edit", [col for col in columns if col != "student_id"])
        new_value = st.text_input("New Value")
        if st.button("Apply Update"):
            cursor.execute(f"""
                UPDATE {selected_table}
                SET {selected_column} = %s
                WHERE id = %s
            """, (new_value, selected_id))
            conn.commit()
            st.success("Update applied.")

