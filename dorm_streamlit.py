import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime
from pytz import timezone

# Database connection
try:
    conn = mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )
    cursor = conn.cursor()
except Exception as e:
    st.error(f"Database connection failed: {e}")
    st.stop()

st.title("Dorm Database Manager")

# View existing tables
cursor.execute("SHOW TABLES")
tables = [table[0] for table in cursor.fetchall() if table[0].lower() not in ("meal", "building")]

selected_table = st.selectbox("Select a table to view and edit", tables)

if selected_table:
    cursor.execute(f"SELECT * FROM {selected_table}")
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    df = pd.DataFrame(rows, columns=columns)
    st.dataframe(df)

    if selected_table == "student":
        with st.expander("Add Student"):
            name = st.text_input("Student Name")
            room_id = st.number_input("Room ID", min_value=1, step=1)
            meal_choice = st.selectbox("Meal Choice", ["A", "B"])
            prescription = st.text_input("Prescription (Optional)")
            description = st.text_area("Health Issue Description (Optional)")
            if st.button("Add Student"):
                try:
                    cursor.execute("INSERT INTO student (name, room_id) VALUES (%s, %s)", (name, room_id))
                    student_id = cursor.lastrowid
                    cursor.execute("INSERT INTO Meals (student_id, weekday, meal_type) VALUES (%s, %s, %s)", (student_id, "Saturday", meal_choice))
                    if prescription or description:
                        cursor.execute("INSERT INTO health_issues (student_id, prescription, description) VALUES (%s, %s, %s)", (student_id, prescription, description))
                    cursor.execute("INSERT INTO penalty (student_id, total_points, time) VALUES (%s, %s, %s)", (student_id, 0, datetime.now(timezone("Africa/Cairo"))))
                    cursor.execute("UPDATE room SET occupancy = occupancy + 1 WHERE room_id = %s", (room_id,))
                    conn.commit()
                    st.success("Student added successfully.")
                    st.experimental_rerun()
                except mysql.connector.Error as e:
                    conn.rollback()
                    st.error(f"Failed to add student: {e}")

        search_id = st.text_input("Search Student by ID")
        if search_id:
            cursor.execute("SELECT * FROM student WHERE student_id = %s", (search_id,))
            student_info = cursor.fetchone()
            if student_info:
                st.write("Student Info:", dict(zip(columns, student_info)))

                # Meal form corrected
                with st.form("update_meal_form"):
                    st.write("Update or Add Meal Preference")
                    weekday_update = st.selectbox("Weekday to Update", 
                                                  ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                                                  key="meal_weekday")
                    meal_update = st.selectbox("New Meal Type", ["A", "B"], key="meal_type")
                    meal_submitted = st.form_submit_button("Submit Meal Update", key="submit_meal_update")

                    if meal_submitted:
                        try:
                            student_id = int(search_id)
                            cursor.execute("""
                                INSERT INTO Meals (student_id, weekday, meal_type)
                                VALUES (%s, %s, %s)
                                ON DUPLICATE KEY UPDATE meal_type = VALUES(meal_type)
                            """, (student_id, weekday_update, meal_update))
                            conn.commit()
                            st.success("Meal preference updated successfully")
                            st.experimental_rerun()
                        except mysql.connector.Error as e:
                            conn.rollback()
                            st.error(f"Error updating meal: {e}")

                # Health issue update form
                with st.form("health_issue_form"):
                    prescription = st.text_input("Prescription", key="prescription_input")
                    description = st.text_area("Health Issue Description", key="description_input")
                    submitted = st.form_submit_button("Update Health Issue")
                    if submitted:
                        try:
                            student_id = int(search_id)
                            cursor.execute("SELECT * FROM health_issues WHERE student_id = %s", (student_id,))
                            if cursor.fetchone():
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
                            st.success("Health issue updated successfully")
                            st.experimental_rerun()
                        except mysql.connector.Error as e:
                            conn.rollback()
                            st.error(f"Error updating health issue: {e}")

                if st.button("Delete Student"):
                    try:
                        student_id = int(search_id)
                        cursor.execute("SELECT room_id FROM student WHERE student_id = %s", (student_id,))
                        room_result = cursor.fetchone()
                        if room_result:
                            room_id = room_result[0]
                            cursor.execute("DELETE FROM student WHERE student_id = %s", (student_id,))
                            cursor.execute("UPDATE room SET occupancy = occupancy - 1 WHERE room_id = %s", (room_id,))
                            conn.commit()
                            st.success("Student deleted successfully")
                            st.experimental_rerun()
                        else:
                            st.error("Student not found.")
                    except mysql.connector.Error as e:
                        conn.rollback()
                        st.error(f"Error deleting student: {e}")
            else:
                st.warning("Student not found.")

    elif selected_table == "penalty":
        st.write("Penalty Table Operations")
        with st.form("update_penalty_form"):
            penalty_id = st.number_input("Penalty ID to update", min_value=1, step=1)
            new_points = st.number_input("New Total Points", step=1)
            submit_penalty = st.form_submit_button("Update Penalty")
            if submit_penalty:
                try:
                    now = datetime.now(timezone("Africa/Cairo"))
                    cursor.execute("UPDATE penalty SET total_points = %s, time = %s WHERE penalty_id = %s",
                                   (new_points, now, penalty_id))
                    conn.commit()
                    st.success("Penalty updated successfully")
                    st.experimental_rerun()
                except mysql.connector.Error as e:
                    conn.rollback()
                    st.error(f"Error updating penalty: {e}")
        with st.form("add_penalty_form"):
            student_id_penalty = st.number_input("Student ID", min_value=1, step=1)
            points = st.number_input("Penalty Points", step=1)
            submit_add_penalty = st.form_submit_button("Add Penalty")
            if submit_add_penalty:
                try:
                    now = datetime.now(timezone("Africa/Cairo"))
                    cursor.execute("INSERT INTO penalty (student_id, total_points, time) VALUES (%s, %s, %s)",
                                   (student_id_penalty, points, now))
                    conn.commit()
                    st.success("Penalty added successfully")
                    st.experimental_rerun()
                except mysql.connector.Error as e:
                    conn.rollback()
                    st.error(f"Error adding penalty: {e}")

    elif selected_table in ["maintenance_requests", "health_issues"]:
        st.write(f"Update Records in {selected_table}")
        with st.form("update_form"):
            row_id = st.number_input(f"Enter {selected_table[:-1]} ID to update", step=1)
            field_to_update = st.text_input("Field to update (e.g., description)")
            new_value = st.text_input("New value")
            submit_update = st.form_submit_button("Update")
            if submit_update:
                try:
                    cursor.execute(f"UPDATE {selected_table} SET {field_to_update} = %s WHERE {selected_table[:-1]}_id = %s",
                                   (new_value, row_id))
                    conn.commit()
                    st.success("Update successful")
                    st.experimental_rerun()
                except mysql.connector.Error as e:
                    conn.rollback()
                    st.error(f"Error updating {selected_table}: {e}")
