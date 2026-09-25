import streamlit as st
import sqlite3
from datetime import datetime
import pandas as pd

# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="Shoe Shop POS",
    page_icon="👟",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_FILE = "shoe_shop.db"


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    return sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )


# ============================================================
# DATABASE SETUP
# ============================================================

def get_table_columns(table_name):
    conn = get_connection()

    try:
        info = pd.read_sql_query(
            f"PRAGMA table_info({table_name})",
            conn
        )

        if info.empty:
            return []

        return info["name"].tolist()

    finally:
        conn.close()


def add_missing_column(table_name, column_name, column_type):
    columns = get_table_columns(table_name)

    if column_name in columns:
        return

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN {column_name} {column_type}"
        )

        conn.commit()

    except Exception:
        pass

    finally:
        conn.close()


def init_database():

    conn = get_connection()
    cur = conn.cursor()

    # Products
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            category TEXT,
            brand TEXT,
            size TEXT,
            color TEXT,
            price REAL DEFAULT 0,
            cost_price REAL DEFAULT 0,
            stock INTEGER DEFAULT 0,
            sku TEXT,
            image TEXT,
            created_at TEXT
        )
    """)

    # Sales
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT,
            customer_name TEXT,
            customer_phone TEXT,
            subtotal REAL DEFAULT 0,
            discount REAL DEFAULT 0,
            total REAL DEFAULT 0,
            payment_method TEXT,
            created_at TEXT
        )
    """)

    # Sale items
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER,
            product_id INTEGER,
            product_name TEXT,
            size TEXT,
            quantity INTEGER,
            price REAL,
            total REAL
        )
    """)

    # Expenses
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            amount REAL DEFAULT 0,
            note TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()

    # --------------------------------------------------------
    # Make old databases compatible
    # --------------------------------------------------------

    product_columns = {
        "name": "TEXT",
        "category": "TEXT",
        "brand": "TEXT",
        "size": "TEXT",
        "color": "TEXT",
        "price": "REAL DEFAULT 0",
        "cost_price": "REAL DEFAULT 0",
        "stock": "INTEGER DEFAULT 0",
        "sku": "TEXT",
        "image": "TEXT",
        "created_at": "TEXT"
    }

    for column, data_type in product_columns.items():
        add_missing_column(
            "products",
            column,
            data_type
        )

    sale_columns = {
        "invoice_no": "TEXT",
        "customer_name": "TEXT",
        "customer_phone": "TEXT",
        "subtotal": "REAL DEFAULT 0",
        "discount": "REAL DEFAULT 0",
        "total": "REAL DEFAULT 0",
        "payment_method": "TEXT",
        "created_at": "TEXT"
    }

    for column, data_type in sale_columns.items():
        add_missing_column(
            "sales",
            column,
            data_type
        )

    sale_item_columns = {
        "sale_id": "INTEGER",
        "product_id": "INTEGER",
        "product_name": "TEXT",
        "size": "TEXT",
        "quantity": "INTEGER",
        "price": "REAL DEFAULT 0",
        "total": "REAL DEFAULT 0"
    }

    for column, data_type in sale_item_columns.items():
        add_missing_column(
            "sale_items",
            column,
            data_type
        )

    expense_columns = {
        "title": "TEXT",
        "amount": "REAL DEFAULT 0",
        "note": "TEXT",
        "created_at": "TEXT"
    }

    for column, data_type in expense_columns.items():
        add_missing_column(
            "expenses",
            column,
            data_type
        )


init_database()


# ============================================================
# PRODUCT DATA
# ============================================================

def get_products(search=""):

    conn = get_connection()

    try:

        df = pd.read_sql_query(
            "SELECT * FROM products ORDER BY id DESC",
            conn
        )

        # ----------------------------------------------------
        # Compatibility with old column names
        # ----------------------------------------------------

        rename_map = {}

        if "product_name" in df.columns and "name" not in df.columns:
            rename_map["product_name"] = "name"

        if (
            "selling_price" in df.columns
            and "price" not in df.columns
        ):
            rename_map["selling_price"] = "price"

        if (
            "sale_price" in df.columns
            and "price" not in df.columns
        ):
            rename_map["sale_price"] = "price"

        if (
            "quantity" in df.columns
            and "stock" not in df.columns
        ):
            rename_map["quantity"] = "stock"

        if (
            "product_category" in df.columns
            and "category" not in df.columns
        ):
            rename_map["product_category"] = "category"

        if (
            "product_brand" in df.columns
            and "brand" not in df.columns
        ):
            rename_map["product_brand"] = "brand"

        if rename_map:
            df = df.rename(
                columns=rename_map
            )

        # ----------------------------------------------------
        # Guarantee required columns
        # ----------------------------------------------------

        defaults = {
            "name": "",
            "category": "",
            "brand": "",
            "size": "",
            "color": "",
            "price": 0,
            "cost_price": 0,
            "stock": 0,
            "sku": "",
            "image": "",
            "created_at": ""
        }

        for column, default in defaults.items():

            if column not in df.columns:
                df[column] = default

        # ----------------------------------------------------
        # Safe numeric conversion
        # ----------------------------------------------------

        df["price"] = pd.to_numeric(
            df["price"],
            errors="coerce"
        ).fillna(0)

        df["cost_price"] = pd.to_numeric(
            df["cost_price"],
            errors="coerce"
        ).fillna(0)

        df["stock"] = pd.to_numeric(
            df["stock"],
            errors="coerce"
        ).fillna(0)

        # ----------------------------------------------------
        # Search
        # ----------------------------------------------------

        if search.strip():

            s = search.strip().lower()

            mask = (
                df["name"]
                .astype(str)
                .str.lower()
                .str.contains(s, na=False)
            )

            mask |= (
                df["brand"]
                .astype(str)
                .str.lower()
                .str.contains(s, na=False)
            )

            mask |= (
                df["category"]
                .astype(str)
                .str.lower()
                .str.contains(s, na=False)
            )

            mask |= (
                df["sku"]
                .astype(str)
                .str.lower()
                .str.contains(s, na=False)
            )

            df = df[mask]

        return df

    except Exception:

        return pd.DataFrame(
            columns=[
                "id",
                "name",
                "category",
                "brand",
                "size",
                "color",
                "price",
                "cost_price",
                "stock",
                "sku",
                "image",
                "created_at"
            ]
        )

    finally:
        conn.close()


# ============================================================
# PRODUCT BY ID
# ============================================================

def get_product_by_id(product_id):

    df = get_products()

    if df.empty:
        return None

    result = df[
        df["id"].astype(int) == int(product_id)
    ]

    if result.empty:
        return None

    return result.iloc[0].to_dict()


# ============================================================
# ADD PRODUCT
# ============================================================

def add_product(
    name,
    category,
    brand,
    size,
    color,
    price,
    cost_price,
    stock,
    sku,
    image
):

    conn = get_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO products
            (
                name,
                category,
                brand,
                size,
                color,
                price,
                cost_price,
                stock,
                sku,
                image,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            category,
            brand,
            size,
            color,
            price,
            cost_price,
            stock,
            sku,
            image,
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        ))

        conn.commit()

        return True, "Product added successfully."

    except Exception as e:

        conn.rollback()

        return False, str(e)

    finally:
        conn.close()


# ============================================================
# UPDATE PRODUCT
# ============================================================

def update_product(
    product_id,
    name,
    category,
    brand,
    size,
    color,
    price,
    cost_price,
    stock,
    sku,
    image
):

    conn = get_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            UPDATE products
            SET
                name = ?,
                category = ?,
                brand = ?,
                size = ?,
                color = ?,
                price = ?,
                cost_price = ?,
                stock = ?,
                sku = ?,
                image = ?
            WHERE id = ?
        """, (
            name,
            category,
            brand,
            size,
            color,
            price,
            cost_price,
            stock,
            sku,
            image,
            product_id
        ))

        conn.commit()

        return True, "Product updated successfully."

    except Exception as e:

        conn.rollback()

        return False, str(e)

    finally:
        conn.close()


