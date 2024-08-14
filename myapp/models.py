#myapp/models.py
import os
from django.db import models
from django.utils import timezone
from decimal import Decimal
from django.conf import settings


# Create your models here.


class Position(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, default='default_name')  # กำหนดค่าดีฟอลต์ที่นี่
    level = models.IntegerField()

    def __str__(self):
        return self.name


class Usert(models.Model):
    id = models.AutoField(primary_key=True)
    appuser = models.CharField(max_length=150, unique=True)
    apppass = models.CharField(max_length=128)
    position = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.user
    
class Status(models.Model):
    id = models.AutoField(primary_key=True)
    description = models.CharField(max_length=20)    

    def __str__(self):
        return self.description

class LoanType(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name   

class Loan(models.Model):
    loanid = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    customer = models.CharField(max_length=255, default='')
    user = models.ForeignKey('Usert', on_delete=models.SET_NULL, null=True)
    start_date = models.DateField(default=timezone.now)
    principal = models.IntegerField()
    perday = models.IntegerField()
    installments = models.IntegerField()
    interest = models.IntegerField()
    status = models.ForeignKey(Status, on_delete=models.SET_NULL, null=True, related_name='loan_status')
    loan_type = models.ForeignKey(LoanType, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    def get_latest_payment_status(self):
        latest_payment = self.payment_set.order_by('-due_date').first()
        if latest_payment:
            return latest_payment.status
        return "No payments"

    def get_latest_due_date(self):
        latest_due_date = self.payment_set.order_by('-due_date').first()
        if latest_due_date:
            return latest_due_date.due_date
        return self.start_date

    def get_total_interest(self):
        # ดอกเบี้ยรวม
        return self.principal * self.interest / 100

    def get_installment_info(self):
        total_installments = self.payment_set.count()
        latest_payment = self.payment_set.order_by('-installment_number').first()
        if latest_payment:
            return f"{latest_payment.installment_number}/{total_installments}"
        return f"0/{total_installments}"
        
    
    @property
    def is_overdue(self):
        return self.due_date < timezone.now().date() and self.installments_paid < self.total_installments

    @property
    def is_paid_off(self):
        return self.installments_paid == self.total_installments
    
def upload_to(instance, filename):
    # รับวันที่และเวลาปัจจุบัน
    now = timezone.now()
    date_str = now.strftime("%Y%m%d_%H%M%S")
    
    # รับ ID ของ loan และ detail_loan
    loan_id = instance.loan.id
    detail_loan_id = instance.id  # สมมุติว่ามี id ใน Payment model

    # สร้างชื่อไฟล์ใหม่
    new_filename = f"{loan_id}_{detail_loan_id}_{date_str}_{filename}"
    return os.path.join('slips/', new_filename)

class Payment(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE)
    installment_number = models.IntegerField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=0)
    slip = models.ImageField(upload_to='slips/', blank=True, null=True)
    status = models.ForeignKey(Status, on_delete=models.SET_NULL, null=True, related_name='payment_status')

    def update_status(self):
        today = timezone.now().date()
        if self.slip:
            self.status = Status.objects.get(description='จ่ายแล้ว')
        elif today > self.due_date:
            self.status = Status.objects.get(description='ค้าง')
        elif today == self.due_date:
            self.status = Status.objects.get(description='วันนี้')
        else:
            self.status = Status.objects.get(description='ยังไม่ถึงกำหนด')
    
    def save(self, *args, **kwargs):
        # ตรวจสอบว่าการเรียก save ซ้ำซ้อนหรือไม่
        if not kwargs.get('update_status', False):
            self.update_status()
        super(Payment, self).save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        # ลบไฟล์สลิปก่อนลบบันทึก
        if self.slip:
            if os.path.isfile(self.slip.path):
                os.remove(self.slip.path)
        super(Payment, self).delete(*args, **kwargs)

 
