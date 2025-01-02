from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'

DB_FILE = 'project.db'

# Utility function to connect to the database
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# @app.route('/')
# def index():
#     return render_template('index.html')

@app.route('/', methods=['GET', 'POST'])
def index():
    search_results = []
    query = ''
    search_type = ''
    if request.method == 'POST':
        search_type = request.form.get('search_type')
        query = request.form.get('query')
        
        conn = get_db_connection()
        
        if search_type == 'product':
            search_results = conn.execute("""
                SELECT * FROM PRODUCT 
                WHERE name LIKE ? OR product_category LIKE ? 
                LIMIT 50
            """, ('%' + query + '%', '%' + query + '%')).fetchall()
        
        elif search_type == 'skin_concern':
            search_results = conn.execute("""
                SELECT s.name AS skin_concern_name, p.name AS product_name, p.product_id
                FROM SKIN_CONCERN s
                JOIN PRODUCT_TO_SKIN_CONCERN ps ON ps.skin_concern_id = s.skin_concern_id
                JOIN PRODUCT p ON ps.product_id = p.product_id
                WHERE s.name LIKE ?
            """, ('%' + query + '%',)).fetchall()
        
        elif search_type == 'ingredient':
            search_results = conn.execute("""
                SELECT i.name AS ingredient_name, p.name AS product_name, p.product_id
                FROM INGREDIENT i
                JOIN PRODUCT_INGREDIENT pi ON pi.ingredient_id = i.ingredient_id
                JOIN PRODUCT p ON pi.product_id = p.product_id
                WHERE i.name LIKE ?
            """, ('%' + query + '%',)).fetchall()

        conn.close()

    return render_template('index.html', search_results=search_results)

# Search route to handle different search types
@app.route('/search', methods=['POST'])
def search():
    query = request.form['query']
    search_type = request.form['search_type']

    conn = get_db_connection()
    
    # Search based on the type selected
    if search_type == 'product':
        # Search for products by name or brand
        results = conn.execute("SELECT * FROM PRODUCT WHERE name LIKE ? OR brand LIKE ?", ('%' + query + '%', '%' + query + '%')).fetchall()
    
    elif search_type == 'skin_concern':
        # Search for products related to a skin concern (using the relationship table PRODUCT_TO_SKIN_CONCERN)
        results = conn.execute("""
            SELECT p.* FROM PRODUCT p
            JOIN PRODUCT_TO_SKIN_CONCERN ps ON p.product_id = ps.product_id
            JOIN SKIN_CONCERN s ON ps.skin_concern_id = s.skin_concern_id
            WHERE s.name LIKE ?
        """, ('%' + query + '%',)).fetchall()

    elif search_type == 'ingredient':
        # Search for products containing a specific ingredient (using the relationship table PRODUCT_INGREDIENT)
        results = conn.execute("""
            SELECT p.* FROM PRODUCT p
            JOIN PRODUCT_INGREDIENT pi ON p.product_id = pi.product_id
            JOIN INGREDIENT i ON pi.ingredient_id = i.ingredient_id
            WHERE i.name LIKE ?
        """, ('%' + query + '%',)).fetchall()

    conn.close()
    
    return render_template('search_results.html', results=results, search_type=search_type, query=query)


# @app.route('/search', methods=['POST'])
# def search():
#     query = request.form['query']
#     conn = get_db_connection()
#     products = conn.execute("SELECT * FROM PRODUCT WHERE name LIKE ?", ('%' + query + '%',)).fetchall()
#     conn.close()
#     return render_template('index.html', products=products)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM USER WHERE email = ?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['user_id']
            session['user_name'] = user['name']
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'error')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO USER (name, email, password) VALUES (?, ?, ?)", (name, email, password))
            conn.commit()
        except sqlite3.IntegrityError:
            flash('Email already exists', 'error')
        conn.close()
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/product/<int:product_id>')
def product_details(product_id):
    conn = get_db_connection()
    
    # Fetch product details
    product = conn.execute("SELECT * FROM PRODUCT WHERE product_id = ?", (product_id,)).fetchone()
    
    # Fetch ingredients related to the product
    ingredients = conn.execute("SELECT * FROM pi_view WHERE product_id = ?", (product_id,)).fetchall()
    
    # Fetch skin concerns related to the product
    skin_concerns = conn.execute("SELECT * FROM ps_view WHERE product_id = ?", (product_id,)).fetchall()
    
    # Fetch reviews with user names
    reviews = conn.execute("""
        SELECT r.text, r.rating, r.date, u.name 
        FROM REVIEW r 
        JOIN USER u ON r.user_id = u.user_id 
        WHERE r.product_id = ?
    """, (product_id,)).fetchall()
    
    conn.close()
    
    # Pass all data to the template
    return render_template(
        'product_details.html', 
        product=product, 
        ingredients=ingredients, 
        skin_concerns=skin_concerns, 
        reviews=reviews
    )


@app.route('/product/<int:product_id>/review', methods=['GET', 'POST'])
def submit_review(product_id):
    # Check if the user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Get the review details from the form
        text = request.form['text']
        rating = request.form['rating']
        
        # Database connection
        conn = get_db_connection()
        cursor = conn.cursor()

        # Step 1: Generate a unique review_id
        cursor.execute("SELECT MAX(review_id) FROM REVIEW")
        max_review_id = cursor.fetchone()[0]
        new_review_id = max_review_id + 1 if max_review_id is not None else 1

        # Step 2: Insert the review into the database
        cursor.execute("""
            INSERT INTO REVIEW (review_id, user_id, product_id, text, rating, date)
            VALUES (?, ?, ?, ?, ?, DATE('now'))
        """, (new_review_id, session['user_id'], product_id, text, rating))

        # Commit changes and close connection
        conn.commit()
        conn.close()

        # Redirect to the product details page after submission
        return redirect(url_for('product_details', product_id=product_id))

    # If it's a GET request, show the review submission form
    conn = get_db_connection()
    product = conn.execute("SELECT name FROM PRODUCT WHERE product_id = ?", (product_id,)).fetchone()

    # Fetch reviews with user name
    reviews = conn.execute("""
        SELECT r.text, r.rating, r.date, u.name AS user_name 
        FROM REVIEW r
        JOIN USER u ON r.user_id = u.user_id
        WHERE r.product_id = ?
        """, (product_id,)).fetchall()

    conn.close()

    # Render the review submission form and display the reviews
    return render_template('review_submission.html', product_name=product['name'], product_id=product_id, reviews=reviews)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
