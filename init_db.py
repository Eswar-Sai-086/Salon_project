import sqlite3
import random
from datetime import datetime

def initialize_database():
    conn = sqlite3.connect('salon.db')
    cursor = conn.cursor()

    cursor.execute('DROP TABLE IF EXISTS Services')
    cursor.execute('DROP TABLE IF EXISTS Products')
    cursor.execute('DROP TABLE IF EXISTS Invoices')
    cursor.execute('DROP TABLE IF EXISTS Staff')
    cursor.execute('DROP TABLE IF EXISTS Admins')
    cursor.execute('DROP TABLE IF EXISTS Customers')
    cursor.execute('DROP TABLE IF EXISTS Attendance')
    cursor.execute('DROP TABLE IF EXISTS Leaves')
    cursor.execute('DROP TABLE IF EXISTS System_Meta')

    # 1. System Meta (NEW: Tracks automated tasks)
    cursor.execute('''CREATE TABLE System_Meta (Key TEXT PRIMARY KEY, Value TEXT NOT NULL)''')
    # Set to last month so it instantly triggers the first automated credit when you boot it up!
    cursor.execute("INSERT INTO System_Meta (Key, Value) VALUES ('Last_Monthly_Credit', '2026-04')")

    # 2. Admins
    cursor.execute('''CREATE TABLE Admins (ID INTEGER PRIMARY KEY AUTOINCREMENT, Username TEXT NOT NULL, Password TEXT NOT NULL)''')
    cursor.execute("INSERT INTO Admins (Username, Password) VALUES ('admin', 'luxe2026')")

    # 3. Customers
    cursor.execute('''CREATE TABLE Customers (Customer_ID INTEGER PRIMARY KEY AUTOINCREMENT, Full_Name TEXT NOT NULL, Phone TEXT UNIQUE NOT NULL, Password TEXT NOT NULL)''')

    # 4. Staff 
    cursor.execute('''CREATE TABLE Staff (Staff_ID INTEGER PRIMARY KEY AUTOINCREMENT, Staff_Name TEXT NOT NULL, Username TEXT UNIQUE NOT NULL, Password TEXT UNIQUE NOT NULL, Leave_Balance INTEGER DEFAULT 2)''')
    staff_members = [("Sarah", "sarah1", "vn2026_1"), ("Michael", "mike1", "vn2026_2"), ("Priya", "priya1", "vn2026_3"), ("David", "david1", "vn2026_4")]
    cursor.executemany("INSERT INTO Staff (Staff_Name, Username, Password) VALUES (?, ?, ?)", staff_members)

    # 5. Attendance (UPGRADED: Clock In, Clock Out, and Hours)
    cursor.execute('''CREATE TABLE Attendance (
        Log_ID INTEGER PRIMARY KEY AUTOINCREMENT, 
        Staff_Name TEXT NOT NULL, 
        Date TEXT NOT NULL,
        Clock_In TIMESTAMP NOT NULL, 
        Clock_Out TIMESTAMP,
        Hours_Worked REAL DEFAULT 0.0,
        Latitude REAL, Longitude REAL, Image_Base64 TEXT)''')

    # 6. Leaves
    cursor.execute('''CREATE TABLE Leaves (Leave_ID INTEGER PRIMARY KEY AUTOINCREMENT, Staff_Name TEXT NOT NULL, Start_Date TEXT NOT NULL, End_Date TEXT NOT NULL, Reason TEXT NOT NULL, Status TEXT DEFAULT 'Pending')''')

    # 7. Services & Products
    cursor.execute('''CREATE TABLE Services (Service_ID INTEGER PRIMARY KEY AUTOINCREMENT, Service_Name TEXT NOT NULL, Price REAL NOT NULL)''')
    cursor.executemany("INSERT INTO Services (Service_Name, Price) VALUES (?, ?)", [(name, float(random.randint(299, 599))) for name in ["Hair Styling", "Bridal Makeup", "Keratin Treatment", "Manicure & Pedicure", "Facial Treatment", "Hair Spa", "Threading & Waxing", "Body Massage", "Hair Coloring", "Scalp Treatment"]])

    cursor.execute('''CREATE TABLE Products (Product_ID INTEGER PRIMARY KEY AUTOINCREMENT, Product_Name TEXT NOT NULL, Price REAL NOT NULL)''')
    cursor.executemany("INSERT INTO Products (Product_Name, Price) VALUES (?, ?)", [(name, float(random.randint(499, 1299))) for name in ["Moroccan Argan Oil", "Sulfate-Free Shampoo", "Keratin Hair Mask", "Vitamin C Face Serum", "Tea Tree Scalp Scrub"]])

    # 8. Invoices
    cursor.execute('''CREATE TABLE Invoices (Invoice_Number TEXT PRIMARY KEY, Date_Time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, Customer_Name TEXT, Customer_Phone TEXT, Staff_Name TEXT, Service_Name TEXT, Product_Name TEXT, Subtotal REAL NOT NULL, Discount REAL NOT NULL, Tax REAL NOT NULL, Total_Amount REAL NOT NULL, Payment_Method TEXT)''')

    conn.commit()
    conn.close()
    print("Database fully upgraded with Automation Tracking and Timesheets!")

if __name__ == '__main__':
    initialize_database()