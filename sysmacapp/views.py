from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout as auth_logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
import requests
import json
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from .models import CartItem, CustomProduct, CustomUser, Wishlist, Cart
from .forms import CustomProductForm, CustomUserCreationForm
from django.views.decorators.http import require_POST
from decimal import Decimal

def home(request):
    api_url = "https://sysmacsynctoolapi.imcbs.com/api/upload-products/"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        products = response.json()
    except requests.RequestException:
        products = []
    
    wishlist_ids = []
    cart_count = 0
    
    if request.user.is_authenticated:
        wishlist_ids = list(request.user.wishlist.values_list('product_id', flat=True))
        cart_count = request.user.cart_items.count()
    
    return render(request, 'home.html', {
        'products': products,
        'wishlist_ids': wishlist_ids,
        'cart_count': cart_count
    })



def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect('admin_dashboard')
        return redirect('home')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            login(request, user)
            if user.is_superuser:
                return redirect('admin_dashboard')
            return redirect('home')
        else:
            messages.error(request, 'Invalid email or password.')
    
    return render(request, 'login.html')



@csrf_exempt
def google_auth(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            token = data.get('credential')
            
            idinfo = id_token.verify_oauth2_token(
                token, 
                google_requests.Request(), 
                settings.GOOGLE_OAUTH2_CLIENT_ID
            )
            
            email = idinfo['email']
            google_id = idinfo['sub']
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')
            profile_picture = idinfo.get('picture', '')
            
            try:
                user = CustomUser.objects.get(email=email)
                if not user.google_id:
                    user.google_id = google_id
                    user.profile_picture = profile_picture
                    user.save()
            except CustomUser.DoesNotExist:
                user = CustomUser.objects.create_user(
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    google_id=google_id,
                    profile_picture=profile_picture,
                    user_type='user'
                )
            
            login(request, user)
            
            if user.is_superuser:
                return JsonResponse({'success': True, 'redirect_url': '/admin-dashboard/'})
            return JsonResponse({'success': True, 'redirect_url': '/'})
            
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Invalid token'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        auth_logout(request)
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('login')
    
    products = CustomProduct.objects.all()
    return render(request, 'admin_dashboard.html', {'products': products})


@login_required
def wishlist_view(request):
    wishlist_items = request.user.wishlist.select_related('product').all()
    cart_count = request.user.cart_items.count()
    
    return render(request, 'wishlist.html', {
        'wishlist_items': wishlist_items,
        'cart_count': cart_count
    })
from decimal import Decimal
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def cart_view(request):
    """Display user's cart with all items and calculations"""
    # Get all cart items for the user
    cart_items = request.user.cart_items.select_related('product').all()
    
    # Initialize totals
    total_price = Decimal('0.00')
    total_original_price = Decimal('0.00')
    cart_count = 0
    
    for item in cart_items:
        # Get price from the item (handles both custom and API products)
        item_price = item.get_price
        quantity = Decimal(str(item.quantity))
        
        # Calculate totals
        total_price += item_price * quantity
        
        # Handle original price (if available)
        if item.product and hasattr(item.product, 'price'):
            # Assuming original_price is a field in CustomProduct
            original_price = getattr(item.product, 'original_price', item_price)
            total_original_price += Decimal(str(original_price)) * quantity
        else:
            # For API products or when original_price isn't available
            total_original_price += item_price * quantity
        
        cart_count += item.quantity
    
    total_discount = max(total_original_price - total_price, Decimal('0.00'))
    
    # Calculate delivery charges (free for orders above ₹500)
    delivery_charge = Decimal('0.00') if total_price >= Decimal('500.00') else Decimal('40.00')
    grand_total = total_price + delivery_charge
    
    context = {
        'cart_items': cart_items,
        'cart_count': cart_count,
        'total_price': total_price,
        'total_original_price': total_original_price,
        'total_discount': total_discount,
        'delivery_charge': delivery_charge,
        'grand_total': grand_total,
    }
    
    return render(request, 'cart.html', context)


@require_POST
@login_required
def add_to_wishlist(request, product_id):
    try:
        product = CustomProduct.objects.get(id=product_id)
        Wishlist.objects.get_or_create(user=request.user, product=product)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@require_POST
@login_required
def remove_from_wishlist(request, product_id):
    try:
        Wishlist.objects.filter(user=request.user, product_id=product_id).delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@require_POST
@login_required
def add_to_cart(request, product_id):
    try:
        product = CustomProduct.objects.get(id=product_id)
        cart_item, created = CartItem.objects.get_or_create(
            user=request.user,
            product=product,
            defaults={'quantity': 1}
        )
        
        if not created:
            cart_item.quantity += 1
            cart_item.save()
        
        cart_count = request.user.cart_items.count()
        return JsonResponse({
            'success': True, 
            'cart_count': cart_count,
            'message': 'Product added to cart successfully'
        })
    except CustomProduct.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'error': 'Product not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)


@login_required
def user_dashboard(request):
    if request.user.is_superuser:
        return redirect('admin_dashboard')
    
    wishlist_items = request.user.wishlist.select_related('product').all()
    cart_items = request.user.cart_items.select_related('product').all()
    
    return render(request, 'user_dashboard.html', {
        'wishlist_items': wishlist_items,
        'cart_items': cart_items
    })

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'signup.html', {'form': form})


