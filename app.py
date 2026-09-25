import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import io

# Optional voice search
try:
    import speech_recognition as sr
    SPEECH_OK = True
except Exception:
    SPEECH_OK = False


# =========================================================
# APP CONFIG
# =========================================================

st.set_page_config(
    page_title="Shoe Shop POS",
    page_icon="👟",
    layout="wide"
)

DB = "shoe_shop.db"


# =========================================================
# DATABASE
# =========================================================

def get_conn():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()

    tables = [
        "CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, brand TEXT, category TEXT, size TEXT, color TEXT, sku TEXT UNIQUE, barcode TEXT UNIQUE, purchase_price REAL DEFAULT 0, sale_price REAL DEFAULT 0, stock INTEGER DEFAULT 0, min_stock INTEGER DEFAULT 5, created_at TEXT)",

        "CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT, address TEXT, credit REAL DEFAULT 0, created_at TEXT)",

        "CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_no TEXT UNIQUE, customer_id INTEGER, subtotal REAL, discount REAL, tax REAL, total REAL, payment_method TEXT, paid REAL, change_amount REAL, created_at TEXT)",

        "CREATE TABLE IF NOT EXISTS sale_items (id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER, product_id INTEGER, name TEXT, size TEXT, qty INTEGER, price REAL, cost REAL, line_total REAL)",

        "CREATE TABLE IF NOT EXISTS expenses (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, amount REAL, note TEXT, created_at TEXT)",

        "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
    ]

    for sql in tables:
        conn.execute(sql)

    defaults = {
        "shop_name": "My Shoe Store",
        "phone": "",
        "address": "",
        "currency": "PKR",
        "tax": "0",
        "receipt_footer": "Thank you for shopping!"
    }

    for key, value in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
            (key, value)
        )

    conn.commit()
    conn.close()


def qdf(sql, params=()):
    conn = get_conn()
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def execute(sql, params=()):
    conn = get_conn()
    cur = conn.execute(sql, params)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


# =========================================================
# SETTINGS HELPERS
# =========================================================

def setting(key):
    df = qdf(
        "SELECT value FROM settings WHERE key=?",
        (key,)
    )

    if df.empty:
        return ""

    return str(df.iloc[0]["value"])


def save_setting(key, value):
    execute(
        "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
        (key, str(value))
    )


def money(value):
    return f"{setting('currency')} {float(value):,.0f}"


# =========================================================
# DEMO PRODUCTS
# =========================================================

def seed_products():

    brands = [
        "Nike",
        "Adidas",
        "Puma",
        "Bata",
        "Skechers",
        "Servis",
        "Reebok",
        "Clarks",
        "Jordan",
        "Local"
    ]

    categories = [
        "Sneakers",
        "Running",
        "Formal",
        "Casual",
        "Sports",
        "Sandals",
        "Boots"
    ]

    sizes = [
        "38",
        "39",
        "40",
        "41",
        "42",
        "43",
        "44"
    ]

    colors = [
        "Black",
        "White",
        "Blue",
        "Brown",
        "Grey",
        "Red"
    ]

    conn = get_conn()

    count = conn.execute(
        "SELECT COUNT(*) FROM products"
    ).fetchone()[0]

    if count == 0:

        for i in range(100):

            brand = brands[i % len(brands)]

            name = f"{brand} Shoe Model {i + 1:03d}"

            category = categories[
                i % len(categories)
            ]

            size = sizes[
                i % len(sizes)
            ]

            color = colors[
                i % len(colors)
            ]

            sku = f"SH-{i + 1:04d}"

            barcode = f"8901000{i + 1:05d}"

            purchase_price = (
                1800 + (i % 12) * 250
            )

            sale_price = (
                purchase_price
                + 900
                + (i % 5) * 200
            )

            stock = 5 + (i % 25)

            conn.execute(
                "INSERT INTO products(name,brand,category,size,color,sku,barcode,purchase_price,sale_price,stock,min_stock,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    name,
                    brand,
                    category,
                    size,
                    color,
                    sku,
                    barcode,
                    purchase_price,
                    sale_price,
                    stock,
                    5,
                    datetime.now().isoformat(
                        timespec="seconds"
                    )
                )
            )

        conn.commit()

    conn.close()


# =========================================================
# SESSION STATE
# =========================================================

def init_state():

    if "cart" not in st.session_state:
        st.session_state.cart = []

    if "last_invoice" not in st.session_state:
        st.session_state.last_invoice = None

    if "last_receipt" not in st.session_state:
        st.session_state.last_receipt = ""


# =========================================================
# START DATABASE
# =========================================================

init_db()
init_state()


# =========================================================
# HEADER
# =========================================================

st.title("👟 Shoe Shop POS")

