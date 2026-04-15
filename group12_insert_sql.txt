-- COMP7640 E-Commerce Platform
-- Database Schema + Sample Data

USE comp7640;

-- ─────────────────────────────────────────────
-- TABLE DEFINITIONS
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS Vendor (
    vendor_id       INT AUTO_INCREMENT PRIMARY KEY,
    business_name   VARCHAR(255) NOT NULL,
    avg_rating      DECIMAL(3,2) DEFAULT 0.00,
    location        VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS Customer (
    customer_id     INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    contact_number  VARCHAR(20),
    shipping_address VARCHAR(500)
);

CREATE TABLE IF NOT EXISTS Vendor_Rating (
    rating_id       INT AUTO_INCREMENT PRIMARY KEY,
    vendor_id       INT NOT NULL,
    customer_id     INT NOT NULL,
    rating          TINYINT NOT NULL,
    comment         VARCHAR(500),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_vendor_customer_rating (vendor_id, customer_id),
    INDEX idx_vendor_rating_vendor (vendor_id),
    INDEX idx_vendor_rating_customer (customer_id),
    CHECK (rating BETWEEN 1 AND 5),
    FOREIGN KEY (vendor_id) REFERENCES Vendor(vendor_id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES Customer(customer_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Product (
    product_id  INT AUTO_INCREMENT PRIMARY KEY,
    vendor_id   INT NOT NULL,
    name        VARCHAR(255) NOT NULL,
    price       DECIMAL(10,2) NOT NULL,
    stock_qty   INT NOT NULL DEFAULT 0,
    tag1        VARCHAR(50),
    tag2        VARCHAR(50),
    tag3        VARCHAR(50),
    INDEX idx_product_vendor_name (vendor_id, name),
    FOREIGN KEY (vendor_id) REFERENCES Vendor(vendor_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Orders (
    order_id    INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    order_date  DATETIME DEFAULT CURRENT_TIMESTAMP,
    total_price DECIMAL(10,2) DEFAULT 0.00,
    status      ENUM('pending', 'processing', 'shipped', 'delivered', 'cancelled') DEFAULT 'pending',
    INDEX idx_orders_customer_date (customer_id, order_date),
    INDEX idx_orders_status_date (status, order_date),
    FOREIGN KEY (customer_id) REFERENCES Customer(customer_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Order_Item (
    order_id    INT NOT NULL,
    product_id  INT NOT NULL,
    quantity    INT NOT NULL DEFAULT 1,
    unit_price  DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (order_id, product_id),
    INDEX idx_order_item_product (product_id),
    FOREIGN KEY (order_id) REFERENCES Orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES Product(product_id) ON DELETE CASCADE
);

-- Tracks payment from one customer to one vendor within an order
CREATE TABLE IF NOT EXISTS Transaction (
    transaction_id  INT AUTO_INCREMENT PRIMARY KEY,
    order_id        INT NOT NULL,
    customer_id     INT NOT NULL,
    vendor_id       INT NOT NULL,
    amount          DECIMAL(10,2) NOT NULL,
    transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_transaction_order (order_id),
    INDEX idx_transaction_customer (customer_id),
    INDEX idx_transaction_vendor (vendor_id),
    FOREIGN KEY (order_id) REFERENCES Orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES Customer(customer_id) ON DELETE CASCADE,
    FOREIGN KEY (vendor_id) REFERENCES Vendor(vendor_id) ON DELETE CASCADE
);

-- ─────────────────────────────────────────────
-- SAMPLE DATA
-- ─────────────────────────────────────────────

INSERT INTO Vendor (business_name, avg_rating, location) VALUES
    ('TechZone HK',     0.00, 'Mong Kok, Hong Kong'),
    ('FashionHub',      0.00, 'Causeway Bay, Hong Kong'),
    ('HomeEssentials',  0.00, 'Tsim Sha Tsui, Hong Kong'),
    ('SportsPro',       0.00, 'Wan Chai, Hong Kong');

INSERT INTO Customer (name, contact_number, shipping_address) VALUES
    ('Alice Chan',  '96001234', '12 Nathan Road, Kowloon'),
    ('Bob Lee',     '93005678', '45 Queen\'s Road, Central'),
    ('Carol Wong',  '91009012', '88 Canton Road, TST');

INSERT INTO Vendor_Rating (vendor_id, customer_id, rating, comment) VALUES
    (1, 1, 5, 'Fast delivery and reliable products'),
    (1, 2, 4, 'Good electronics selection'),
    (2, 1, 4, 'Comfortable clothing'),
    (2, 3, 4, 'Good value'),
    (3, 1, 5, 'Excellent kitchen items'),
    (3, 2, 4, 'Helpful home products'),
    (4, 2, 4, 'Good sports gear'),
    (4, 3, 4, 'Solid product quality');

UPDATE Vendor v
LEFT JOIN (
    SELECT vendor_id, ROUND(AVG(rating), 2) AS avg_rating
    FROM Vendor_Rating
    GROUP BY vendor_id
) r ON v.vendor_id = r.vendor_id
SET v.avg_rating = COALESCE(r.avg_rating, 0.00);

INSERT INTO Product (vendor_id, name, price, stock_qty, tag1, tag2, tag3) VALUES
    (1, 'Wireless Earbuds Pro',   299.00, 50,  'electronics', 'audio',    'wireless'),
    (1, 'USB-C Hub 7-in-1',       199.00, 30,  'electronics', 'usb',      'hub'),
    (1, 'Mechanical Keyboard',    450.00, 20,  'electronics', 'keyboard', 'gaming'),
    (2, 'Slim Fit Chinos',         89.00, 100, 'fashion',     'pants',    'casual'),
    (2, 'Cotton Polo Shirt',       59.00, 150, 'fashion',     'shirt',    'casual'),
    (3, 'Bamboo Cutting Board',    45.00, 60,  'kitchen',     'bamboo',   'cooking'),
    (3, 'Stainless Steel Kettle', 120.00, 40,  'kitchen',     'kettle',   'appliance'),
    (4, 'Running Shoes X200',     380.00, 35,  'sports',      'shoes',    'running'),
    (4, 'Yoga Mat Premium',        95.00, 45,  'sports',      'yoga',     'fitness');

INSERT INTO Orders (customer_id, order_date, total_price, status) VALUES
    (1, '2026-03-01 10:00:00', 498.00, 'delivered'),
    (2, '2026-03-15 14:30:00', 830.00, 'processing'),
    (3, '2026-03-28 09:15:00', 149.00, 'pending');

INSERT INTO Order_Item (order_id, product_id, quantity, unit_price) VALUES
    (1, 1, 1, 299.00),
    (1, 2, 1, 199.00),
    (2, 3, 1, 450.00),
    (2, 8, 1, 380.00),
    (3, 6, 2,  45.00),
    (3, 5, 1,  59.00);

INSERT INTO Transaction (order_id, customer_id, vendor_id, amount, transaction_date) VALUES
    (1, 1, 1, 498.00, '2026-03-01 10:01:00'),
    (2, 2, 1, 450.00, '2026-03-15 14:31:00'),
    (2, 2, 4, 380.00, '2026-03-15 14:31:00'),
    (3, 3, 3,  90.00, '2026-03-28 09:16:00'),
    (3, 3, 2,  59.00, '2026-03-28 09:16:00');
