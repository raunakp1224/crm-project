from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3

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
            notes TEXT
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT
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
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    total_customers = conn.execute('SELECT COUNT(*) FROM customers').fetchone()[0]

    total_companies = conn.execute(
        'SELECT COUNT(DISTINCT company) FROM customers'
    ).fetchone()[0]

    recent_customers = conn.execute(
        'SELECT * FROM customers ORDER BY id DESC LIMIT 5'
    ).fetchall()

    conn.close()

    return render_template(
        'dashboard.html',
        total_customers=total_customers,
        total_companies=total_companies,
        recent_customers=recent_customers
    )

@app.route('/customers')
def customers():
    search = request.args.get('search')

    conn = get_db_connection()

    if search:
        customers = conn.execute(
            '''SELECT * FROM customers
               WHERE name LIKE ? OR email LIKE ? OR company LIKE ?''',
            (f'%{search}%', f'%{search}%', f'%{search}%')
        ).fetchall()
    else:
        customers = conn.execute('SELECT * FROM customers').fetchall()

    conn.close()

    return render_template('customers.html', customers=customers)

@app.route('/add_customer', methods=['GET', 'POST'])
def add_customer():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        company = request.form['company']
        notes = request.form['notes']

        conn = get_db_connection()
        conn.execute(
            'INSERT INTO customers (name, email, phone, company, notes) VALUES (?, ?, ?, ?, ?)',
            (name, email, phone, company, notes)
        )
        conn.commit()
        conn.close()

        return redirect(url_for('customers'))

    return render_template('add_customer.html')

@app.route('/edit_customer/<int:id>', methods=['GET', 'POST'])
def edit_customer(id):
    conn = get_db_connection()

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        company = request.form['company']
        notes = request.form['notes']

        conn.execute('''
            UPDATE customers
            SET name = ?, email = ?, phone = ?, company = ?, notes = ?
            WHERE id = ?
        ''', (name, email, phone, company, notes, id))

        conn.commit()
        conn.close()

        return redirect(url_for('customers'))

    customer = conn.execute('SELECT * FROM customers WHERE id = ?', (id,)).fetchone()
    conn.close()

    return render_template('edit_customer.html', customer=customer)

@app.route('/delete_customer/<int:id>')
def delete_customer(id):
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

        conn = get_db_connection()
        conn.execute(
            'INSERT INTO users (username, password) VALUES (?, ?)',
            (username, password)
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

        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ? AND password = ?',
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            session['user'] = user['username']
            return redirect(url_for('dashboard'))
        else:
            return "Invalid credentials"

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))



if __name__ == '__main__':
    app.run(debug=True)