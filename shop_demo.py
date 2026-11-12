"""
shop_demo.py - Demo Data Modelling MongoDB bằng PyMongo: Cửa hàng online mini
Khớp 100% Lược đồ cơ sở dữ liệu (Hình ảnh 8):
  - Collections: customers, products, reviews, orders
  - Patterns:
      + Polymorphic: products.details (book, laptop, clothing)
      + Subset: products.recentReviews (tối đa 3 review mới nhất)
      + Computed: products.ratingSum, ratingCount, ratingAvg; orders.totalAmount
      + Embedded: customers.address; orders.shippingAddress, orders.items
      + Snapshot/Copy: orders.items (name, unitPrice), reviews.customerName, recentReviews.*
      + Reference: reviews -> products, customers; orders -> customers

Cài đặt:  pip install pymongo
Chạy UI:  python ui.py
"""
import os
import sys
from datetime import datetime
import re

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from bson import ObjectId
from bson.json_util import dumps
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo import ReturnDocument

DB_NAME = "shop_demo"
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")

def show(title, data):
    print(f"\n=== {title} ===")
    print(dumps(data, indent=2, ensure_ascii=False))


def ensure_unique_index(collection, field):
    index_name = f"uq_{field}_ci"
    expected_keys = [(field, ASCENDING)]
    indexes = collection.index_information()
    target = indexes.get(index_name)
    if (
        target
        and target.get("key") == expected_keys
        and target.get("unique")
        and target.get("collation", {}).get("locale") == "en"
        and target.get("collation", {}).get("strength") == 2
    ):
        return

    collection.create_index(
        expected_keys,
        unique=True,
        name=index_name,
        collation={"locale": "en", "strength": 2},
    )
    for name, info in indexes.items():
        if name != index_name and info.get("key") == expected_keys:
            collection.drop_index(name)


def ensure_unique_data_indexes(shop):
    ensure_unique_index(shop.customers, "email")
    ensure_unique_index(shop.products, "sku")


# ---------------------------------------------------------------------
# ĐO HIỆU NĂNG: explain("executionStats")
# ---------------------------------------------------------------------
def explain_find(coll, flt, projection=None, sort=None, limit=0, hint=None):
    cmd = {"find": coll.name, "filter": flt}
    if projection:
        cmd["projection"] = projection
    if sort:
        cmd["sort"] = sort
    if limit:
        cmd["limit"] = limit
    if hint:
        cmd["hint"] = hint
    res = coll.database.command({"explain": cmd, "verbosity": "executionStats"})
    es = res["executionStats"]
    plan = dumps(res["queryPlanner"]["winningPlan"])
    return {
        "stage": "IXSCAN" if "IXSCAN" in plan else "COLLSCAN",
        "executionTimeMillis": es["executionTimeMillis"],
        "nReturned": es["nReturned"],
        "totalKeysExamined": es["totalKeysExamined"],
        "totalDocsExamined": es["totalDocsExamined"]
    }


def print_stats(label, s):
    print(f"  [{label:<14}] plan={s['stage']:<8} executionTimeMillis={s['executionTimeMillis']:<4} "
          f"nReturned={s['nReturned']:<6} totalKeysExamined={s['totalKeysExamined']:<7} "
          f"totalDocsExamined={s['totalDocsExamined']}")


def load_demo_data():
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=2500)
    try:
        shop = client[DB_NAME]
        ensure_unique_data_indexes(shop)
        return {
            name: list(shop[name].find())
            for name in ("customers", "products", "orders", "reviews")
        }
    finally:
        client.close()


def load_customers():
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=2500)
    try:
        shop = client[DB_NAME]
        ensure_unique_data_indexes(shop)
        return list(shop.customers.find())
    finally:
        client.close()


def query_products(category=None, min_price=None, max_price=None):
    query = {}
    if category:
        query["category"] = category
    price_range = {}
    if min_price is not None:
        price_range["$gte"] = min_price
    if max_price is not None:
        price_range["$lte"] = max_price
    if price_range:
        query["price"] = price_range

    projection = {
        "sku": 1,
        "name": 1,
        "category": 1,
        "price": 1,
        "stock": 1,
        "thumbnail": 1,
        "ratingAvg": 1,
        "ratingCount": 1,
    }
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=2500)
    try:
        return list(
            client[DB_NAME].products.find(query, projection).sort("price", ASCENDING)
        )
    finally:
        client.close()


