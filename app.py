import os
import uuid
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'organic_health_secret_key_2025')

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD_HASH = generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'organic123'))

DATABASE = 'products.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                description TEXT NOT NULL,
                image_filename TEXT
            )
        ''')
        cursor = conn.execute('SELECT COUNT(*) as count FROM products')
        count = cursor.fetchone()['count']
        if count == 0:
            initial_products = [
                ('Water Filter', 8000, 'High-performance water filter removes sediment, chlorine, and impurities. Improves taste and clarity of your drinking water. Great for organic health living.', None),
                ('Alkaline Salt', 5000, 'Natural alkaline mineral salt that raises water pH level, provides antioxidant properties, and balances body acidity. Essential for alkaline diet.', None),
                ('Complete Alkaline Water Bucket System', 35000, 'Complete water filtration system including bucket, water filter, and alkaline salt. Produces clean, mineral-rich alkaline water for the whole family. Easy to use and maintain.', None)
            ]
            conn.executemany('INSERT INTO products (name, price, description, image_filename) VALUES (?, ?, ?, ?)', initial_products)
        conn.commit()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Please log in to access admin area.', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    with get_db() as conn:
        products = conn.execute('SELECT * FROM products ORDER BY id').fetchall()
    return render_template('index.html', products=products)

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['admin_logged_in'] = True
            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('admin_login.html')

@app.route('/admin-logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin_dashboard():
    with get_db() as conn:
        products = conn.execute('SELECT * FROM products ORDER BY id').fetchall()
    return render_template('admin.html', products=products)

@app.route('/admin/add', methods=['POST'])
@login_required
def add_product():
    name = request.form.get('name', '').strip()
    price = request.form.get('price', '').strip()
    description = request.form.get('description', '').strip()
    image = request.files.get('image')
    
    if not name or not price.isdigit() or not description:
        flash('All fields required and price must be a number.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    price = int(price)
    image_filename = None
    if image and allowed_file(image.filename):
        ext = image.filename.rsplit('.', 1)[1].lower()
        unique_name = f"{uuid.uuid4().hex}.{ext}"
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
        image_filename = unique_name
    
    with get_db() as conn:
        conn.execute('INSERT INTO products (name, price, description, image_filename) VALUES (?, ?, ?, ?)',
                     (name, price, description, image_filename))
        conn.commit()
    flash(f'Product "{name}" added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    with get_db() as conn:
        product = conn.execute('SELECT image_filename FROM products WHERE id = ?', (product_id,)).fetchone()
        if product and product['image_filename']:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], product['image_filename'])
            if os.path.exists(image_path):
                os.remove(image_path)
        conn.execute('DELETE FROM products WHERE id = ?', (product_id,))
        conn.commit()
    flash('Product deleted successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

with app.app_context():
    init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
