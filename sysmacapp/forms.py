from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, CustomProduct

class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(max_length=254, required=True, help_text='Required. Enter a valid email address.')

    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already in use.")
        return email

class CustomProductForm(forms.ModelForm):
    class Meta:
        model = CustomProduct
        fields = ['name', 'company', 'brand', 'category', 'price', 'unit', 'product', 'description', 'main_image', 'stock_quantity', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter product name',
                'required': True
            }),
            'company': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter company name'
            }),
            'brand': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter brand name'
            }),
            'category': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter category'
            }),
            'unit': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter unit (e.g., kg, pcs, ltr)'
            }),
            'product': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter product type'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter product description'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00',
                'required': True
            }),
            'stock_quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': '0'
            }),
            'main_image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = True
        self.fields['price'].required = True
        self.fields['price'].help_text = 'Enter price in decimal format (e.g., 99.99)'
        self.fields['stock_quantity'].help_text = 'Enter available quantity'