# ============================================================
# DELETE PRODUCT
# ============================================================

def delete_product(product_id):

    conn = get_connection()
    cur = conn.cursor()

    try:

        cur.execute(
            "DELETE FROM products WHERE id = ?",
            (product_id,)
        )

        conn.commit()

        return True

    except Exception:

        conn.rollback()

        return False

    finally:
        conn.close()


# ============================================================
# DASHBOARD STATS
# ============================================================

def get_dashboard_stats():

    conn = get_connection()
    cur = conn.cursor()

    try:

        cur.execute(
            "SELECT COUNT(*) FROM products"
        )

        products = cur.fetchone()[0]

        cur.execute(
            "SELECT COALESCE(SUM(stock), 0) FROM products"
        )

        stock = cur.fetchone()[0]

        cur.execute(
            "SELECT COALESCE(SUM(total), 0) FROM sales"
        )

        sales = cur.fetchone()[0]

        cur.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses"
        )

        expenses = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*)
            FROM sales
            WHERE DATE(created_at) = DATE('now')
        """)

        today_orders = cur.fetchone()[0]

        return (
            products,
            stock,
            sales,
            expenses,
            today_orders
        )

    finally:
        conn.close()


# ============================================================
# INVOICE NUMBER
# ============================================================

def generate_invoice():

    return (
        "INV-"
        + datetime.now().strftime(
            "%Y%m%d%H%M%S%f"
        )[:-3]
    )


# ============================================================
# SAVE SALE
# ============================================================

def save_sale(
    customer_name,
    customer_phone,
    cart,
    discount,
    payment_method
):

    conn = get_connection()
    cur = conn.cursor()

    try:

        subtotal = sum(
            item["price"] * item["quantity"]
            for item in cart
        )

        total = max(
            subtotal - discount,
            0
        )

        invoice_no = generate_invoice()

        cur.execute("""
            INSERT INTO sales
            (
                invoice_no,
                customer_name,
                customer_phone,
                subtotal,
                discount,
                total,
                payment_method,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            invoice_no,
            customer_name,
            customer_phone,
            subtotal,
            discount,
            total,
            payment_method,
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        ))

        sale_id = cur.lastrowid

        for item in cart:

            cur.execute("""
                INSERT INTO sale_items
                (
                    sale_id,
                    product_id,
                    product_name,
                    size,
                    quantity,
                    price,
                    total
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                sale_id,
                item["product_id"],
                item["name"],
                item["size"],
                item["quantity"],
                item["price"],
                item["price"] * item["quantity"]
            ))

            cur.execute("""
                UPDATE products
                SET stock = stock - ?
                WHERE id = ?
            """, (
                item["quantity"],
                item["product_id"]
            ))

        conn.commit()

        return True, invoice_no, total

    except Exception as e:

        conn.rollback()

        return False, str(e), 0

    finally:
        conn.close()


# ============================================================
# EXPENSE
# ============================================================

def add_expense(
    title,
    amount,
    note
):

    conn = get_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO expenses
            (
                title,
                amount,
                note,
                created_at
            )
            VALUES (?, ?, ?, ?)
        """, (
            title,
            amount,
            note,
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        ))

        conn.commit()

        return True

    except Exception:

        conn.rollback()

        return False

    finally:
        conn.close()


