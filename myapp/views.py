#myapp/view.py
# from django.shortcuts import render
# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.http import HttpResponse
from django.db import connection
from django.contrib.auth.models import User
from django.shortcuts import render, get_object_or_404, Http404
from django.utils import timezone
from .forms import LoginForm, SlipUploadForm
from .models import Usert, Position, Loan, Payment, Status, LoanType
from datetime import timedelta
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.db.models import Sum, F
from django.db.models import Max
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import math
from datetime import timedelta


def test_db_connection():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        one = cursor.fetchone()
        print(one)

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            
            # ตรวจสอบจากฐานข้อมูลโดยตรง
            try:
                user = Usert.objects.get(appuser=username, apppass=password)
                position = user.position.level
                request.session['username'] = username
                request.session['position'] = position  # เก็บตำแหน่งใน session
                if position == 0:  # superadmin
                    return redirect('index')
                else:
                    return redirect('loan')
            except Usert.DoesNotExist:
                form.add_error(None, 'Invalid username or password')
    else:
        form = LoginForm()

    return render(request, 'login.html', {'form': form})

def index(request):
    username = request.session.get('username', 'Guest')
    user = Usert.objects.get(appuser=username)
    user_level = user.position.level
    
    today = timezone.now().date()
    
    # ข้อมูลเงินกู้ทั้งหมด
    total_loans = Loan.objects.count()
    total_outstanding_amount = Payment.objects.filter(status__description='ค้าง').aggregate(total_amount=Sum('amount'))['total_amount'] or 0
    total_paid_amount = Payment.objects.filter(status__description='จ่ายแล้ว').aggregate(total_amount=Sum('amount'))['total_amount'] or 0
    total_due_loans = Loan.objects.filter(payment__due_date__lt=today, payment__status__description='ยังไม่ถึงกำหนด').count()
    
    # สถานะการชำระเงิน
    overdue_payments_count = Payment.objects.filter(due_date__lt=today, status__description='ค้าง').count()
    payments_today_count = Payment.objects.filter(due_date=today, status__description='วันนี้').count()
    due_payments_count = Payment.objects.filter(due_date__exact=today).count()
    
    # ข้อมูลเกี่ยวกับผู้ใช้งาน
    total_users = User.objects.count()
    active_users_count = User.objects.filter(is_active=True).count()
    inactive_users_count = User.objects.filter(is_active=False).count()
    
    # ข้อมูลสำหรับกราฟ
    daily_labels = ["วันที่ 1", "วันที่ 2", "วันที่ 3", "วันที่ 4", "วันที่ 5"]  # เปลี่ยนเป็นวันที่จริง
    daily_data = [1000, 2000, 1500, 1200, 1800]  # ข้อมูลการชำระเงินที่แท้จริง
    monthly_labels = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม"]  # เปลี่ยนเป็นเดือนจริง
    monthly_data = [5000, 6000, 7000, 8000, 9000]  # ข้อมูลการชำระเงินที่แท้จริง

    context = {
        'total_loans': total_loans,
        'total_outstanding_amount': total_outstanding_amount,
        'total_paid_amount': total_paid_amount,
        'total_due_loans': total_due_loans,
        'overdue_payments_count': overdue_payments_count,
        'payments_today_count': payments_today_count,
        'due_payments_count': due_payments_count,
        'total_users': total_users,
        'active_users_count': active_users_count,
        'inactive_users_count': inactive_users_count,
        'daily_labels': daily_labels,
        'daily_data': daily_data,
        'monthly_labels': monthly_labels,
        'monthly_data': monthly_data,
    }
    

    return render(request, 'index.html', context)

def addaccount(request):
    success_message = None
    error_message = None

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        position_id = request.POST.get('position')
        
        try:
            position = Position.objects.get(id=position_id)
            new_user = Usert(appuser=username, apppass=password, position=position)
            new_user.save()
            success_message = "เพิ่มสำเร็จ"
        except Exception as e:
            error_message = "เพิ่มไม่สำเร็จ: " + str(e)
    
    users = Usert.objects.all()
    positions = Position.objects.all()
    
    return render(request, 'addaccount.html', {
        'success_message': success_message,
        'error_message': error_message,
        'users': users,
        'positions': positions,
    })



