#myapp/url.py
from django.urls import path
from myapp import views
from .views import login_view, addaccount, add_loan, loan, detail_loan, upload_slip

urlpatterns = [
    path('', login_view, name='login'),  # หน้า login เป็นหน้าแรก
    path('index/', views.index, name='index'),
    path('addaccount/', views.addaccount, name='addaccount'),
    path('addloan/', views.add_loan, name='add_loan'),
    path('loan/', views.loan, name='loan'),
    path('detail/<int:loan_id>/', views.detail_loan, name='loan_detail'),
    path('upload_slip/<int:payment_id>/', upload_slip, name='upload_slip'),
    path('account_settings/', views.account_settings, name='account_settings'),
    path('sign_out/', views.sign_out, name='sign_out'),
    path('delete_loan/', views.delete_loan, name='delete_loan'),
    
]
