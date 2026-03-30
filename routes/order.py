from flask import Blueprint, render_template, request, redirect, url_for, flash
from db import get_connection

order_bp = Blueprint("order", __name__)


@order_bp.route("/orders")
def list_orders():
    customer_id = request.args.get("customer_id", type=int)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if customer_id:
                cur.execute(
                    "SELECT o.*, c.name as customer_name FROM Orders o "
                    "JOIN Customer c ON o.customer_id = c.customer_id "
                    "WHERE o.customer_id = %s ORDER BY o.order_date DESC",
                    (customer_id,),
                )
            else:
                cur.execute(
                    "SELECT o.*, c.name as customer_name FROM Orders o "
                    "JOIN Customer c ON o.customer_id = c.customer_id "
                    "ORDER BY o.order_date DESC"
                )
            orders = cur.fetchall()
    finally:
        conn.close()
    return render_template("orders/index.html", orders=orders, customer_id=customer_id)


@order_bp.route("/orders/<int:order_id>")
def order_detail(order_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT o.*, c.name as customer_name FROM Orders o "
                "JOIN Customer c ON o.customer_id = c.customer_id "
                "WHERE o.order_id = %s",
                (order_id,),
            )
            order = cur.fetchone()
            if not order:
                flash("Order not found.", "danger")
                return redirect(url_for("order.list_orders"))
            cur.execute(
                "SELECT oi.*, p.name as product_name, v.business_name "
                "FROM Order_Item oi "
                "JOIN Product p ON oi.product_id = p.product_id "
                "JOIN Vendor v ON p.vendor_id = v.vendor_id "
                "WHERE oi.order_id = %s",
                (order_id,),
            )
            items = cur.fetchall()
    finally:
        conn.close()
    return render_template("orders/detail.html", order=order, items=items)


@order_bp.route("/orders/new", methods=["GET", "POST"])
def new_order():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT customer_id, name FROM Customer ORDER BY name")
            customers = cur.fetchall()
            cur.execute(
                "SELECT p.*, v.business_name FROM Product p "
                "JOIN Vendor v ON p.vendor_id = v.vendor_id "
                "WHERE p.stock_qty > 0 ORDER BY v.business_name, p.name"
            )
            products = cur.fetchall()
    finally:
        conn.close()

    if request.method == "POST":
        customer_id = request.form.get("customer_id", type=int)
        product_ids = request.form.getlist("product_id[]", type=int)
        quantities = request.form.getlist("quantity[]", type=int)

        if not customer_id or not product_ids:
            flash("Please select a customer and at least one product.", "danger")
            return render_template("orders/new.html", customers=customers, products=products)

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                # Create the order
                cur.execute(
                    "INSERT INTO Orders (customer_id, status) VALUES (%s, 'pending')",
                    (customer_id,),
                )
                order_id = conn.insert_id()

                total = 0.0
                vendor_amounts = {}

                for pid, qty in zip(product_ids, quantities):
                    if qty <= 0:
                        continue
                    cur.execute(
                        "SELECT product_id, price, stock_qty, vendor_id FROM Product WHERE product_id = %s",
                        (pid,),
                    )
                    product = cur.fetchone()
                    if not product:
                        continue
                    if product["stock_qty"] < qty:
                        conn.rollback()
                        flash(f"Insufficient stock for product #{pid}.", "danger")
                        return render_template("orders/new.html", customers=customers, products=products)

                    unit_price = float(product["price"])
                    subtotal = unit_price * qty
                    total += subtotal

                    cur.execute(
                        "INSERT INTO Order_Item (order_id, product_id, quantity, unit_price) "
                        "VALUES (%s, %s, %s, %s)",
                        (order_id, pid, qty, unit_price),
                    )
                    # Deduct stock
                    cur.execute(
                        "UPDATE Product SET stock_qty = stock_qty - %s WHERE product_id = %s",
                        (qty, pid),
                    )
                    # Accumulate per-vendor totals for transactions
                    vid = product["vendor_id"]
                    vendor_amounts[vid] = vendor_amounts.get(vid, 0.0) + subtotal

                # Update order total
                cur.execute(
                    "UPDATE Orders SET total_price = %s WHERE order_id = %s",
                    (total, order_id),
                )

                # Record one transaction per vendor
                for vendor_id, amount in vendor_amounts.items():
                    cur.execute(
                        "INSERT INTO Transaction (order_id, customer_id, vendor_id, amount) "
                        "VALUES (%s, %s, %s, %s)",
                        (order_id, customer_id, vendor_id, amount),
                    )

            conn.commit()
            flash(f"Order #{order_id} placed successfully. Total: HK${total:.2f}", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Error placing order: {e}", "danger")
        finally:
            conn.close()
        return redirect(url_for("order.order_detail", order_id=order_id))

    return render_template("orders/new.html", customers=customers, products=products)


@order_bp.route("/orders/<int:order_id>/remove-item/<int:product_id>", methods=["POST"])
def remove_item(order_id, product_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM Orders WHERE order_id = %s", (order_id,))
            order = cur.fetchone()
            if not order:
                flash("Order not found.", "danger")
                return redirect(url_for("order.list_orders"))
            if order["status"] not in ("pending", "processing"):
                flash("Cannot modify an order that has already shipped.", "warning")
                return redirect(url_for("order.order_detail", order_id=order_id))

            # Restore stock
            cur.execute(
                "SELECT quantity, product_id FROM Order_Item WHERE order_id=%s AND product_id=%s",
                (order_id, product_id),
            )
            item = cur.fetchone()
            if item:
                cur.execute(
                    "UPDATE Product SET stock_qty = stock_qty + %s WHERE product_id = %s",
                    (item["quantity"], product_id),
                )
                cur.execute(
                    "DELETE FROM Order_Item WHERE order_id=%s AND product_id=%s",
                    (order_id, product_id),
                )
                # Recalculate total
                cur.execute(
                    "SELECT SUM(unit_price * quantity) as new_total FROM Order_Item WHERE order_id=%s",
                    (order_id,),
                )
                row = cur.fetchone()
                new_total = row["new_total"] or 0
                cur.execute(
                    "UPDATE Orders SET total_price=%s WHERE order_id=%s",
                    (new_total, order_id),
                )
        conn.commit()
        flash("Item removed from order.", "success")
    finally:
        conn.close()
    return redirect(url_for("order.order_detail", order_id=order_id))


@order_bp.route("/orders/<int:order_id>/cancel", methods=["POST"])
def cancel_order(order_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM Orders WHERE order_id = %s", (order_id,))
            order = cur.fetchone()
            if not order:
                flash("Order not found.", "danger")
                return redirect(url_for("order.list_orders"))
            if order["status"] not in ("pending", "processing"):
                flash("Cannot cancel an order that has already shipped.", "warning")
                return redirect(url_for("order.order_detail", order_id=order_id))

            # Restore stock for all items
            cur.execute(
                "SELECT product_id, quantity FROM Order_Item WHERE order_id=%s", (order_id,)
            )
            for item in cur.fetchall():
                cur.execute(
                    "UPDATE Product SET stock_qty = stock_qty + %s WHERE product_id=%s",
                    (item["quantity"], item["product_id"]),
                )

            cur.execute(
                "UPDATE Orders SET status='cancelled' WHERE order_id=%s", (order_id,)
            )
        conn.commit()
        flash(f"Order #{order_id} has been cancelled.", "success")
    finally:
        conn.close()
    return redirect(url_for("order.order_detail", order_id=order_id))