def add_loan(request):
    success_message = None
    error_message = None
    users = []

    username = request.session.get('username')
    logged_in_user = Usert.objects.get(appuser=username)
    user_level = logged_in_user.position.level

    if request.method == 'POST':
        customer_name = request.POST.get('customer_name')
        start_date_str = request.POST.get('start_date')
        principal_str = request.POST.get('principal')
        num_installments_str = request.POST.get('num_installments')
        perday_str = request.POST.get('perday')
        interest_rate_str = request.POST.get('interest_rate')
        admin_user_id = request.POST.get('admin_user')
        loan_type_id = int(request.POST.get('loan_type'))
        status = 1  # ค่าเริ่มต้นสำหรับสถานะ

        try:
            principal = math.ceil(float(principal_str))  # ปัดเศษขึ้น
            num_installments = int(num_installments_str) if num_installments_str else None
            perday = math.ceil(float(perday_str))  # ปัดเศษขึ้น
            interest_rate = math.ceil(float(interest_rate_str))  # ปัดเศษขึ้น
        except ValueError as e:
            error_message = 'ข้อมูลที่กรอกไม่ถูกต้อง: {}'.format(e)
            users = get_users_for_level(user_level, logged_in_user)
            return render(request, 'addloan.html', {'error_message': error_message, 'users': users, 'today_date': timezone.now().date()})

        # ตรวจสอบประเภทสินเชื่อ
        try:
            loan_type = LoanType.objects.get(id=loan_type_id)
        except LoanType.DoesNotExist:
            error_message = 'ประเภทสินเชื่อไม่ถูกต้อง'
            users = get_users_for_level(user_level, logged_in_user)
            return render(request, 'addloan.html', {'error_message': error_message, 'users': users, 'today_date': timezone.now().date()})

        # กำหนดจำนวนงวดเป็น None สำหรับประเภทดอกลอย
        if loan_type.name == 'ดอกลอย':
            num_installments = 0  # เปลี่ยนเป็น 0 แทนการใช้ None
            
        else:
            if not num_installments:
                error_message = 'จำนวนงวดไม่สามารถเว้นว่างได้'
                users = get_users_for_level(user_level, logged_in_user)
                return render(request, 'addloan.html', {'error_message': error_message, 'users': users, 'today_date': timezone.now().date()})

        admin_user = Usert.objects.get(id=admin_user_id)
        loan_name = f"{customer_name} ต้น {principal} ราย {perday} วัน"

        start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()

        try:
            # สร้างข้อมูลสินเชื่อใหม่
            loan = Loan.objects.create(
                name=loan_name,
                customer=customer_name,
                user=admin_user,
                start_date=start_date,
                principal=principal,
                installments=num_installments,  # ใช้ 0 แทน None
                perday=perday,
                interest=interest_rate,
                status_id=status,
                loan_type=loan_type,  # กำหนดประเภทสินเชื่อ
            )

            # สร้างตารางการชำระเงินสำหรับสินเชื่อที่ไม่ใช่ดอกลอย
            
            payments = generate_payment_schedule(loan, num_installments, principal, interest_rate, start_date, perday, loan_type)
            for payment in payments:
                Payment.objects.create(
                    loan=loan,
                    installment_number=payment['installment_number'],
                    due_date=payment['due_date'],
                    amount=math.ceil(payment['amount'])  # ปัดเศษขึ้น
                )

            success_message = 'เพิ่มข้อมูลสินเชื่อเรียบร้อยแล้ว'
            users = get_users_for_level(user_level, logged_in_user)
            return render(request, 'addloan.html', {'success_message': success_message, 'users': users, 'today_date': timezone.now().date()})
        except Exception as e:
            error_message = str(e)
            return render(request, 'addloan.html', {'error_message': error_message, 'users': users, 'today_date': timezone.now().date()})

    users = get_users_for_level(user_level, logged_in_user)
    return render(request, 'addloan.html', {'users': users, 'today_date': timezone.now().date()})


def get_users_for_level(user_level, logged_in_user):
    """ Return a list of users based on the login user's level """
    if user_level == 2:  # user
        return Usert.objects.filter(id=logged_in_user.id)
    else:
        return Usert.objects.all()