def save_product(sku, name, category, price, stock, description, product_id=None):
    product = {
        "sku": sku.strip(),
        "name": name.strip(),
        "category": category,
        "price": price,
        "stock": stock,
        "description": description.strip(),
    }
    if not all((product["sku"], product["name"], product["category"])):
        raise ValueError("Vui lòng nhập SKU, tên sản phẩm và loại.")
    if price < 0 or stock < 0:
        raise ValueError("Giá và tồn kho không được là số âm.")

    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=2500)
    try:
        shop = client[DB_NAME]
        ensure_unique_data_indexes(shop)
        products = shop.products
        if product_id is None:
            product.update({
                "thumbnail": "",
                "details": {},
                "ratingSum": 0,
                "ratingCount": 0,
                "ratingAvg": 0,
                "recentReviews": [],
                "createdAt": datetime.utcnow(),
            })
            product_id = products.insert_one(product).inserted_id
        else:
            result = products.find_one_and_update(
                {"_id": product_id},
                {"$set": product},
                return_document=ReturnDocument.AFTER,
            )
            if result is None:
                raise RuntimeError("Không tìm thấy sản phẩm; hãy tải lại dữ liệu.")
            return result
        return products.find_one({"_id": product_id})
    finally:
        client.close()


def query_orders(start_date=None, end_date=None, customer_query=""):
    query = {}
    created_at = {}
    if start_date is not None:
        created_at["$gte"] = start_date
    if end_date is not None:
        created_at["$lt"] = end_date
    if created_at:
        query["createdAt"] = created_at

    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=2500)
    try:
        shop = client[DB_NAME]
        customer_query = customer_query.strip()
        if customer_query:
            pattern = re.escape(customer_query)
            customer_ids = [
                customer["_id"]
                for customer in shop.customers.find(
                    {
                        "$or": [
                            {"name": {"$regex": pattern, "$options": "i"}},
                            {"email": {"$regex": pattern, "$options": "i"}},
                        ]
                    },
                    {"_id": 1},
                )
            ]
            if not customer_ids:
                return []
            query["customerId"] = {"$in": customer_ids}
        return list(shop.orders.find(query).sort("createdAt", DESCENDING))
    finally:
        client.close()


def update_order_status(order_id, status):
    if status not in ("paid", "shipped", "done"):
        raise ValueError("Trạng thái đơn hàng không hợp lệ.")
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=2500)
    try:
        result = client[DB_NAME].orders.find_one_and_update(
            {"_id": order_id},
            {"$set": {"status": status}},
            return_document=ReturnDocument.AFTER,
        )
        if result is None:
            raise RuntimeError("Không tìm thấy đơn hàng; hãy tải lại dữ liệu.")
        return result
    finally:
        client.close()


def save_customer(name, email, street, city, customer_id=None):
    customer = {
        "name": name.strip(),
        "email": email.strip().lower(),
        "address": {"street": street.strip(), "city": city.strip()},
    }
    if not all((customer["name"], customer["email"], street.strip(), city.strip())):
        raise ValueError("Vui lòng nhập đầy đủ tên, email, địa chỉ và thành phố.")

    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=2500)
    try:
        shop = client[DB_NAME]
        ensure_unique_data_indexes(shop)
        customers = shop.customers
        if customer_id is None:
            return customers.insert_one(customer).inserted_id

        result = customers.update_one({"_id": customer_id}, {"$set": customer})
        if result.matched_count == 0:
            raise RuntimeError("Không tìm thấy khách hàng; hãy tải lại dữ liệu.")
        return customer_id
    finally:
        client.close()


def delete_customer(customer_id: ObjectId):
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=2500)
    try:
        result = client[DB_NAME].customers.delete_one({"_id": customer_id})
        if result.deleted_count == 0:
            raise RuntimeError("Không tìm thấy khách hàng; hãy tải lại dữ liệu.")
    finally:
        client.close()


def compare(title, coll, flt, **kw):
    print(f"\n--- explain: {title} ---")
    print_stats("CÓ index", explain_find(coll, flt, **kw))
    print_stats("KHÔNG index", explain_find(coll, flt, hint={"$natural": 1}, **kw))


