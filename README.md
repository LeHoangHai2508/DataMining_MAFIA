READ ME </br>
Làm sao để chạy code </br>
Bước 1: pip install Django</br>
Bước 2: pip install xhtml2pdf</br>
Bước 3: pip install django-widget-tweaks</br>
Bước 4: python manage.py makemigrations </br>
Bước 5: python manage.py migrate</br>
Bước 6: python manage.py runserver</br>
Bước 7: 
Lưu y : Phải đăng nhập vào mới có hình ảnh </br>

ACCOUNT Admin </br>
Tạo admin: python manage.py createsuperuser</br>
Điền thông tin mail (fake)
user name : hp</br>
email:Của thầy </br>
password : 123 (Nhấn Yes cho đến hết)</br>

Sau khi vào admin import các file sau đây để có dữ liệu:</br>
- Vào Product: import file tên "real_100_products.csv" (dữ liệu sản phẩm)</br>
- Vào Transaction: import file "generated_transactions_rich.csv" (dữ liệu mua hàng)</br>
