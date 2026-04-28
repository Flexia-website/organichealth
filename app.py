# app.py
import os
import uuid
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash

# Configuration
app = Flask(__name__)

# Use environment variable for secret key in production
app.secret_key = os.environ.get('SECRET_KEY', 'organic_health_secret_key_2025')

# File upload configuration
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Admin credentials - Use environment variables in production
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD_HASH = generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'organic123'))

# Database setup
DATABASE = 'products.db'

def get_db():
    """Return database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with products table and default products"""
    with get_db() as conn:
        # Create products table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                description TEXT NOT NULL,
                image_filename TEXT
            )
        ''')
        
        # Check if products table is empty and seed with initial products
        cursor = conn.execute('SELECT COUNT(*) as count FROM products')
        count = cursor.fetchone()['count']
        
        if count == 0:
            # Seed initial products from Mrs A's information
            initial_products = [
                ('Water Filter', 8000, 'High-performance water filter removes sediment, chlorine, and impurities. Improves taste and clarity of your drinking water. Great for organic health living.', None),
                ('Alkaline Salt', 5000, 'Natural alkaline mineral salt that raises water pH level, provides antioxidant properties, and balances body acidity. Essential for alkaline diet.', None),
                ('Complete Alkaline Water Bucket System', 35000, 'Complete water filtration system including bucket, water filter, and alkaline salt. Produces clean, mineral-rich alkaline water for the whole family. Easy to use and maintain.', None)
            ]
            conn.executemany(
                'INSERT INTO products (name, price, description, image_filename) VALUES (?, ?, ?, ?)',
                initial_products
            )
        conn.commit()

def login_required(f):
    """Decorator to protect admin routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Please log in to access admin area.', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Routes
@app.route('/')
def index():
    """Homepage - display all products"""
    with get_db() as conn:
        products = conn.execute('SELECT * FROM products ORDER BY id').fetchall()
    return render_template('index.html', products=products)

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
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
    """Logout admin"""
    session.pop('admin_logged_in', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin_dashboard():
    """Admin dashboard - show products and add form"""
    with get_db() as conn:
        products = conn.execute('SELECT * FROM products ORDER BY id').fetchall()
    return render_template('admin.html', products=products)

@app.route('/admin/add', methods=['POST'])
@login_required
def add_product():
    """Add new product with image upload"""
    name = request.form.get('name', '').strip()
    price = request.form.get('price', '').strip()
    description = request.form.get('description', '').strip()
    image = request.files.get('image')
    
    # Validation
    if not name:
        flash('Product name is required.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    if not price or not price.isdigit():
        flash('Valid price (numbers only) is required.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    if not description:
        flash('Product description/function is required.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    price = int(price)
    image_filename = None
    
    # Handle image upload
    if image and allowed_file(image.filename):
        # Generate unique filename to avoid conflicts
        ext = image.filename.rsplit('.', 1)[1].lower()
        unique_name = f"{uuid.uuid4().hex}.{ext}"
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
        image.save(image_path)
        image_filename = unique_name
        flash('Product added with image!', 'success')
    else:
        if image and image.filename:
            flash('Invalid image format. Use PNG, JPG, JPEG, GIF, or WEBP.', 'warning')
        else:
            flash('Product added (no image provided).', 'info')
    
    # Insert into database
    with get_db() as conn:
        conn.execute(
            'INSERT INTO products (name, price, description, image_filename) VALUES (?, ?, ?, ?)',
            (name, price, description, image_filename)
        )
        conn.commit()
    
    flash(f'Product "{name}" added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    """Delete product and its associated image file"""
    with get_db() as conn:
        # Get product image before deletion
        product = conn.execute('SELECT image_filename FROM products WHERE id = ?', (product_id,)).fetchone()
        
        if product and product['image_filename']:
            # Delete image file if exists
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], product['image_filename'])
            if os.path.exists(image_path):
                os.remove(image_path)
        
        # Delete product from database
        conn.execute('DELETE FROM products WHERE id = ?', (product_id,))
        conn.commit()
    
    flash('Product deleted successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

# Initialize database on startup
with app.app_context():
    init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)