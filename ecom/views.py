import os
import time
from django.shortcuts import render,redirect,reverse
from . import forms,models
from django.http import HttpResponseRedirect,HttpResponse
from django.core.mail import send_mail
from django.contrib.auth.models import Group
from django.contrib.auth.decorators import login_required,user_passes_test
from django.contrib import messages
from django.conf import settings
from collections import defaultdict
from . import models
from django.db.models import Prefetch
from django.shortcuts import render, redirect
from .forms import ProductCSVForm, TransactionCSVForm
from io import TextIOWrapper
from .models import Transaction, Orders, Product
import csv, ast
from .mafia import find_maximal_itemsets, build_tidsets, mafia
from itertools import combinations
from .models import AssociationRule
from django.core.files.base import ContentFile
import requests
from django.contrib.staticfiles import finders




def home_view(request):
    products=models.Product.objects.all()
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        counter=product_ids.split('|')
        product_count_in_cart=len(set(counter))
    else:
        product_count_in_cart=0
    if request.user.is_authenticated:
        return HttpResponseRedirect('afterlogin')
    return render(request,'ecom/index.html',{'products':products,'product_count_in_cart':product_count_in_cart})


#for showing login button for admin(by sumit)
def adminclick_view(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect('afterlogin')
    return HttpResponseRedirect('adminlogin')


def customer_signup_view(request):
    userForm=forms.CustomerUserForm()
    customerForm=forms.CustomerForm()
    mydict={'userForm':userForm,'customerForm':customerForm}
    if request.method=='POST':
        userForm=forms.CustomerUserForm(request.POST)
        customerForm=forms.CustomerForm(request.POST,request.FILES)
        if userForm.is_valid() and customerForm.is_valid():
            user=userForm.save()
            user.set_password(user.password)
            user.save()
            customer=customerForm.save(commit=False)
            customer.user=user
            customer.save()
            my_customer_group = Group.objects.get_or_create(name='CUSTOMER')
            my_customer_group[0].user_set.add(user)
        return HttpResponseRedirect('customerlogin')
    return render(request,'ecom/customersignup.html',context=mydict)

#-----------for checking user iscustomer
def is_customer(user):
    return user.groups.filter(name='CUSTOMER').exists()



#---------AFTER ENTERING CREDENTIALS WE CHECK WHETHER USERNAME AND PASSWORD IS OF ADMIN,CUSTOMER
def afterlogin_view(request):
    if is_customer(request.user):
        return redirect('customer-home')
    else:
        return redirect('admin-dashboard')

#---------------------------------------------------------------------------------
#------------------------ ADMIN RELATED VIEWS START ------------------------------
#---------------------------------------------------------------------------------
@login_required(login_url='adminlogin')
def admin_dashboard_view(request):
    # for cards on dashboard
    customercount=models.Customer.objects.all().count()
    productcount=models.Product.objects.all().count()
    ordercount=models.Orders.objects.all().count()

    # for recent order tables
    orders=models.Orders.objects.all()
    ordered_products=[]
    ordered_bys=[]
    for order in orders:
        ordered_product=models.Product.objects.all().filter(id=order.product.id)
        ordered_by=models.Customer.objects.all().filter(id = order.customer.id)
        ordered_products.append(ordered_product)
        ordered_bys.append(ordered_by)

    mydict={
    'customercount':customercount,
    'productcount':productcount,
    'ordercount':ordercount,
    'data':zip(ordered_products,ordered_bys,orders),
    }
    return render(request,'ecom/admin_dashboard.html',context=mydict)


# admin view customer table
@login_required(login_url='adminlogin')
def view_customer_view(request):
    customers=models.Customer.objects.all()
    return render(request,'ecom/view_customer.html',{'customers':customers})

# admin delete customer
@login_required(login_url='adminlogin')
def delete_customer_view(request,pk):
    customer=models.Customer.objects.get(id=pk)
    user=models.User.objects.get(id=customer.user_id)
    user.delete()
    customer.delete()
    return redirect('view-customer')


@login_required(login_url='adminlogin')
def update_customer_view(request,pk):
    customer=models.Customer.objects.get(id=pk)
    user=models.User.objects.get(id=customer.user_id)
    userForm=forms.CustomerUserForm(instance=user)
    customerForm=forms.CustomerForm(request.FILES,instance=customer)
    mydict={'userForm':userForm,'customerForm':customerForm}
    if request.method=='POST':
        userForm=forms.CustomerUserForm(request.POST,instance=user)
        customerForm=forms.CustomerForm(request.POST,instance=customer)
        if userForm.is_valid() and customerForm.is_valid():
            user=userForm.save()
            user.set_password(user.password)
            user.save()
            customerForm.save()
            return redirect('view-customer')
    return render(request,'ecom/admin_update_customer.html',context=mydict)

# admin view the product
@login_required(login_url='adminlogin')
def admin_products_view(request):
    products=models.Product.objects.all()
    return render(request,'ecom/admin_products.html',{'products':products})

@login_required(login_url='adminlogin')
def import_products_csv(request):
   # Load form + existing products
    products = Product.objects.all()
    form = ProductCSVForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        csv_file = form.cleaned_data['csv_file']
        # Kiểm tra extension .csv
        if not csv_file.name.lower().endswith('.csv'):
            messages.error(request, 'File phải có định dạng .csv')
            return redirect('import-products-csv')

        # Đọc nội dung
        data_lines = csv_file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(data_lines)
        created = 0

        for idx, row in enumerate(reader, start=1):
            name = row.get('name', '').strip()
            price = row.get('price', '').strip()
            desc  = row.get('description', '').strip()[:40]
            img   = row.get('image', '').strip()

            print(f"[DEBUG] Row {idx}: name={name}, price={price}, image={img}")

            # Tạo đối tượng nhưng chưa save
            try:
                price_int = int(price)
            except ValueError:
                messages.warning(request, f"Row {idx}: Giá không hợp lệ, skip")
                continue

            product = Product(
                name=name,  # Không thêm timestamp
                price=price_int,
                description=desc
            )

            # Xử lý image
            if img.lower().startswith('http://') or img.lower().startswith('https://'):
                # Download từ URL
                try:
                    resp = requests.get(img, timeout=10)
                    resp.raise_for_status()
                    print(f"[DEBUG] Downloaded {len(resp.content)} bytes from {img}")
                    filename = os.path.basename(img.split('?')[0]) or f"img_{idx}.jpg"
                    product.product_image.save(
                        filename,
                        ContentFile(resp.content),
                        save=False
                    )
                    print(f"[DEBUG] Saved image to product_image/{filename}")
                except Exception as e:
                    print(f"[DEBUG] Error downloading {img}: {e}")
                    messages.warning(request, f"Row {idx}: Không tải được ảnh từ URL")
            else:
                # Fallback static
                static_path = finders.find(img)
                if static_path and os.path.isfile(static_path):
                    with open(static_path, 'rb') as f:
                        data = f.read()
                        product.product_image.save(
                            os.path.basename(img),
                            ContentFile(data),
                            save=False
                        )
                    print(f"[DEBUG] Copied static {img} into media/product_image/")
                else:
                    print(f"[DEBUG] Static image not found: {img}")
                    messages.warning(request, f"Row {idx}: Không tìm thấy static image {img}")

            # Save product
            product.save()
            created += 1

        messages.success(request, f'Imported {created} products!')
        # Sau khi import xong, làm mới form
        return redirect('import-products-csv')

    return render(request, 'ecom/import_products.html', {
        'form': form,
        'products': products,
    })

# admin add product by clicking on floating button
@login_required(login_url='adminlogin')
def admin_add_product_view(request):
    productForm=forms.ProductForm()
    if request.method=='POST':
        productForm=forms.ProductForm(request.POST, request.FILES)
        if productForm.is_valid():
            productForm.save()
        return HttpResponseRedirect('admin-products')
    return render(request,'ecom/admin_add_products.html',{'productForm':productForm})


@login_required(login_url='adminlogin')
def delete_product_view(request,pk):
    product=models.Product.objects.get(id=pk)
    product.delete()
    return redirect('admin-products')


@login_required(login_url='adminlogin')
def update_product_view(request,pk):
    product=models.Product.objects.get(id=pk)
    productForm=forms.ProductForm(instance=product)
    if request.method=='POST':
        productForm=forms.ProductForm(request.POST,request.FILES,instance=product)
        if productForm.is_valid():
            productForm.save()
            return redirect('admin-products')
    return render(request,'ecom/admin_update_product.html',{'productForm':productForm})


@login_required(login_url='adminlogin')
def admin_view_booking_view(request):
    orders=models.Orders.objects.all()
    ordered_products=[]
    ordered_bys=[]
    for order in orders:
        ordered_product=models.Product.objects.all().filter(id=order.product.id)
        ordered_by=models.Customer.objects.all().filter(id = order.customer.id)
        ordered_products.append(ordered_product)
        ordered_bys.append(ordered_by)
    return render(request,'ecom/admin_view_booking.html',{'data':zip(ordered_products,ordered_bys,orders)})


@login_required(login_url='adminlogin')
def delete_order_view(request,pk):
    order=models.Orders.objects.get(id=pk)
    order.delete()
    return redirect('admin-view-booking')

# for changing status of order (pending,delivered...)
@login_required(login_url='adminlogin')
def update_order_view(request,pk):
    order=models.Orders.objects.get(id=pk)
    orderForm=forms.OrderForm(instance=order)
    if request.method=='POST':
        orderForm=forms.OrderForm(request.POST,instance=order)
        if orderForm.is_valid():
            orderForm.save()
            return redirect('admin-view-booking')
    return render(request,'ecom/update_order.html',{'orderForm':orderForm})


# admin view the feedback
@login_required(login_url='adminlogin')
def view_feedback_view(request):
    feedbacks=models.Feedback.objects.all().order_by('-id')
    return render(request,'ecom/view_feedback.html',{'feedbacks':feedbacks})



#---------------------------------------------------------------------------------
#------------------------ PUBLIC CUSTOMER RELATED VIEWS START ---------------------
#---------------------------------------------------------------------------------
def search_view(request):
    # whatever user write in search box we get in query
    query = request.GET['query']
    products=models.Product.objects.all().filter(name__icontains=query)
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        counter=product_ids.split('|')
        product_count_in_cart=len(set(counter))
    else:
        product_count_in_cart=0

    # word variable will be shown in html when user click on search button
    word="Searched Result :"

    if request.user.is_authenticated:
        return render(request,'ecom/customer_home.html',{'products':products,'word':word,'product_count_in_cart':product_count_in_cart})
    return render(request,'ecom/index.html',{'products':products,'word':word,'product_count_in_cart':product_count_in_cart})


# Anyone can add product to cart
def add_to_cart_view(request, pk):
    product = models.Product.objects.get(id=pk)

    # Xử lý cookie để thêm sản phẩm vào giỏ hàng
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        if product_ids == "":
            product_ids = str(pk)
        else:
            product_ids = product_ids + "|" + str(pk)
    else:
        product_ids = str(pk)

    # Thêm message thông báo
    messages.info(request, f"✅ '{product.name}' đã được thêm vào giỏ hàng.")

    # Tạo response chuyển về trang home
    response = redirect('customer-home')

    # Cập nhật cookie
    response.set_cookie('product_ids', product_ids)

    return response



# for checkout of cart
def cart_view(request):
    #for cart counter
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        counter=product_ids.split('|')
        product_count_in_cart=len(set(counter))
    else:
        product_count_in_cart=0

    # fetching product details from db whose id is present in cookie
    products=None
    total=0
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        if product_ids != "":
            product_id_in_cart=product_ids.split('|')
            products=models.Product.objects.all().filter(id__in = product_id_in_cart)

            #for total price shown in cart
            for p in products:
                total=total+p.price
    return render(request,'ecom/cart.html',{'products':products,'total':total,'product_count_in_cart':product_count_in_cart})


def remove_from_cart_view(request,pk):
    #for counter in cart
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        counter=product_ids.split('|')
        product_count_in_cart=len(set(counter))
    else:
        product_count_in_cart=0

    # removing product id from cookie
    total=0
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        product_id_in_cart=product_ids.split('|')
        product_id_in_cart=list(set(product_id_in_cart))
        product_id_in_cart.remove(str(pk))
        products=models.Product.objects.all().filter(id__in = product_id_in_cart)
        #for total price shown in cart after removing product
        for p in products:
            total=total+p.price

        #  for update coookie value after removing product id in cart
        value=""
        for i in range(len(product_id_in_cart)):
            if i==0:
                value=value+product_id_in_cart[0]
            else:
                value=value+"|"+product_id_in_cart[i]
        response = render(request, 'ecom/cart.html',{'products':products,'total':total,'product_count_in_cart':product_count_in_cart})
        if value=="":
            response.delete_cookie('product_ids')
        response.set_cookie('product_ids',value)
        return response


def send_feedback_view(request):
    feedbackForm=forms.FeedbackForm()
    if request.method == 'POST':
        feedbackForm = forms.FeedbackForm(request.POST)
        if feedbackForm.is_valid():
            feedbackForm.save()
            return render(request, 'ecom/feedback_sent.html')
    return render(request, 'ecom/send_feedback.html', {'feedbackForm':feedbackForm})


#---------------------------------------------------------------------------------
#------------------------ CUSTOMER RELATED VIEWS START ------------------------------
#---------------------------------------------------------------------------------
@login_required(login_url='customerlogin')
@user_passes_test(is_customer)
def customer_home_view(request):
    products=models.Product.objects.all()
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        counter=product_ids.split('|')
        product_count_in_cart=len(set(counter))
    else:
        product_count_in_cart=0
    return render(request,'ecom/customer_home.html',{'products':products,'product_count_in_cart':product_count_in_cart})



# shipment address before placing order
@login_required(login_url='customerlogin')
def customer_address_view(request):
    # this is for checking whether product is present in cart or not
    # if there is no product in cart we will not show address form
    product_in_cart=False
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        if product_ids != "":
            product_in_cart=True
    #for counter in cart
    if 'product_ids' in request.COOKIES:
        product_ids = request.COOKIES['product_ids']
        counter=product_ids.split('|')
        product_count_in_cart=len(set(counter))
    else:
        product_count_in_cart=0

    addressForm = forms.AddressForm()
    if request.method == 'POST':
        addressForm = forms.AddressForm(request.POST)
        if addressForm.is_valid():
            # here we are taking address, email, mobile at time of order placement
            # we are not taking it from customer account table because
            # these thing can be changes
            email = addressForm.cleaned_data['Email']
            mobile=addressForm.cleaned_data['Mobile']
            address = addressForm.cleaned_data['Address']
            #for showing total price on payment page.....accessing id from cookies then fetching  price of product from db
            total=0
            if 'product_ids' in request.COOKIES:
                product_ids = request.COOKIES['product_ids']
                if product_ids != "":
                    product_id_in_cart=product_ids.split('|')
                    products=models.Product.objects.all().filter(id__in = product_id_in_cart)
                    for p in products:
                        total=total+p.price

            response = render(request, 'ecom/payment.html',{'total':total})
            response.set_cookie('email',email)
            response.set_cookie('mobile',mobile)
            response.set_cookie('address',address)
            return response
    return render(request,'ecom/customer_address.html',{'addressForm':addressForm,'product_in_cart':product_in_cart,'product_count_in_cart':product_count_in_cart})




# here we are just directing to this view...actually we have to check whther payment is successful or not
#then only this view should be accessed
@login_required(login_url='customerlogin')
def payment_success_view(request):
    from .models import Orders, Transaction, Product, Customer
    customer = Customer.objects.get(user_id=request.user.id)

    product_ids = request.COOKIES.get('product_ids', '')
    email = request.COOKIES.get('email', '')
    mobile = request.COOKIES.get('mobile', '')
    address = request.COOKIES.get('address', '')

    products = []
    if product_ids:
        product_id_in_cart = product_ids.split('|')
        products = Product.objects.filter(id__in=product_id_in_cart)

    # Đặt hàng như cũ
    for product in products:
        order, created = Orders.objects.get_or_create(
            customer=customer,
            product=product,
            status='Pending',
            email=email,
            mobile=mobile,
            address=address
        )
        Transaction.objects.get_or_create(order=order, product=product, quantity=1)

    # -------------------------
    # GỢI Ý SẢN PHẨM SAU THANH TOÁN
    # -------------------------
    # Lấy luật từ session (đã lưu khi sinh luật)
    rules = request.session.get('mafia_rules', [])
    cart_items = set(p.name for p in products)
    suggested_products = set()

    for rule in rules:
        lhs = set(rule['lhs'].split(', '))
        rhs = set(rule['rhs'].split(', '))
        if lhs.issubset(cart_items):
            suggested_products.update(rhs - cart_items)

    # Lấy thông tin sản phẩm được gợi ý
    recommended_products = Product.objects.filter(name__in=suggested_products)

    # -------------------------
    # KẾT THÚC - Trả về view với dữ liệu
    # -------------------------
    response = render(request, 'ecom/payment_success.html', {
        'recommended_products': recommended_products
    })
    response.delete_cookie('product_ids')
    response.delete_cookie('email')
    response.delete_cookie('mobile')
    response.delete_cookie('address')
    return response



@login_required(login_url='customerlogin')
@user_passes_test(is_customer)
def my_order_view(request):
    customer = models.Customer.objects.get(user_id=request.user.id)
    orders = models.Orders.objects.filter(customer=customer)

    ordered_products = []
    basket_items = set()
    
    for order in orders:
        product = models.Product.objects.get(id=order.product.id)
        ordered_products.append(([product], order))
        basket_items.add(product.name.lower().strip())  # chuẩn hoá để so sánh

    # ✅ Lấy tất cả luật từ DB
    rules = AssociationRule.objects.all()
    print("🎯 Basket Items:", basket_items)
    print("📋 Total Rules Loaded:", rules.count())

    suggestions = set()

    for rule in rules:
        lhs = set(item.strip().lower() for item in rule.lhs.split(','))
        rhs = set(item.strip() for item in rule.rhs.split(','))

        if lhs.issubset(basket_items):
            print(f"✅ Rule Matched: {lhs} => {rhs}")
            suggestions.update(rhs - basket_items)
        else:
            print(f"❌ Rule Not Matched: {lhs} => {rhs}")

    print("✨ Suggested Items:", suggestions)

    # ✅ Chuẩn hoá tên để tìm đúng sản phẩm trong DB
    standardized_suggestions = [s.strip().title() for s in suggestions]
    recommended_products = models.Product.objects.filter(name__in=standardized_suggestions)

    print("📦 Recommended Products from DB:", list(recommended_products.values('id', 'name')))

    return render(request, 'ecom/my_order.html', {
        'data': ordered_products,
        'recommended_products': recommended_products,
    })



#--------------for discharge patient bill (pdf) download and printing
import io
from xhtml2pdf import pisa
from django.template.loader import get_template
from django.template import Context
from django.http import HttpResponse


def render_to_pdf(template_src, context_dict):
    template = get_template(template_src)
    html  = template.render(context_dict)
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("ISO-8859-1")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return

@login_required(login_url='customerlogin')
@user_passes_test(is_customer)
def download_invoice_view(request,orderID,productID):
    order=models.Orders.objects.get(id=orderID)
    product=models.Product.objects.get(id=productID)
    mydict={
        'orderDate':order.order_date,
        'customerName':request.user,
        'customerEmail':order.email,
        'customerMobile':order.mobile,
        'shipmentAddress':order.address,
        'orderStatus':order.status,

        'productName':product.name,
        'productImage':product.product_image,
        'productPrice':product.price,
        'productDescription':product.description,


    }
    return render_to_pdf('ecom/download_invoice.html',mydict)






@login_required(login_url='customerlogin')
@user_passes_test(is_customer)
def my_profile_view(request):
    customer=models.Customer.objects.get(user_id=request.user.id)
    return render(request,'ecom/my_profile.html',{'customer':customer})


@login_required(login_url='customerlogin')
@user_passes_test(is_customer)
def edit_profile_view(request):
    customer=models.Customer.objects.get(user_id=request.user.id)
    user=models.User.objects.get(id=customer.user_id)
    userForm=forms.CustomerUserForm(instance=user)
    customerForm=forms.CustomerForm(request.FILES,instance=customer)
    mydict={'userForm':userForm,'customerForm':customerForm}
    if request.method=='POST':
        userForm=forms.CustomerUserForm(request.POST,instance=user)
        customerForm=forms.CustomerForm(request.POST,instance=customer)
        if userForm.is_valid() and customerForm.is_valid():
            user=userForm.save()
            user.set_password(user.password)
            user.save()
            customerForm.save()
            return HttpResponseRedirect('my-profile')
    return render(request,'ecom/edit_profile.html',context=mydict)



#---------------------------------------------------------------------------------
#------------------------ ABOUT US AND CONTACT US VIEWS START --------------------
#---------------------------------------------------------------------------------
def aboutus_view(request):
    return render(request,'ecom/aboutus.html')

def contactus_view(request):
    sub = forms.ContactusForm()
    if request.method == 'POST':
        sub = forms.ContactusForm(request.POST)
        if sub.is_valid():
            email = sub.cleaned_data['Email']
            name=sub.cleaned_data['Name']
            message = sub.cleaned_data['Message']
            send_mail(str(name)+' || '+str(email),message, settings.EMAIL_HOST_USER, settings.EMAIL_RECEIVING_USER, fail_silently = False)
            return render(request, 'ecom/contactussuccess.html')
    return render(request, 'ecom/contactus.html', {'form':sub})


@login_required(login_url='adminlogin')
def view_transactions(request):
    form = TransactionCSVForm()

    # Khởi tạo dữ liệu mặc định nếu không phải POST
    table_data = request.session.get('mafia_data', [])
    freq_table_sorted = []
    maximal_table = []

    # Khi người dùng POST CSV lên
    if request.method == 'POST':
        form = TransactionCSVForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'Vui lòng tải lên file CSV.')
            else:
                try:
                    csv_reader = csv.DictReader(TextIOWrapper(csv_file.file, encoding='utf-8'))
                    table_data = []

                    for row in csv_reader:
                        transaction_id = row.get('Transaction ID')
                        items_str = row.get('Items')

                        if not transaction_id or not items_str:
                            continue

                        try:
                            items = ast.literal_eval(items_str)
                            formatted_items = ', '.join(sorted(items))
                            table_data.append({
                                'order_id': transaction_id,
                                'items': formatted_items
                            })
                        except Exception as e:
                            messages.warning(request, f"Lỗi dòng {transaction_id}: {str(e)}")

                    request.session['mafia_data'] = table_data
                    messages.success(request, f"Đã import {len(table_data)} giao dịch.")
                except Exception as e:
                    messages.error(request, f"Lỗi xử lý file: {str(e)}")

    # Tính tần suất sản phẩm nếu có dữ liệu
    if table_data:
        freq_count = {}
        for row in table_data:
            items = [item.strip() for item in row['items'].split(',')]
            for item in items:
                freq_count.setdefault(item, set()).add(row['order_id'])

        freq_table = [{
            'product_name': product,
            'order_ids': sorted(order_ids),
            'count': len(order_ids)
        } for product, order_ids in freq_count.items()]
        freq_table_sorted = sorted(freq_table, key=lambda x: -x['count'])

        # Gọi thuật toán MAFIA
        from .mafia import find_maximal_itemsets
        transactions = [[item.strip() for item in row['items'].split(',')] for row in table_data]
        mfi_result = find_maximal_itemsets(transactions, min_support=0.3)
        # Lưu vào session để gợi ý sau này
        request.session['mafia_maximal_itemsets'] = [list(s) for s in mfi_result]

        maximal_table = [{
            'index': i + 1,
            'itemset': ', '.join(sorted(itemset)),
            'length': len(itemset)
        } for i, itemset in enumerate(mfi_result)]

    return render(request, 'ecom/view_transactions_mafia.html', {
        'form': form,
        'table_data': table_data,
        'freq_table': freq_table_sorted,
        'maximal_table': maximal_table
    })




