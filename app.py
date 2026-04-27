from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from flask import flash

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Function to connect DB
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Create table (run once)
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

@app.route('/dashboard')
def dashboard():
    # 🔒 Protect route
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    # 🔹 Total customers
    total_customers = conn.execute(
        'SELECT COUNT(*) FROM customers'
    ).fetchone()[0]

    # 🔹 Total companies
    total_companies = conn.execute(
        'SELECT COUNT(DISTINCT company) FROM customers'
    ).fetchone()[0]

    # 🔹 Status distribution (for pie chart)
    status_data = conn.execute('''
        SELECT status, COUNT(*) as count
        FROM customers
        GROUP BY status
    ''').fetchall()

    status_labels = [row['status'] for row in status_data]
    status_counts = [row['count'] for row in status_data]

    # 🔹 Growth data (simple version based on IDs)
    all_customers = conn.execute(
        'SELECT id FROM customers ORDER BY id ASC'
    ).fetchall()

    growth_labels = list(range(1, len(all_customers) + 1))
    growth_data = growth_labels

    # 🔹 Recent customers
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

@app.route('/customers')
def customers():
    if 'user' not in session:
        return redirect(url_for('login'))

    search = request.args.get('search')
    company = request.args.get('company')
    status = request.args.get('status')   # 👈 HERE
    sort = request.args.get('sort')

    conn = get_db_connection()

    query = "SELECT * FROM customers WHERE 1=1"
    params = []

    if search:
        query += " AND (name LIKE ? OR email LIKE ? OR company LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])

    if company:
        query += " AND company = ?"
        params.append(company)

    if status:   # 👈 HERE
        query += " AND status = ?"
        params.append(status)

    if sort == 'asc':
        query += " ORDER BY name ASC"
    elif sort == 'desc':
        query += " ORDER BY name DESC"

    customers = conn.execute(query, params).fetchall()

    companies = conn.execute(
        "SELECT DISTINCT company FROM customers"
    ).fetchall()

    conn.close()

    return render_template(
        'customers.html',
        customers=customers,
        companies=companies
    )

@app.route('/add_customer', methods=['GET', 'POST'])
def add_customer():
    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        company = request.form['company']
        notes = request.form['notes']
        status = request.form['status']

        conn = get_db_connection()
        conn.execute(
            'INSERT INTO customers (name, email, phone, company, notes, status) VALUES (?, ?, ?, ?, ?, ?)',
            (name, email, phone, company, notes, status)
)
        conn.commit()
        conn.close()

        return redirect(url_for('customers'))

    return render_template('add_customer.html')

@app.route('/edit_customer/<int:id>', methods=['GET', 'POST'])
def edit_customer(id):
    # 🔒 Protect route
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    # 👉 POST: Update customer
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

        return redirect(url_for('customers'))

    # 👉 GET: Load customer data
    customer = conn.execute(
        'SELECT * FROM customers WHERE id = ?',
        (id,)
    ).fetchone()

    # 👉 GET: Load notes for this customer
    notes = conn.execute(
        'SELECT * FROM notes WHERE customer_id = ? ORDER BY created_at DESC',
        (id,)
    ).fetchall()

    conn.close()

    # 👉 Send data to HTML page
    return render_template(
        'edit_customer.html',
        customer=customer,
        notes=notes
    )

@app.route('/delete_customer/<int:id>')
def delete_customer(id):
    # 🔒 Protect route
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    conn.execute('DELETE FROM customers WHERE id = ?', (id,))
    conn.commit()
    conn.close()

    return redirect(url_for('customers'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # ✅ PUT IT HERE
        if not username or not password:
            flash("All fields are required", "danger")
            return redirect(url_for('signup'))

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        conn.execute(
            'INSERT INTO users (username, password) VALUES (?, ?)',
            (username, hashed_password)
        )
        conn.commit()
        conn.close()

        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # 🔒 Validation
        if not username or not password:
            flash("Username and password are required", "danger")
            return redirect(url_for('login'))

        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ?',
            (username,)
        ).fetchone()
        conn.close()

        # 🔐 Check password
        if user and check_password_hash(user['password'], password):
            session['user'] = username   # ✅ STORE SESSION
            return redirect(url_for('dashboard'))
        else:
            return "Invalid credentials"

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))


@app.route('/add_note/<int:customer_id>', methods=['POST'])
def add_note(customer_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    content = request.form['content']

    conn = get_db_connection()
    conn.execute(
        'INSERT INTO notes (customer_id, content) VALUES (?, ?)',
        (customer_id, content)
    )
    conn.commit()
    conn.close()

    return redirect(url_for('edit_customer', id=customer_id))


if __name__ == "__main__":
    app.run()