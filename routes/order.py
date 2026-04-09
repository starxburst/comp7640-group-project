from flask import Blueprint, render_template, request, redirect, url_for, flash
from db import get_connection

order_bp = Blueprint("order", __name__)

PER_PAGE = 20
NEW_ORDER_CUSTOMER_PER_PAGE = 10
NEW_ORDER_PRODUCT_PER_PAGE = 15


def load_new_order_page_data(args):
    customer_page = max(args.get("customer_page", default=1, type=int), 1)
    product_page = max(args.get("product_page", default=1, type=int), 1)
    customer_query = args.get("customer_q", default="", type=str).strip()
    product_query = args.get("product_q", default="", type=str).strip()
    vendor_id = args.get("vendor_id", type=int)

    customer_offset = (customer_page - 1) * NEW_ORDER_CUSTOMER_PER_PAGE
    product_offset = (product_page - 1) * NEW_ORDER_PRODUCT_PER_PAGE

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT vendor_id, business_name FROM Vendor ORDER BY business_name")
            vendors = cur.fetchall()

            customer_count_sql = "SELECT COUNT(*) AS total FROM Customer WHERE 1=1"
            customer_data_sql = "SELECT customer_id, name, contact_number FROM Customer WHERE 1=1"
            customer_params = []

            if customer_query:
                like = f"%{customer_query}%"
                customer_count_sql += " AND (name LIKE %s OR contact_number LIKE %s)"
                customer_data_sql += " AND (name LIKE %s OR contact_number LIKE %s)"
                customer_params.extend([like, like])

            cur.execute(customer_count_sql, tuple(customer_params))
            customer_total = cur.fetchone()["total"]
            customer_data_sql += " ORDER BY name LIMIT %s OFFSET %s"
            cur.execute(
                customer_data_sql,
                tuple(customer_params + [NEW_ORDER_CUSTOMER_PER_PAGE, customer_offset]),
            )
            customers = cur.fetchall()

            product_count_sql = (
                "SELECT COUNT(*) AS total FROM Product p "
                "JOIN Vendor v ON p.vendor_id = v.vendor_id "
                "WHERE p.stock_qty > 0"
            )
            product_data_sql = (
                "SELECT p.*, v.business_name FROM Product p "
                "JOIN Vendor v ON p.vendor_id = v.vendor_id "
                "WHERE p.stock_qty > 0"
            )
            product_params = []

            if vendor_id:
                product_count_sql += " AND p.vendor_id = %s"
                product_data_sql += " AND p.vendor_id = %s"
                product_params.append(vendor_id)

            if product_query:
                like = f"%{product_query}%"
                product_count_sql += (
                    " AND (p.name LIKE %s OR p.tag1 LIKE %s OR p.tag2 LIKE %s OR p.tag3 LIKE %s)"
                )
                product_data_sql += (
                    " AND (p.name LIKE %s OR p.tag1 LIKE %s OR p.tag2 LIKE %s OR p.tag3 LIKE %s)"
                )
                product_params.extend([like, like, like, like])

            cur.execute(product_count_sql, tuple(product_params))
            product_total = cur.fetchone()["total"]
            product_data_sql += " ORDER BY v.business_name, p.name LIMIT %s OFFSET %s"
            cur.execute(
                product_data_sql,
                tuple(product_params + [NEW_ORDER_PRODUCT_PER_PAGE, product_offset]),
            )
            products = cur.fetchall()
    finally:
        conn.close()

    return {
        "customers": customers,
        "vendors": vendors,
        "products": products,
        "customer_page": customer_page,
        "product_page": product_page,
        "customer_q": customer_query,
        "product_q": product_query,
        "selected_vendor": vendor_id,
        "customer_total": customer_total,
        "product_total": product_total,
        "customer_total_pages": max((customer_total + NEW_ORDER_CUSTOMER_PER_PAGE - 1) // NEW_ORDER_CUSTOMER_PER_PAGE, 1),
        "product_total_pages": max((product_total + NEW_ORDER_PRODUCT_PER_PAGE - 1) // NEW_ORDER_PRODUCT_PER_PAGE, 1),
    }


@order_bp.route("/orders")
def list_orders():
    page = max(request.args.get("page", default=1, type=int), 1)
    customer_id = request.args.get("customer_id", type=int)
    status = request.args.get("status", default="", type=str).strip()
    offset = (page - 1) * PER_PAGE
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            count_sql = (
                "SELECT COUNT(*) AS total FROM Orders o "
                "JOIN Customer c ON o.customer_id = c.customer_id "
                "WHERE 1=1"
            )
            data_sql = (
                "SELECT o.*, c.name as customer_name FROM Orders o "
                "JOIN Customer c ON o.customer_id = c.customer_id "
                "WHERE 1=1"
            )
            params = []

            if customer_id:
                count_sql += " AND o.customer_id = %s"
                data_sql += " AND o.customer_id = %s"
                params.append(customer_id)
            if status:
                count_sql += " AND o.status = %s"
                data_sql += " AND o.status = %s"
                params.append(status)

            cur.execute(count_sql, tuple(params))
            total = cur.fetchone()["total"]
            data_sql += " ORDER BY o.order_date DESC LIMIT %s OFFSET %s"
            data_params = tuple(params + [PER_PAGE, offset])
            cur.execute(data_sql, data_params)
            orders = cur.fetchall()
    finally:
        conn.close()

    total_pages = max((total + PER_PAGE - 1) // PER_PAGE, 1)
    return render_template(
        "orders/index.html",
        orders=orders,
        customer_id=customer_id,
        status=status,
        page=page,
        per_page=PER_PAGE,
        total=total,
        total_pages=total_pages,
        status_options=["pending", "processing", "shipped", "delivered", "cancelled"],
    )


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
    page_data = load_new_order_page_data(request.args)

    if request.method == "POST":
        customer_id = request.form.get("customer_id", type=int)
        product_ids = request.form.getlist("product_id[]", type=int)
        quantities = request.form.getlist("quantity[]", type=int)

        if not customer_id or not product_ids:
            flash("Please select a customer and at least one product.", "danger")
            return render_template("orders/new.html", **page_data)

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
                        return render_template("orders/new.html", **page_data)

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

    return render_template("orders/new.html", **page_data)


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
