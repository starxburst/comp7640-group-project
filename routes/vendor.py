from flask import Blueprint, render_template, request, redirect, url_for, flash
from db import get_connection

vendor_bp = Blueprint("vendor", __name__)


@vendor_bp.route("/vendors")
def list_vendors():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM Vendor ORDER BY vendor_id")
            vendors = cur.fetchall()
    finally:
        conn.close()
    return render_template("vendors/index.html", vendors=vendors)


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
