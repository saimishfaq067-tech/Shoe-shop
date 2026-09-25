import streamlit as st
import sqlite3
from datetime import datetime
import pandas as pd

# =========================================================
# PAGE CONFIG
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

def db():
    return sqlite3.connect(DB, check_same_thread=False)


def setup_database():

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            brand TEXT,
            size TEXT,
            color TEXT,
            price REAL NOT NULL DEFAULT 0,
            cost REAL DEFAULT 0,
            stock INTEGER DEFAULT 0,
            sku TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice TEXT,
            customer TEXT,
            phone TEXT,
            subtotal REAL,
            discount REAL,
            total REAL,
            payment TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER,
            product_id INTEGER,
            name TEXT,
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


setup_database()


# =========================================================
# SESSION STATE
# =========================================================

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

if "cart" not in st.session_state:
    st.session_state.cart = []


# =========================================================
# FUNCTIONS
# =========================================================

def products():

    conn = db()

    df = pd.read_sql_query(
        "SELECT * FROM products ORDER BY id DESC",
        conn
    )

    conn.close()

    return df


def add_product(
    name,
    category,
    brand,
    size,
    color,
    price,
    cost,
    stock,
    sku
):

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO products
        (
            name,
            category,
            brand,
            size,
            color,
            price,
            cost,
            stock,
            sku,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        name,
        category,
        brand,
        size,
        color,
        price,
        cost,
        stock,
        sku,
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    ))

    conn.commit()
    conn.close()


def delete_product(product_id):

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM products WHERE id = ?",
        (product_id,)
    )

    conn.commit()
    conn.close()


def invoice_number():

    return "INV-" + datetime.now().strftime(
        "%Y%m%d%H%M%S"
    )


def complete_sale(
    customer,
    phone,
    discount,
    payment
):

    if not st.session_state.cart:
        return False, "Cart is empty."

    conn = db()
    cur = conn.cursor()

    try:

        subtotal = sum(
            item["price"] * item["quantity"]
            for item in st.session_state.cart
        )

        total = max(
            subtotal - discount,
            0
        )

        invoice = invoice_number()

        cur.execute("""
            INSERT INTO sales
            (
                invoice,
                customer,
                phone,
                subtotal,
                discount,
                total,
                payment,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            invoice,
            customer,
            phone,
            subtotal,
            discount,
            total,
            payment,
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        ))

        sale_id = cur.lastrowid

        for item in st.session_state.cart:

            cur.execute("""
                INSERT INTO sale_items
                (
                    sale_id,
                    product_id,
                    name,
                    size,
                    quantity,
                    price,
                    total
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                sale_id,
                item["id"],
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
                item["id"]
            ))

        conn.commit()

        st.session_state.cart = []

        return True, invoice

    except Exception as e:

        conn.rollback()

        return False, str(e)

    finally:

        conn.close()


# =========================================================
# STYLE
# =========================================================

