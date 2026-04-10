from flask import Blueprint, render_template, request, redirect, url_for, flash
from db import get_connection

order_bp = Blueprint("order", __name__)

PER_PAGE = 20
NEW_ORDER_CUSTOMER_PER_PAGE = 10
NEW_ORDER_PRODUCT_PER_PAGE = 15
STATUS_OPTIONS = ["pending", "processing", "shipped", "delivered", "cancelled"]
MANUAL_STATUS_OPTIONS = ["pending", "processing", "shipped", "delivered"]
ALLOWED_STATUS_TRANSITIONS = {
    "pending": ["pending", "processing", "shipped", "delivered"],
    "processing": ["processing", "shipped", "delivered"],
    "shipped": ["shipped", "delivered"],
    "delivered": ["delivered"],
}


def refresh_order_transactions(cur, order_id, customer_id):
    cur.execute("DELETE FROM Transaction WHERE order_id = %s", (order_id,))
    cur.execute(
        "SELECT p.vendor_id, SUM(oi.unit_price * oi.quantity) AS amount "
        "FROM Order_Item oi "
        "JOIN Product p ON oi.product_id = p.product_id "
        "WHERE oi.order_id = %s "
        "GROUP BY p.vendor_id",
        (order_id,),
    )
    for row in cur.fetchall():
        if row["amount"] and row["amount"] > 0:
            cur.execute(
                "INSERT INTO Transaction (order_id, customer_id, vendor_id, amount) "
                "VALUES (%s, %s, %s, %s)",
                (order_id, customer_id, row["vendor_id"], row["amount"]),
            )


def allowed_manual_statuses(current_status):
    return ALLOWED_STATUS_TRANSITIONS.get(current_status, [])


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
        status_options=STATUS_OPTIONS,
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
    return render_template(
        "orders/detail.html",
        order=order,
        items=items,
        manual_status_options=allowed_manual_statuses(order["status"]),
    )


@order_bp.route("/orders/<int:order_id>/status", methods=["POST"])
def update_status(order_id):
    new_status = request.form.get("status", "").strip()
    if new_status not in MANUAL_STATUS_OPTIONS:
        flash("Please choose a valid order status.", "danger")
        return redirect(url_for("order.order_detail", order_id=order_id))

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM Orders WHERE order_id = %s FOR UPDATE",
                (order_id,),
            )
            order = cur.fetchone()
            if not order:
                flash("Order not found.", "danger")
                return redirect(url_for("order.list_orders"))
            if order["status"] == "cancelled":
                flash("Cancelled orders cannot be moved back to another status.", "warning")
                return redirect(url_for("order.order_detail", order_id=order_id))
            if new_status not in allowed_manual_statuses(order["status"]):
                flash("Order status cannot move backwards after shipping.", "warning")
                return redirect(url_for("order.order_detail", order_id=order_id))

            cur.execute(
                "UPDATE Orders SET status = %s WHERE order_id = %s",
                (new_status, order_id),
            )
        conn.commit()
        flash(f"Order status updated to {new_status}.", "success")
    finally:
        conn.close()

    return redirect(url_for("order.order_detail", order_id=order_id))


@order_bp.route("/orders/new", methods=["GET", "POST"])
def new_order():
    page_data = load_new_order_page_data(request.args)

    if request.method == "POST":
        customer_id = request.form.get("customer_id", type=int)
        selected_product_ids = request.form.getlist("selected_product_id[]", type=int)

        if not customer_id or not selected_product_ids:
            flash("Please select a customer and at least one product.", "danger")
            return render_template("orders/new.html", **page_data)

        requested_items = {}
        for product_id in selected_product_ids:
            qty = request.form.get(f"quantity_{product_id}", type=int)
            if not qty or qty <= 0:
                flash("Each selected product must have a positive quantity.", "danger")
                return render_template("orders/new.html", **page_data)
            requested_items[product_id] = requested_items.get(product_id, 0) + qty

        conn = get_connection()
        order_id = None
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT customer_id FROM Customer WHERE customer_id = %s",
                    (customer_id,),
                )
                if not cur.fetchone():
                    flash("Selected customer does not exist.", "danger")
                    return render_template("orders/new.html", **page_data)

                order_lines = []
                total = 0
                vendor_amounts = {}

                for pid, qty in requested_items.items():
                    cur.execute(
                        "SELECT product_id, price, stock_qty, vendor_id "
                        "FROM Product WHERE product_id = %s FOR UPDATE",
                        (pid,),
                    )
                    product = cur.fetchone()
                    if not product:
                        conn.rollback()
                        flash(f"Product #{pid} does not exist.", "danger")
                        return render_template("orders/new.html", **page_data)
                    if product["stock_qty"] < qty:
                        conn.rollback()
                        flash(f"Insufficient stock for product #{pid}.", "danger")
                        return render_template("orders/new.html", **page_data)

                    unit_price = product["price"]
                    subtotal = unit_price * qty
                    total += subtotal
                    order_lines.append((pid, qty, unit_price))

                    vid = product["vendor_id"]
                    vendor_amounts[vid] = vendor_amounts.get(vid, 0) + subtotal

                if not order_lines:
                    flash("Please select at least one valid product.", "danger")
                    return render_template("orders/new.html", **page_data)

                cur.execute(
                    "INSERT INTO Orders (customer_id, total_price, status) "
                    "VALUES (%s, %s, 'pending')",
                    (customer_id, total),
                )
                order_id = conn.insert_id()

                for pid, qty, unit_price in order_lines:
                    cur.execute(
                        "INSERT INTO Order_Item (order_id, product_id, quantity, unit_price) "
                        "VALUES (%s, %s, %s, %s)",
                        (order_id, pid, qty, unit_price),
                    )
                    cur.execute(
                        "UPDATE Product SET stock_qty = stock_qty - %s "
                        "WHERE product_id = %s AND stock_qty >= %s",
                        (qty, pid, qty),
                    )
                    if cur.rowcount != 1:
                        conn.rollback()
                        flash(f"Insufficient stock for product #{pid}.", "danger")
                        return render_template("orders/new.html", **page_data)

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
            return render_template("orders/new.html", **page_data)
        finally:
            conn.close()
        return redirect(url_for("order.order_detail", order_id=order_id))

    return render_template("orders/new.html", **page_data)


