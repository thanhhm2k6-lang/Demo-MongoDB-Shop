"""Giao diện desktop để xem dữ liệu của demo MongoDB."""
import threading
import tkinter as tk
from datetime import datetime, timedelta, timezone
from tkinter import messagebox, ttk

from bson.json_util import dumps
from pymongo.errors import PyMongoError

from shop_demo import (
    DB_NAME,
    delete_customer,
    load_customers,
    load_demo_data,
    query_orders as fetch_orders,
    query_products as fetch_products,
    save_product,
    save_customer,
    update_order_status,
)

TABLES = {
    "customers": {
        "title": "Khách hàng",
        "columns": ("name", "email", "city"),
        "headings": ("Tên khách hàng", "Email", "Thành phố"),
        "widths": (190, 250, 140),
    },
    "products": {
        "title": "Sản phẩm",
        "columns": ("sku", "name", "category", "price", "stock", "rating"),
        "headings": ("SKU", "Tên sản phẩm", "Loại", "Giá", "Tồn kho", "Điểm"),
        "widths": (100, 220, 110, 130, 90, 80),
    },
    "orders": {
        "title": "Đơn hàng",
        "columns": ("customer", "email", "status", "items", "total", "created"),
        "headings": (
            "Khách hàng", "Email", "Trạng thái", "Số mặt hàng", "Tổng tiền", "Ngày tạo"
        ),
        "widths": (190, 230, 130, 100, 160, 210),
    },
    "reviews": {
        "title": "Đánh giá",
        "columns": ("customer", "rating", "comment", "created"),
        "headings": ("Khách hàng", "Điểm", "Nội dung", "Ngày tạo"),
        "widths": (170, 70, 390, 220),
    },
}


def format_price(value):
    return f"{value:,.0f} đ"


def row_values(table_name, record, customer=None):
    if table_name == "customers":
        return (
            record.get("name", ""),
            record.get("email", ""),
            record.get("address", {}).get("city", ""),
        )
    if table_name == "products":
        category_names = {
            "book": "Sách",
            "laptop": "Laptop",
            "clothing": "Quần áo",
        }
        return (
            record.get("sku", ""),
            record.get("name", ""),
            category_names.get(record.get("category"), record.get("category", "")),
            format_price(record.get("price", 0)),
            record.get("stock", 0),
            record.get("ratingAvg", 0),
        )
    if table_name == "orders":
        status_names = {
            "paid": "Đã thanh toán",
            "shipped": "Đang giao",
            "done": "Hoàn tất",
        }
        return (
            customer.get("name", "Không tìm thấy khách hàng") if customer else "Không tìm thấy khách hàng",
            customer.get("email", "") if customer else "",
            status_names.get(record.get("status"), record.get("status", "")),
            len(record.get("items", [])),
            format_price(record.get("totalAmount", 0)),
            str(record.get("createdAt", ""))[:19],
        )
    return (
        record.get("customerName", ""),
        record.get("rating", ""),
        record.get("comment", ""),
        str(record.get("createdAt", ""))[:19],
    )


