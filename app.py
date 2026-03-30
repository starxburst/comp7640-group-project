from flask import Flask
from routes.vendor import vendor_bp
from routes.product import product_bp
from routes.customer import customer_bp
from routes.order import order_bp

app = Flask(__name__)
app.secret_key = "comp7640-secret"
app.jinja_env.auto_reload = True

app.register_blueprint(vendor_bp)
app.register_blueprint(product_bp)
app.register_blueprint(customer_bp)
app.register_blueprint(order_bp)


@app.route("/")
def index():
    from flask import redirect, url_for
    return redirect(url_for("vendor.list_vendors"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)