@login_required
def user_dashboard(request):
    if request.user.is_superuser:
        return redirect('admin_dashboard')
    return render(request, 'user_dashboard.html')


@login_required
def sysmac_products(request):
    if not request.user.is_superuser:
        auth_logout(request)
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('login')
    
    api_url = "https://sysmacsynctoolapi.imcbs.com/api/upload-products/"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        products = response.json()
    except requests.RequestException:
        products = []
    
    return render(request, 'sysmac_products.html', {'products': products})

def logout_view(request):
    auth_logout(request)
    return redirect('login')


@login_required
def custom_products(request):
    if not request.user.is_superuser:
        auth_logout(request)
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('login')
    
    products = CustomProduct.objects.all()
    return render(request, 'customproducts.html', {'products': products})


@login_required
def add_custom_product(request):
    if not request.user.is_superuser:
        auth_logout(request)
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('login')
    
    if request.method == 'POST':
        form = CustomProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product added successfully!')
            return redirect('custom_products')
    else:
        form = CustomProductForm()
    
    return render(request, 'edit_custom_product.html', {'form': form, 'action': 'Add'})


@login_required
def edit_custom_product(request, product_id):
    if not request.user.is_superuser:
        auth_logout(request)
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('login')
    
    product = get_object_or_404(CustomProduct, id=product_id)
    
    if request.method == 'POST':
        form = CustomProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product updated successfully!')
            return redirect('custom_products')
    else:
        form = CustomProductForm(instance=product)
    
    return render(request, 'edit_custom_product.html', {'form': form, 'action': 'Edit', 'product': product})


@login_required
def delete_custom_product(request, product_id):

    if not request.user.is_superuser:
        auth_logout(request)
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('login')
    
    product = get_object_or_404(CustomProduct, id=product_id)
    product.delete()
    messages.success(request, 'Product deleted successfully!')
    return redirect('custom_products')

import logging
from django.shortcuts import render, get_object_or_404
from django.http import Http404
from django.core.exceptions import ObjectDoesNotExist
import requests
from .models import CustomProduct, Wishlist, Cart

logger = logging.getLogger(__name__)
def product_detail(request, product_identifier):
    """Handle both API products (using code) and custom products (using id)"""
    product = None
    is_custom_product = False
    
    # First try to find as custom product by ID (if identifier is numeric)
    if product_identifier.isdigit():
        try:
            product = CustomProduct.objects.get(id=int(product_identifier))
            is_custom_product = True
        except CustomProduct.DoesNotExist:
            pass
    
    # If not found as custom product, try API with the code
    if not product:
        api_url = "https://sysmacsynctoolapi.imcbs.com/api/upload-products/"
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            api_products = response.json()
            
            # Find product by code in API response
            product = next((p for p in api_products if str(p.get('code')) == str(product_identifier)), None)
            
            if not product:
                raise Http404("Product not found")
                
        except requests.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            raise Http404("Could not retrieve products")
    
    # Handle wishlist and cart
    in_wishlist = False
    cart_count = 0
    
    if request.user.is_authenticated:
        if is_custom_product:
            in_wishlist = Wishlist.objects.filter(
                user=request.user,
                product_id=product.id
            ).exists()
        else:
            # For API products, check by api_product_code
            in_wishlist = Wishlist.objects.filter(
                user=request.user,
                api_product_code=product.get('code')
            ).exists()
        
        cart_count = request.user.cart_items.count()
    
    context = {
        'product': product,
        'in_wishlist': in_wishlist,
        'cart_count': cart_count,
        'is_custom_product': is_custom_product,
        'product_identifier': product_identifier,
    }
    
    return render(request, 'productview.html', context)
@login_required
def add_api_product_to_cart(request, product_code):
    """Add API product to cart using product code"""
    if request.method == 'POST':
        try:
            # Fetch the product from API to get details
            api_url = "https://sysmacsynctoolapi.imcbs.com/api/upload-products/"
            response = requests.get(api_url)
            response.raise_for_status()
            api_products = response.json()
            
            # Find the specific product
            product = next((p for p in api_products if str(p.get('code')) == str(product_code)), None)
            
            if not product:
                return JsonResponse({'error': 'Product not found'}, status=404)
            
            # Check if product already exists in cart
            cart_item, created = CartItem.objects.get_or_create(
                user=request.user,
                api_product_code=product_code,
                defaults={
                    'api_product_name': product.get('name', 'Unknown Product'),
                    'api_product_price': Decimal(str(product.get('price', 0))),
                    'quantity': 1
                }
            )
            
            if not created:
                # If item already exists, increment quantity
                cart_item.quantity += 1
                cart_item.save()
            
            # Get updated cart count
            cart_count = CartItem.objects.filter(user=request.user).count()
            
            return JsonResponse({
                'success': True,
                'message': 'Product added to cart successfully',
                'cart_count': cart_count
            })
            
        except requests.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            return JsonResponse({'error': 'Failed to fetch product details'}, status=500)
        except Exception as e:
            logger.error(f"Error adding API product to cart: {str(e)}")
            return JsonResponse({'error': 'An error occurred'}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)








@property
def get_price(self):
    """Get the price of the item as Decimal"""
    if self.product:
        return Decimal(str(self.product.price))
    elif self.api_product_price:
        return Decimal(str(self.api_product_price))
    return Decimal('0.00')