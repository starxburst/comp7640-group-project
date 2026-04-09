from flask import Blueprint, render_template, request, redirect, url_for, flash
from db import get_connection

customer_bp = Blueprint("customer", __name__)

PER_PAGE = 20


@customer_bp.route("/customers")
def list_customers():
    page = max(request.args.get("page", default=1, type=int), 1)
    query = request.args.get("q", default="", type=str).strip()
    offset = (page - 1) * PER_PAGE

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if query:
                like = f"%{query}%"
                cur.execute(
                    "SELECT COUNT(*) AS total FROM Customer "
                    "WHERE name LIKE %s OR contact_number LIKE %s OR shipping_address LIKE %s",
                    (like, like, like),
                )
                total = cur.fetchone()["total"]
                cur.execute(
                    "SELECT * FROM Customer "
                    "WHERE name LIKE %s OR contact_number LIKE %s OR shipping_address LIKE %s "
                    "ORDER BY customer_id LIMIT %s OFFSET %s",
                    (like, like, like, PER_PAGE, offset),
                )
            else:
                cur.execute("SELECT COUNT(*) AS total FROM Customer")
                total = cur.fetchone()["total"]
                cur.execute(
                    "SELECT * FROM Customer ORDER BY customer_id LIMIT %s OFFSET %s",
                    (PER_PAGE, offset),
                )
            customers = cur.fetchall()
    finally:
        conn.close()
    total_pages = max((total + PER_PAGE - 1) // PER_PAGE, 1)
    return render_template(
        "customers/index.html",
        customers=customers,
        page=page,
        per_page=PER_PAGE,
        total=total,
        total_pages=total_pages,
        query=query,
    )


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
