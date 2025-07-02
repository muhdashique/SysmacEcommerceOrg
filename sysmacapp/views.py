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
    wishlist_api_ids = []
    cart_ids = []
    cart_api_ids = []
    cart_count = 0
    
    if request.user.is_authenticated:
        # Get IDs of custom products in wishlist
        wishlist_ids = list(request.user.wishlist.filter(product__isnull=False)
                          .values_list('product_id', flat=True))
        # Get codes of API products in wishlist
        wishlist_api_ids = list(request.user.wishlist.filter(api_product_code__isnull=False)
                              .values_list('api_product_code', flat=True))
        # Get cart information
        cart_ids = list(request.user.cart_items.filter(product__isnull=False)
                        .values_list('product_id', flat=True))
        cart_api_ids = list(request.user.cart_items.filter(api_product_code__isnull=False)
                            .values_list('api_product_code', flat=True))
        cart_count = request.user.cart_items.count()
    
    return render(request, 'home.html', {
        'products': products,
        'wishlist_ids': wishlist_ids,
        'wishlist_api_ids': wishlist_api_ids,
        'cart_ids': cart_ids,
        'cart_api_ids': cart_api_ids,
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

# ADMIN
 
@login_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        auth_logout(request)
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('login')
    
    products = CustomProduct.objects.all()
    return render(request, 'admin_dashboard.html', {'products': products})


# WISHLIST

@login_required
def wishlist_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    # Get all wishlist items for the user
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product')
    
    # Debug print to check what's in the wishlist
    print(f"Wishlist items count: {wishlist_items.count()}")
    for item in wishlist_items:
        print(f"Item ID: {item.id}, Product: {item.product}, API Code: {item.api_product_code}")
    
    # Separate custom products and API product codes
    custom_products = []
    api_product_codes = []
    
    for item in wishlist_items:
        if item.product:  # Custom product
            custom_products.append(item)
        elif item.api_product_code:  # API product
            api_product_codes.append(str(item.api_product_code))  # Convert to string
    
    print(f"API product codes to search: {api_product_codes}")
    
    # Fetch API product details
    api_products = []
    if api_product_codes:
        api_url = "https://sysmacsynctoolapi.imcbs.com/api/upload-products/"
        try:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            all_api_products = response.json()
            
            print(f"Total API products from API: {len(all_api_products)}")
            
            # Find matching products by code - more flexible matching
            for product in all_api_products:
                product_code = product.get('code')
                
                # Handle different data types for product code
                if product_code is not None:
                    product_code_str = str(product_code)
                    
                    # Check if this product code is in our wishlist
                    if product_code_str in api_product_codes:
                        api_products.append(product)
                        print(f"Found matching API product: {product.get('name')} (Code: {product_code_str})")
                    
                    # Also check for integer matching in case of type mismatch
                    try:
                        if str(int(product_code)) in api_product_codes:
                            if product not in api_products:  # Avoid duplicates
                                api_products.append(product)
                                print(f"Found matching API product (int match): {product.get('name')} (Code: {product_code})")
                    except (ValueError, TypeError):
                        pass
            
            print(f"Matched API products: {len(api_products)}")
            
            # If no matches found, let's debug the API response structure
            if not api_products and all_api_products:
                print("No matches found. Sample API product structure:")
                sample_product = all_api_products[0] if all_api_products else {}
                print(f"Sample product keys: {list(sample_product.keys())}")
                print(f"Sample product: {sample_product}")
                
                # Check if the API uses different field names
                for product in all_api_products[:5]:  # Check first 5 products
                    for key, value in product.items():
                        if str(value) in api_product_codes:
                            print(f"Found potential match in field '{key}': {value}")
            
        except requests.RequestException as e:
            print(f"Error fetching API products: {str(e)}")
            api_products = []
        except json.JSONDecodeError as e:
            print(f"Error parsing API response: {str(e)}")
            api_products = []
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            api_products = []
    
    # Get cart information for the current user
    cart_ids = list(request.user.cart_items.filter(product__isnull=False)
                  .values_list('product_id', flat=True))
    cart_api_ids = list(request.user.cart_items.filter(api_product_code__isnull=False)
                  .values_list('api_product_code', flat=True))
    
    context = {
        'wishlist_items': custom_products,  # Only custom products
        'api_products': api_products,       # API products with full details
        'cart_count': getattr(request.user, 'cart_items', CartItem.objects.filter(user=request.user)).count(),
        'cart_ids': cart_ids,                # IDs of custom products in cart
        'cart_api_ids': cart_api_ids         # Codes of API products in cart
    }
    
    print(f"Context - Custom products: {len(custom_products)}, API products: {len(api_products)}")
    print(f"Cart info - Custom IDs: {cart_ids}, API IDs: {cart_api_ids}")
    
    return render(request, 'wishlist.html', context)
 
@require_POST
@login_required
def add_to_wishlist(request, product_id):
    try:
        data = json.loads(request.body)
        is_custom = data.get('is_custom', False)
        
        if is_custom:
            # Handle custom product
            product = CustomProduct.objects.get(id=product_id)
            Wishlist.objects.get_or_create(
                user=request.user, 
                product=product
            )
        else:
            # Handle API product
            Wishlist.objects.get_or_create(
                user=request.user,
                api_product_code=product_id
            )
            
        return JsonResponse({'success': True})
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


@require_POST
@login_required
def remove_from_wishlist(request, product_id):
    try:
        # Parse request body to get product type
        data = json.loads(request.body) if request.body else {}
        is_custom = data.get('is_custom', False)
        
        if is_custom:
            # Remove custom product from wishlist
            wishlist_item = Wishlist.objects.get(
                user=request.user, 
                product_id=product_id
            )
        else:
            # Remove API product from wishlist
            wishlist_item = Wishlist.objects.get(
                user=request.user,
                api_product_code=product_id
            )
        
        wishlist_item.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Item removed from wishlist'
        })
        
    except Wishlist.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'error': 'Item not found in wishlist'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False, 
            'error': 'Invalid request data'
        }, status=400)
    except Exception as e:
        print(f"Error removing from wishlist: {str(e)}")
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)
    

    
# CART

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
        
            cart_count = request.user.cart_items.count()

    
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

 
# In views.py

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
        
        # Only increment if not newly created AND we want to allow increasing quantity
        if not created:
            cart_item.quantity += 1
            cart_item.save()
        
        cart_count = request.user.cart_items.count()

        return JsonResponse({
            'success': True, 
            'cart_count': cart_count,
            'message': 'Product added to cart successfully',
            'quantity': cart_item.quantity  # Return the actual quantity
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



@csrf_exempt
@require_POST
@login_required
def add_api_product_to_cart(request, product_code):
    try:
        # Fetch the product from API to get details
        api_url = "https://sysmacsynctoolapi.imcbs.com/api/upload-products/"
        response = requests.get(api_url)
        response.raise_for_status()
        api_products = response.json()
        
        # Find the specific product
        product = next((p for p in api_products if str(p.get('code')) == str(product_code)), None)
        
        if not product:
            logger.error(f"Product with code {product_code} not found in API response")
            return JsonResponse({'success': False, 'error': 'Product not found'}, status=404)
        
        # Get price or default to 0 if not available
        price = Decimal(str(product.get('price', 0)))
        
        # Check if product already exists in cart
        cart_item, created = CartItem.objects.get_or_create(
            user=request.user,
            api_product_code=product_code,
            defaults={
                'api_product_name': product.get('name', 'Unknown Product'),
                'api_product_price': price,
                'quantity': 1  # Set initial quantity to 1
            }
        )
        
        # Only increment if not newly created
        if not created:
            cart_item.quantity += 1
            cart_item.save()
        
        # Get updated cart count
        cart_count = request.user.cart_items.count()

        return JsonResponse({
            'success': True,
            'message': 'Product added to cart successfully',
            'cart_count': cart_count,
            'quantity': cart_item.quantity  # Return the actual quantity
        })
        
    except requests.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        return JsonResponse({'success': False, 'error': 'Failed to fetch product details'}, status=500)
    except Exception as e:
        logger.error(f"Error adding API product to cart: {str(e)}")
        return JsonResponse({'success': False, 'error': 'An error occurred'}, status=500)



@require_POST
@login_required
def remove_from_cart(request, product_code):
    """Handle removal of custom products (numeric ID)"""
    try:
        # Try to find as custom product first
        cart_item = get_object_or_404(
            CartItem,
            user=request.user,
            product__id=product_code
        )
        cart_item.delete()
        
        # Recalculate cart totals
        return get_cart_response_data(request.user)
        
    except Http404:
        # If not found as custom product, try as API product
        return remove_api_product_from_cart(request, product_code)




@property
def get_price(self):
    """Get the price of the item as Decimal"""
    if self.product:
        return Decimal(str(self.product.price))
    elif self.api_product_price:
        return Decimal(str(self.api_product_price))
    return Decimal('0.00')


@require_POST
@login_required
def remove_api_product_from_cart(request, product_code):
    """Handle removal of API products from cart"""
    try:
        # Get the cart item and verify it belongs to the current user
        cart_item = get_object_or_404(
            CartItem,
            user=request.user,
            api_product_code=product_code
        )
        
        # Delete the item
        cart_item.delete()
        
        # Return updated cart data
        response_data = calculate_cart_totals(request.user)
        response_data['success'] = True
        return JsonResponse(response_data)
        
    except Http404:
        return JsonResponse({
            'success': False,
            'error': 'Item not found in your cart'
        }, status=404)
        
    except Exception as e:
        # Log the error for debugging
        logger.error(f"Error removing API product {product_code}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while removing the item'
        }, status=500)

def calculate_cart_totals(user):
    """Helper function to calculate cart totals"""
    cart_items = user.cart_items.all()
    cart_count = cart_items.count()
    
    total_price = Decimal('0.00')
    total_original_price = Decimal('0.00')
    
    for item in cart_items:
        if item.product:
            # Custom product calculations
            price = item.product.price
            original_price = getattr(item.product, 'original_price', price)
            total_price += price * item.quantity
            total_original_price += original_price * item.quantity
        else:
            # API product calculations
            price = item.api_product_price
            total_price += price * item.quantity
            total_original_price += price * item.quantity  # Assuming no discount for API products
    
    total_discount = max(total_original_price - total_price, Decimal('0.00'))
    delivery_charge = Decimal('0.00') if total_price >= Decimal('500.00') else Decimal('40.00')
    grand_total = total_price + delivery_charge
    
    return {
        'cart_count': cart_count,
        'total_price': str(total_price),
        'total_original_price': str(total_original_price),
        'total_discount': str(total_discount),
        'delivery_charge': str(delivery_charge),
        'grand_total': str(grand_total)
    }

def get_cart_response_data(user):
    """Helper function to calculate cart totals after removal"""
    cart_items = user.cart_items.all()
    cart_count = cart_items.count()
    
    total_price = Decimal('0.00')
    total_discount = Decimal('0.00')
    
    for item in cart_items:
        if item.product:
            # Custom product calculations
            price = item.product.price
            original_price = getattr(item.product, 'original_price', price)
            total_price += price * item.quantity
            total_discount += (original_price - price) * item.quantity
        else:
            # API product calculations
            price = item.api_product_price
            total_price += price * item.quantity
            # API products might not have discount info
    
    delivery_charge = Decimal('0.00') if total_price >= Decimal('500.00') else Decimal('40.00')
    grand_total = total_price + delivery_charge
    
    return JsonResponse({
        'success': True,
        'cart_count': cart_count,
        'total_price': str(total_price),
        'total_discount': str(total_discount),
        'delivery_charge': str(delivery_charge),
        'grand_total': str(grand_total)
    })
    try:
        CartItem.objects.filter(
            user=request.user,
            api_product_code=product_code
        ).delete()
        cart_count = request.user.cart_items.count()
        return JsonResponse({
            'success': True,
            'cart_count': cart_count,
            'message': 'Product removed from cart'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
    from django.http import JsonResponse


from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt  # If you're not using CSRF tokens properly (not recommended for production)
def update_cart_quantity(request, product_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            quantity = data.get('quantity')
            # Logic to update cart item with new quantity
            # Example:
            # cart_item = CartItem.objects.get(user=request.user, product_id=product_id)
            # cart_item.quantity = quantity
            # cart_item.save()
            return JsonResponse({'success': True, 'quantity': quantity, 'cart_count': 5, 'total_price': 500, 'total_discount': 50, 'delivery_charge': 0, 'grand_total': 450})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
    return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)


# Add these views to your views.py

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
import requests
import logging

logger = logging.getLogger(__name__)

@require_GET
@login_required
def check_cart_status_api(request, product_code):
    """Check if an API product is in the user's cart"""
    try:
        cart_item = CartItem.objects.filter(
            user=request.user,
            api_product_code=product_code
        ).first()
        
        if cart_item:
            return JsonResponse({
                'in_cart': True,
                'quantity': cart_item.quantity
            })
        else:
            return JsonResponse({
                'in_cart': False,
                'quantity': 0
            })
            
    except Exception as e:
        logger.error(f"Error checking cart status for API product {product_code}: {str(e)}")
        return JsonResponse({
            'in_cart': False,
            'quantity': 0,
            'error': 'An error occurred'
        }, status=500)


@require_GET
@login_required
def check_wishlist_status_api(request, product_code):
    """Check if an API product is in the user's wishlist"""
    try:
        # Assuming you have a Wishlist model similar to CartItem
        wishlist_item = Wishlist.objects.filter(
            user=request.user,
            api_product_code=product_code
        ).first()
        
        return JsonResponse({
            'in_wishlist': bool(wishlist_item)
        })
            
    except Exception as e:
        logger.error(f"Error checking wishlist status for API product {product_code}: {str(e)}")
        return JsonResponse({
            'in_wishlist': False,
            'error': 'An error occurred'
        }, status=500)


# USERDASHBOARD

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


# API PRODUCTS

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


# LOGOUT

def logout_view(request):
    auth_logout(request)
    return redirect('login')

# CUSTOMER PRODUCT

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



# Add this temporary debug view to help diagnose the issue
import requests
import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

@login_required
def debug_wishlist_api(request):
    """Debug view to check API response and matching"""
    
    # Get wishlist items
    wishlist_items = Wishlist.objects.filter(user=request.user)
    api_codes = [str(item.api_product_code) for item in wishlist_items if item.api_product_code]
    
    debug_info = {
        'wishlist_api_codes': api_codes,
        'api_response_sample': None,
        'matching_products': [],
        'api_error': None
    }
    
    # Fetch API products
    api_url = "https://sysmacsynctoolapi.imcbs.com/api/upload-products/"
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        all_api_products = response.json()
        
        # Get sample of API response
        if all_api_products:
            debug_info['api_response_sample'] = all_api_products[0]
            debug_info['total_api_products'] = len(all_api_products)
        
        # Try to find matches
        for product in all_api_products:
            product_code = str(product.get('code', ''))
            if product_code in api_codes:
                debug_info['matching_products'].append({
                    'code': product_code,
                    'name': product.get('name'),
                    'price': product.get('price')
                })
                
        # If no matches, check all fields for potential matches
        if not debug_info['matching_products']:
            debug_info['potential_matches'] = []
            for product in all_api_products[:10]:  # First 10 products
                for key, value in product.items():
                    if str(value) in api_codes:
                        debug_info['potential_matches'].append({
                            'field': key,
                            'value': value,
                            'product_name': product.get('name', 'Unknown')
                        })
                
    except Exception as e:
        debug_info['api_error'] = str(e)
    
    return JsonResponse(debug_info, indent=2)

# Add this URL to your urls.py temporarily:
# path('debug/wishlist-api/', debug_wishlist_api, name='debug_wishlist_api'),





