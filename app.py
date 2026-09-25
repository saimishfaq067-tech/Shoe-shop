import streamlit as st
import sqlite3
from datetime import datetime
from pathlib import Path
import pandas as pd

# =========================================================
# SHOE SHOP POS SYSTEM
# =========================================================

st.set_page_config(
    page_title="Shoe Shop POS",
    page_icon="👟",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# DATABASE
# =========================================================

DB_FILE = "shoe_shop.db"


def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)


def init_database():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            brand TEXT,
            size TEXT,
            color TEXT,
            price REAL DEFAULT 0,
            cost_price REAL DEFAULT 0,
            stock INTEGER DEFAULT 0,
            sku TEXT UNIQUE,
            image TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT UNIQUE,
            customer_name TEXT,
            customer_phone TEXT,
            subtotal REAL DEFAULT 0,
            discount REAL DEFAULT 0,
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
            size TEXT,
            quantity INTEGER,
            price REAL,
            total REAL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            amount REAL,
            note TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


init_database()


# =========================================================
# HELPERS
# =========================================================

def generate_invoice():
    now = datetime.now()
    return "INV-" + now.strftime("%Y%m%d%H%M%S")


def get_products(search=""):
    conn = get_connection()

    if search:
        query = """
            SELECT *
            FROM products
            WHERE name LIKE ?
               OR brand LIKE ?
               OR category LIKE ?
               OR sku LIKE ?
            ORDER BY id DESC
        """
        value = f"%{search}%"
        df = pd.read_sql_query(
            query,
            conn,
            params=(value, value, value, value)
        )
    else:
        df = pd.read_sql_query(
            "SELECT * FROM products ORDER BY id DESC",
            conn
        )

    conn.close()
    return df


def get_product_by_id(product_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    )

    row = cur.fetchone()
    conn.close()

    return row


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
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        conn.commit()
        return True, "Product added successfully."

    except sqlite3.IntegrityError:
        return False, "SKU already exists."

    except Exception as e:
        return False, str(e)

    finally:
        conn.close()


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
        return False, str(e)

    finally:
        conn.close()


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
        return False

    finally:
        conn.close()


def get_dashboard_stats():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM products")
    total_products = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(stock), 0) FROM products")
    total_stock = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(total), 0) FROM sales")
    total_sales = cur.fetchone()[0]

    cur.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
    """)
    expenses = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM sales
        WHERE DATE(created_at) = DATE('now')
    """)
    today_orders = cur.fetchone()[0]

    conn.close()

    return (
        total_products,
        total_stock,
        total_sales,
        expenses,
        today_orders
    )


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

        total = max(subtotal - discount, 0)
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
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        sale_id = cur.lastrowid

        for item in cart:
            product_id = item["product_id"]
            quantity = item["quantity"]

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
                product_id,
                item["name"],
                item["size"],
                quantity,
                item["price"],
                item["price"] * quantity
            ))

            cur.execute("""
                UPDATE products
                SET stock = stock - ?
                WHERE id = ?
            """, (
                quantity,
                product_id
            ))

        conn.commit()

        return True, invoice_no, total

    except Exception as e:
        conn.rollback()
        return False, str(e), 0

    finally:
        conn.close()


def add_expense(title, amount, note):
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
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        conn.commit()
        return True

    except Exception:
        return False

    finally:
        conn.close()


# =========================================================
# SESSION STATE
# =========================================================

if "cart" not in st.session_state:
    st.session_state.cart = []

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"


# =========================================================
# CSS
# =========================================================

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

.metric-card {
    padding: 20px;
    border-radius: 15px;
    background: #ffffff;
    border: 1px solid #eeeeee;
    box-shadow: 0 3px 15px rgba(0,0,0,0.05);
}

.product-card {
    padding: 18px;
    border-radius: 15px;
    border: 1px solid #eeeeee;
    margin-bottom: 12px;
}

