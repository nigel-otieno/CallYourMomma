from django import forms
from django.contrib.auth import get_user_model
from .models import *
User = get_user_model()

class EmailUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email']
