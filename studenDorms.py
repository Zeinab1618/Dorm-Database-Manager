import mysql.connector

conn = mysql.connector.connect(
    host=st.secrets["mysql"]["host"],
    user=st.secrets["mysql"]["user"],
    password=st.secrets["mysql"]["password"],
    database=st.secrets["mysql"]["database"],
    port=st.secrets["mysql"]["port"],
    ssl_ca=st.secrets["mysql"]["ssl_ca"]
)

cursor = conn.cursor()
sql_statements = [
    """CREATE TABLE IF NOT EXISTS Building(
            id INT PRIMARY KEY,
            building_name VARCHAR (100) NOT NULL UNIQUE
    );
    """,
    """CREATE TABLE IF NOT EXISTS room(
            id INT PRIMARY KEY,
            floor INT NOT NULL,
            building_id INT,
            capacity INT NOT NULL DEFAULT 0,
            current_occupancy INT NOT NULL DEFAULT 0,
            FOREIGN KEY (building_id) REFERENCES building(id)
    );
    """,
    """CREATE TABLE IF NOT EXISTS student(
            id INT PRIMARY KEY,
            student_Name VARCHAR(100),
            contact VARCHAR(11) NOT NULL UNIQUE,
            room_id INT NOT NULL,
            FOREIGN KEY (room_id) REFERENCES room(id)
    );
    """,
    """CREATE TABLE IF NOT EXISTS MaintenanceRequest(
            id INT PRIMARY KEY,
            statues ENUM('Pending','In Progress','Resolved') NOT NULL DEFAULT 'Pending',
            room_id INT NOT NULL,
            description TEXT,
            date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id) REFERENCES room(id)
    );
    """,
    """CREATE TABLE IF NOT EXISTS Penalty(
            student_id INT PRIMARY KEY,
            total_points INT DEFAULT 0 CHECK (total_points >= 0),
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES student(id)
    );
    """,
    """CREATE TABLE IF NOT EXISTS Meals(
            student_id INT,
            meal_type ENUM('A','B') NOT NULL,
            weekday VARCHAR(10) NOT NULL,
            PRIMARY KEY (student_id, weekday),
            FOREIGN KEY (student_id) REFERENCES student(id)
    );
    """,
    """
      CREATE TABLE IF NOT EXISTS health_issues (
          student_id INT PRIMARY KEY,
          description TEXT,
          prescription TEXT,
          guardian_contact VARCHAR(11) NOT NULL,
          FOREIGN KEY (student_id) REFERENCES student(id)
      );
      """
]

for sql in sql_statements:
    cursor.execute(sql)

cursor.execute("""
    INSERT INTO Building (id, building_name) VALUES
    (1, 'A Building'),
    (2, 'B Building')
    ON DUPLICATE KEY UPDATE building_name = VALUES(building_name);
""")

cursor.execute("""
    INSERT INTO room (id, floor, building_id, capacity, current_occupancy) VALUES
    (101, 1, 1, 2, 1),
    (102, 1, 1, 3, 2),
    (201, 2, 2, 2, 0)
    ON DUPLICATE KEY UPDATE floor = VALUES(floor),
                              building_id = VALUES(building_id),
                              capacity = VALUES(capacity),
                              current_occupancy = VALUES(current_occupancy);
""")

cursor.execute("""
    INSERT INTO student (id, student_Name, contact, room_id) VALUES
    (1, 'John Doe', '01234567890', 101),
    (2, 'Jane Smith', '01111111111', 102),
    (3, 'Alice Johnson', '01022223333', 102)
    ON DUPLICATE KEY UPDATE student_Name = VALUES(student_Name),
                             contact = VALUES(contact),
                             room_id = VALUES(room_id);
""")

cursor.execute("""
    INSERT INTO MaintenanceRequest (id, statues, room_id, description) VALUES
    (1, 'Pending', 101, 'Leaky faucet'),
    (2, 'In Progress', 102, 'Broken light bulb')
    ON DUPLICATE KEY UPDATE statues = VALUES(statues),
                             room_id = VALUES(room_id),
                             description = VALUES(description);
""")

cursor.execute("""
    INSERT INTO Penalty (student_id, total_points) VALUES
    (1, 2),
    (2, 0),
    (3, 1)
    ON DUPLICATE KEY UPDATE total_points = VALUES(total_points);
""")

cursor.execute("""
    INSERT INTO Meals (student_id, meal_type, weekday) VALUES
    (1, 'A', 'Monday'),
    (2, 'B', 'Tuesday'),
    (3, 'A', 'Wednesday')
    ON DUPLICATE KEY UPDATE meal_type = VALUES(meal_type);
""")

cursor.execute("""
    INSERT INTO health_issues (student_id, description, prescription, guardian_contact) VALUES
    (1, 'Asthma', 'Inhaler', '01098765432'),
    (3, 'Peanut allergy', 'EpiPen', '01234567891')
    ON DUPLICATE KEY UPDATE description = VALUES(description),
                             prescription = VALUES(prescription),
                             guardian_contact = VALUES(guardian_contact);
""")


conn.commit()
cursor.close()
conn.close()
print("✅ Tables created and sample data inserted successfully!")