@login_required(login_url='adminlogin')
def basket_market_view(request):
    from .mafia import find_maximal_itemsets
    from .models import AssociationRule

    result = []

    # Lấy min_support từ form (dạng chuỗi, thay dấu phẩy nếu có)
    min_support = float(request.GET.get('min_support', '0.3').replace(',', '.'))

    # Lấy min_conf từ form, KHÔNG gán mặc định
    min_conf_str = request.GET.get('min_conf', '').replace(',', '.')
    if min_conf_str.strip():
        try:
            min_confidence = float(min_conf_str)
            if not (0 <= min_confidence <= 1):
                messages.warning(request, "min_conf phải nằm trong khoảng [0, 1].")
                min_confidence = None
        except ValueError:
            messages.warning(request, "min_conf không hợp lệ.")
            min_confidence = None
    else:
        min_confidence = None

    # Lấy giao dịch từ session
    transactions = request.session.get('mafia_data', [])
    if not transactions:
        messages.warning(request, "Vui lòng import transaction trước.")
        return redirect('view-transactions')

    # Tạo danh sách basket
    basket = [[item.strip() for item in row['items'].split(',')] for row in transactions]

    # Sinh tập phổ biến cực đại
    maximal_sets = find_maximal_itemsets(basket, min_support=min_support)

    result = [{
        'index': i + 1,
        'itemset': ', '.join(sorted(itemset)),
        'length': len(itemset)
    } for i, itemset in enumerate(maximal_sets)]

    # Sinh luật nếu có min_conf được nhập
    if min_confidence is not None:
        AssociationRule.objects.all().delete()
        generate_association_rules(maximal_sets, basket, min_confidence)
        total_rules = AssociationRule.objects.count()
        messages.success(request, f"Đã sinh {total_rules} luật với min_conf = {min_confidence}")
    else:
        messages.info(request, "Không sinh luật vì chưa nhập min_conf.")

    return render(request, 'ecom/basket_market.html', {
        'result': result,
        'min_support': min_support,
        'min_conf': min_confidence
    })