# ============================================================
# SESSION STATE
# ============================================================

if "cart" not in st.session_state:
    st.session_state.cart = []

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"


# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

.main-title {
    font-size: 32px;
    font-weight: 800;
    margin-bottom: 5px;
}

.sub-title {
    color: #777;
    margin-bottom: 25px;
}

.stButton > button {
    border-radius: 10px;
    font-weight: 600;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("# 👟 Shoe Shop")

    st.caption("Professional POS System")

    st.divider()

    pages = [
        "Dashboard",
        "POS / New Sale",
        "Products",
        "Add Product",
        "Sales",
        "Expenses",
        "Reports"
    ]

    for page in pages:

        if st.button(
            page,
            use_container_width=True,
            key=f"menu_{page}"
        ):

            st.session_state.page = page
            st.rerun()

    st.divider()

    st.caption("Shoe Shop POS v1.0")


# ============================================================
# DASHBOARD
# ============================================================

if st.session_state.page == "Dashboard":

    st.markdown(
        '<div class="main-title">Dashboard</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="sub-title">'
        'Welcome to your Shoe Shop POS'
        '</div>',
        unsafe_allow_html=True
    )

    (
        total_products,
        total_stock,
        total_sales,
        expenses,
        today_orders
    ) = get_dashboard_stats()

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "Products",
            total_products
        )

    with c2:
        st.metric(
            "Total Stock",
            total_stock
        )

    with c3:
        st.metric(
            "Total Sales",
            f"Rs {total_sales:,.0f}"
        )

    with c4:
        st.metric(
            "Today's Orders",
            today_orders
        )

    st.divider()

    c1, c2 = st.columns(2)

    with c1:

        st.subheader("💰 Financial Overview")

        st.write(
            f"Total Sales: Rs {total_sales:,.2f}"
        )

        st.write(
            f"Expenses: Rs {expenses:,.2f}"
        )

        st.write(
            f"Sales - Expenses: "
            f"Rs {total_sales - expenses:,.2f}"
        )

    with c2:

        st.subheader("📦 Inventory")

        products_df = get_products()

        if products_df.empty:

            st.info(
                "No products added yet."
            )

        else:

            low_stock = products_df[
                products_df["stock"] <= 5
            ]

            if low_stock.empty:

                st.success(
                    "All products have healthy stock."
                )

            else:

                st.warning(
                    f"{len(low_stock)} "
                    "product(s)
