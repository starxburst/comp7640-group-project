from flask import Blueprint, render_template, request, redirect, url_for, flash
from db import get_connection

vendor_bp = Blueprint("vendor", __name__)

PER_PAGE = 20


def recalculate_vendor_rating(cur, vendor_id):
    cur.execute(
        "UPDATE Vendor v "
        "LEFT JOIN ("
        "  SELECT vendor_id, ROUND(AVG(rating), 2) AS avg_rating "
        "  FROM Vendor_Rating WHERE vendor_id = %s GROUP BY vendor_id"
        ") r ON v.vendor_id = r.vendor_id "
        "SET v.avg_rating = COALESCE(r.avg_rating, 0.00) "
        "WHERE v.vendor_id = %s",
        (vendor_id, vendor_id),
    )


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
                    "SELECT v.*, COUNT(vr.rating_id) AS rating_count "
                    "FROM Vendor v "
                    "LEFT JOIN Vendor_Rating vr ON v.vendor_id = vr.vendor_id "
                    "WHERE v.business_name LIKE %s OR v.location LIKE %s "
                    "GROUP BY v.vendor_id, v.business_name, v.avg_rating, v.location "
                    "ORDER BY v.vendor_id LIMIT %s OFFSET %s",
                    (like, like, PER_PAGE, offset),
                )
            else:
                cur.execute("SELECT COUNT(*) AS total FROM Vendor")
                total = cur.fetchone()["total"]
                cur.execute(
                    "SELECT v.*, COUNT(vr.rating_id) AS rating_count "
                    "FROM Vendor v "
                    "LEFT JOIN Vendor_Rating vr ON v.vendor_id = vr.vendor_id "
                    "GROUP BY v.vendor_id, v.business_name, v.avg_rating, v.location "
                    "ORDER BY v.vendor_id LIMIT %s OFFSET %s",
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


@vendor_bp.route("/vendors/<int:vendor_id>/rate", methods=["GET", "POST"])
def rate_vendor(vendor_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM Vendor WHERE vendor_id = %s", (vendor_id,))
            vendor = cur.fetchone()
            if not vendor:
                flash("Vendor not found.", "danger")
                return redirect(url_for("vendor.list_vendors"))

            cur.execute("SELECT customer_id, name FROM Customer ORDER BY name")
            customers = cur.fetchall()

            if request.method == "POST":
                customer_id = request.form.get("customer_id", type=int)
                rating = request.form.get("rating", type=int)
                comment = request.form.get("comment", "").strip() or None

                if not customer_id or rating not in (1, 2, 3, 4, 5):
                    flash("Please choose a customer and a rating from 1 to 5.", "danger")
                    return render_template(
                        "vendors/rate.html",
                        vendor=vendor,
                        customers=customers,
                    )

                cur.execute(
                    "SELECT customer_id FROM Customer WHERE customer_id = %s",
                    (customer_id,),
                )
                if not cur.fetchone():
                    flash("Selected customer does not exist.", "danger")
                    return render_template(
                        "vendors/rate.html",
                        vendor=vendor,
                        customers=customers,
                    )

                cur.execute(
                    "INSERT INTO Vendor_Rating (vendor_id, customer_id, rating, comment) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE "
                    "rating = VALUES(rating), comment = VALUES(comment), created_at = CURRENT_TIMESTAMP",
                    (vendor_id, customer_id, rating, comment),
                )
                recalculate_vendor_rating(cur, vendor_id)
                conn.commit()
                flash("Vendor rating saved and average rating recalculated.", "success")
                return redirect(url_for("vendor.list_vendors"))
    finally:
        conn.close()

    return render_template("vendors/rate.html", vendor=vendor, customers=customers)
