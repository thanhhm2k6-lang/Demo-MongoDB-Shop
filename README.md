# MongoDB Shop Demo

Các thành phần của demo MongoDB:

- `ui.py`: giao diện desktop Tkinter để xem khách hàng, sản phẩm, đơn hàng và đánh giá.
- `shop_demo.py`: kết nối MongoDB, đọc dữ liệu và lưu/sửa/xóa khách hàng.

## Cài đặt và chạy

Yêu cầu Python 3.10 trở lên, MongoDB Server 4.2 trở lên đang chạy, và Tkinter (thường có sẵn trong Python trên Windows).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python ui.py
```

Trong giao diện:

- Tổng quan hiển thị số lượng khách hàng, sản phẩm, đơn hàng và đánh giá.
- Tab **Toàn bộ dữ liệu** cho phép chọn collection và xem tất cả bản ghi cùng đầy đủ trường JSON; không giới hạn vài dòng đầu.
- Nút **Tải lại từ MongoDB** đọc lại dữ liệu sau khi có thay đổi.
- Trong tab **Sản phẩm**, chọn loại và nhập giá tối thiểu/tối đa (đồng), sau đó chọn **Truy vấn** để lọc trực tiếp trên MongoDB và sắp xếp kết quả theo giá tăng dần. Có thể để trống một hoặc cả hai mức giá; **Xóa lọc** khôi phục danh sách đã tải gần nhất.
- Trong tab **Sản phẩm**, có thể thêm sản phẩm hoặc chọn sản phẩm để sửa SKU, tên, loại, giá, tồn kho và mô tả. Khi sửa, các trường `details`, đánh giá và thông tin khác được giữ nguyên; SKU trùng không phân biệt chữ hoa/thường sẽ bị MongoDB từ chối.
- Trong tab **Đơn hàng**, lọc theo khoảng ngày (định dạng `YYYY-MM-DD`, theo ngày địa phương) và tên/email khách hàng, rồi chọn **Tìm đơn**. Chọn một đơn và **Đổi trạng thái đơn đã chọn** để chuyển giữa Đã thanh toán, Đang giao và Hoàn tất.
- Tab **Đơn hàng** hiển thị tên/email khách hàng tham chiếu; chọn khách hàng để xem các đơn hàng và mặt hàng liên quan trong phần xem trước.
- Trong tab **Khách hàng**, có thể tìm theo tên/email/địa chỉ/thành phố, thêm mới, sửa hoặc xóa hồ sơ. Xóa hồ sơ không xóa các đơn hàng và đánh giá lịch sử.
- Khách hàng được thêm bằng biểu mẫu. Đánh giá hiện được thêm/sửa trực tiếp trong MongoDB Compass hoặc MongoDB Shell.
- Chọn một dòng để xem bản ghi và các liên kết liên quan.

Email khách hàng và SKU sản phẩm có unique index không phân biệt chữ hoa/chữ thường. MongoDB sẽ từ chối email/SKU trùng, kể cả khi nhập trực tiếp trong Compass hoặc Shell.

## Trình diễn kiểm thử CRUD khách hàng

Để chạy một lượt kiểm thử có kết quả `PASS/FAIL` cho người xem:

```powershell
python crud_test_demo.py
```

Kịch bản kiểm tra trường bắt buộc, thêm/đọc/sửa/xóa khách hàng, email trùng (kể cả khác chữ hoa/thường), cập nhật trùng email và ID không tồn tại. Kịch bản chỉ tạo một khách hàng thử với email `crud-demo-test@example.invalid`, xóa khách thử ở cuối và xác nhận tổng số khách trước/sau không đổi. Nếu email thử này đã tồn tại, chương trình dừng để tránh đụng vào dữ liệu đó.

Để trình diễn thao tác trực tiếp trên giao diện, mở `python ui.py`, vào tab **Khách hàng**, thêm khách thử bằng email riêng, chọn khách đó để sửa, rồi xóa và xác nhận. Thử thêm một lần nữa bằng email đã có để xem MongoDB từ chối dữ liệu trùng. Các thao tác này dùng database thật; nên chỉ dùng email thử nghiệm và xóa bản ghi thử sau phần trình diễn.

Để xem số lượng bản ghi hiện có mà không thay đổi dữ liệu:

```powershell
python shop_demo.py
```

Giao diện và script cùng dùng database `shop_demo` và kết nối bằng `MONGODB_URI` (mặc định `mongodb://localhost:27017`). Ứng dụng không còn sinh hoặc nạp dữ liệu mẫu tự động; dữ liệu hiện có trong MongoDB được giữ nguyên.

## Địa chỉ MongoDB

Mặc định, ứng dụng kết nối tới `mongodb://localhost:27017`. Có thể đặt biến môi trường `MONGODB_URI` để dùng máy chủ khác:

```powershell
$env:MONGODB_URI = "mongodb://localhost:27017"
python ui.py
```