st.caption(
    "Inventory • POS Billing • Customers • Expenses • Reports"
)


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.header("📋 Menu")

    page = st.radio(
        "Go to",
        [
            "Dashboard",
            "POS Billing",
            "Products",
            "Customers",
            "Expenses",
            "Reports",
            "Settings"
        ]
    )

    st.divider()

    if st.button(
        "📦 Add 100 Demo Products",
        use_container_width=True
    ):

        seed_products()

        st.success(
            "Demo products are ready."
        )

        st.rerun()


# =========================================================
# DASHBOARD
# =========================================================

if page == "Dashboard":

    st.subheader("📊 Dashboard")

    sales = qdf(
        "SELECT COALESCE(SUM(total),0) total FROM sales"
    )

    today = datetime.now().strftime("%Y-%m-%d")

    today_sales = qdf(
        "SELECT COALESCE(SUM(total),0) total FROM sales WHERE date(created_at)=date(?)",
        (today,)
    )

    products = qdf(
        "SELECT COUNT(*) count FROM products"
    )

    stock = qdf(
        "SELECT COALESCE(SUM(stock),0) stock FROM products"
    )

    low = qdf(
        "SELECT COUNT(*) count FROM products WHERE stock<=min_stock"
    )

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "All Sales",
        money(sales.iloc[0]["total"])
    )

    c2.metric(
        "Today",
        money(today_sales.iloc[0]["total"])
    )

    c3.metric(
        "Products",
        int(products.iloc[0]["count"])
    )

    c4.metric(
        "Stock Units",
        int(stock.iloc[0]["stock"])
    )

    c5.metric(
        "Low Stock",
        int(low.iloc[0]["count"])
    )

    st.divider()

    st.subheader("🧾 Recent Sales")

    recent = qdf(
        "SELECT invoice_no,total,payment_method,created_at FROM sales ORDER BY id DESC LIMIT 10"
    )

    if recent.empty:
        st.info("No sales yet.")
    else:
        st.dataframe(
            recent,
            use_container_width=True,
            hide_index=True
        )

    st.subheader("⚠️ Low Stock")

    low_df = qdf(
        "SELECT name,brand,size,color,stock,min_stock FROM products WHERE stock<=min_stock ORDER BY stock ASC LIMIT 20"
    )

    if low_df.empty:
        st.success(
            "No low-stock products."
        )
    else:
        st.dataframe(
            low_df,
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# POS BILLING
# =========================================================

elif page == "POS Billing":

    st.subheader("🧾 New Sale")

    col1, col2 = st.columns([3, 1])

    with col1:

        search = st.text_input(
            "🔎 Search product",
            placeholder="Name, brand, SKU, barcode, size or color...",
            key="pos_search"
        )

    with col2:

        if SPEECH_OK:

            audio = st.audio_input(
                "🎤 Voice Search"
            )

            if audio:

                try:

                    recognizer = sr.Recognizer()

                    with sr.AudioFile(
                        io.BytesIO(audio.getvalue())
                    ) as source:

                        data = recognizer.record(
                            source
                        )

                    voice_text = recognizer.recognize_google(
                        data
                    )

                    st.info(
                        f"Voice: {voice_text}"
                    )

                    search = voice_text

                except Exception:

                    st.warning(
                        "Voice could not be recognized."
                    )

        else:

            st.caption(
                "Install SpeechRecognition for voice search."
            )

    # Product search

    if search.strip():

        term = f"%{search.strip()}%"

        products = qdf(
            "SELECT * FROM products WHERE name LIKE ? OR brand LIKE ? OR sku LIKE ? OR barcode LIKE ? OR size LIKE ? OR color LIKE ? ORDER BY name LIMIT 100",
            (
                term,
                term,
                term,
                term,
                term,
                term
            )
        )

    else:

        products = qdf(
            "SELECT * FROM products ORDER BY id DESC LIMIT 50"
        )

    # Product list

    if not products.empty:

        st.write("### Products")

        for _, product in products.iterrows():

            a, b, c, d, e = st.columns(
                [3, 1, 1, 1, 1]
            )

            a.write(
                f"**{product['name']}**"
            )

            b.write(
                f"Size: {product['size']}"
            )

            c.write(
                f"Stock: {product['stock']}"
            )

            d.write(
                money(product["sale_price"])
            )

            if e.button(
                "Add",
                key=f"add_{int(product['id'])}"
            ):

                if int(product["stock"]) <= 0:

                    st.error(
                        "Out of stock."
                    )

                else:

                    existing = next(
                        (
                            item
                            for item in st.session_state.cart
                            if item["id"] == int(product["id"])
                        ),
                        None
                    )

                    if existing:

                        if (
                            existing["qty"]
                            < int(product["stock"])
                        ):

                            existing["qty"] += 1

                    else:

                        st.session_state.cart.append(
                            {
                                "id": int(product["id"]),
                                "name": product["name"],
                                "size": product["size"],
                                "qty": 1,
                                "price": float(
                                    product["sale_price"]
                                ),
                                "cost": float(
                                    product["purchase_price"]
                                ),
                                "stock": int(
                                    product["stock"]
                                )
                            }
                        )

                st.rerun()

    st.divider()

    st.subheader("🛒 Cart")

    if not st.session_state.cart:

        st.info(
            "Cart is empty."
        )

    else:

        subtotal = 0.0

        for i, item in enumerate(
            st.session_state.cart
        ):

            a, b, c, d, e = st.columns(
                [3, 1, 1, 1, 1]
            )

            a.write(
                f"{item['name']} "
                f"(Size {item['size']})"
            )

            qty = b.number_input(
                "Qty",
                min_value=1,
                max_value=item["stock"],
                value=item["qty"],
                key=f"qty_{i}"
            )

            item["qty"] = int(qty)

            c.write(
                money(item["price"])
            )

            line_total = (
                item["qty"]
                * item["price"]
            )

            subtotal += line_total

            d.write(
                money(line_total)
            )

            if e.button(
                "Remove",
                key=f"remove_{i}"
            ):

                st.session_state.cart.pop(i)

                st.rerun()

        st.divider()

        a, b, c = st.columns(3)

        discount = a.number_input(
            "Discount",
            min_value=0.0,
            value=0.0,
            step=100.0
        )

        tax_rate = b.number_input(
            "Tax %",
            min_value=0.0,
            value=float(
                setting("tax") or 0
            ),
            step=1.0
        )

        payment = c.selectbox(
            "Payment",
            [
                "Cash",
                "Card",
                "Bank",
                "JazzCash",
                "Easypaisa",
                "Credit"
            ]
        )

        tax = (
            max(
                0,
                subtotal - discount
            )
            * tax_rate
            / 100
        )

        total = max(
            0,
            subtotal - discount + tax
        )

        st.metric(
            "Total",
            money(total)
        )

        paid = st.number_input(
            "Paid Amount",
            min_value=0.0,
            value=float(total),
            step=100.0
        )

        change = max(
            0,
            paid - total
        )

        # Customer

        customer_id = None

        customers = qdf(
            "SELECT id,name,phone FROM customers ORDER BY name"
        )

        if not customers.empty:

            options = ["Walk-in"]

            for row in customers.itertuples():

                options.append(
                    f"{int(row.id)} - "
                    f"{row.name} "
                    f"({row.phone or ''})"
                )

            selected = st.selectbox(
                "Customer",
                options
            )

            if selected != "Walk-in":

                customer_id = int(
                    selected.split(" - ")[0]
                )

        # Complete sale

        if st.button(
            "✅ Complete Sale",
            type="primary",
            use_container_width=True
        ):

            if (
                payment != "Credit"
                and paid < total
            ):

                st.error(
                    "Paid amount is less than total."
                )

            else:

                conn = get_conn()

                try:

                    invoice = (
                        "INV-"
                        + datetime.now().strftime(
                            "%Y%m%d-%H%M%S"
                        )
                    )

                    cur = conn.cursor()

                    cur.execute(
                        "INSERT INTO sales(invoice_no,customer_id,subtotal,discount,tax,total,payment_method,paid,change_amount,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (
                            invoice,
                            customer_id,
                            subtotal,
                            discount,
                            tax,
                            total,
                            payment,
                            paid,
                            change,
                            datetime.now().isoformat(
                                timespec="seconds"
                            )
                        )
                    )

                    sale_id = cur.lastrowid

                    for item in st.session_state.cart:

                        stock_row = cur.execute(
                            "SELECT stock FROM products WHERE id=?",
                            (item["id"],)
                        ).fetchone()

                        if (
                            not stock_row
                            or stock_row[0]
                            < item["qty"]
                        ):

                            raise ValueError(
                                f"Not enough stock for {item['name']}."
                            )

                        cur.execute(
                            "UPDATE products SET stock=stock-? WHERE id=?",
                            (
                                item["qty"],
                                item["id"]
                            )
                        )

                        cur.execute(
                            "INSERT INTO sale_items(sale_id,product_id,name,size,qty,price,cost,line_total) VALUES(?,?,?,?,?,?,?,?)",
                            (
                                sale_id,
                                item["id"],
                                item["name"],
                                item["size"],
                                item["qty"],
                                item["price"],
                                item["cost"],
                                item["qty"]
                                * item["price"]
                            )
                        )

                    if (
                        payment == "Credit"
                        and customer_id
                    ):

                        cur.execute(
                            "UPDATE customers SET credit=credit+? WHERE id=?",
                            (
                                total,
                                customer_id
                            )
                        )

                    conn.commit()

                    # Receipt

                    receipt = (
                        f"{setting('shop_name')}\n"
                        f"Invoice: {invoice}\n"
                        f"Date: "
                        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                    )

                    for item in st.session_state.cart:

                        receipt += (
                            f"{item['name']} | "
                            f"{item['qty']} x "
        )
                           
