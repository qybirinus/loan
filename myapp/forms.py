from django import forms
from .models import Payment

class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)

class SlipUploadForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['slip']

class UpdateStatusForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['status']
