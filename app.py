from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from waitress import serve
import os
import json
from functools import wraps

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Flask-Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.getenv("EMAIL_USER")
app.config['MAIL_PASSWORD'] = os.getenv("EMAIL_PASS")
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("EMAIL_USER")

mail = Mail(app)

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "adminpass")

def load_menu():
    with open('menu.json', 'r') as f:
        return json.load(f)

def save_menu(menu):
    with open('menu.json', 'w') as f:
        json.dump(menu, f, indent=4)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def before_request():
    if (
        "user" not in session
        and not request.path.startswith("/admin")
        and request.endpoint not in ["login", "signup", "static"]
    ):
        return redirect(url_for("login"))

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form["password"]
        if password == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid admin password")
    return render_template("admin_login.html")

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html")

@app.route("/admin/manage_menu", methods=["GET", "POST"])
@admin_required
def manage_menu():
    menu = load_menu()

    if request.method == 'POST':
        if "update_item" in request.form:
            name = request.form['item_name']
            new_price = float(request.form['new_price'])
            if name in menu:
                menu[name]['price'] = new_price
                flash(f"Updated price for {name}.")
        elif "remove_item" in request.form:
            name = request.form['item_name']
            if name in menu:
                del menu[name]
                flash(f"Removed item {name}.")
        else:
            name = request.form['name']
            price = float(request.form['price'])
            category = request.form['category']
            menu[name] = {
                'price': price,
                'available': True,
                'available_quantity': 10,
                'category': category
            }
            flash(f"Added item {name}.")

        save_menu(menu)
        return redirect(url_for('manage_menu'))

    return render_template('manage_menu.html', menu=menu)

@app.route('/admin/change_price', methods=['POST'])
@admin_required
def change_price():
    item_name = request.form.get('item_name')
    new_price = request.form.get('new_price')

    if not item_name or not new_price:
        flash("Missing item name or price.")
        return redirect(url_for('manage_menu'))

    try:
        new_price = float(new_price)
        if new_price <= 0:
            raise ValueError
    except ValueError:
        flash("Invalid price entered.")
        return redirect(url_for('manage_menu'))

    menu = load_menu()
    if item_name in menu:
        menu[item_name]['price'] = new_price
        save_menu(menu)
        flash("Price updated successfully.")
    else:
        flash("Item not found.")

    return redirect(url_for('manage_menu'))

@app.route("/admin/availability", methods=["GET", "POST"])
@admin_required
def menu_availability():
    menu = load_menu()
    categories = [
        "Rice Meal", "Pasta (3-4 pax)", "Pancit (3-4 pax)",
        "Burger (B1 T1)", "Fries", "Milk Tea", "Fruit Soda", "Frappe"
    ]

    if request.method == 'POST':
        for item, item_data in menu.items():
            qty = request.form.get(f"quantities[{item}]")
            if qty is not None:
                qty = int(qty)
                item_data['available_quantity'] = qty
                item_data['available'] = qty > 0
        save_menu(menu)
        flash("Menu availability updated.")
        return redirect(url_for('menu_availability'))

    return render_template("menu_availability.html", menu=menu, categories=categories)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    flash("Admin logged out.")
    return redirect(url_for("admin_login"))

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        phone = request.form["phone"]
        hashed_password = generate_password_hash(password)

        # Save user to file
        with open("users.txt", "a") as file:
            file.write(f"{username},{hashed_password},{phone}\n")

        # Send email to store owner
        msg = Message("New User Signup", recipients=["tristanorias118@gmail.com"])
        msg.body = f"""A new user has signed up:

Username: {username}
Phone Number: {phone}
"""
        try:
            mail.send(msg)
        except Exception as e:
            flash(f"User created but failed to send email: {e}")

        flash("Account created successfully. You can now log in.")
        return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        with open("users.txt", "r") as file:
            for line in file:
                if not line.strip():
                    continue
                try:
                    stored_user, stored_hash, stored_phone = line.strip().split(",")
                except ValueError:
                    continue
                if stored_user == username and check_password_hash(stored_hash, password):
                    session["user"] = username
                    session["phone"] = stored_phone
                    flash("Login successful!")
                    return redirect(url_for("order_page"))
        flash("Invalid username or password")
    return render_template("login.html")  

@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("phone", None)
    flash("Logged out successfully.")
    return redirect(url_for("login"))

@app.route('/order', methods=['GET', 'POST'])
@login_required
def order_page():
    menu = load_menu()
    categorized_menu = {}
    for item_name, item_data in menu.items():
        if item_data.get("available"):
            category = item_data.get("category", "Other")
            categorized_menu.setdefault(category, []).append({
                "name": item_name,
                "price": item_data["price"],
                "available_quantity": item_data.get("available_quantity", 0)
            })

    return render_template("order.html", categorized_menu=categorized_menu)

@app.route("/add_to_cart", methods=["POST"])
@login_required
def add_to_cart():
    item = request.form.get("item")
    quantity = int(request.form.get("quantity", 1))
    menu = load_menu()

    item_data = menu.get(item)
    if not item_data:
        flash("Item not found.")
        return redirect(url_for("order_page"))

    available_qty = item_data.get("available_quantity", 0)
    if quantity > available_qty:
        flash(f"Only {available_qty} of {item} available.")
        return redirect(url_for("order_page"))

    if "cart" not in session:
        session["cart"] = []

    price = item_data.get("price", 0) * quantity
    session["cart"].append({"item": item, "quantity": quantity, "price": price})
    session.modified = True
    return redirect(url_for("cart"))

@app.route("/cart")
@login_required
def cart():
    cart_items = session.get("cart", [])
    total_price = sum(item["price"] for item in cart_items)
    return render_template("cart.html", cart=cart_items, total=total_price)

@app.route("/checkout", methods=["POST"])
@login_required
def checkout():
    cart_items = session.get("cart", [])
    if not cart_items:
        return "Your cart is empty."

    total_price = sum(item["price"] for item in cart_items)
    order_details = "\n".join([f"{item['quantity']}x {item['item']} - \u20b1{item['price']}" for item in cart_items])

    payment_mode = request.form.get("payment_mode")
    delivery_mode = request.form.get("delivery_mode")

    if delivery_mode == "Deliver":
        total_price += 10

    msg = Message("Order Confirmation", recipients=["tristanorias118@gmail.com"])
    msg.body = f"""Customer Order!

Order Details:
{order_details}

Total: \u20b1{total_price}
Payment Mode: {payment_mode}
Delivery Mode: {delivery_mode}

We appreciate your business!
"""

    try:
        mail.send(msg)
        session.pop("user", None)
        session.pop("phone", None)
        session["cart"] = []
        return render_template(
            "order_confirmation.html",
            order_details=order_details,
            total_price=total_price,
            payment_mode=payment_mode,
            delivery_mode=delivery_mode
        )
    except Exception as e:
        return f"Error sending email: {str(e)}"

if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5000)