def update_loan_and_payment_status():
    loans = Loan.objects.all()
    today = timezone.now().date()

    # Status instances
    normal_status = Status.objects.get(id=1)  # ปกติ
    overdue_status = Status.objects.get(id=2)  # ค้างจ่าย
    today_status = Status.objects.get(id=3)  # วันนี้
    not_due_status = Status.objects.get(id=4)  # ยังไม่ถึงกำหนด
    paid_status = Status.objects.get(id=6)  # จ่ายแล้ว
    completed_status = Status.objects.get(id=5)  # ครบแล้ว

    for loan in loans:
        payments = Payment.objects.filter(loan=loan).order_by('installment_number')
        overdue_exists = False
        today_exists = False
        all_paid = True

        # Calculate and update payment statuses
        for payment in payments:
            if payment.due_date > today:
                payment.status = not_due_status
            elif payment.due_date == today and not payment.slip:
                payment.status = today_status
                today_exists = True
            elif payment.due_date < today and not payment.slip:
                payment.status = overdue_status
                overdue_exists = True
            elif payment.slip:
                payment.status = paid_status
            payment.save()

        # Update loan status based on payment statuses
        if overdue_exists:
            loan.status = overdue_status
        elif today_exists:
            loan.status = today_status
        elif payments.filter(status=not_due_status).exists():
            loan.status = normal_status
        elif payments.filter(status=paid_status).count() == payments.count():
            loan.status = completed_status
        else:
            loan.status = normal_status

        loan.save()

from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from datetime import timedelta
from .models import Loan, Payment, Status

def detail_loan(request, loan_id):
    try:
        loan = get_object_or_404(Loan, loanid=loan_id)
    except Loan.DoesNotExist:
        return render(request, '404.html', status=404)

    today = timezone.now().date()

    normal_status = Status.objects.get(id=1)
    overdue_status = Status.objects.get(id=2)
    today_status = Status.objects.get(id=3)
    not_due_status = Status.objects.get(id=4)
    paid_status = Status.objects.get(id=6)
    completed_status = Status.objects.get(id=5)

    if loan.loan_type.name == 'ดอกลอย':
        installments = handle_floating_loan(loan, today, normal_status, overdue_status, today_status, not_due_status, paid_status, completed_status)
    else:
        installments = handle_fixed_loan(loan, today, normal_status, overdue_status, today_status, not_due_status, paid_status, completed_status)

    return render(request, 'detailloan.html', {
        'loan': loan,
        'installments': installments,
        'today': today,
    })

def handle_floating_loan(loan, today, normal_status, overdue_status, today_status, not_due_status, paid_status, completed_status):
    installments = []
    current_due_date = loan.start_date
    total_amount = loan.principal * loan.interest / 100

    # ตรวจสอบงวดล่าสุด
    latest_payment = Payment.objects.filter(loan=loan).order_by('-installment_number').first()
    next_installment_number = (latest_payment.installment_number + 1) if latest_payment else 1
    
    if latest_payment:
        # ตรวจสอบสถานะของงวดล่าสุด
        if latest_payment.status == overdue_status:
            current_due_date = latest_payment.due_date + timedelta(days=loan.perday)
        elif latest_payment.status == paid_status:
            current_due_date = latest_payment.due_date + timedelta(days=loan.perday)
        else:
            # หากสถานะไม่ตรงกับที่คาดหวัง ให้หยุดสร้างงวดใหม่
            return Payment.objects.filter(loan=loan).order_by('installment_number')
    else:
        # หากไม่มีงวดชำระใด ๆ ให้เริ่มต้นจากวันที่เริ่มต้น
        current_due_date = loan.start_date

    while True:
        payment = Payment.objects.filter(loan=loan, due_date=current_due_date).first()
        amount = total_amount if payment else loan.principal * loan.interest / 100

        installments.append({
            'installment_number': next_installment_number,
            'due_date': current_due_date,
            'amount': amount,
            'slip': payment.slip if payment else None,
            'status': payment.status if payment else not_due_status,
            'payment_id': payment.id if payment else None
        })

        # อัปเดตหมายเลขงวดถัดไป
        next_installment_number += 1

        current_due_date += timedelta(days=loan.perday)

        # หยุดการวนลูปเมื่อมีจำนวนงวดครบ
        if len(installments) >= loan.installments:
            break

    # อัปเดตสถานะการชำระเงิน
    update_payment_status(loan, installments, today, normal_status, overdue_status, today_status, not_due_status, paid_status)

    # อัปเดตสถานะของสินเชื่อ
    update_loan_status(loan, normal_status, overdue_status, today_status, completed_status)

    # คืนค่ารายการการชำระเงิน
    return Payment.objects.filter(loan=loan).order_by('installment_number')




