from flask import Blueprint, render_template, request, redirect, url_for, flash
from db import get_connection

product_bp = Blueprint("product", __name__)

PER_PAGE = 20


@product_bp.route("/products")
def browse():
    page = max(request.args.get("page", default=1, type=int), 1)
    vendor_id = request.args.get("vendor_id", type=int)
    offset = (page - 1) * PER_PAGE
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM Vendor ORDER BY business_name")
            vendors = cur.fetchall()
            if vendor_id:
                cur.execute(
                    "SELECT COUNT(*) AS total FROM Product WHERE vendor_id = %s",
                    (vendor_id,),
                )
                total = cur.fetchone()["total"]
                cur.execute(
                    "SELECT p.*, v.business_name FROM Product p "
                    "JOIN Vendor v ON p.vendor_id = v.vendor_id "
                    "WHERE p.vendor_id = %s ORDER BY p.name LIMIT %s OFFSET %s",
                    (vendor_id, PER_PAGE, offset),
                )
            else:
                cur.execute("SELECT COUNT(*) AS total FROM Product")
                total = cur.fetchone()["total"]
                cur.execute(
                    "SELECT p.*, v.business_name FROM Product p "
                    "JOIN Vendor v ON p.vendor_id = v.vendor_id "
                    "ORDER BY v.business_name, p.name LIMIT %s OFFSET %s",
                    (PER_PAGE, offset),
                )
            products = cur.fetchall()
    finally:
        conn.close()
    total_pages = max((total + PER_PAGE - 1) // PER_PAGE, 1)
    return render_template(
        "products/index.html",
        products=products,
        vendors=vendors,
        selected_vendor=vendor_id,
        page=page,
        per_page=PER_PAGE,
        total=total,
        total_pages=total_pages,
    )


@product_bp.route("/products/search")
def search():
    page = max(request.args.get("page", default=1, type=int), 1)
    query = request.args.get("q", "").strip()
    offset = (page - 1) * PER_PAGE
    results = []
    total = 0
    if query:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                like = f"%{query}%"
                cur.execute(
                    "SELECT COUNT(*) AS total FROM Product p "
                    "WHERE p.name LIKE %s OR p.tag1 LIKE %s "
                    "   OR p.tag2 LIKE %s OR p.tag3 LIKE %s",
                    (like, like, like, like),
                )
                total = cur.fetchone()["total"]
                cur.execute(
                    "SELECT p.*, v.business_name FROM Product p "
                    "JOIN Vendor v ON p.vendor_id = v.vendor_id "
                    "WHERE p.name LIKE %s OR p.tag1 LIKE %s "
                    "   OR p.tag2 LIKE %s OR p.tag3 LIKE %s "
                    "ORDER BY p.name LIMIT %s OFFSET %s",
                    (like, like, like, like, PER_PAGE, offset),
                )
                results = cur.fetchall()
        finally:
            conn.close()
    total_pages = max((total + PER_PAGE - 1) // PER_PAGE, 1)
    return render_template(
        "products/search.html",
        results=results,
        query=query,
        page=page,
        per_page=PER_PAGE,
        total=total,
        total_pages=total_pages,
    )


@product_bp.route("/products/add", methods=["GET", "POST"])
def add_product():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT vendor_id, business_name FROM Vendor ORDER BY business_name")
            vendors = cur.fetchall()
    finally:
        conn.close()

    if request.method == "POST":
        vendor_id = request.form.get("vendor_id", type=int)
        name = request.form["name"].strip()
        price = request.form.get("price", type=float)
        stock_qty = request.form.get("stock_qty", type=int)
        tag1 = request.form["tag1"].strip() or None
        tag2 = request.form["tag2"].strip() or None
        tag3 = request.form["tag3"].strip() or None

        if not vendor_id or not name or price is None or stock_qty is None:
            flash("Vendor, name, price and stock quantity are required.", "danger")
            return render_template("products/add.html", vendors=vendors)

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO Product (vendor_id, name, price, stock_qty, tag1, tag2, tag3) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (vendor_id, name, price, stock_qty, tag1, tag2, tag3),
                )
            conn.commit()
            flash(f"Product '{name}' added successfully.", "success")
        finally:
            conn.close()
        return redirect(url_for("product.browse", vendor_id=vendor_id))

    return render_template("products/add.html", vendors=vendors)
