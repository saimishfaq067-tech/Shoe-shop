import streamlit as st
import sqlite3
import pandas as pd
import io
from datetime import datetime, date

# Optional voice package
try:
    import speech_recognition as sr
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False


# =========================================================
# APP CONFIG
# =========================================================

st.set_page_config(
    page_title="ShoeShop Pro POS",
    page_icon="👟",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_FILE = "shoe_shop.db"


# =========================================================
# DATABASE
# =========================================================

def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():

    conn = get_connection()
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
            subtotal REAL DEFAULT 0,
            discount REAL DEFAULT 0,
            tax REAL DEFAULT 0,
            total REAL DEFAULT 0,
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
            amount REAL DEFAULT 0,
            category TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


init_database()


# =========================================================
# GENERAL FUNCTIONS
# =========================================================

def fetch_df(query, params=()):

    conn = get_connection()

    try:
        return pd.read_sql_query(
            query,
            conn,
            params=params
        )
    finally:
        conn.close()


def execute_query(query, params=()):

    conn = get_connection()

    try:
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def money(value):
    return f"Rs. {float(value):,.0f}"


def clean_text(value):
    return str(value).strip().lower()


# =========================================================
# DEMO DATA
# =========================================================

def add_demo_products():

    brands = [
        "Nike",
        "Adidas",
        "Puma",
        "Skechers",
        "Bata",
        "Servis",
        "Hush Puppies",
        "UrbanStep",
        "WalkPro",
        "RoyalFeet"
    ]

    categories = [
        "Running",
        "Casual",
        "Formal",
        "Sports",
        "Sneakers",
        "Sandals",
        "School",
        "Boots"
    ]

    colors = [
        "Black",
        "White",
        "Blue",
        "Red",
        "Brown",
        "Grey",
        "Green",
        "Navy"
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

    conn = get_connection()
    cur = conn.cursor()

    added = 0

    for i in range(1, 101):

        brand = brands[(i - 1) % len(brands)]
        category = categories[(i - 1) % len(categories)]
        color = colors[(i - 1) % len(colors)]
        size = sizes[(i - 1) % len(sizes)]

        name = f"{brand} {category} {i}"
        sku = f"SHOE-{i:04d}"
        barcode = f"8901000{i:05d}"

        purchase = 1800 + ((i * 127) % 4000)
        sale = purchase + 900 + ((i * 83) % 2500)
        stock = 5 + (i % 20)

        try:

            cur.execute("""
                INSERT INTO products (
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
                    created_at
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

            added += 1

        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()

    return added


# =========================================================
# SEARCH
# =========================================================

def search_products(search):

    products = fetch_df("""
        SELECT *
        FROM products
        ORDER BY id DESC
    """)

    if products.empty:
        return products

    search = clean_text(search)

    if not search:
        return products

    columns = [
        "name",
        "brand",
        "category",
        "size",
        "color",
        "sku",
        "barcode"
    ]

    mask = pd.Series(
        False,
        index=products.index
    )

    for column in columns:

        mask = mask | (
            products[column]
            .fillna("")
            .astype(str)
            .str.lower()
            .str.contains(
                search,
                regex=False
            )
        )

    results = products[mask]

    # Token search
    if results.empty:

        words = search.split()

        combined = products[
            columns
        ].fillna("").astype(str).agg(
            " ".join,
            axis=1
        ).str.lower()

        token_mask = combined.apply(
            lambda x: all(
                word in x
                for word in words
            )
        )

        results = products[token_mask]

    return results


# =========================================================
# VOICE SEARCH
# =========================================================

def recognize_voice(audio_bytes, language):

    if not VOICE_AVAILABLE:
        return ""

    try:

        recognizer = sr.Recognizer()

        audio_file = sr.AudioFile(
            io.BytesIO(audio_bytes)
        )

        with audio_file as source:

            audio = recognizer.record(source)

        result = recognizer.recognize_google(
            audio,
            language=language
        )

        return result

    except Exception:
        return ""


# =========================================================
# SESSION STATE
# =========================================================

if "cart" not in st.session_state:
    st.session_state.cart = []

if "search_text" not in st.session_state:
    st.session_state.search_text = ""


def add_to_cart(product_id):

    conn = get_connection()

    row = conn.execute("""
        SELECT *
        FROM products
        WHERE id = ?
    """, (product_id,)).fetchone()

    conn.close()

    if row is None:
        return

    for item in st.session_state.cart:

        if item["id"] == product_id:

            if item["quantity"] < row["stock"]:
                item["quantity"] += 1

            return

    if row["stock"] > 0:

        st.session_state.cart.append({
            "id": row["id"],
            "name": row["name"],
            "sku": row["sku"],
            "size": row["size"],
            "price": float(row["sale_price"]),
            "cost": float(row["purchase_price"]),
            "quantity": 1
        })


def cart_total():

    return sum(
        item["price"] * item["quantity"]
        for item in st.session_state.cart
    )


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown("# 👟 ShoeShop Pro")

    st.caption(
        "Professional Shoe Shop POS"
    )

    st.divider()

    page = st.radio(
        "MAIN MENU",
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

    st.markdown("### ⚡ Quick Action")

    if st.button(
        "➕ Add 100 Demo Products",
        use_container_width=True
    ):

        number = add_demo_products()

        st.success(
            f"{number} products added."
        )

        st.rerun()

    st.divider()

    st.caption(
        "ShoeShop Pro v1.0"
    )


# =========================================================
# DASHBOARD
# =========================================================

if page == "📊 Dashboard":

    st.title("📊 Dashboard")

    st.write(
        "Welcome to ShoeShop Pro."
    )

    today = date.today().isoformat()

    today_data = fetch_df("""
        SELECT
            COALESCE(SUM(total), 0) AS sales,
            COUNT(*) AS invoices
        FROM sales
        WHERE DATE(created_at) = ?
    """, (today,))

    product_count = fetch_df("""
        SELECT COUNT(*) AS total
        FROM products
    """)

    stock_count = fetch_df("""
        SELECT COALESCE(SUM(stock), 0) AS total
        FROM products
    """)

    low_stock = fetch_df("""
        SELECT COUNT(*) AS total
        FROM products
        WHERE stock <= 5
    """)

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Today's Sales",
        money(today_data.iloc[0]["sales"])
    )

    c2.metric(
        "Invoices",
        int(today_data.iloc[0]["invoices"])
    )

    c3.metric(
        "Total Products",
        int(product_count.iloc[0]["total"])
    )

    c4.metric(
        "Low Stock",
        int(low_stock.iloc[0]["total"])
    )

    st.divider()

    left, right = st.columns(2)

    with left:

        st.subheader("📦 Stock Overview")

        inventory = fetch_df("""
            SELECT
                brand,
                COUNT(*) AS products,
                SUM(stock) AS units
            FROM products
            GROUP BY brand
            ORDER BY units DESC
        """)

        if inventory.empty:

            st.info(
                "No products yet. Use 'Add 100 Demo Products'."
            )

        else:

            st.dataframe(
                inventory,
                use_container_width=True,
                hide_index=True
            )

    with right:

        st.subheader("⚠️ Low Stock")

        low = fetch_df("""
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

            st.success(
                "No low-stock products."
            )

        else:

            st.dataframe(
                low,
                use_container_width=True,
                hide_index=True
            )

    st.divider()

    st.subheader("💰 Recent Sales")

    recent = fetch_df("""
        SELECT
            id AS invoice,
            total,
            payment_method,
            created_at
        FROM sales
        ORDER BY id DESC
        LIMIT 10
    """)

    if recent.empty:

        st.info(
            "No sales yet."
        )

    else:

        st.dataframe(
            recent,
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# POS
# =========================================================

elif page == "🛒 POS":

    st.title("🛒 Point of Sale")

    st.markdown(
        "### 🔎 Search your product"
    )

    col1, col2 = st.columns(
        [4, 1]
    )

    with col1:

        search = st.text_input(
            "Product Name / Brand / SKU / Barcode / Size",
            value=st.session_state.search_text,
            placeholder="Example: Nike, Running, 42, SHOE-0001"
        )

        st.session_state.search_text = search

    with col2:

        language = st.selectbox(
            "Voice Language",
            [
                "English",
                "Urdu"
            ]
        )

        if VOICE_AVAILABLE:

            audio = st.audio_input(
                "🎙️ Speak",
                key="voice_input"
            )

            if audio is not None:

                lang = (
                    "ur-PK"
                    if language == "Urdu"
                    else "en-US"
                )

                voice_text = recognize_voice(
                    audio.getvalue(),
                    lang
                )

                if voice_text:

                    st.session_state.search_text = voice_text

                    st.success(
                        f"Voice: {voice_text}"
                    )

                    st.rerun()

        else:

            st.warning(
                "SpeechRecognition is not installed."
            )

    results = search_products(
        st.session_state.search_text
    )

    st.write(
        f"**{len(results)} products found**"
    )

    if results.empty:

        st.info(
            "No product found."
        )

    else:

        for _, product in results.head(100).iterrows():

            c1, c2, c3, c4, c5, c6 = st.columns(
                [3, 1, 1, 1, 1, 1]
            )

            with c1:

                st.markdown(
                    f"**{product['name']}**"
                )

                st.caption(
                    f"{product['brand']} • "
                    f"{product['category']} • "
                    f"{product['sku']}"
                )

            with c2:

                st.write(
                    f"Size: {product['size']}"
                )

            with c3:

                st.write(
                    f"Stock: {product['stock']}"
                )

            with c4:

                st.write(
                    money(product["sale_price"])
                )

            with c5:

                st.write(
                    product["color"]
                )

            with c6:

                if st.button(
                    "ADD",
                    key=f"cart_{product['id']}"
                ):

                    add_to_cart(
                        int(product["id"])
                    )

                    st.rerun()

    st.divider()

    st.subheader("🛍️ Cart")

    if not st.session_state.cart:

        st.info(
            "Cart is empty."
        )

    else:

        for index, item in enumerate(
            st.session_state.cart
        ):

            c1, c2, c3, c4, c5 = st.columns(
                [3, 1, 1, 1, 1]
            )

            with c1:
                st.write(item["name"])

            with c2:
                st.write(
                    money(item["price"])
                )

            with c3:

                qty = st.number_input(
                    "Qty",
                    min_value=1,
                    max_value=100,
                    value=item["quantity"],
                    key=f"quantity_{index}"
                )

                item["quantity"] = qty

            with c4:

                total = (
                    item["price"]
                    * item["quantity"]
                )

                st.write(
                    money(total)
                )

            with c5:

                if st.button(
                    "Remove",
                    key=f"remove_{index}"
                ):

                    st.session_state.cart.pop(
                        index
                    )

                    st.rerun()

        st.divider()

        subtotal = cart_total()

        c1, c2, c3 = st.columns(3)

        with c1:

            discount = st.number_input(
                "Discount",
                min_value=0.0,
                value=0.0,
                step=100.0
            )

        with c2:

            tax_percent = st.number_input(
                "Tax %",
                min_value=0.0,
                value=0.0,
                step=1.0
            )

        with c3:

            payment = st.selectbox(
                "Payment Method",
                [
                    "Cash",
                    "Card",
                    "Bank Transfer",
                    "JazzCash",
                    "Easypaisa",
                    "Credit"
                ]
            )

        taxable = max(
            subtotal - discount,
            0
        )

        tax = (
            taxable
            * tax_percent
            / 100
        )

        grand_total = (
            taxable + tax
        )

        st.markdown(
            f"# Total: {money(grand_total)}"
        )

        if st.button(
            "💳 COMPLETE SALE",
            type="primary",
            use_container_width=True
        ):

            conn = get_connection()
            cur = conn.cursor()

            try:

                # Check stock
                for item in st.session_state.cart:

                    stock = cur.execute("""
                        SELECT stock
                        FROM products
                        WHERE id = ?
                    """, (
                        item["id"],
                    )).fetchone()

                    if stock is None:

                        raise Exception(
                            f"Product not found: {item['name']}"
                        )

                    if stock["stock"] < item["quantity"]:

                        raise Exception(
                            f"Not enough stock: {item['name']}"
                        )

                # Create invoice
                cur.execute("""
                    INSERT INTO sales (
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
                    payment,
                    datetime.now().isoformat()
                ))

                sale_id = cur.lastrowid

                # Sale items
                for item in st.session_state.cart:

                    line_total = (
                        item["price"]
                        * item["quantity"]
                    )

                    cur.execute("""
                        INSERT INTO sale_items (
                            sale_id,
                            product_id,
                            product_name,
                            quantity,
                            price,
                            cost,
                            total
                        )
                        VALUE
