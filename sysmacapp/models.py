from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinValueValidator
from decimal import Decimal

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    USER_TYPES = (
        ('admin', 'Admin'),
        ('user', 'Regular User'),
    )
    
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    user_type = models.CharField(max_length=10, choices=USER_TYPES, default='user')
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    
    # Google OAuth fields
    google_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    profile_picture = models.URLField(blank=True, null=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    objects = CustomUserManager()
    
    def __str__(self):
        return self.email
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    @property
    def is_admin(self):
        return self.user_type == 'admin' or self.is_superuser

class CustomProduct(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    main_image = models.ImageField(upload_to='products/', blank=True, null=True)
    company = models.CharField(max_length=100, blank=True, null=True)
    brand = models.CharField(max_length=100, blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    unit = models.CharField(max_length=50, blank=True, null=True)
    product = models.CharField(max_length=100, blank=True, null=True, verbose_name="Product Type")
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


from django.db import models
from django.core.exceptions import ValidationError

class Wishlist(models.Model):
    """
    Model to track user's wishlist items.
    Can store either custom products (through ForeignKey) or API products (through product code).
    """
    
    user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE,
        related_name='wishlist_items',
        verbose_name='User'
    )
    
    product = models.ForeignKey(
        CustomProduct,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='wishlisted_by',
        verbose_name='Custom Product'
    )
    
    api_product_code = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='API Product Code',
        help_text='Product code from external API'
    )
    
    added_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Added Date'
    )

    class Meta:
        unique_together = [
            ('user', 'product'),  # A user can't wishlist same custom product multiple times
            ('user', 'api_product_code')  # A user can't wishlist same API product multiple times
        ]
        verbose_name = 'Wishlist Item'
        verbose_name_plural = 'Wishlist Items'
        ordering = ['-added_at']  # Newest items first

    def __str__(self):
        if self.product:
            return f"{self.user.email} - {self.product.name}"
        return f"{self.user.email} - API Product {self.api_product_code}"

    def clean(self):
        """
        Validate that either product or api_product_code is set, but not both
        """
        if not self.product and not self.api_product_code:
            raise ValidationError("Either product or API product code must be set")
        
        if self.product and self.api_product_code:
            raise ValidationError("Cannot set both product and API product code")
    
    def save(self, *args, **kwargs):
        self.full_clean()  # Run validation before saving
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        """Get display name for the product"""
        if self.product:
            return self.product.name
        return f"API Product {self.api_product_code}"

    @property
    def product_type(self):
        """Get product type for templates"""
        return 'custom' if self.product else 'api'


class CartItem(models.Model):
    # Fixed: Changed User to CustomUser
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='cart_items')
    
    # For custom products
    product = models.ForeignKey('CustomProduct', on_delete=models.CASCADE, null=True, blank=True)
    
    # For API products
    api_product_code = models.CharField(max_length=100, null=True, blank=True)
    api_product_name = models.CharField(max_length=255, null=True, blank=True)
    api_product_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        # Ensure a user can't have duplicate items in cart
        unique_together = [
            ['user', 'product'],  # For custom products
            ['user', 'api_product_code'],  # For API products
        ]
    
    def __str__(self):
        if self.product:
            return f"{self.user.email} - {self.product.name} (Custom)"
        elif self.api_product_code:
            return f"{self.user.email} - {self.api_product_name} (API)"
        return f"{self.user.email} - Unknown Product"
    
    @property
    def get_price(self):
        """Get the price of the item"""
        if self.product:
            return self.product.price
        elif self.api_product_price:
            return self.api_product_price
        return Decimal('0.00')
    
    @property
    def get_name(self):
        """Get the name of the item"""
        if self.product:
            return self.product.name
        elif self.api_product_name:
            return self.api_product_name
        return "Unknown Product"

# Optional: Add a Cart model if needed for your views
class Cart(models.Model):
    """
    Optional Cart model - you can use this if your views expect a Cart model,
    or you can modify your views to work directly with CartItem
    """
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Cart for {self.user.email}"
    
    @property
    def total_items(self):
        return self.user.cart_items.count()
    
    @property
    def total_price(self):
        total = Decimal('0.00')
        for item in self.user.cart_items.all():
            total += item.get_price * item.quantity
        return total


class EditedAPIProduct(models.Model):
    original_code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    product = models.CharField(max_length=100, blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    unit = models.CharField(max_length=50, blank=True, null=True)
    tax_code = models.CharField(max_length=50, blank=True, null=True)
    company = models.CharField(max_length=100, blank=True, null=True)
    brand = models.CharField(max_length=100, blank=True, null=True)
    text6 = models.CharField(max_length=100, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    image = models.ImageField(upload_to='api_products/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} (Edited)"        
    

# If you want to create a Product model to store API products locally
class Product(models.Model):
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    product_type = models.CharField(max_length=100, blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    unit = models.CharField(max_length=50, blank=True, null=True)
    tax_code = models.CharField(max_length=50, blank=True, null=True)
    company = models.CharField(max_length=100, blank=True, null=True)
    brand = models.CharField(max_length=100, blank=True, null=True)
    text6 = models.CharField(max_length=100, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    image = models.URLField(blank=True, null=True)  # Store API image URL
    is_active = models.BooleanField(default=True)
    last_synced = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.code})"