from flask import Flask, render_template, request, jsonify
import sqlite3
import os
import numpy as np
from sklearn.linear_model import LinearRegression

app = Flask(__name__)
DATABASE = "retail.db"
print("app is starting")


# -----------------------------
# DATABASE SETUP
# -----------------------------
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Product table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            base_price REAL NOT NULL,
            stock INTEGER NOT NULL,
            last_7_days_sales TEXT NOT NULL
        )
    """)

    # Add sample data only if table is empty
    cursor.execute("SELECT COUNT(*) FROM products")
    count = cursor.fetchone()[0]

    if count == 0:
        sample_products = [
            ("Rice Bag", "Groceries", 1200, 50, "12,14,11,15,17,13,16"),
            ("Milk Pack", "Dairy", 30, 100, "40,42,39,45,50,48,52"),
            ("Bread", "Bakery", 40, 80, "20,22,25,23,26,28,30"),
            ("Egg Tray", "Poultry", 180, 60, "10,12,14,13,15,16,18"),
            ("Oil Bottle", "Groceries", 160, 35, "7,8,9,10,11,9,12")
        ]

        cursor.executemany("""
            INSERT INTO products (name, category, base_price, stock, last_7_days_sales)
            VALUES (?, ?, ?, ?, ?)
        """, sample_products)

    conn.commit()
    conn.close()


# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def predict_demand(sales_str):
    """
    Predict next-day demand using simple Linear Regression
    based on last 7 days sales.
    """
    sales = list(map(int, sales_str.split(",")))

    # X = day numbers, y = sales
    X = np.array(range(1, len(sales) + 1)).reshape(-1, 1)
    y = np.array(sales)

    model = LinearRegression()
    model.fit(X, y)

    next_day = np.array([[len(sales) + 1]])
    predicted = model.predict(next_day)[0]

    # prevent negative values
    return max(0, round(predicted))


def dynamic_price(base_price, predicted_demand, current_stock):
    """
    Simple dynamic pricing logic:
    - If demand is high and stock is low -> increase price
    - If demand is low and stock is high -> decrease price
    - Otherwise normal slight adjustment
    """
    if current_stock == 0:
        return round(base_price * 1.20, 2)

    demand_stock_ratio = predicted_demand / current_stock

    if demand_stock_ratio > 0.8:
        # high demand, low stock
        new_price = base_price * 1.15
    elif demand_stock_ratio > 0.5:
        # moderate demand
        new_price = base_price * 1.08
    elif demand_stock_ratio < 0.3:
        # low demand, high stock
        new_price = base_price * 0.90
    else:
        # stable condition
        new_price = base_price * 1.00

    return round(new_price, 2)


def suggest_inventory(predicted_demand, current_stock):
    """
    Inventory recommendation logic:
    - Keep extra buffer stock of 20%
    """
    recommended_stock = int(predicted_demand * 1.2)

    if current_stock < recommended_stock:
        reorder_qty = recommended_stock - current_stock
        status = "Reorder Needed"
    else:
        reorder_qty = 0
        status = "Stock Sufficient"

    return recommended_stock, reorder_qty, status


# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def home():
    conn = get_db_connection()
    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()

    product_list = []
    for product in products:
        predicted = predict_demand(product["last_7_days_sales"])
        new_price = dynamic_price(product["base_price"], predicted, product["stock"])
        recommended_stock, reorder_qty, status = suggest_inventory(predicted, product["stock"])

        product_list.append({
            "id": product["id"],
            "name": product["name"],
            "category": product["category"],
            "base_price": product["base_price"],
            "stock": product["stock"],
            "sales_history": product["last_7_days_sales"],
            "predicted_demand": predicted,
            "suggested_price": new_price,
            "recommended_stock": recommended_stock,
            "reorder_qty": reorder_qty,
            "status": status
        })

    return render_template("index.html", products=product_list)


@app.route("/add_product", methods=["POST"])
def add_product():
    name = request.form.get("name")
    category = request.form.get("category")
    base_price = request.form.get("base_price")
    stock = request.form.get("stock")
    sales_history = request.form.get("sales_history")

    if not all([name, category, base_price, stock, sales_history]):
        return "Missing data", 400

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO products (name, category, base_price, stock, last_7_days_sales)
        VALUES (?, ?, ?, ?, ?)
    """, (name, category, float(base_price), int(stock), sales_history))
    conn.commit()
    conn.close()

    return jsonify({"message": "Product added successfully"})


@app.route("/delete_product/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": "Product deleted successfully"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)