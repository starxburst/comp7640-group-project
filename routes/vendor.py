from flask import Blueprint, render_template, request, redirect, url_for, flash
from db import get_connection

vendor_bp = Blueprint("vendor", __name__)

PER_PAGE = 20


@vendor_bp.route("/vendors")
def list_vendors():
    page = max(request.args.get("page", default=1, type=int), 1)
    query = request.args.get("q", default="", type=str).strip()
    offset = (page - 1) * PER_PAGE

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if query:
                like = f"%{query}%"
                cur.execute(
                    "SELECT COUNT(*) AS total FROM Vendor "
                    "WHERE business_name LIKE %s OR location LIKE %s",
                    (like, like),
                )
                total = cur.fetchone()["total"]
                cur.execute(
                    "SELECT * FROM Vendor "
                    "WHERE business_name LIKE %s OR location LIKE %s "
                    "ORDER BY vendor_id LIMIT %s OFFSET %s",
                    (like, like, PER_PAGE, offset),
                )
            else:
                cur.execute("SELECT COUNT(*) AS total FROM Vendor")
                total = cur.fetchone()["total"]
                cur.execute(
                    "SELECT * FROM Vendor ORDER BY vendor_id LIMIT %s OFFSET %s",
                    (PER_PAGE, offset),
                )
            vendors = cur.fetchall()
    finally:
        conn.close()

    total_pages = max((total + PER_PAGE - 1) // PER_PAGE, 1)
    return render_template(
        "vendors/index.html",
        vendors=vendors,
        page=page,
        per_page=PER_PAGE,
        total=total,
        total_pages=total_pages,
        query=query,
    )


@vendor_bp.route("/vendors/add", methods=["GET", "POST"])
def add_vendor():
    if request.method == "POST":
        name = request.form["business_name"].strip()
        location = request.form["location"].strip()
        if not name:
            flash("Business name is required.", "danger")
            return redirect(url_for("vendor.add_vendor"))
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO Vendor (business_name, avg_rating, location) VALUES (%s, 0.00, %s)",
                    (name, location or None),
                )
            conn.commit()
            flash(f"Vendor '{name}' added successfully.", "success")
        finally:
            conn.close()
        return redirect(url_for("vendor.list_vendors"))
    return render_template("vendors/add.html")