# ---------------------------------------------------------------------
# TRUY VẤN DEMO (map đúng với bảng workload trong tài liệu)
# ---------------------------------------------------------------------
def run_queries(shop, an, p):
    hot = shop.products.find_one(sort=[("ratingCount", DESCENDING)])

    q1 = {"category": "laptop", "price": {"$gte": 10_000_000, "$lte": 30_000_000}}
    proj1 = {"name": 1, "price": 1, "thumbnail": 1, "ratingAvg": 1, "ratingCount": 1}
    show("Q1: Laptop 10-30 triệu, sắp theo giá (index category_price)",
         list(shop.products.find(q1, proj1).sort("price", ASCENDING).limit(5)))
    compare("Q1 category + price range", shop.products, q1, projection=proj1, sort={"price": 1}, limit=10)

    show("Q2: Chi tiết sản phẩm (1 query, đã có rating + 3 review mới nhất)",
         shop.products.find_one({"sku": "BK-001"}))
    compare("Q2 sku", shop.products, {"sku": "BK-001"})

    show("Q3: Review của sản phẩm nhiều review nhất, trang 1 (index product_createdAt)",
         list(shop.reviews.find({"productId": hot["_id"]}).sort("createdAt", DESCENDING).skip(0).limit(3)))
    compare("Q3 reviews của 1 sản phẩm", shop.reviews, {"productId": hot["_id"]},
            sort={"createdAt": -1}, limit=10)

    q4 = {"$text": {"$search": "code"}}
    show("Q4: Tìm kiếm text 'code' (index text_search)",
         list(shop.products.find(q4, {"name": 1, "score": {"$meta": "textScore"}})
              .sort([("score", {"$meta": "textScore"})]).limit(5)))
    print("\n--- explain: Q4 text search ---")
    print_stats("CÓ index", explain_find(shop.products, q4))

    show("Q5: Lịch sử đơn hàng của khách An (index customer_createdAt)",
         list(shop.orders.find({"customerId": an["_id"]}, {"status": 1, "totalAmount": 1, "createdAt": 1})
              .sort("createdAt", DESCENDING).limit(5)))
    compare("Q5 orders của 1 khách", shop.orders, {"customerId": an["_id"]}, sort={"createdAt": -1}, limit=5)

    q6 = {"category": "laptop", "details.ramGb": {"$gte": 16}}
    proj6 = {"name": 1, "details": 1}
    show("Q6: Polymorphic - laptop RAM >= 16GB", list(shop.products.find(q6, proj6).limit(3)))
    print("\n--- explain: Q6 polymorphic field (details.ramGb) ---")
    print_stats("CHƯA có index", explain_find(shop.products, q6, projection=proj6))
    shop.products.create_index([("category", ASCENDING), ("details.ramGb", ASCENDING)], name="category_ramGb")
    print("  -> đã tạo index category_ramGb (category + details.ramGb)")
    print_stats("SAU khi index", explain_find(shop.products, q6, projection=proj6))

    show("Q7a: Computed - giá trị lưu sẵn",
         shop.products.find_one({"_id": hot["_id"]}, {"name": 1, "ratingAvg": 1, "ratingCount": 1}))
    show("Q7b: Computed - tính lại bằng aggregation (phải khớp Q7a)",
         list(shop.reviews.aggregate([
             {"$match": {"productId": hot["_id"]}},
             {"$group": {"_id": "$productId", "avg": {"$avg": "$rating"}, "count": {"$sum": 1}}},
         ])))

    show("Q8: Phân bố rating của toàn bộ review",
         list(shop.reviews.aggregate([
             {"$group": {"_id": "$rating", "soLuong": {"$sum": 1}}},
             {"$sort": {"_id": 1}},
         ])))
    show("Q8b: Điểm trung bình toàn shop và 3 comment mẫu cho mỗi mức 1 sao / 3 sao / 5 sao",
         {"ratingAvgToanShop": next(shop.reviews.aggregate([{"$group": {"_id": None, "avg": {"$avg": "$rating"}}}]))["avg"],
          "mau": {str(r): [x["comment"] for x in shop.reviews.find({"rating": r}, {"comment": 1}).limit(3)]
                  for r in (1, 3, 5)}})


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------
def main():
    data = load_demo_data()
    print(f"Database {DB_NAME} (chỉ đọc):")
    for name, records in data.items():
        print(f"  {name}: {len(records):,}")


if __name__ == "__main__":
    main()