.stButton > button {
    border-radius: 10px;
    font-weight: 600;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# SIDEBAR
# =========================================================

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


# =========================================================
# DASHBOARD
# =========================================================

if st.session_state.page == "Dashboard":

    st.markdown(
        '<div class="main-title">Dashboard</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="sub-title">Welcome to your Shoe Shop POS</div>',
        unsafe_allow_html=True
    )

    (
        total_products,
        total_stock,
        total_sales,
        expenses,
        today_orders
    ) = get_dashboard_stats()

    profit_estimate = total_sales - expenses

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
            f"**Total Sales:** Rs {total_sales:,.2f}"
        )

        st.write(
            f"**Expenses:** Rs {expenses:,.2f}"
        )

        st.write(
            f"**Sales - Expenses:** Rs {profit_estimate:,.2f}"
        )

    with c2:
        st.subheader("📦 Inventory")

        products_df = get_products()

        if products_df.empty:
            st.info("No products added yet.")
        else:
            low_stock = products_df[
                products_df["stock"] <= 5
            ]

            if low_stock.empty:
                st.success("All products have healthy stock.")
            else:
                st.warning(
                    f"{len(low_stock)} product(s) have low stock."
                )

                st.dataframe(
                    low_stock[
                        [
                            "name",
                            "brand",
                            "size",
                            "stock"
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True
                )


# =========================================================
# POS
# =========================================================

elif st.session_state.page == "POS / New Sale":

    st.markdown(
        '<div class="main-title">🛒 New Sale</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="sub-title">Create a new customer invoice</div>',
        unsafe_allow_html=True
    )

    products_df = get_products()

    if products_df.empty:
        st.warning("Please add products first.")
        st.stop()

    left, right = st.columns([1.4, 1])

    with left:

        st.subheader("Add Product")

        product_options = {}

        for _, row in products_df.iterrows():

            label = (
                f"{row['name']} | "
                f"Size {row['size']} | "
                f"Rs {row['price']:,.0f} | "
                f"Stock {row['stock']}"
            )

            product_options[label] = int(row["id"])

        selected_label = st.selectbox(
            "Select product",
            list(product_options.keys())
        )

        selected_id = product_options[selected_label]

        product = get_product_by_id(selected_id)

        if product:

            (
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
                image,
                created_at
            ) = product

            st.write(f"**Product:** {name}")
            st.write(f"**Brand:** {brand}")
            st.write(f"**Size:** {size}")
            st.write(f"**Color:** {color}")
            st.write(f"**Price:** Rs {price:,.2f}")
            st.write(f"**Available:** {stock}")

            quantity = st.number_input(
                "Quantity",
                min_value=1,
                max_value=max(int(stock), 1),
                value=1,
                step=1
            )

            if st.button(
                "➕ Add to Cart",
                use_container_width=True
            ):

                found = False

                for item in st.session_state.cart:

                    if item["product_id"] == product_id:

                        if (
                            item["quantity"] + quantity
                            <= stock
                        ):
                            item["quantity"] += quantity
                            found = True

                        else:
                            st.error("Not enough stock.")

                        break

                if not found:

                    if quantity <= stock:

                        st.session_state.cart.append({
                            "product_id": product_id,
                            "name": name,
                            "size": size,
                            "price": float(price),
                            "quantity": int(quantity)
                        })

                    else:
                        st.error("Not enough stock.")

                st.rerun()

    with right:

        st.subheader("🧾 Cart")

        if not st.session_state.cart:

            st.info("Cart is empty.")

        else:

            subtotal = 0

            for index, item in enumerate(
                st.session_state.cart
            ):

                item_total = (
                    item["price"] *
                    item["quantity"]
                )

                subtotal += item_total

                st.markdown(
                    f"""
                    **{item['name']}**
                    
                    Size: {item['size']}  
                    Qty: {item['quantity']}  
                    Price: Rs {item['price']:,.2f}  
                    Total: Rs {item_total:,.2f}
                    """
                )

                if st.button(
                    "Remove",
                    key=f"remove_{index}"
                ):
                    st.session_state.cart.pop(index)
                    st.rerun()

                st.divider()

            discount = st.number_input(
                "Discount",
                min_value=0.0,
                value=0.0,
                step=100.0
            )

            total = max(
                subtotal - discount,
                0
            )

            st.write(
                f"**Subtotal:** Rs {subtotal:,.2f}"
            )

            st.write(
                f"**Discount:** Rs {discount:,.2f}"
            )

            st.markdown(
                f"### Total: Rs {total:,.2f}"
            )

            st.divider()

            customer_name = st.text_input(
                "Customer Name"
            )

            customer_phone = st.text_input(
                "Customer Phone"
            )

            payment_method = st.selectbox(
                "Payment Method",
                [
                    "Cash",
                    "JazzCash",
                    "EasyPaisa",
                    "Bank Transfer",
                    "Card"
                ]
            )

            if st.button(
                "✅ Complete Sale",
                use_container_width=True
            ):

                if not customer_name.strip():
                    customer_name = "Walk-in Customer"

                success, invoice, final_total = save_sale(
                    customer_name,
                    customer_phone,
                    st.session_state.cart,
                    discount,
                    payment_method
                )

                if success:

                    st.success(
                        f"Sale completed! Invoice: {invoice}"
                    )

                    st.session_state.cart = []

                    st.rerun()

                else:

                    st.error(
                        f"Sale failed: {invoice}"
                    )


# =========================================================
# PRODUCTS
# =========================================================

elif st.session_state.page == "Products":

    st.markdown(
        '<div class="main-title">📦 Products</div>',
        unsafe_allow_html=True
    )

    search = st.text_input(
        "🔎 Search products",
        placeholder="Search by name, brand, category or SKU..."
    )

    df = get_products(search)

    if df.empty:

        st.info("No products found.")

    else:

        display_df = df[
            [
                "id",
                "name",
                "category",
                "brand",
                "size",
                "color",
                "price",
                "stock",
                "sku"
            ]
        ].copy()

        display_df["price"] = display_df[
            "price"
        ].apply(
            la 
        )
