from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import csv
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key')


# 🔐 Login Required Decorator
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return wrapper


# 📦 DB Connection
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn


# 🛠 Create Tables
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


@app.route('/')
def home():
    return render_template('home.html')


# 🔹 DASHBOARD
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

    all_customers = conn.execute(
        'SELECT id FROM customers ORDER BY id ASC'
    ).fetchall()

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


# 🔹 CUSTOMERS
@app.route('/customers')
@login_required
def customers():
    search = request.args.get('search')
    company = request.args.get('company')
    status = request.args.get('status')
    sort = request.args.get('sort')

    page = request.args.get('page', 1, type=int)
    per_page = 5
    offset = (page - 1) * per_page

    conn = get_db_connection()

    query = "SELECT * FROM customers WHERE 1=1"
    params = []

    if search:
        query += " AND (name LIKE ? OR email LIKE ? OR company LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])

    if company:
        query += " AND company = ?"
        params.append(company)

    if status:
        query += " AND status = ?"
        params.append(status)

    count_query = query.replace("SELECT *", "SELECT COUNT(*)")
    total = conn.execute(count_query, params).fetchone()[0]

    if sort == 'asc':
        query += " ORDER BY name ASC"
    elif sort == 'desc':
        query += " ORDER BY name DESC"

    query += " LIMIT ? OFFSET ?"
    params.extend([per_page, offset])

    customers = conn.execute(query, params).fetchall()

    companies = conn.execute(
        "SELECT DISTINCT company FROM customers"
    ).fetchall()

    conn.close()

    total_pages = (total + per_page - 1) // per_page

    return render_template(
        'customers.html',
        customers=customers,
        companies=companies,
        page=page,
        total_pages=total_pages
    )


# 🔹 ADD CUSTOMER
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


# 🔹 EDIT CUSTOMER
@app.route('/edit_customer/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_customer(id):
    conn = get_db_connection()

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        company = request.form['company']
        notes_text = request.form['notes']
        status = request.form['status']

        conn.execute('''
            UPDATE customers
            SET name=?, email=?, phone=?, company=?, notes=?, status=?
            WHERE id=?
        ''', (name, email, phone, company, notes_text, status, id))

        conn.commit()
        conn.close()

        flash("Customer updated successfully!", "info")
        return redirect(url_for('customers'))

    customer = conn.execute(
        'SELECT * FROM customers WHERE id = ?',
        (id,)
    ).fetchone()

    notes = conn.execute(
        'SELECT * FROM notes WHERE customer_id = ? ORDER BY created_at DESC',
        (id,)
    ).fetchall()

    conn.close()

    return render_template('edit_customer.html', customer=customer, notes=notes)


# 🔹 DELETE CUSTOMER
@app.route('/delete_customer/<int:id>')
@login_required
def delete_customer(id):
    conn = get_db_connection()

    customer = conn.execute(
        'SELECT * FROM customers WHERE id = ?',
        (id,)
    ).fetchone()

    if not customer:
        flash("Customer not found!", "danger")
        return redirect(url_for('customers'))

    conn.execute('DELETE FROM customers WHERE id = ?', (id,))
    conn.commit()
    conn.close()

    flash("Customer deleted successfully!", "warning")
    return redirect(url_for('customers'))


# 🔹 SIGNUP
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            error = "All fields are required"
            return render_template('signup.html', error=error)

        conn = get_db_connection()

        existing_user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if existing_user:
            conn.close()
            error = "Username already exists"
            return render_template('signup.html', error=error)

        hashed_password = generate_password_hash(password)

        conn.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hashed_password)
        )
        conn.commit()
        conn.close()

        flash("Account created successfully! Please login.", "success")
        return redirect(url_for('login'))

    return render_template('signup.html')


# 🔹 LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            error = "All fields are required"
            return render_template('login.html', error=error)

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user'] = username
            return redirect('/dashboard')
        else:
            error = "Invalid username or password"

    return render_template('login.html', error=error)


# 🔹 LOGOUT
@app.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect('/login')


# 🔹 ADD NOTE
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

    flash("Note added successfully!", "success")
    return redirect(url_for('edit_customer', id=customer_id))


# 🔹 EXPORT CSV
@app.route('/export_csv')
@login_required
def export_csv():
    conn = get_db_connection()
    customers = conn.execute("SELECT * FROM customers").fetchall()
    conn.close()

    def generate():
        header = ['Name', 'Email', 'Phone', 'Company', 'Status']
        yield ','.join(header) + '\n'

        for c in customers:
            yield ','.join([
                c['name'],
                c['email'],
                c['phone'],
                c['company'],
                c['status']
            ]) + '\n'

    return Response(generate(), mimetype='text/csv',
                    headers={"Content-Disposition": "attachment;filename=customers.csv"})


if __name__ == "__main__":
    app.run(debug=True)