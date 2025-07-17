from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, CustomProduct, EditedAPIProduct  # Added EditedAPIProduct import


# forms.py - Add this at the top of your file
from django.forms import ClearableFileInput, MultipleHiddenInput
from django.utils.translation import ngettext

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

    def __init__(self, attrs=None):
        default_attrs = {'multiple': True}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)

    def value_from_datadict(self, data, files, name):
        if hasattr(files, 'getlist'):
            return files.getlist(name)
        return None


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


class EditedAPIProductForm(forms.ModelForm):
    class Meta:
        model = EditedAPIProduct
        fields = ['name', 'product', 'category', 'unit', 'tax_code', 'company', 
                 'brand', 'text6', 'price', 'original_price', 'image']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter product name',
                'required': True
            }),
            'product': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter product type'
            }),
            'category': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter category'
            }),
            'unit': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter unit (e.g., kg, pcs, ltr)'
            }),
            'tax_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter tax code'
            }),
            'company': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter company name'
            }),
            'brand': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter brand name'
            }),
            'text6': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter additional info'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00',
                'required': True
            }),
            'original_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            })
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = True
        self.fields['price'].required = True
        self.fields['price'].help_text = 'Enter price in decimal format (e.g., 99.99)'



from django import forms
from .models import Product

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name', 'product_type', 'category', 'unit', 'tax_code',
            'company', 'brand', 'text6', 'price', 'original_price', 'is_active'
        ]






# forms.py - Modify your existing forms

from django import forms
from .models import ProductImage

# forms.py - Update your BaseProductForm
class BaseProductForm:
    additional_images = forms.FileField(
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        required=False,
        label='Additional Images'
    )

    def save_additional_images(self, product):
        """Handle saving additional images"""
        if 'additional_images' in self.files:
            for image in self.files.getlist('additional_images'):
                if image:  # Only save if there's actually a file
                    if isinstance(product, CustomProduct):
                        ProductImage.objects.create(custom_product=product, image=image)
                    else:
                        ProductImage.objects.create(api_product=product, image=image)

class  CustomProductForm(forms.ModelForm):
    class Meta:
        model = CustomProduct
        fields = ['name', 'company', 'brand', 'category', 'price', 
                 'unit', 'product', 'description', 'main_image', 
                 'stock_quantity', 'is_active']
        
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter product name',
                'required': True
            }),
            # ... keep your other widgets as they were ...
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = True
        self.fields['price'].required = True
        self.fields['price'].help_text = 'Enter price in decimal format (e.g., 99.99)'
        self.fields['stock_quantity'].help_text = 'Enter available quantity'

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            BaseProductForm.save_additional_images(self, instance)
        return instance

class EditedAPIProductForm(forms.ModelForm):
    class Meta:
        model = EditedAPIProduct
        fields = ['name', 'product', 'category', 'unit', 'tax_code', 
                 'company', 'brand', 'text6', 'price', 'original_price', 'image']
        
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter product name',
                'required': True
            }),
            # ... keep your other widgets as they were ...
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = True
        self.fields['price'].required = True
        self.fields['price'].help_text = 'Enter price in decimal format (e.g., 99.99)'

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            BaseProductForm.save_additional_images(self, instance)
        return instance