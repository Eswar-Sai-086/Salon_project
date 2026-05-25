from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import json
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'super_secure_vn_key_2026'

@app.template_filter('in_time')
def in_time(value):
    if not value: return ''
    try:
        dt = datetime.strptime(value[:19], '%Y-%m-%d %H:%M:%S')
        return dt.strftime('%I:%M %p') # Just shows the time beautifully
    except: return value

def get_db_connection():
    conn = sqlite3.connect('salon.db')
    conn.row_factory = sqlite3.Row
    return conn

# --- NEW: SILENT AUTOMATION ENGINE ---
# Runs invisibly before any page loads to check if a new month has started
@app.before_request
def automated_monthly_tasks():
    if request.endpoint == 'static': return
    conn = get_db_connection()
    current_month = datetime.now().strftime('%Y-%m')
    try:
        last_credit = conn.execute("SELECT Value FROM System_Meta WHERE Key = 'Last_Monthly_Credit'").fetchone()
        if last_credit and last_credit['Value'] != current_month:
            # It is a new month! Auto-add 2 leaves to everyone.
            conn.execute('UPDATE Staff SET Leave_Balance = Leave_Balance + 2')
            conn.execute("UPDATE System_Meta SET Value = ? WHERE Key = 'Last_Monthly_Credit'", (current_month,))
            conn.commit()
            print(f"AUTOMATION: Successfully credited 2 leaves for {current_month}")
    except: pass
    conn.close()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin': return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def staff_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'staff': return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def customer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'customer': return redirect(url_for('client_auth'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def customer_home():
    conn = get_db_connection()
    services = conn.execute('SELECT Service_Name FROM Services').fetchall()
    conn.close()
    return render_template('index.html', services=services)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        conn = get_db_connection()
        admin = conn.execute('SELECT * FROM Admins WHERE Username = ? AND Password = ?', (username, password)).fetchone()
        if admin:
            session['role'], session['username'] = 'admin', admin['Username']
            conn.close()
            return redirect(url_for('admin_dashboard'))
        staff = conn.execute('SELECT * FROM Staff WHERE Username = ? AND Password = ?', (username, password)).fetchone()
        if staff:
            session['role'], session['staff_name'] = 'staff', staff['Staff_Name']
            conn.close()
            return redirect(url_for('staff_dashboard'))
        conn.close()
        flash('Invalid credentials.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    role = session.get('role')
    session.clear()
    if role == 'customer': return redirect(url_for('client_auth'))
    return redirect(url_for('login'))

@app.route('/client/auth', methods=['GET', 'POST'])
def client_auth():
    if request.method == 'POST':
        action, phone, password = request.form.get('action'), request.form.get('phone'), request.form.get('password')
        conn = get_db_connection()
        if action == 'login':
            customer = conn.execute('SELECT * FROM Customers WHERE Phone = ? AND Password = ?', (phone, password)).fetchone()
            if customer:
                session['role'], session['customer_phone'], session['customer_name'] = 'customer', customer['Phone'], customer['Full_Name']
                conn.close()
                return redirect(url_for('client_dashboard'))
            flash('Invalid phone number or password.')
        elif action == 'register':
            name = request.form.get('full_name')
            try:
                conn.execute('INSERT INTO Customers (Full_Name, Phone, Password) VALUES (?, ?, ?)', (name, phone, password))
                conn.commit()
                flash('Registration successful! You can now log in.')
            except sqlite3.IntegrityError: flash('Phone number already registered.')
        conn.close()
    return render_template('customer_login.html')

@app.route('/client/dashboard')
@customer_required
def client_dashboard():
    conn = get_db_connection()
    invoices = conn.execute('SELECT * FROM Invoices WHERE Customer_Phone = ? ORDER BY Date_Time DESC', (session['customer_phone'],)).fetchall()
    total_spent = sum(inv['Total_Amount'] for inv in invoices)
    conn.close()
    return render_template('customer_dashboard.html', invoices=invoices, total_spent=total_spent)

@app.route('/api/customer/<phone>')
@admin_required
def api_get_customer(phone):
    conn = get_db_connection()
    customer = conn.execute('SELECT Full_Name FROM Customers WHERE Phone = ?', (phone,)).fetchone()
    conn.close()
    return jsonify({'name': customer['Full_Name']}) if customer else jsonify({'name': ''})

# --- UPGRADED STAFF DASHBOARD (Clock In & Out + Timesheet) ---
@app.route('/staff/dashboard', methods=['GET', 'POST'])
@staff_required
def staff_dashboard():
    conn = get_db_connection()
    today_date = datetime.now().strftime('%Y-%m-%d')
    
    if request.method == 'POST':
        action = request.form.get('action_type')
        if action == 'attendance':
            img_data, lat, lon = request.form.get('image_data'), request.form.get('latitude'), request.form.get('longitude')
            local_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Check if they have clocked in today
            existing_log = conn.execute("SELECT * FROM Attendance WHERE Staff_Name = ? AND Date = ?", (session['staff_name'], today_date)).fetchone()
            
            if not existing_log:
                # CLOCK IN
                conn.execute('INSERT INTO Attendance (Staff_Name, Date, Clock_In, Latitude, Longitude, Image_Base64) VALUES (?, ?, ?, ?, ?, ?)', (session['staff_name'], today_date, local_time, lat, lon, img_data))
                flash('Clocked In Successfully! Have a great shift.')
            elif not existing_log['Clock_Out']:
                # CLOCK OUT - Calculate Hours
                in_time = datetime.strptime(existing_log['Clock_In'], '%Y-%m-%d %H:%M:%S')
                out_time = datetime.strptime(local_time, '%Y-%m-%d %H:%M:%S')
                hours_worked = round((out_time - in_time).total_seconds() / 3600, 2)
                
                conn.execute('UPDATE Attendance SET Clock_Out = ?, Hours_Worked = ? WHERE Log_ID = ?', (local_time, hours_worked, existing_log['Log_ID']))
                flash(f'Clocked Out Successfully! You worked {hours_worked} hours today.')
            conn.commit()
            
        elif action == 'leave':
            start_date, end_date, reason = request.form.get('start_date'), request.form.get('end_date'), request.form.get('reason')
            conn.execute('INSERT INTO Leaves (Staff_Name, Start_Date, End_Date, Reason) VALUES (?, ?, ?, ?)', (session['staff_name'], start_date, end_date, reason))
            conn.commit()
            flash('Leave Request Submitted!')

    # Fetch status for UI
    today_log = conn.execute("SELECT * FROM Attendance WHERE Staff_Name = ? AND Date = ?", (session['staff_name'], today_date)).fetchone()
    
    # Timesheet Data
    timesheet = conn.execute("SELECT * FROM Attendance WHERE Staff_Name = ? ORDER BY Date DESC", (session['staff_name'],)).fetchall()
    
    today_sales = conn.execute("SELECT Date_Time, Customer_Name FROM Invoices WHERE Staff_Name = ? AND date(Date_Time) = date('now', 'localtime') ORDER BY Date_Time DESC", (session['staff_name'],)).fetchall()
    leaves = conn.execute("SELECT * FROM Leaves WHERE Staff_Name = ? ORDER BY Leave_ID DESC", (session['staff_name'],)).fetchall()
    staff_data = conn.execute("SELECT Leave_Balance FROM Staff WHERE Staff_Name = ?", (session['staff_name'],)).fetchone()
    
    conn.close()
    return render_template('staff_dashboard.html', today_log=today_log, timesheet=timesheet, sales=today_sales, leaves=leaves, balance=staff_data['Leave_Balance'])

@app.route('/admin/staff', methods=['GET', 'POST'])
@admin_required
def manage_staff():
    conn = get_db_connection()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            s_name, s_user, s_pass = request.form.get('new_staff_name'), request.form.get('new_staff_user'), request.form.get('new_staff_pass')
            if conn.execute('SELECT * FROM Staff WHERE Password = ?', (s_pass,)).fetchone():
                flash("Error: Password already assigned. Must be unique.")
            else:
                try:
                    conn.execute('INSERT INTO Staff (Staff_Name, Username, Password) VALUES (?, ?, ?)', (s_name, s_user, s_pass))
                    conn.commit()
                    flash(f"Staff account created for {s_name}!")
                except sqlite3.IntegrityError: flash("Error: Username taken.")
        elif action == 'delete':
            staff_id = request.form.get('staff_id')
            conn.execute('DELETE FROM Staff WHERE Staff_ID = ?', (staff_id,))
            conn.commit()
            flash("Access Revoked successfully.")
        elif action == 'adjust_balance':
            staff_id, new_balance = request.form.get('staff_id'), request.form.get('new_balance')
            conn.execute('UPDATE Staff SET Leave_Balance = ? WHERE Staff_ID = ?', (new_balance, staff_id))
            conn.commit()
            flash("Leave balance updated manually.")
        return redirect(url_for('manage_staff'))
        
    staff = conn.execute('SELECT * FROM Staff ORDER BY Staff_Name').fetchall()
    conn.close()
    return render_template('staff_management.html', staff=staff)

@app.route('/admin', methods=('GET', 'POST'))
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    if request.method == 'POST':
        action = request.form.get('action_type')
        if action == 'checkout':
            customer_name, customer_phone = request.form.get('customer_name', 'Walk-in').strip(), request.form.get('customer_phone', '').strip()
            staff_name, payment_method = request.form.get('staff_name', 'Unassigned'), request.form.get('payment_method', 'Cash')
            discount, tax_rate = float(request.form.get('discount', 0.0) or 0.0), float(request.form.get('tax', 0.0) or 0.0)
            local_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if customer_phone and not conn.execute('SELECT * FROM Customers WHERE Phone = ?', (customer_phone,)).fetchone():
                default_pw = f"vn{customer_phone[-4:]}" if len(customer_phone) >= 4 else f"vn{customer_phone}"
                try:
                    conn.execute('INSERT INTO Customers (Full_Name, Phone, Password) VALUES (?, ?, ?)', (customer_name, customer_phone, default_pw))
                    flash(f"Client account auto-created! Temp Password: {default_pw}")
                except Exception: pass

            cart_data = request.form.get('cart_data')
            if cart_data:
                items = json.loads(cart_data)
                subtotal = sum(float(i['price']) for i in items)
                service_names = [f"{i['name']}|{i['price']}" for i in items if i['type'] == 'service']
                product_names = [f"{i['name']}|{i['price']}" for i in items if i['type'] == 'product']
                tax_amount = (subtotal - discount) * (tax_rate / 100.0)
                total_amount = (subtotal - discount) + tax_amount

                cursor = conn.cursor()
                today_str = datetime.now().strftime('%Y%m%d')
                daily_count = cursor.execute("SELECT COUNT(*) FROM Invoices WHERE Invoice_Number LIKE ?", (f"INV-{today_str}-%",)).fetchone()[0] + 1
                invoice_number = f"INV-{today_str}-{daily_count:03d}"

                conn.execute('''INSERT INTO Invoices (Invoice_Number, Date_Time, Customer_Name, Customer_Phone, Staff_Name, Service_Name, Product_Name, Subtotal, Discount, Tax, Total_Amount, Payment_Method) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (invoice_number, local_time, customer_name, customer_phone or 'N/A', staff_name, ", ".join(service_names) or "None", ", ".join(product_names) or "None", subtotal, discount, tax_amount, total_amount, payment_method))
                conn.commit()
                
        elif action in ['approve_leave', 'reject_leave']:
            leave_id = request.form.get('leave_id')
            status = 'Approved' if action == 'approve_leave' else 'Rejected'
            leave = conn.execute('SELECT * FROM Leaves WHERE Leave_ID = ?', (leave_id,)).fetchone()
            if status == 'Approved' and leave['Status'] == 'Pending':
                d1 = datetime.strptime(leave['Start_Date'], '%Y-%m-%d')
                d2 = datetime.strptime(leave['End_Date'], '%Y-%m-%d')
                days_taken = max(1, (d2 - d1).days + 1)
                conn.execute('UPDATE Staff SET Leave_Balance = Leave_Balance - ? WHERE Staff_Name = ?', (days_taken, leave['Staff_Name']))
            conn.execute('UPDATE Leaves SET Status = ? WHERE Leave_ID = ?', (status, leave_id))
            conn.commit()
            flash(f"Leave {status}!")
            
        return redirect(url_for('admin_dashboard'))

    services, products, staff = conn.execute('SELECT * FROM Services').fetchall(), conn.execute('SELECT * FROM Products').fetchall(), conn.execute('SELECT * FROM Staff').fetchall()
    attendance_logs = conn.execute("SELECT * FROM Attendance WHERE Date = date('now', 'localtime') ORDER BY Clock_In DESC").fetchall()
    leaves = conn.execute("SELECT * FROM Leaves WHERE Status = 'Pending' ORDER BY Leave_ID DESC").fetchall()
    daily, weekly, monthly = conn.execute("SELECT SUM(Total_Amount) FROM Invoices WHERE date(Date_Time) = date('now', 'localtime')").fetchone()[0] or 0.0, conn.execute("SELECT SUM(Total_Amount) FROM Invoices WHERE strftime('%W', Date_Time) = strftime('%W', 'now', 'localtime')").fetchone()[0] or 0.0, conn.execute("SELECT SUM(Total_Amount) FROM Invoices WHERE strftime('%m', Date_Time) = strftime('%m', 'now', 'localtime')").fetchone()[0] or 0.0
    invoices = conn.execute("SELECT * FROM Invoices ORDER BY Date_Time DESC LIMIT 10").fetchall()
    conn.close()
    return render_template('admin.html', services=services, products=products, staff=staff, daily=daily, weekly=weekly, monthly=monthly, invoices=invoices, attendance_logs=attendance_logs, leaves=leaves)

@app.route('/invoice/<invoice_number>')
def print_invoice(invoice_number):
    if 'role' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    invoice = conn.execute('SELECT * FROM Invoices WHERE Invoice_Number = ?', (invoice_number,)).fetchone()
    conn.close()
    if not invoice: return "Invoice not found", 404
    if session.get('role') == 'customer' and invoice['Customer_Phone'] != session.get('customer_phone'): return "Unauthorized.", 403
    return render_template('invoice.html', invoice=invoice)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
