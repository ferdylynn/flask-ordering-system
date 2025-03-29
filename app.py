from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mail import Mail, Message
from waitress import serve
import os  # For environment variables

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Flask-Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.getenv("EMAIL_USER")  # Use environment variable
app.config['MAIL_PASSWORD'] = os.getenv("EMAIL_PASS")  # Use environment variable
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("EMAIL_USER")

# Initialize Flask-Mail
mail = Mail(app)

# Prices
flavor_prices = {
    "Hotsilog": 50, "Hamsilog": 55, "Tocilog": 55, "Shanghai silog": 65, "Tapsilog": 85, "Bangsilog": 85
}

# Categories
subcategories = {
    "Rice Meal & Ulam": ["Hotsilog", "Hamsilog", "Tocilog"],
    "Pasta": ["Spaghetti", "Carbonara"],
    "Drinks": ["Okinawa", "Winter Melon"]
}

@app.route("/")
def home():
    return render_template("index.html", categories=subcategories)

@app.route("/order/<category>")
def order(category):
    return render_template("order.html", category=category, items=subcategories[category])

@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    item = request.form.get("item")
    quantity = int(request.form.get("quantity", 1))
    
    if "cart" not in session:
        session["cart"] = []
    
    price = flavor_prices.get(item, 0) * quantity
    session["cart"].append({"item": item, "quantity": quantity, "price": price})
    session.modified = True  # Update session
    
    return redirect(url_for("cart"))

@app.route("/cart")
def cart():
    cart_items = session.get("cart", [])
    total_price = sum(item["price"] for item in cart_items)
    return render_template("cart.html", cart=cart_items, total=total_price)

@app.route("/checkout")
def checkout():
    cart_items = session.get("cart", [])
    if not cart_items:
        return "Your cart is empty."

    total_price = sum(item["price"] for item in cart_items)
    order_details = "\n".join([f"{item['quantity']}x {item['item']} - ₱{item['price']}" for item in cart_items])

    # Email message
    msg = Message("Order Confirmation", recipients=["tristanorias118@gmail.com"])
    msg.body = f"Thank you for your order!\n\nYour Order Details:\n{order_details}\n\nTotal: ₱{total_price}"

    try:
        mail.send(msg)
        session["cart"] = []  # Clear the cart after checkout
        return "Order Confirmed! Email sent."
    except Exception as e:
        return f"Error sending email: {str(e)}"

if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5000)
