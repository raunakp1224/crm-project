from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key')


# =============================
# 🔐 LOGIN REQUIRED DECORATOR
# =============================
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return wrapper


# =============================
# 📦 DB CONNECTION
# =============================
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn


# =============================
# 🛠 CREATE TABLES
# =============================
def create_table():
    conn = get_db_connection()

    conn.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            phone TEXT,
            company TEXT,
            notes TEXT,
            status TEXT
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()


create_table()


# =============================
# 🏠 HOME
# =============================
@app.route('/')
def home():
    return render_template('home.html')


# =============================
# 📊 DASHBOARD
# =============================
@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()

    total_customers = conn.execute('SELECT COUNT(*) FROM customers').fetchone()[0]

    total_companies = conn.execute(
        'SELECT COUNT(DISTINCT company) FROM customers'
    ).fetchone()[0]

    status_data = conn.execute('''
        SELECT status, COUNT(*) as count
        FROM customers
        GROUP BY status
    ''').fetchall()

    status_labels = [row['status'] for row in status_data]
    status_counts = [row['count'] for row in status_data]

    all_customers = conn.execute('SELECT id FROM customers').fetchall()
    growth_labels = list(range(1, len(all_customers) + 1))
    growth_data = growth_labels

    recent_customers = conn.execute(
        'SELECT * FROM customers ORDER BY id DESC LIMIT 5'
    ).fetchall()

    conn.close()

    return render_template(
        'dashboard.html',
        total_customers=total_customers,
        total_companies=total_companies,
        status_labels=status_labels,
        status_counts=status_counts,
        growth_labels=growth_labels,
        growth_data=growth_data,
        recent_customers=recent_customers
    )


# =============================
# 👥 CUSTOMERS (PAGINATION FIXED)
# =============================
@app.route('/customers')
@login_required
def customers():
    # 🔹 Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 10

    # 🔹 Filters
    search = request.args.get('search', '')
    company = request.args.get('company', '')
    status = request.args.get('status', '')
    sort = request.args.get('sort', '')

    conn = get_db_connection()

    query = "SELECT * FROM customers WHERE 1=1"
    params = []

    # 🔍 Search
    if search:
        query += " AND (name LIKE ? OR email LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    # 🏢 Company
    if company:
        query += " AND company = ?"
        params.append(company)

    # 📊 Status
    if status:
        query += " AND status = ?"
        params.append(status)

    # 🔽 SORTING (IMPORTANT)
    if sort == "asc":
        query += " ORDER BY name ASC"
    elif sort == "desc":
        query += " ORDER BY name DESC"
    else:
        query += " ORDER BY id DESC"  # default

    # 🔢 Total count
    total = conn.execute(
        query.replace("SELECT *", "SELECT COUNT(*)"),
        params
    ).fetchone()[0]

    # 🔹 Pagination
    query += " LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])

    customers = conn.execute(query, params).fetchall()

    total_pages = (total + per_page - 1) // per_page

    companies = conn.execute(
        "SELECT DISTINCT company FROM customers"
    ).fetchall()

    conn.close()

    return render_template(
        'customers.html',
        customers=customers,
        page=page,
        total_pages=total_pages,
        search=search,
        selected_company=company,
        selected_status=status,
        sort=sort,
        companies=companies
    )


# =============================
# ➕ ADD CUSTOMER
# =============================
@app.route('/add_customer', methods=['GET', 'POST'])
@login_required
def add_customer():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        company = request.form['company']
        notes = request.form['notes']
        status = request.form['status']

        if not name or not email:
            flash("Name and Email are required!", "danger")
            return redirect(url_for('add_customer'))

        conn = get_db_connection()
        conn.execute(
            'INSERT INTO customers (name, email, phone, company, notes, status) VALUES (?, ?, ?, ?, ?, ?)',
            (name, email, phone, company, notes, status)
        )
        conn.commit()
        conn.close()

        flash("Customer added successfully!", "success")
        return redirect(url_for('customers'))

    return render_template('add_customer.html')


