import streamlit as st
import sqlite3
import pandas as pd
import io
import os
from datetime import datetime, date
import speech_recognition as sr

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="ShoeShop Pro POS",
    page_icon="👟",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB = "shoe_shop.db"

# =========================================================
# DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            brand TEXT,
            category TEXT,
            size TEXT,
            color TEXT,
            sku TEXT UNIQUE,
            barcode TEXT UNIQUE,
            purchase_price REAL DEFAULT 0,
            sale_price REAL DEFAULT 0,
            stock INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            address TEXT,
            credit REAL DEFAULT 0,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            subtotal REAL,
            discount REAL,
            tax REAL,
            total REAL,
            payment_method TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER,
            product_id INTEGER,
            product_name TEXT,
            quantity INTEGER,
            price REAL,
            cost REAL,
            total REAL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            amount REAL,
            category TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()

# =========================================================
# HELPERS
# =========================================================

def query_df(sql, params=()):
    conn = get_db()
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def execute(sql, params=()):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


def normalize(text):
    return str(text).strip().lower()


def money(value):
    return f"Rs. {float(value):,.0f}"


# =========================================================
# DEMO PRODUCTS - 100 PRODUCTS
# =========================================================

def add_100_products():
    brands = [
        "Nike", "Adidas", "Puma", "Skechers", "Bata",
        "Servis", "Hush Puppies", "UrbanStep", "WalkPro", "RoyalFeet"
    ]

    categories = [
        "Running", "Casual", "Formal", "Sports",
        "Sneakers", "Sandals", "School", "Boots"
    ]

    colors = [
        "Black", "White", "Blue", "Red", "Brown",
        "Grey", "Green", "Navy"
    ]

    sizes = [
        "38", "39", "40", "41", "42", "43", "44"
    ]

    conn = get_db()
    cur = conn.cursor()

    existing = cur.execute(
        "SELECT COUNT(*) FROM products"
    ).fetchone()[0]

    for i in range(1, 101):
        brand = brands[(i - 1) % len(brands)]
        category = categories[(i - 1) % len(categories)]
        color = colors[(i - 1) % len(colors)]
        size = sizes[(i - 1) % len(sizes)]

        name = f"{brand} {category} {i}"
        sku = f"SHOE-{i:04d}"
        barcode = f"8901000{i:05d}"

        purchase = 1800 + ((i * 137) % 4500)
        sale = purchase + 1000 + ((i * 71) % 2500)
        stock = 5 + (i % 26)

        try:
            cur.execute("""
                INSERT INTO products
                (
                    name, brand, category, size, color,
                    sku, barcode, purchase_price,
                    sale_price, stock, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name,
                brand,
                category,
                size,
                color,
                sku,
                barcode,
                purchase,
                sale,
                stock,
                datetime.now().isoformat()
            ))
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()


# =========================================================
# VOICE SEARCH
# =========================================================

def voice_to_text(audio_bytes, language="en-US"):
    try:
        recognizer = sr.Recognizer()

        audio_file = sr.AudioFile(io.BytesIO(audio_bytes))

        with audio_file as source:
            audio = recognizer.record(source)

        text = recognizer.recognize_google(
            audio,
            language=language
        )

        return text

    except Exception:
        return ""


# =========================================================
# PRODUCT SEARCH
# =========================================================

def search_products(search_text):
    products = query_df("""
        SELECT *
        FROM products
        ORDER BY id DESC
    """)

    if products.empty:
        return products

    search_text = normalize(search_text)

    if not search_text:
        return products

    searchable_columns = [
        "name",
        "brand",
        "category",
        "size",
        "color",
        "sku",
        "barcode"
    ]

    # Full phrase search
    mask = False

    for column in searchable_columns:
        mask = mask | products[column].fillna("").astype(str).str.lower().str.contains(
            search_text,
            regex=False
        )

    results = products[mask]

    # Token-based flexible search
    if results.empty:
        tokens = search_text.split()

        if tokens:
            combined = products[searchable_columns].fillna("").astype(str).agg(
                " ".join,
                axis=1
            ).str.lower()

            token_mask = combined.apply(
                lambda x: all(token in x for token in tokens)
            )

            results = products[token_mask]

    return results


# =========================================================
# CART
# =========================================================

if "cart" not in st.session_state:
    st.session_state.cart = []

if "voice_query" not in st.session_state:
    st.session_state.voice_query = ""


def add_to_cart(product_id):
    product = query_df(
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    )

    if product.empty:
        return

    row = product.iloc[0]

    for item in st.session_state.cart:
        if item["id"] == product_id:
            if item["quantity"] < int(row["stock"]):
                item["quantity"] += 1
            return

    if int(row["stock"]) > 0:
        st.session_state.cart.append({
            "id": int(row["id"]),
            "name": row["name"],
            "sku": row["sku"],
            "size": row["size"],
            "price": float(row["sale_price"]),
            "cost": float(row["purchase_price"]),
            "quantity": 1
        })


def cart_subtotal():
    return sum(
        item["price"] * item["quantity"]
        for item in st.session_state.cart
    )


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown("# 👟 ShoeShop Pro")

    st.caption("Professional Shoe Shop POS")

    st.divider()

    page = st.radio(
        "Navigation",
        [
            "📊 Dashboard",
            "🛒 POS",
            "👟 Products",
            "👥 Customers",
            "💰 Expenses",
            "📈 Reports",
            "⚙️ Settings"
        ]
    )

    st.divider()

    st.markdown("### Quick Actions")

    if st.button(
        "➕ Add 100 Demo Products",
        use_container_width=True
    ):
        add_100_products()
        st.success("100 products processed successfully!")
        st.rerun()

# =========================================================
# DASHBOARD
# =========================================================

if page == "📊 Dashboard":

    st.title("📊 Dashboard")

    today = date.today().isoformat()

    sales_today = query_df("""
        SELECT
            COALESCE(SUM(total), 0) AS total,
            COUNT(*) AS invoices
        FROM sales
        WHERE DATE(created_at) = ?
    """, (today,))

    products = query_df("""
        SELECT COUNT(*) AS count
        FROM products
    """)

    stock = query_df("""
        SELECT COALESCE(SUM(stock), 0) AS stock
        FROM products
    """)

    low_stock = query_df("""
        SELECT COUNT(*) AS count
        FROM products
        WHERE stock <= 5
    """)

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Today's Sales",
        money(sales_today.iloc[0]["total"])
    )

    c2.metric(
        "Invoices",
        int(sales_today.iloc[0]["invoices"])
    )

    c3.metric(
        "Products",
        int(products.iloc[0]["count"])
    )

    c4.metric(
        "Low Stock",
        int(low_stock.iloc[0]["count"])
    )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📦 Inventory")

        inventory = query_df("""
            SELECT
                brand,
                COUNT(*) AS products,
                SUM(stock) AS units
            FROM products
            GROUP BY brand
            ORDER BY units DESC
        """)

        if not inventory.empty:
            st.dataframe(
                inventory,
                use_container_width=True,
                hide_index=True
            )

    with col2:
        st.subheader("⚠️ Low Stock Products")

        low = query_df("""
            SELECT
                name,
                brand,
                size,
                stock,
                sale_price
            FROM products
            WHERE stock <= 5
            ORDER BY stock ASC
            LIMIT 15
        """)

        if low.empty:
            st.success("No low-stock products.")
        else:
            st.dataframe(
                low,
                use_container_width=True,
                hide_index=True
            )

# =========================================================
# POS
# =========================================================

elif page == "🛒 POS":

    st.title("🛒 Point of Sale")

    # -----------------------------------------------------
    # VOICE
    # -----------------------------------------------------

    col1, col2 = st.columns([3, 1])

    with col1:

        st.markdown("### 🔎 Search Product")

        search_language = st.selectbox(
            "Voice language",
            [
                "English",
                "Urdu"
            ],
            horizontal=True
        )

        language_code = (
            "ur-PK"
            if search_language == "Urdu"
            else "en-US"
        )

    with col2:

        st.markdown("### 🎙️ Voice")

        audio = st.audio_input(
            "Speak Product Name",
            key="voice_search"
        )

    if audio is not None:

        transcript = voice_to_text(
            audio.getvalue(),
            language_code
        )

        if transcript:

            st.session_state.voice_query = transcript

            st.success(
                f"Voice search: {transcript}"
            )

        else:

            st.warning(
                "Voice could not be recognized. Please try again."
            )

    search_query = st.text_input(
        "Product name / Brand / SKU / Barcode / Size",
        value=st.session_state.voice_query,
        placeholder="Example: Nike Air Max or Nike",
        key="product_search"
    )

    # -----------------------------------------------------
    # PRODUCTS
    # -----------------------------------------------------

    results = search_products(search_query)

    st.markdown(
        f"### Products Found: {len(results)}"
    )

    if results.empty:

        st.info(
            "No products found. Add products from the Products section."
        )

    else:

        for _, product in results.head(100).iterrows():

            col1, col2, col3, col4, col5, col6 = st.columns(
                [3, 1.3, 1, 1, 1, 1]
            )

            with col1:

                st.markdown(
                    f"**{product['name']}**"
                )

                st.caption(
                    f"{product['brand']} • "
                    f"{product['category']} • "
                    f"SKU: {product['sku']}"
                )

            with col2:
                st.write(
                    f"Size: {product['size']}"
                )

            with col3:
                st.write(
                    f"Stock: {product['stock']}"
                )

            with col4:
                st.write(
                    money(product["sale_price"])
                )

            with col5:
                st.write(
                    product["color"]
                )

            with col6:

                if st.button(
                    "Add",
                    key=f"add_{product['id']}",
                    use_container_width=True
                ):

                    add_to_cart(
                        int(product["id"])
                    )

                    st.rerun()

    st.divider()

    # -----------------------------------------------------
    # CART
    # -----------------------------------------------------

    st.subheader("🛍️ Current Cart")

    if not st.session_state.cart:

        st.info("Cart is empty.")

    else:

        total = 0

        for index, item in enumerate(
            st.session_state.cart
        ):

            col1, col2, col3, col4, col5 = st.columns(
                [3, 1, 1, 1, 1]
            )

            with col1:
                st.write(item["name"])

            with col2:
                st.write(
                    money(item["price"])
                )

            with col3:

                quantity = st.number_input(
                    "Qty",
                    min_value=1,
                    max_value=100,
                    value=item["quantity"],
                    key=f"qty_{index}"
                )

                item["quantity"] = quantity

            with col4:

                line_total = (
                    item["price"] *
                    item["quantity"]
                )

                st.write(
                    money(line_total)
                )

                total += line_total

            with col5:

                if st.button(
                    "❌",
                    key=f"remove_{index}"
                ):

                    st.session_state.cart.pop(index)
                    st.rerun()

        st.divider()

        subtotal = cart_subtotal()

        col1, col2, col3 = st.columns(3)

        with col1:

            discount = st.number_input(
                "Discount",
                min_value=0.0,
                value=0.0,
                step=100.0
            )

        with col2:

            tax_percent = st.number_input(
                "Tax %",
                min_value=0.0,
                value=0.0,
                step=1.0
            )

        with col3:

            payment_method = st.selectbox(
                "Payment",
                [
                    "Cash",
                    "Card",
                    "Bank Transfer",
                    "JazzCash",
                    "Easypaisa",
                    "Credit"
                ]
            )

        tax = (
            max(subtotal - discount, 0)
            * tax_percent
            / 100
        )

        grand_total = (
            subtotal
            - discount
            + tax
        )

        st.markdown(
            f"## Total: {money(grand_total)}"
        )

        if st.button(
            "💳 COMPLETE SALE",
            type="primary",
            use_container_width=True
        ):

            conn = get_db()
            cur = conn.cursor()

            try:

                # Check stock first
                for item in st.session_state.cart:

                    stock_row = cur.execute(
                        """
                        SELECT stock
                        FROM products
                        WHERE id = ?
                        """,
                        (item["id"],)
                    ).fetchone()

                    if not stock_row:
                        raise Exception(
                            f"Product not found: {item['name']}"
                        )

                    if stock_row["stock"] < item["quantity"]:
                        raise Exception(
                            f"Insufficient stock: {item['name']}"
                        )

                cur.execute("""
                    INSERT INTO sales
                    (
                        subtotal,
                        discount,
                        tax,
                        total,
                        payment_method,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    subtotal,
                    discount,
                    tax,
                    grand_total,
                    payment_method,
                    datetime.now().isoformat()
                ))

                sale_id = cur.lastrowid

                for item in st.session_state.cart:

                    line_total = (
                        item["price"] *
                        item["quantity"]
                    )

                    cur.execute("""
                        INSERT INTO sale_items
                        (
                            sale_id,
                            product_id,
                            product_name,
                            quantity,
                            price,
                            cost,
                            total
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        sale_id,
                        item["id"],
                        item["name"],
                        item["quantity"],
                        item["price"],
                        item["cost"],
                        line_total
                    ))

                    cur.execute("""
                        UPDATE products
                        SET stock = stock - ?
                        WHERE id = ?
                    """, (
                        item["quantity"],
                        item["id"]
                    ))

                conn.commit()

                st.session_state.cart = []

                st.success(
                    f"Sale completed! Invoice #{sale_id}"
                )

                st.balloons()

            except Exception as e:

                conn.rollback()

                st.error(str(e))

            finally:

                conn.close()

# =========================================================
# PRODUCTS
# =========================================================

elif page == "👟 Products":

    st.title("👟 Product & Inventory Management")

    tabs
