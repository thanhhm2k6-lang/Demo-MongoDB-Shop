"""Run a safe, temporary CRUD demonstration against the shop_demo database."""
import sys

from bson import ObjectId
from pymongo import MongoClient
from pymongo.collation import Collation
from pymongo.errors import DuplicateKeyError

from shop_demo import (
    DB_NAME,
    MONGODB_URI,
    delete_customer,
    load_customers,
    save_customer,
)

TEST_EMAIL = "crud-demo-test@example.invalid"
TEST_EMAIL_COLLATION = Collation(locale="en", strength=2)


def expect_error(error_type, action):
    try:
        action()
    except error_type:
        return
    raise AssertionError(f"Expected {error_type.__name__} was not raised.")


def run_demo():
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=2500)
    temporary_customer_id = None

    try:
        shop = client[DB_NAME]
        existing = shop.customers.find_one(
            {"email": TEST_EMAIL},
            collation=TEST_EMAIL_COLLATION,
        )
        if existing:
            raise RuntimeError(
                f"Email thử nghiệm {TEST_EMAIL} đã tồn tại. "
                "Hãy kiểm tra và xóa riêng bản ghi thử nghiệm đó trước khi chạy lại."
            )

        start_count = shop.customers.count_documents({})
        print(f"Database: {DB_NAME}")
        print(f"Khách hàng trước khi thử: {start_count:,}")

        expect_error(
            ValueError,
            lambda: save_customer("", TEST_EMAIL, "Địa chỉ thử", "Hà Nội"),
        )
        print("PASS - Create: từ chối trường bắt buộc bị bỏ trống")

        temporary_customer_id = save_customer(
            "Khách kiểm thử CRUD",
            TEST_EMAIL,
            "1 Đường Kiểm Thử",
            "Hà Nội",
        )
        customer = next(
            item for item in load_customers()
            if item["_id"] == temporary_customer_id
        )
        assert customer["email"] == TEST_EMAIL
        print("PASS - Create/Read: thêm và đọc lại khách thử nghiệm từ MongoDB")

        for duplicate_email in (TEST_EMAIL, TEST_EMAIL.upper()):
            expect_error(
                DuplicateKeyError,
                lambda email=duplicate_email: save_customer(
                    "Khách bị trùng email",
                    email,
                    "2 Đường Kiểm Thử",
                    "Đà Nẵng",
                ),
            )
        print("PASS - Create: MongoDB chặn email trùng, kể cả khác chữ hoa/thường")

        other_customer = shop.customers.find_one(
            {"_id": {"$ne": temporary_customer_id}},
            {"email": 1},
        )
        if other_customer is None:
            raise RuntimeError(
                "Cần có ít nhất một khách hàng có sẵn để kiểm thử email trùng khi sửa."
            )

        save_customer(
            "Khách đã cập nhật",
            TEST_EMAIL,
            "2 Đường Kiểm Thử",
            "Đà Nẵng",
            temporary_customer_id,
        )
        updated = next(
            item for item in load_customers()
            if item["_id"] == temporary_customer_id
        )
        assert updated["name"] == "Khách đã cập nhật"
        assert updated["address"]["city"] == "Đà Nẵng"
        print("PASS - Update: sửa khách và xác nhận dữ liệu mới đã lưu")

        expect_error(
            DuplicateKeyError,
            lambda: save_customer(
                "Khách đã cập nhật",
                other_customer["email"],
                "2 Đường Kiểm Thử",
                "Đà Nẵng",
                temporary_customer_id,
            ),
        )
        print("PASS - Update: từ chối đổi sang email của khách khác")

        expect_error(
            RuntimeError,
            lambda: save_customer(
                "ID không tồn tại",
                "missing-customer@example.invalid",
                "Địa chỉ thử",
                "Hà Nội",
                ObjectId(),
            ),
        )
        print("PASS - Update: báo lỗi khi hồ sơ đã bị xóa hoặc không tồn tại")

        delete_customer(temporary_customer_id)
        temporary_customer_id = None
        assert shop.customers.find_one(
            {"email": TEST_EMAIL},
            collation=TEST_EMAIL_COLLATION,
        ) is None
        print("PASS - Delete: xóa khách thử nghiệm")

        expect_error(RuntimeError, lambda: delete_customer(ObjectId()))
        print("PASS - Delete: báo lỗi khi hồ sơ cần xóa không tồn tại")

        end_count = shop.customers.count_documents({})
        assert end_count == start_count, (
            f"Số khách trước/sau khác nhau: {start_count} -> {end_count}"
        )
        print(f"PASS - An toàn dữ liệu: số khách trước/sau đều là {end_count:,}")
        print("KẾT QUẢ: TẤT CẢ TESTCASE ĐỀU PASS")
    finally:
        if temporary_customer_id is not None:
            delete_customer(temporary_customer_id)
        client.close()


if __name__ == "__main__":
    try:
        run_demo()
    except (AssertionError, DuplicateKeyError, RuntimeError, ValueError) as error:
        print(f"FAIL - {error}", file=sys.stderr)
        raise SystemExit(1) from error