@login_required(login_url='adminlogin')
def mafia_recommend_view(request):
    # Lấy dữ liệu từ session
    table_data = request.session.get('mafia_data', [])
    if not table_data:
        messages.warning(request, "Vui lòng import transaction trước.")
        return redirect('view-transactions')

    transactions = [[item.strip() for item in row['items'].split(',')] for row in table_data]

    # Lấy ngưỡng từ request
    minsup_ratio = float(request.POST.get('minsup', 0.3)) if request.method == 'POST' else 0.3
    min_conf = float(request.POST.get('min_conf', 0.3)) if request.method == 'POST' else 0.3

    minsup = max(int(minsup_ratio * len(transactions)), 1)

    # Chuyển dữ liệu về dạng bitmap (tidsets)
    tidsets = defaultdict(set)
    for tid, transaction in enumerate(transactions):
        for item in transaction:
            tidsets[item].add(tid)

    all_tids = set(range(len(transactions)))
    items = sorted(tidsets.keys())

    # Tạo các itemsets phổ biến
    MFI = []
    for i in range(1, len(items) + 1):  # Kiểm tra từ độ dài 1 đến độ dài các itemsets
        for comb in combinations(items, i):
            comb_set = set(comb)
            support = len(all_tids.intersection(*[tidsets[item] for item in comb_set]))
            if support >= minsup:
                MFI.append(comb_set)

    # Sinh các luật từ các itemsets có độ dài >= 2
    rules = []
    total_transactions = len(transactions)

    # Lấy tất cả các itemsets có độ dài >= 2
    for itemset in MFI:
        if len(itemset) < 2:
            continue
        # Kiểm tra mọi tập con của itemset có độ dài >= 2
        for i in range(1, len(itemset)):  # Bắt đầu từ độ dài 1 đến độ dài itemset-1
            for lhs in combinations(itemset, i):
                lhs = set(lhs)
                rhs = itemset - lhs
                # Tính toán hỗ trợ và confidence
                lhs_count = sum(1 for t in transactions if lhs.issubset(set(t)))
                both_count = sum(1 for t in transactions if lhs.issubset(set(t)) and rhs.issubset(set(t)))
                if lhs_count == 0:
                    continue
                confidence = both_count / lhs_count
                if confidence >= min_conf:
                    rhs_count = sum(1 for t in transactions if rhs.issubset(set(t)))
                    lift = confidence / (rhs_count / total_transactions) if rhs_count else 0
                    rules.append({
                        'lhs': ', '.join(sorted(lhs)),
                        'rhs': ', '.join(sorted(rhs)),
                        'support': round(both_count / total_transactions, 2),
                        'confidence': round(confidence, 2),
                        'lift': round(lift, 2),
                        'frequency': both_count
                    })

        # Sắp xếp các luật theo confidence và support
    sorted_rules = sorted(rules, key=lambda x: (-x['confidence'], -x['support']))

    # Lưu luật vào session
    request.session['mafia_rules'] = sorted_rules

    return render(request, 'ecom/mafia_recommend.html', {
        'rules': sorted_rules,
        'minsup': minsup_ratio,
        'min_conf': min_conf
    })