@order_bp.route("/orders/<int:order_id>/remove-item/<int:product_id>", methods=["POST"])
def remove_item(order_id, product_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, customer_id FROM Orders WHERE order_id = %s FOR UPDATE",
                (order_id,),
            )
            order = cur.fetchone()
            if not order:
                flash("Order not found.", "danger")
                return redirect(url_for("order.list_orders"))
            if order["status"] not in ("pending", "processing"):
                flash("Cannot modify an order that has already shipped.", "warning")
                return redirect(url_for("order.order_detail", order_id=order_id))

            # Restore stock
            cur.execute(
                "SELECT quantity, product_id FROM Order_Item "
                "WHERE order_id=%s AND product_id=%s FOR UPDATE",
                (order_id, product_id),
            )
            item = cur.fetchone()
            if not item:
                flash("Item is not in this order.", "warning")
                return redirect(url_for("order.order_detail", order_id=order_id))

            cur.execute(
                "UPDATE Product SET stock_qty = stock_qty + %s WHERE product_id = %s",
                (item["quantity"], product_id),
            )
            cur.execute(
                "DELETE FROM Order_Item WHERE order_id=%s AND product_id=%s",
                (order_id, product_id),
            )
            cur.execute(
                "SELECT COALESCE(SUM(unit_price * quantity), 0) as new_total "
                "FROM Order_Item WHERE order_id=%s",
                (order_id,),
            )
            new_total = cur.fetchone()["new_total"]
            if new_total == 0:
                cur.execute(
                    "UPDATE Orders SET total_price=%s, status='cancelled' WHERE order_id=%s",
                    (new_total, order_id),
                )
            else:
                cur.execute(
                    "UPDATE Orders SET total_price=%s WHERE order_id=%s",
                    (new_total, order_id),
                )
            refresh_order_transactions(cur, order_id, order["customer_id"])
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
            cur.execute(
                "SELECT status FROM Orders WHERE order_id = %s FOR UPDATE",
                (order_id,),
            )
            order = cur.fetchone()
            if not order:
                flash("Order not found.", "danger")
                return redirect(url_for("order.list_orders"))
            if order["status"] not in ("pending", "processing"):
                flash("Cannot cancel an order that has already shipped.", "warning")
                return redirect(url_for("order.order_detail", order_id=order_id))

            # Restore stock for all items
            cur.execute(
                "SELECT product_id, quantity FROM Order_Item WHERE order_id=%s FOR UPDATE",
                (order_id,),
            )
            for item in cur.fetchall():
                cur.execute(
                    "UPDATE Product SET stock_qty = stock_qty + %s WHERE product_id=%s",
                    (item["quantity"], item["product_id"]),
                )

            cur.execute("DELETE FROM Order_Item WHERE order_id=%s", (order_id,))
            cur.execute("DELETE FROM Transaction WHERE order_id=%s", (order_id,))
            cur.execute(
                "UPDATE Orders SET status='cancelled', total_price=0.00 WHERE order_id=%s",
                (order_id,),
            )
        conn.commit()
        flash(f"Order #{order_id} has been cancelled.", "success")
    finally:
        conn.close()
    return redirect(url_for("order.order_detail", order_id=order_id))