def handle_fixed_loan(loan, today, normal_status, overdue_status, today_status, not_due_status, paid_status, completed_status):
    payments = Payment.objects.filter(loan=loan).order_by('installment_number')

    for payment in payments:
        if payment.due_date > today:
            payment.status = not_due_status
        elif payment.due_date == today and not payment.slip:
            payment.status = today_status
        elif payment.due_date < today and not payment.slip:
            payment.status = overdue_status
        elif payment.slip:
            payment.status = paid_status
        payment.save()

    # อัปเดตสถานะของสินเชื่อ
    update_loan_status(loan, normal_status, overdue_status, today_status, completed_status)

    return payments

def update_payment_status(loan, installments, today, normal_status, overdue_status, today_status, not_due_status, paid_status):
    overdue_exists = False
    today_exists = False

    for installment in installments:
        payment = Payment.objects.filter(loan=loan, due_date=installment['due_date']).first()
        if payment:
            if payment.due_date > today:
                payment.status = not_due_status
            elif payment.due_date == today:
                if payment.slip:
                    payment.status = paid_status
                else:
                    payment.status = today_status
                    today_exists = True
            elif payment.due_date < today:
                payment.status = overdue_status
                overdue_exists = True
            payment.save()
        else:
            payment = Payment.objects.create(
                loan=loan,
                installment_number=installment['installment_number'],
                due_date=installment['due_date'],
                amount=installment['amount'],
                status=not_due_status
            )
            if payment.due_date < today:
                payment.status = overdue_status
                overdue_exists = True
            elif payment.due_date == today:
                payment.status = today_status
            payment.save()

    return overdue_exists, today_exists

def update_loan_status(loan, normal_status, overdue_status, today_status, completed_status):
    if Payment.objects.filter(loan=loan, status=overdue_status).exists():
        loan.status = overdue_status
    elif Payment.objects.filter(loan=loan, status=today_status).exists():
        loan.status = today_status
    elif Payment.objects.filter(loan=loan, status=normal_status).exists():
        loan.status = normal_status
    elif Payment.objects.filter(loan=loan, status=completed_status).count() == Payment.objects.filter(loan=loan).count():
        loan.status = completed_status
    else:
        loan.status = normal_status

    loan.save()





def loan(request):
    today = timezone.now().date()
    update_loan_and_payment_status() 
    username = request.session.get('username', 'Guest')
    user = Usert.objects.get(appuser=username)
    user_level = user.position.level
    #loans = Loan.objects.select_related('loan_type').all()  # ใช้ select_related เพื่อโหลดข้อมูลที่เชื่อมโยง
    loan_types = LoanType.objects.all()

    if user_level == 0:  # superadmin
        loans = Loan.objects.all()
    elif user_level == 1:  # admin
        loans = Loan.objects.all()
    elif user_level == 2:  # user
        loans = Loan.objects.filter(user=user)

    loan_data = []

    for loan in loans:
        payments = Payment.objects.filter(loan=loan).order_by('installment_number')
        
        next_due_date = None
        today_pay = 0
        for payment in payments:
            if payment.due_date == today and (payment.slip is None or payment.slip == ''):
                next_due_date = payment.due_date
                break


        total_interest = loan.get_total_interest()

        total_installments = payments.count()
        paid_installments = payments.filter(slip__isnull=False).filter(slip__gt='').count()
        installment_info = f"{paid_installments}/{total_installments}"

        loan_data.append({
            'name': loan.name,
            'customer': loan.customer,
            'user': loan.user.appuser if loan.user else 'ไม่มีผู้ดูแล',
            'start_date': loan.start_date,
            'principal': loan.principal,
            'installments': installment_info,
            'interest': total_interest,
            'next_due_date': next_due_date,
            'status': loan.status.id,  # ใช้ description จาก status
            'loan_id': loan.loanid,
            'today' : today,
            'user_level' : user_level,
            'type' : user_level,
            'loan_types': loan.loan_type,

        })

    context = {
        'loans': loan_data,
    }
    
    return render(request, 'loan.html', context)