st.markdown("""
<style>

.main-title {
    font-size: 34px;
    font-weight: 800;
}

.subtitle {
    color: #777;
    margin-bottom: 25px;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.title("👟 Shoe Shop")

    st.caption("Professional POS")

    st.divider()

    menu = [
        "Dashboard",
        "New Sale",
        "Products",
        "Add Product",
        "Sales",
        "Expenses"
    ]

    for item in menu:

        if st.button(
            item,
            use_container_width=True,
            key="menu_" + item
        ):

            st.session_state.page = item
            st.rerun()

    st.divider()

    st.caption("Shoe Shop POS v1.0")


# =========================================================
# DASHBOARD
# =========================================================

if st.session_state.page == "Dashboard":

    st.markdown(
        '<div class="main-title">'
        'Dashboard'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        'Shoe Shop Management System'
        '</div>',
        unsafe_allow_html=True
    )

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM products"
    )

    total_products = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(SUM(stock),0) FROM products"
    )

    total_stock = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(SUM(total),0) FROM sales"
    )

    total_sales = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(SUM(amount),0) FROM expenses"
    )

    total_expenses = cur.fetchone()[0]

    conn.close()

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Products",
        total_products
    )

    c2.metric(
        "Stock",
        total_stock
    )

    c3.metric(
        "Sales",
        f"Rs {total_sales:,.0f}"
    )

    c4.metric(
        "Expenses",
        f"Rs {total_expenses:,.0f}"
    )

    st.divider()

    st.subheader("📊 Business Summary")

    profit = total_sales - total_expenses

    st.write(
        f"**Estimated Balance:** Rs {profit:,.2f}"
    )

    df = products()

    if not df.empty:

        st.subheader("⚠️ Low Stock")

        low = df[df["stock"] <= 5]

        if low.empty:

            st.success(
                "No low-stock products."
            )

        else:

            st.dataframe(
                low[
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
# NEW SALE
# =========================================================

elif st.session_state.page == "New Sale":

    st.markdown(
        '<div class="main-title">'
        '🛒 New Sale'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        'Create customer invoice'
        '</div>',
        unsafe_allow_html=True
    )

    df = products()

    if df.empty:

        st.warning(
            "No products available. Add products first."
        )

    else:

        left, right = st.columns(
            [1.2, 1]
        )

        # -------------------------------------------------
        # PRODUCT SELECTOR
        # -------------------------------------------------

        with left:

            st.subheader(
                "Select Product"
            )

            options = {}

            for _, row in df.iterrows():

                label = (
                    f"{row['name']} | "
                    f"Size {row['size']} | "
                    f"Rs {row['price']:,.0f} | "
                    f"Stock {row['stock']}"
                )

                options[label] = int(
                    row["id"]
                )

            selected = st.selectbox(
                "Product",
                list(options.keys())
            )

            product_id = options[selected]

            product = df[
                df["id"] == product_id
            ].iloc[0]

            st.write(
                f"**Name:** {product['name']}"
            )

            st.write(
                f"**Brand:** {product['brand']}"
            )

            st.write(
                f"**Size:** {product['size']}"
            )

            st.write(
                f"**Color:** {product['color']}"
            )

            st.write(
                f"**Price:** Rs {product['price']:,.2f}"
            )

            stock = int(
                product["stock"]
            )

            if stock > 0:

                qty = st.number_input(
                    "Quantity",
                    min_value=1,
                    max_value=stock,
                    value=1
                )

                if st.button(
                    "➕ Add to Cart",
                    use_container_width=True
                ):

                    found = False

                    for item in st.session_state.cart:

                        if (
                            item["id"]
                            == product_id
                        ):

                            item["quantity"] += qty
                            found = True
                            break

                    if not found:

                        st.session_state.cart.append({
                            "id": product_id,
                            "name": product["name"],
                            "size": product["size"],
                            "price": float(
                                product["price"]
                            ),
                            "quantity": int(qty)
                        })

                    st.rerun()

            else:

                st.error(
                    "Out of stock."
                )

        # -------------------------------------------------
        # CART
        # -------------------------------------------------

        with right:

            st.subheader(
                "🧾 Cart"
            )

            if not st.session_state.cart:

                st.info(
                    "Cart is empty."
                )

            else:

                subtotal = 0

                for i, item in enumerate(
                    st.session_state.cart
                ):

                    item_total = (
                        item["price"]
                        * item["quantity"]
                    )

                    subtotal += item_total

                    st.markdown(
                        f"""
**{item['name']}**

Size: {item['size']}  
Quantity: {item['quantity']}  
Price: Rs {item['price']:,.2f}  
Total: Rs {item_total:,.2f}
"""
                    )

                    if st.button(
                        "Remove",
                        key=f"remove_{i}"
                    ):

                        st.session_state.cart.pop(
                            i
                        )

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
                    f"Subtotal: Rs {subtotal:,.2f}"
                )

                st.write(
                    f"Discount: Rs {discount:,.2f}"
                )

                st.markdown(
                    f"### Total: Rs {total:,.2f}"
                )

                st.divider()

                customer = st.text_input(
                    "Customer Name",
                    value="Walk-in Customer"
                )

                phone = st.text_input(
                    "Phone"
                )

                payment = st.selectbox(
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

                    success, result = complete_sale(
                        customer,
                        phone,
                        discount,
                        payment
                    )

                    if success:

                        st.success(
                            f"Sale completed! "
                            f"Invoice: {result}"
                        )

                        st.rerun()

                    else:

                        st.error(result)


# =========================================================
# PRODUCTS
# =========================================================

elif st.session_state.page == "Products":

    st.markdown(
        '<div class="main-title">'
        '📦 Products'
        '</div>',
        unsafe_allow_html=True
    )

    search = st.text_input(
        "🔎 Search Product"
    )

    df = products()

    if search:

        text = search.lower()

        df = df[
            df["name"]
            .astype(str)
            .str.lower()
            .str.contains(
                text,
                na=False
            )
        ]

    if df.empty:

        st.info(
            "No products found."
        )

    else:

        show = df[
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
        ]

        st.dataframe(
            show,
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        delete_id = st.number_input(
            "Product ID to delete",
            min_value=1,
            step=1
        )

        if st.button(
            "🗑️ Delete Product"
        ):

            delete_product(
                delete_id
            )

            st.success(
                "Product deleted."
            )

            st.rerun()


# =========================================================
# ADD PRODUCT
# =========================================================

elif st.session_state.page == "Add Product":

    st.markdown(
        '<div class="main-title">'
        '➕ Add Product'
        '</div>',
        unsafe_allow_html=True
    )

    with st.form(
        "product_form"
    ):

        c1, c2 = st.columns(2)

        with c1:

            name = st.text_input(
                "Product Name *"
            )

            category = st.text_input(
                "Category",
                value="Shoes"
            )

            brand = st.text_input(
                "Brand"
            )

            size = st.text_input(
                "Size"
            )

            color = st.text_input(
                "Color"
            )

        with c2:

            price = st.number_input(
                "Selling Price",
                min_value=0.0,
                step=100.0
            )

            cost = st.number_input(
                "Cost Price",
                min_value=0.0,
                step=100.0
            )

            stock = st.number_input(
                "Stock",
                min_value=0,
                step=1
            )

            sku = st.text_input(
                "SKU"
            )

        save = st.form_submit_button(
            "💾 Save Product",
            use_container_width=True
        )

        if save:

            if not name.strip():

                st.error(
                    "Product name is required."
                )

            else:

                add_product(
                    name,
                    category,
                    brand,
                    size,
                    color,
                    price,
                    cost,
                    stock,
                    sku
                )

                st.success(
                    "Product added successfully!"
                )


# =========================================================
# SALES HISTORY
# =========================================================

elif st.session_state.page == "Sales":

    st.markdown(
        '<div class="main-title">'
        '💰 Sales History'
        '</div>',
        unsafe_allow_html=True
    )

    conn = db()

    df = pd.read_sql_query(
        """
        SELECT
            invoice,
            customer,
            phone,
            subtotal,
            discount,
            total,
            payment,
            created_at
        FROM sales
        ORDER BY id DESC
        """,
        conn
    )

    conn.close()

    if df.empty:

        st.info(
            "No sales recorded yet."
        )

    else:

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# EXPENSES
# =========================================================

elif st.session_state.page == "Expenses":

    st.markdown(
        '<div class="main-title">'
        '💸 Expenses'
        '</div>',
        unsafe_allow_html=True
    )

    with st.form(
        "expense_form"
    ):

        title = st.text_input(
            "Expense"
        )

        amount = st.number_input(
            "Amount",
            min_value=0.0,
            step=100.0
        )

        note = st.text_area(
            "Note"
        )

        save = st.form_submit_bu