# =============================
# 📂 BULK UPLOAD
# =============================
@app.route('/upload_customers', methods=['POST'])
@login_required
def upload_customers():
    file = request.files.get('file')

    if not file:
        flash("No file selected!", "danger")
        return redirect(url_for('add_customer'))

    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)

        conn = get_db_connection()

        for _, row in df.iterrows():
            conn.execute(
                '''
                INSERT INTO customers (name, email, phone, company, notes, status)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (
                    row.get('name'),
                    row.get('email'),
                    row.get('phone'),
                    row.get('company'),
                    row.get('notes'),
                    row.get('status', 'Lead')
                )
            )

        conn.commit()
        conn.close()

        flash("Customers uploaded successfully!", "success")

    except Exception as e:
        flash(f"Upload error: {str(e)}", "danger")

    return redirect(url_for('customers'))


# =============================
# ✏️ EDIT CUSTOMER
# =============================
@app.route('/edit_customer/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_customer(id):
    conn = get_db_connection()

    if request.method == 'POST':
        conn.execute('''
            UPDATE customers
            SET name=?, email=?, phone=?, company=?, notes=?, status=?
            WHERE id=?
        ''', (
            request.form['name'],
            request.form['email'],
            request.form['phone'],
            request.form['company'],
            request.form['notes'],
            request.form['status'],
            id
        ))
        conn.commit()
        conn.close()

        flash("Customer updated!", "success")
        return redirect('/customers')

    customer = conn.execute(
        'SELECT * FROM customers WHERE id=?', (id,)
    ).fetchone()

    notes = conn.execute(
        'SELECT * FROM notes WHERE customer_id=? ORDER BY created_at DESC',
        (id,)
    ).fetchall()

    conn.close()

    return render_template('edit_customer.html', customer=customer, notes=notes)


# =============================
# 📝 ADD NOTE
# =============================
@app.route('/add_note/<int:customer_id>', methods=['POST'])
@login_required
def add_note(customer_id):
    content = request.form['content']

    conn = get_db_connection()
    conn.execute(
        'INSERT INTO notes (customer_id, content) VALUES (?, ?)',
        (customer_id, content)
    )
    conn.commit()
    conn.close()

    return redirect(f'/edit_customer/{customer_id}')


# =============================
# ❌ DELETE CUSTOMER
# =============================
@app.route('/delete_customer/<int:id>')
@login_required
def delete_customer(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM customers WHERE id = ?', (id,))
    conn.commit()
    conn.close()

    flash("Customer deleted!", "warning")
    return redirect('/customers')


# =============================
# 🔐 SIGNUP
# =============================
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        conn = get_db_connection()
        conn.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, password)
        )
        conn.commit()
        conn.close()

        flash("Account created! Please login.", "success")
        return redirect('/login')

    return render_template('signup.html')


# =============================
# 🔐 LOGIN
# =============================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (request.form['username'],)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], request.form['password']):
            session['user'] = user['username']
            return redirect('/dashboard')
        else:
            flash("Invalid credentials", "danger")

    return render_template('login.html')


# =============================
# 🚪 LOGOUT
# =============================
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# =============================
# 📥 EXPORT CSV
# =============================
@app.route('/export_csv')
@login_required
def export_csv():
    conn = get_db_connection()
    customers = conn.execute("SELECT * FROM customers").fetchall()
    conn.close()

    def generate():
        yield "Name,Email,Phone,Company,Status\n"
        for c in customers:
            yield f"{c['name']},{c['email']},{c['phone']},{c['company']},{c['status']}\n"

    return Response(generate(), mimetype='text/csv',
                    headers={"Content-Disposition": "attachment;filename=customers.csv"})

@app.route('/download_template')
@login_required
def download_template():
    def generate():
        yield "name,email,phone,company,notes,status\n"
        yield "John Doe,john@gmail.com,1234567890,ABC Corp,Important client,Lead\n"

    return Response(
        generate(),
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment; filename=template.csv"}
    )


# =============================
# ▶️ RUN
# =============================
if __name__ == "__main__":
    app.run(debug=True)