def launch_ui():
    root = tk.Tk()
    root.title("Cửa hàng mẫu | MongoDB")
    root.geometry("1120x790")
    root.minsize(900, 650)

    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    style.configure("Treeview", rowheight=30, font=("", 10))
    style.configure("Treeview.Heading", font=("", 10, "bold"))
    style.configure("Title.TLabel", font=("", 21, "bold"))
    style.configure("Section.TLabel", font=("", 11, "bold"))

    page = ttk.Frame(root, padding=(22, 18))
    page.pack(fill="both", expand=True)
    page.columnconfigure(0, weight=1)
    page.rowconfigure(3, weight=3)
    page.rowconfigure(5, weight=2)

    ttk.Label(page, text="Cửa hàng mẫu MongoDB", style="Title.TLabel").grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(
        page,
        text=f"Dữ liệu cửa hàng · MongoDB “{DB_NAME}”",
    ).grid(row=1, column=0, sticky="w", pady=(5, 8))

    status = tk.StringVar(value="Đang tải dữ liệu...")
    data_by_table = {name: [] for name in TABLES}
    trees = {}
    action_buttons = []
    detail_text = None
    counts = {}
    customer_search = tk.StringVar()
    product_category = tk.StringVar(value="Tất cả")
    product_min_price = tk.StringVar()
    product_max_price = tk.StringVar()
    product_result_count = tk.StringVar(value="0 kết quả")
    order_start_date = tk.StringVar()
    order_end_date = tk.StringVar()
    order_customer_query = tk.StringVar()
    order_result_count = tk.StringVar(value="0 kết quả")
    customers_by_id = {}
    product_display_records = []
    order_display_records = []
    all_data_collection = tk.StringVar(value="customers")
    all_data_count = tk.StringVar(value="0 bản ghi")
    all_data_text = None

    header_actions = ttk.Frame(page)
    header_actions.grid(row=0, column=1, rowspan=2, sticky="e")

    def set_detail(text):
        detail_text.configure(state="normal")
        detail_text.delete("1.0", "end")
        detail_text.insert("1.0", text)
        detail_text.configure(state="disabled")

    def set_status(text):
        status.set(text)

    def render_customers():
        tree = trees.get("customers")
        if tree is None:
            return
        query = customer_search.get().strip().casefold()
        tree.delete(*tree.get_children())
        for index, customer in enumerate(data_by_table["customers"]):
            searchable = " ".join((
                customer.get("name", ""),
                customer.get("email", ""),
                customer.get("address", {}).get("city", ""),
                customer.get("address", {}).get("street", ""),
            )).casefold()
            if query and query not in searchable:
                continue
            tree.insert(
                "",
                "end",
                iid=str(index),
                values=row_values("customers", customer),
            )

    def render_products(records):
        product_display_records[:] = records
        tree = trees.get("products")
        if tree is None:
            return
        tree.delete(*tree.get_children())
        for index, product in enumerate(records):
            tree.insert(
                "",
                "end",
                iid=str(index),
                values=row_values("products", product),
            )
        product_result_count.set(f"{len(records):,} kết quả")

    def render_orders(records):
        order_display_records[:] = records
        tree = trees.get("orders")
        if tree is None:
            return
        tree.delete(*tree.get_children())
        for index, order in enumerate(records):
            tree.insert(
                "",
                "end",
                iid=str(index),
                values=row_values(
                    "orders",
                    order,
                    customers_by_id.get(order.get("customerId")),
                ),
            )
        order_result_count.set(f"{len(records):,} kết quả")

    def refresh_tables(data):
        product_category.set("Tất cả")
        product_min_price.set("")
        product_max_price.set("")
        order_start_date.set("")
        order_end_date.set("")
        order_customer_query.set("")
        customers_by_id.clear()
        customers_by_id.update(
            (customer["_id"], customer)
            for customer in data.get("customers", [])
        )
        for name, tree in trees.items():
            records = data.get(name, [])
            data_by_table[name] = records
            tree.delete(*tree.get_children())
            counts[name].set(f"{len(records):,}")
            if name in ("customers", "products", "orders"):
                continue
            for index, record in enumerate(records):
                tree.insert(
                    "",
                    "end",
                    iid=str(index),
                    values=row_values(
                        name,
                        record,
                        customers_by_id.get(record.get("customerId")),
                    ),
                )
        render_products(data.get("products", []))
        render_orders(data.get("orders", []))
        render_customers()
        render_all_data()
        set_detail("Chọn một dòng trong bảng để xem toàn bộ bản ghi JSON.")

        total = sum(len(data.get(name, [])) for name in TABLES)
        if total:
            set_status(
                "Đã tải dữ liệu. Chọn tab để xem từng nhóm; "
                "việc tải dữ liệu không làm thay đổi database."
            )
        else:
            set_status(
                "Database đang trống. Hãy thêm dữ liệu qua giao diện hoặc MongoDB."
            )

    def refresh_customers(customers, selected_customer_id):
        data_by_table["customers"] = customers
        customers_by_id.clear()
        customers_by_id.update(
            (customer["_id"], customer)
            for customer in customers
        )
        counts["customers"].set(f"{len(customers):,}")
        customer_search.set("")
        render_customers()
        if all_data_collection.get() == "customers":
            render_all_data()

        tree = trees["customers"]
        selected_index = next(
            (
                index for index, customer in enumerate(customers)
                if customer["_id"] == selected_customer_id
            ),
            None,
        )
        if selected_index is not None:
            item_id = str(selected_index)
            tree.selection_set(item_id)
            tree.focus(item_id)
            tree.see(item_id)

    def show_selected(table_name, event):
        tree = event.widget
        selection = tree.selection()
        if not selection:
            return
        records_by_table = {
            "products": product_display_records,
            "orders": order_display_records,
        }
        records = records_by_table.get(table_name, data_by_table[table_name])
        record = records[int(selection[0])]
        preview = dict(record)
        if table_name == "orders":
            customer = customers_by_id.get(record.get("customerId"))
            preview["customerPreview"] = (
                {
                    "name": customer.get("name"),
                    "email": customer.get("email"),
                    "address": customer.get("address"),
                }
                if customer
                else {"message": "Không tìm thấy hồ sơ khách hàng"}
            )
        elif table_name == "customers":
            customer_id = record.get("_id")
            customer_orders = [
                order for order in data_by_table["orders"]
                if order.get("customerId") == customer_id
            ]
            customer_reviews = [
                review for review in data_by_table["reviews"]
                if review.get("customerId") == customer_id
            ]
            preview["activityPreview"] = {
                "orderCount": len(customer_orders),
                "reviewCount": len(customer_reviews),
                "orders": [
                    {
                        "status": order.get("status"),
                        "totalAmount": order.get("totalAmount"),
                        "createdAt": order.get("createdAt"),
                        "items": [
                            {
                                "name": item.get("name"),
                                "qty": item.get("qty"),
                                "unitPrice": item.get("unitPrice"),
                            }
                            for item in order.get("items", [])
                        ],
                    }
                    for order in customer_orders
                ],
            }
        set_detail(dumps(preview, indent=2, ensure_ascii=False))

    def render_all_data(_event=None):
        if all_data_text is None:
            return
        collection = all_data_collection.get()
        records = data_by_table.get(collection, [])
        all_data_count.set(f"{len(records):,} bản ghi")
        all_data_text.configure(state="normal")
        all_data_text.delete("1.0", "end")
        all_data_text.insert(
            "1.0",
            dumps(records, indent=2, ensure_ascii=False),
        )
        all_data_text.configure(state="disabled")

    def selected_customer():
        tree = trees["customers"]
        selection = tree.selection()
        if not selection:
            messagebox.showinfo(
                "Chưa chọn khách hàng",
                "Hãy chọn một khách hàng trong bảng trước.",
                parent=root,
            )
            return None
        return data_by_table["customers"][int(selection[0])]

    def open_customer_form(customer=None):
        is_edit = customer is not None
        dialog = tk.Toplevel(root)
        dialog.title("Sửa khách hàng" if is_edit else "Thêm khách hàng")
        dialog.transient(root)
        dialog.resizable(False, False)
        form = ttk.Frame(dialog, padding=18)
        form.pack(fill="both", expand=True)
        form.columnconfigure(1, weight=1)

        fields = (
            ("name", "Tên khách hàng", customer.get("name", "") if customer else ""),
            ("email", "Email", customer.get("email", "") if customer else ""),
            (
                "street",
                "Địa chỉ",
                customer.get("address", {}).get("street", "") if customer else "",
            ),
            (
                "city",
                "Thành phố",
                customer.get("address", {}).get("city", "") if customer else "",
            ),
        )
        entries = {}
        for row, (key, label, value) in enumerate(fields):
            ttk.Label(form, text=label).grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=6
            )
            entry = ttk.Entry(form, width=42)
            entry.insert(0, value)
            entry.grid(row=row, column=1, sticky="ew", pady=6)
            entries[key] = entry

        def save():
            values = {key: entry.get().strip() for key, entry in entries.items()}
            if not all(values.values()):
                messagebox.showwarning(
                    "Thiếu thông tin",
                    "Vui lòng điền đầy đủ cả bốn trường.",
                    parent=dialog,
                )
                return
            dialog.destroy()

            def save_and_reload():
                customer_id = save_customer(
                    values["name"],
                    values["email"],
                    values["street"],
                    values["city"],
                    customer.get("_id") if customer else None,
                )
                return load_customers(), customer_id

            def show_saved_customer(result):
                customers, customer_id = result
                refresh_customers(customers, customer_id)
                set_status("Đã lưu khách hàng vào MongoDB và cập nhật danh sách.")

            run_async(
                save_and_reload,
                show_saved_customer,
                "Đang lưu thông tin khách hàng...",
            )

        buttons = ttk.Frame(form)
        buttons.grid(row=len(fields), column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Hủy", command=dialog.destroy).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(
            buttons,
            text="Lưu thay đổi" if is_edit else "Thêm khách hàng",
            command=save,
        ).pack(side="right")
        entries["name"].focus_set()
        dialog.bind("<Return>", lambda _event: save())
        dialog.grab_set()

    def add_customer():
        open_customer_form()

    def edit_customer():
        customer = selected_customer()
        if customer is not None:
            open_customer_form(customer)

    def remove_customer():
        customer = selected_customer()
        if customer is None:
            return
        confirmed = messagebox.askyesno(
            "Xóa khách hàng?",
            (
                f"Xóa hồ sơ của {customer.get('name', 'khách hàng')} "
                f"({customer.get('email', '')})?\n\n"
                "Đơn hàng và đánh giá lịch sử được giữ nguyên; "
                "chỉ hồ sơ khách hàng bị xóa."
            ),
            icon="warning",
            parent=root,
        )
        if not confirmed:
            return

        def remove_and_reload():
            delete_customer(customer["_id"])
            return load_demo_data()

        run_async(
            remove_and_reload,
            refresh_tables,
            "Đang xóa hồ sơ khách hàng...",
        )

    def run_product_query():
        minimum = product_min_price.get().strip()
        maximum = product_max_price.get().strip()
        try:
            min_price = int(minimum) if minimum else None
            max_price = int(maximum) if maximum else None
        except ValueError:
            messagebox.showwarning(
                "Giá không hợp lệ",
                "Giá tối thiểu và tối đa phải là số nguyên (đồng).",
                parent=root,
            )
            return
        if (min_price is not None and min_price < 0) or (
            max_price is not None and max_price < 0
        ):
            messagebox.showwarning(
                "Giá không hợp lệ",
                "Giá không được là số âm.",
                parent=root,
            )
            return
        if min_price is not None and max_price is not None and min_price > max_price:
            messagebox.showwarning(
                "Khoảng giá không hợp lệ",
                "Giá tối thiểu phải nhỏ hơn hoặc bằng giá tối đa.",
                parent=root,
            )
            return

        category_values = {
            "Laptop": "laptop",
            "Sách": "book",
            "Quần áo": "clothing",
        }
        category = category_values.get(product_category.get())
        run_async(
            lambda: fetch_products(category, min_price, max_price),
            render_products,
            "Đang truy vấn sản phẩm trên MongoDB...",
        )

    def clear_product_query():
        product_category.set("Tất cả")
        product_min_price.set("")
        product_max_price.set("")
        render_products(data_by_table["products"])
        set_status("Đã xóa bộ lọc sản phẩm.")

    def run_order_query():
        start_text = order_start_date.get().strip()
        end_text = order_end_date.get().strip()
        try:
            start = (
                datetime.strptime(start_text, "%Y-%m-%d")
                .astimezone(timezone.utc)
                .replace(tzinfo=None)
                if start_text else None
            )
            end = (
                (
                    datetime.strptime(end_text, "%Y-%m-%d") + timedelta(days=1)
                ).astimezone(timezone.utc).replace(tzinfo=None)
                if end_text else None
            )
        except ValueError:
            messagebox.showwarning(
                "Ngày không hợp lệ",
                "Ngày bắt đầu/kết thúc phải theo định dạng YYYY-MM-DD.",
                parent=root,
            )
            return
        if start is not None and end is not None and start >= end:
            messagebox.showwarning(
                "Khoảng ngày không hợp lệ",
                "Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.",
                parent=root,
            )
            return

        customer_query = order_customer_query.get().strip()
        run_async(
            lambda: fetch_orders(start, end, customer_query),
            render_orders,
            "Đang truy vấn đơn hàng trên MongoDB...",
        )

    def clear_order_query():
        order_start_date.set("")
        order_end_date.set("")
        order_customer_query.set("")
        render_orders(data_by_table["orders"])
        set_status("Đã xóa bộ lọc đơn hàng.")

    def selected_record(table_name, records):
        selection = trees[table_name].selection()
        if not selection:
            messagebox.showinfo(
                "Chưa chọn bản ghi",
                f"Hãy chọn một dòng trong bảng {TABLES[table_name]['title'].lower()} trước.",
                parent=root,
            )
            return None
        return records[int(selection[0])]

    def edit_order_status():
        order = selected_record("orders", order_display_records)
        if order is None:
            return

        status_names = {
            "paid": "Đã thanh toán",
            "shipped": "Đang giao",
            "done": "Hoàn tất",
        }
        dialog = tk.Toplevel(root)
        dialog.title("Đổi trạng thái đơn hàng")
        dialog.transient(root)
        dialog.resizable(False, False)
        form = ttk.Frame(dialog, padding=18)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text=f"Mã đơn: {order['_id']}").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )
        ttk.Label(form, text="Trạng thái:").grid(
            row=1, column=0, sticky="w", padx=(0, 12)
        )
        status_value = tk.StringVar(
            value=status_names.get(order.get("status"), "Đã thanh toán")
        )
        status_selector = ttk.Combobox(
            form,
            textvariable=status_value,
            values=tuple(status_names.values()),
            state="readonly",
            width=22,
        )
        status_selector.grid(row=1, column=1, sticky="ew")

        def save_status():
            value_to_status = {value: key for key, value in status_names.items()}
            new_status = value_to_status[status_value.get()]
            dialog.destroy()

            def show_updated_order(updated_order):
                for records in (data_by_table["orders"], order_display_records):
                    for index, record in enumerate(records):
                        if record.get("_id") == updated_order["_id"]:
                            records[index] = updated_order
                render_orders(order_display_records)
                render_all_data()
                set_detail(dumps(updated_order, indent=2, ensure_ascii=False))
                set_status("Đã cập nhật trạng thái đơn hàng trong MongoDB.")

            run_async(
                lambda: update_order_status(order["_id"], new_status),
                show_updated_order,
                "Đang cập nhật trạng thái đơn hàng...",
            )

        buttons = ttk.Frame(form)
        buttons.grid(row=2, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Hủy", command=dialog.destroy).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(buttons, text="Lưu trạng thái", command=save_status).pack(
            side="right"
        )
        dialog.grab_set()

    def open_product_form(product=None):
        is_edit = product is not None
        dialog = tk.Toplevel(root)
        dialog.title("Sửa sản phẩm" if is_edit else "Thêm sản phẩm mới")
        dialog.transient(root)
        dialog.resizable(False, False)
        form = ttk.Frame(dialog, padding=18)
        form.pack(fill="both", expand=True)
        form.columnconfigure(1, weight=1)

        fields = (
            ("sku", "SKU", product.get("sku", "") if product else ""),
            ("name", "Tên sản phẩm", product.get("name", "") if product else ""),
            (
                "price",
                "Giá (đồng)",
                str(product.get("price", "")) if product else "",
            ),
            (
                "stock",
                "Tồn kho",
                str(product.get("stock", "")) if product else "",
            ),
            (
                "description",
                "Mô tả",
                product.get("description", "") if product else "",
            ),
        )
        entries = {}
        for row, (key, label, value) in enumerate(fields):
            ttk.Label(form, text=label).grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=6
            )
            entry = ttk.Entry(form, width=42)
            entry.insert(0, value)
            entry.grid(row=row, column=1, sticky="ew", pady=6)
            entries[key] = entry

        category_labels = {
            "book": "Sách",
            "laptop": "Laptop",
            "clothing": "Quần áo",
        }
        category_value = tk.StringVar(
            value=category_labels.get(product.get("category"), "Sách")
            if product else "Sách"
        )
        category_row = len(fields)
        ttk.Label(form, text="Loại sản phẩm").grid(
            row=category_row, column=0, sticky="w", padx=(0, 12), pady=6
        )
        ttk.Combobox(
            form,
            textvariable=category_value,
            values=tuple(category_labels.values()),
            state="readonly",
            width=39,
        ).grid(row=category_row, column=1, sticky="ew", pady=6)
        ttk.Label(
            form,
            text="Thông tin details hiện có sẽ được giữ nguyên khi sửa.",
        ).grid(
            row=category_row + 1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(4, 0),
        )

        def save():
            values = {key: entry.get().strip() for key, entry in entries.items()}
            try:
                price = int(values["price"])
                stock = int(values["stock"])
            except ValueError:
                messagebox.showwarning(
                    "Giá trị không hợp lệ",
                    "Giá và tồn kho phải là số nguyên không âm.",
                    parent=dialog,
                )
                return
            if not values["sku"] or not values["name"]:
                messagebox.showwarning(
                    "Thiếu thông tin",
                    "Vui lòng nhập SKU và tên sản phẩm.",
                    parent=dialog,
                )
                return
            if price < 0 or stock < 0:
                messagebox.showwarning(
                    "Giá trị không hợp lệ",
                    "Giá và tồn kho không được là số âm.",
                    parent=dialog,
                )
                return
            category_values = {value: key for key, value in category_labels.items()}
            dialog.destroy()

            def show_saved_product(saved_product):
                products = data_by_table["products"]
                existing_index = next(
                    (
                        index for index, item in enumerate(products)
                        if item.get("_id") == saved_product["_id"]
                    ),
                    None,
                )
                if existing_index is None:
                    products.append(saved_product)
                else:
                    products[existing_index] = saved_product
                product_category.set("Tất cả")
                product_min_price.set("")
                product_max_price.set("")
                counts["products"].set(f"{len(products):,}")
                render_products(products)
                render_all_data()
                selected_index = next(
                    index for index, item in enumerate(product_display_records)
                    if item.get("_id") == saved_product["_id"]
                )
                item_id = str(selected_index)
                trees["products"].selection_set(item_id)
                trees["products"].focus(item_id)
                trees["products"].see(item_id)
                set_detail(dumps(saved_product, indent=2, ensure_ascii=False))
                set_status(
                    "Đã lưu sản phẩm vào MongoDB; các trường details hiện có được giữ nguyên."
                )

            run_async(
                lambda: save_product(
                    values["sku"],
                    values["name"],
                    category_values[category_value.get()],
                    price,
                    stock,
                    values["description"],
                    product.get("_id") if product else None,
                ),
                show_saved_product,
                "Đang lưu sản phẩm vào MongoDB...",
            )

        buttons = ttk.Frame(form)
        buttons.grid(
            row=category_row + 2,
            column=0,
            columnspan=2,
            sticky="e",
            pady=(12, 0),
        )
        ttk.Button(buttons, text="Hủy", command=dialog.destroy).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(
            buttons,
            text="Lưu thay đổi" if is_edit else "Thêm sản phẩm",
            command=save,
        ).pack(side="right")
        entries["sku"].focus_set()
        dialog.bind("<Return>", lambda _event: save())
        dialog.grab_set()

    def add_product():
        open_product_form()

    def edit_product():
        product = selected_record("products", product_display_records)
        if product is not None:
            open_product_form(product)

    def show_error(error):
        for button in action_buttons:
            button.configure(state="normal")
        set_status("Không hoàn tất được thao tác. Xem nội dung lỗi trong hộp thoại.")
        messagebox.showerror(
            "Không thể kết nối hoặc xử lý dữ liệu",
            str(error),
            parent=root,
        )

    def run_async(task, on_success, progress_text):
        for button in action_buttons:
            button.configure(state="disabled")
        set_status(progress_text)

        def worker():
            try:
                result = task()
            except (PyMongoError, RuntimeError, ValueError) as error:
                root.after(0, lambda error=error: show_error(error))
                return

            def finish_success():
                on_success(result)
                for button in action_buttons:
                    button.configure(state="normal")

            root.after(0, finish_success)

        threading.Thread(target=worker, daemon=True).start()

    def reload_data():
        run_async(
            load_demo_data,
            refresh_tables,
            "Đang tải dữ liệu trực tiếp từ MongoDB...",
        )

    refresh_button = ttk.Button(
        header_actions,
        text="Tải lại từ MongoDB",
        command=reload_data,
    )
    refresh_button.pack(side="left", padx=(0, 8))
    action_buttons.append(refresh_button)

    overview = ttk.LabelFrame(page, text="Tổng quan dữ liệu", padding=(12, 8))
    overview.grid(row=2, column=0, sticky="ew", pady=(8, 10))
    for column, name in enumerate(TABLES):
        overview.columnconfigure(column, weight=1)
        card = ttk.Frame(overview, padding=(8, 2))
        card.grid(row=0, column=column, sticky="ew")
        title = "Tổng khách hàng" if name == "customers" else TABLES[name]["title"]
        ttk.Label(card, text=title).pack(anchor="w")
        counts[name] = tk.StringVar(value="—")
        ttk.Label(card, textvariable=counts[name], font=("", 18, "bold")).pack(
            anchor="w"
        )

    notebook = ttk.Notebook(page)
    notebook.grid(row=3, column=0, sticky="nsew")
    for name, spec in TABLES.items():
        tab = ttk.Frame(notebook, padding=8)
        table_row = 0
        if name == "customers":
            toolbar = ttk.Frame(tab)
            toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
            toolbar.columnconfigure(4, weight=1)

            add_button = ttk.Button(
                toolbar,
                text="Thêm khách hàng",
                command=add_customer,
            )
            add_button.grid(row=0, column=0, padx=(0, 6))
            edit_button = ttk.Button(
                toolbar,
                text="Sửa khách hàng",
                command=edit_customer,
            )
            edit_button.grid(row=0, column=1, padx=6)
            delete_button = ttk.Button(
                toolbar,
                text="Xóa khách hàng",
                command=remove_customer,
            )
            delete_button.grid(row=0, column=2, padx=6)
            action_buttons.extend((add_button, edit_button, delete_button))
            ttk.Label(toolbar, text="Tìm khách:").grid(
                row=0, column=3, padx=(18, 6)
            )
            search_entry = ttk.Entry(toolbar, textvariable=customer_search, width=30)
            search_entry.grid(row=0, column=4, sticky="ew")
            search_entry.bind("<KeyRelease>", lambda _event: render_customers())
            table_row = 1
        elif name == "products":
            toolbar = ttk.Frame(tab)
            toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
            ttk.Label(toolbar, text="Loại:").grid(row=0, column=0, padx=(0, 6))
            category_selector = ttk.Combobox(
                toolbar,
                textvariable=product_category,
                values=("Tất cả", "Laptop", "Sách", "Quần áo"),
                state="readonly",
                width=12,
            )
            category_selector.grid(row=0, column=1, padx=(0, 12))
            ttk.Label(toolbar, text="Giá từ (đ):").grid(
                row=0, column=2, padx=(0, 6)
            )
            ttk.Entry(
                toolbar,
                textvariable=product_min_price,
                width=13,
            ).grid(row=0, column=3, padx=(0, 12))
            ttk.Label(toolbar, text="đến (đ):").grid(
                row=0, column=4, padx=(0, 6)
            )
            ttk.Entry(
                toolbar,
                textvariable=product_max_price,
                width=13,
            ).grid(row=0, column=5, padx=(0, 8))
            query_button = ttk.Button(
                toolbar,
                text="Truy vấn",
                command=run_product_query,
            )
            query_button.grid(row=0, column=6, padx=4)
            clear_button = ttk.Button(
                toolbar,
                text="Xóa lọc",
                command=clear_product_query,
            )
            clear_button.grid(row=0, column=7, padx=4)
            action_buttons.extend((query_button, clear_button))
            ttk.Label(
                toolbar,
                textvariable=product_result_count,
                font=("", 10, "bold"),
            ).grid(row=0, column=8, padx=10)
            add_product_button = ttk.Button(
                toolbar,
                text="Thêm sản phẩm",
                command=add_product,
            )
            add_product_button.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
            edit_product_button = ttk.Button(
                toolbar,
                text="Sửa sản phẩm đã chọn",
                command=edit_product,
            )
            edit_product_button.grid(row=1, column=2, columnspan=2, sticky="w", pady=(6, 0))
            action_buttons.extend((add_product_button, edit_product_button))
            table_row = 2
        elif name == "orders":
            toolbar = ttk.Frame(tab)
            toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
            ttk.Label(toolbar, text="Từ ngày:").grid(
                row=0, column=0, padx=(0, 6), pady=3
            )
            ttk.Entry(
                toolbar,
                textvariable=order_start_date,
                width=12,
            ).grid(row=0, column=1, padx=(0, 12), pady=3)
            ttk.Label(toolbar, text="Đến ngày:").grid(
                row=0, column=2, padx=(0, 6), pady=3
            )
            ttk.Entry(
                toolbar,
                textvariable=order_end_date,
                width=12,
            ).grid(row=0, column=3, padx=(0, 12), pady=3)
            ttk.Label(toolbar, text="Tên/email khách:").grid(
                row=0, column=4, padx=(0, 6), pady=3
            )
            ttk.Entry(
                toolbar,
                textvariable=order_customer_query,
                width=24,
            ).grid(row=0, column=5, padx=(0, 8), pady=3)
            query_orders_button = ttk.Button(
                toolbar,
                text="Tìm đơn",
                command=run_order_query,
            )
            query_orders_button.grid(row=0, column=6, padx=4, pady=3)
            clear_orders_button = ttk.Button(
                toolbar,
                text="Xóa lọc",
                command=clear_order_query,
            )
            clear_orders_button.grid(row=0, column=7, padx=4, pady=3)
            ttk.Label(
                toolbar,
                textvariable=order_result_count,
                font=("", 10, "bold"),
            ).grid(row=0, column=8, padx=8, pady=3)
            change_status_button = ttk.Button(
                toolbar,
                text="Đổi trạng thái đơn đã chọn",
                command=edit_order_status,
            )
            change_status_button.grid(
                row=1, column=0, columnspan=3, sticky="w", pady=(4, 0)
            )
            action_buttons.extend((
                query_orders_button,
                clear_orders_button,
                change_status_button,
            ))
            ttk.Label(
                toolbar,
                text="Ngày theo định dạng YYYY-MM-DD",
            ).grid(row=1, column=3, columnspan=3, sticky="w", pady=(4, 0))
            table_row = 2

        tab.rowconfigure(table_row, weight=1)
        tab.columnconfigure(0, weight=1)
        notebook.add(tab, text=spec["title"])

        tree = ttk.Treeview(
            tab,
            columns=spec["columns"],
            show="headings",
            selectmode="browse",
        )
        trees[name] = tree
        for column, heading, width in zip(
            spec["columns"], spec["headings"], spec["widths"]
        ):
            tree.heading(column, text=heading)
            tree.column(column, width=width, minwidth=65, anchor="w")

        vertical = ttk.Scrollbar(tab, orient="vertical", command=tree.yview)
        horizontal = ttk.Scrollbar(tab, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=table_row, column=0, sticky="nsew")
        vertical.grid(row=table_row, column=1, sticky="ns")
        horizontal.grid(row=table_row + 1, column=0, sticky="ew")
        tree.bind(
            "<<TreeviewSelect>>",
            lambda event, table_name=name: show_selected(table_name, event),
        )

    all_data_tab = ttk.Frame(notebook, padding=8)
    all_data_tab.rowconfigure(1, weight=1)
    all_data_tab.columnconfigure(0, weight=1)
    notebook.add(all_data_tab, text="Toàn bộ dữ liệu")

    all_data_toolbar = ttk.Frame(all_data_tab)
    all_data_toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
    ttk.Label(all_data_toolbar, text="Collection:").pack(side="left", padx=(0, 8))
    all_data_selector = ttk.Combobox(
        all_data_toolbar,
        textvariable=all_data_collection,
        values=tuple(TABLES),
        state="readonly",
        width=18,
    )
    all_data_selector.pack(side="left")
    all_data_selector.bind("<<ComboboxSelected>>", render_all_data)
    ttk.Label(
        all_data_toolbar,
        textvariable=all_data_count,
        font=("", 10, "bold"),
    ).pack(side="left", padx=12)
    ttk.Label(
        all_data_toolbar,
        text="Hiển thị toàn bộ trường và bản ghi của collection đã chọn.",
    ).pack(side="left", padx=8)

    all_data_frame = ttk.Frame(all_data_tab)
    all_data_frame.grid(row=1, column=0, sticky="nsew")
    all_data_frame.rowconfigure(0, weight=1)
    all_data_frame.columnconfigure(0, weight=1)
    all_data_text = tk.Text(
        all_data_frame,
        wrap="none",
        font=("Consolas", 10),
        state="disabled",
    )
    all_data_vertical = ttk.Scrollbar(
        all_data_frame,
        orient="vertical",
        command=all_data_text.yview,
    )
    all_data_horizontal = ttk.Scrollbar(
        all_data_frame,
        orient="horizontal",
        command=all_data_text.xview,
    )
    all_data_text.configure(
        yscrollcommand=all_data_vertical.set,
        xscrollcommand=all_data_horizontal.set,
    )
    all_data_text.grid(row=0, column=0, sticky="nsew")
    all_data_vertical.grid(row=0, column=1, sticky="ns")
    all_data_horizontal.grid(row=1, column=0, sticky="ew")

    ttk.Label(page, text="Xem trước & liên kết dữ liệu", style="Section.TLabel").grid(
        row=4, column=0, sticky="w", pady=(10, 5)
    )
    detail_frame = ttk.Frame(page)
    detail_frame.grid(row=5, column=0, sticky="nsew")
    detail_frame.rowconfigure(0, weight=1)
    detail_frame.columnconfigure(0, weight=1)
    detail_text = tk.Text(
        detail_frame,
        height=5,
        wrap="none",
        font=("Consolas", 10),
        state="disabled",
    )
    detail_scroll = ttk.Scrollbar(
        detail_frame,
        orient="vertical",
        command=detail_text.yview,
    )
    detail_text.configure(yscrollcommand=detail_scroll.set)
    detail_text.grid(row=0, column=0, sticky="nsew")
    detail_scroll.grid(row=0, column=1, sticky="ns")
    set_detail("Chọn một dòng trong bảng để xem toàn bộ bản ghi JSON.")

    ttk.Label(page, textvariable=status, anchor="w").grid(
        row=6, column=0, sticky="ew", pady=(7, 0)
    )

    reload_data()
    root.mainloop()


if __name__ == "__main__":
    launch_ui()