def upload_slip(request, payment_id):
    payment = get_object_or_404(Payment, pk=payment_id)
    if request.method == 'POST':
        form = SlipUploadForm(request.POST, request.FILES)
        if form.is_valid():
            payment.slip = form.cleaned_data['slip']
            payment.save()
            return redirect('loan_detail', loan_id=payment.loan.loanid)
    else:
        form = SlipUploadForm()
    return render(request, 'upload_slip.html', {'form': form, 'payment': payment})

def generate_payment_schedule(loan, num_installments, principal, interest_rate, start_date, perday, loan_type):
    payments = []
    if num_installments == 0:
        num_installments = 1
    total_amount = principal + (principal * interest_rate / 100)
    amount_per_installment = total_amount / num_installments

    if isinstance(start_date, str):
        start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
    
    first_due_date = start_date + timedelta(days=perday)
    
    for i in range(num_installments):
        due_date = first_due_date + timedelta(days=i * perday)
        payments.append({
            'installment_number': i + 1,
            'due_date': due_date,
            'amount': amount_per_installment
        })
    
    return payments



def account_settings(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, 'Your password was successfully updated!')
            return redirect('account_settings')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'account_settings.html', {
        'form': form
    })

def sign_out(request):
    logout(request)
    return redirect('login')

def dashboard(request):
    total_principal = Loan.objects.aggregate(Sum('principal_amount'))['principal_amount__sum']
    total_interest = Loan.objects.aggregate(Sum('total_interest_paid'))['total_interest_paid__sum']
    total_loans = Loan.objects.count()
    overdue_loans = Loan.objects.filter(due_date__lt=timezone.now(), installments_paid__lt=F('total_installments')).count()
    unpaid_interest = Loan.objects.filter(due_date__lt=timezone.now(), installments_paid__lt=F('total_installments')).aggregate(Sum('total_interest_paid'))['total_interest_paid__sum']
    paid_off_loans = Loan.objects.filter(installments_paid=F('total_installments')).count()
    today_payments = Loan.objects.filter(due_date=timezone.now().date())
    overdue_customers = Loan.objects.filter(due_date__lt=timezone.now(), installments_paid__lt=F('total_installments')).values('customer__name')

    context = {
        'total_principal': total_principal,
        'total_interest': total_interest,
        'total_loans': total_loans,
        'overdue_loans': overdue_loans,
        'unpaid_interest': unpaid_interest,
        'paid_off_loans': paid_off_loans,
        'today_payments': today_payments,
        'overdue_customers': overdue_customers,
    }
    return render(request, 'index.html', context)

@csrf_exempt
def delete_loan(request):
    if request.method == 'POST':
        loan_id = request.POST.get('loan_id')
        try:
            loan = Loan.objects.get(pk=loan_id)
            payments = loan.payment_set.all()
            for payment in payments:
                payment.delete()
            loan.delete()
            return JsonResponse({'success': True})
        except Loan.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'ไม่พบข้อมูลสินเชื่อ'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'คำขอไม่ถูกต้อง'})

def update_loan_and_payment_status():
    loans = Loan.objects.all()
    today = timezone.now().date()

    # Status instances
    normal_status = Status.objects.get(id=1)  # ปกติ
    overdue_status = Status.objects.get(id=2)  # ค้างจ่าย
    today_status = Status.objects.get(id=3)  # วันนี้
    not_due_status = Status.objects.get(id=4)  # ยังไม่ถึงกำหนด
    paid_status = Status.objects.get(id=6)  # จ่ายแล้ว
    completed_status = Status.objects.get(id=5)  # ครบแล้ว

    for loan in loans:
        payments = Payment.objects.filter(loan=loan).order_by('installment_number')
        overdue_exists = False
        today_exists = False
        all_paid = True

        # Calculate and update payment statuses
        for payment in payments:
            if payment.due_date > today:
                payment.status = not_due_status
            elif payment.due_date == today and not payment.slip:
                payment.status = today_status
                today_exists = True
            elif payment.due_date < today and not payment.slip:
                payment.status = overdue_status
                overdue_exists = True
            elif payment.slip:
                payment.status = paid_status
            payment.save()

        # Update loan status based on payment statuses
        if overdue_exists:
            loan.status = overdue_status
        elif today_exists:
            loan.status = today_status
        elif payments.filter(status=not_due_status).exists():
            loan.status = normal_status
        elif payments.filter(status=paid_status).count() == payments.count():
            loan.status = completed_status
        else:
            loan.status = normal_status

        loan.save()