def generate_association_rules(mfi_itemsets, transactions, min_confidence):
    from itertools import combinations

    def count_support(itemset):
        return sum(1 for t in transactions if itemset.issubset(set(t)))

    rules = []
    total_transactions = len(transactions)

    # Xoá luật cũ (tuỳ chỉnh nếu muốn giữ lịch sử)
    AssociationRule.objects.all().delete()

    for itemset in mfi_itemsets:
        itemset = set(itemset)
        if len(itemset) < 2:
            continue

        for i in range(1, len(itemset)):
            for lhs in combinations(itemset, i):
                lhs = set(lhs)
                rhs = itemset - lhs
                if not rhs:
                    continue

                lhs_support = count_support(lhs)
                full_support = count_support(itemset)

                if lhs_support == 0:
                    continue

                confidence = full_support / lhs_support

                if confidence >= min_confidence:
                    rhs_support = count_support(rhs)
                    lift = confidence / (rhs_support / total_transactions) if rhs_support else 0

                    # Lưu luật vào DB
                    AssociationRule.objects.create(
                        lhs=', '.join(sorted(lhs)),
                        rhs=', '.join(sorted(rhs)),
                        support=round(full_support / total_transactions, 2),
                        confidence=round(confidence, 2),
                        lift=round(lift, 2),
                        frequency=full_support
                    )

    return AssociationRule.objects.all().order_by('-confidence', '-support')