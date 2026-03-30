from flask import Blueprint, render_template, request, redirect, url_for, flash
from db import get_connection

customer_bp = Blueprint("customer", __name__)


@customer_bp.route("/customers")
def list_customers():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM Customer ORDER BY customer_id")
            customers = cur.fetchall()
    finally:
        conn.close()
    return render_template("customers/index.html", customers=customers)


@customer_bp.route("/customers/add", methods=["GET", "POST"])
def add_customer():
    if request.method == "POST":
        name = request.form["name"].strip()
        contact = request.form["contact_number"].strip()
        address = request.form["shipping_address"].strip()
        if not name:
            flash("Name is required.", "danger")
            return redirect(url_for("customer.add_customer"))
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO Customer (name, contact_number, shipping_address) VALUES (%s, %s, %s)",
                    (name, contact or None, address or None),
                )
            conn.commit()
            flash(f"Customer '{name}' added successfully.", "success")
        finally:
            conn.close()
        return redirect(url_for("customer.list_customers"))
    return render_template("customers/add.html")
