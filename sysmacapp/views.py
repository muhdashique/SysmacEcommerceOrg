from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout as auth_logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
import requests
import json
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from .models import CartItem, CustomProduct, CustomUser, ProductImage, Wishlist, Cart
from .forms import CustomProductForm, CustomUserCreationForm
from django.views.decorators.http import require_POST
from decimal import Decimal
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from .models import CartItem, CustomProduct, CustomUser, Wishlist, Cart, EditedAPIProduct
from .forms import EditedAPIProductForm

 
def home(request):
    # Fetch API products
    api_url = "https://sysmacsynctoolapi.imcbs.com/api/upload-products/"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        api_products = response.json()
    except requests.RequestException:
        api_products = []
    
    # Get all edited products
    edited_products = EditedAPIProduct.objects.all()
    edited_product_map = {p.original_code: p for p in edited_products}
    
    # Merge API products with edited data
    processed_products = []
    for product in api_products:
        product_code = str(product.get('code', ''))
        edited_product = edited_product_map.get(product_code)
        
        processed_product = {
            'id': None,  # API products don't have an ID
            'code': product_code,
            'name': product.get('name', 'Unknown Product'),
            'product': product.get('product', ''),
            'catagory': product.get('catagory', ''),
            'unit': product.get('unit', ''),
            'taxcode': product.get('taxcode', ''),
            'company': product.get('company', ''),
            'brand': product.get('brand', ''),
            'text6': product.get('text6', ''),
            'price': product.get('price', '0.00'),
            'original_price': product.get('original_price', '0.00'),
            'image': product.get('image', ''),
            'edited_name': edited_product.name if edited_product else None,
            'edited_product': edited_product.product if edited_product else None,
            'edited_category': edited_product.category if edited_product else None,
            'edited_unit': edited_product.unit if edited_product else None,
            'edited_taxcode': edited_product.tax_code if edited_product else None,
            'edited_company': edited_product.company if edited_product else None,
            'edited_brand': edited_product.brand if edited_product else None,
            'edited_text6': edited_product.text6 if edited_product else None,
            'edited_price': edited_product.price if edited_product else None,
            'edited_image': edited_product.image if edited_product else None,
            'is_custom': False  # Mark as API product
        }
        processed_products.append(processed_product)

    # Add custom products
    custom_products = CustomProduct.objects.filter(is_active=True)
    for product in custom_products:
        processed_products.append({
            'id': product.id,
            'code': str(product.id),  # Use ID as code for custom products
            'name': product.name,
            'product': product.product or "Custom Product",
            'catagory': product.category or "General",
            'unit': "",
            'taxcode': "",
            'company': product.company or "SYSMAC",
            'brand': product.brand or "SYSMAC",
            'text6': "",
            'price': str(product.price),
            'original_price': str(product.price),  # Custom products don't have discounts
            'image': product.main_image.url if product.main_image else "",
            'edited_name': None,
            'edited_product': None,
            'edited_category': None,
            'edited_unit': None,
            'edited_taxcode': None,
            'edited_company': None,
            'edited_brand': None,
            'edited_text6': None,
            'edited_price': None,
            'edited_image': None,
            'is_custom': True  # Mark as custom product
        })

    # Sorting logic
    # Sorting logic
    sort_option = request.GET.get('sort', 'all')
    
    if sort_option == 'price_low_high':
        processed_products.sort(key=lambda x: float(x['edited_price']) if x['edited_price'] is not None else float(x['price']))
    elif sort_option == 'price_high_low':
        processed_products.sort(key=lambda x: float(x['edited_price']) if x['edited_price'] is not None else float(x['price']), reverse=True)
    
    
    
    # Category filtering
    category_filter = request.GET.get('category', 'all')
    if category_filter != 'all':
        processed_products = [p for p in processed_products if 
                            (p['edited_category'] or p['catagory'] or '').lower() == category_filter.lower()]

    # Search filtering
    search_query = request.GET.get('search', '').lower()
    if search_query:
        processed_products = [p for p in processed_products if 
                            search_query in (p['edited_name'] or p['name'] or '').lower() or
                            search_query in (p['edited_brand'] or p['brand'] or '').lower() or
                            search_query in (p['edited_category'] or p['catagory'] or '').lower()]

    # Get wishlist and cart info
    # Get wishlist and cart info
    wishlist_ids = []
    wishlist_api_ids = []
    cart_ids = []
    cart_api_ids = []
    cart_count = 0
    
    if request.user.is_authenticated:
        wishlist_ids = list(str(id) for id in request.user.wishlist_items.filter(product__isnull=False).values_list('product_id', flat=True))
        wishlist_api_ids = list(str(code) for code in request.user.wishlist_items.filter(api_product_code__isnull=False).values_list('api_product_code', flat=True))
        cart_ids = list(str(id) for id in request.user.cart_items.filter(product__isnull=False).values_list('product_id', flat=True))
        cart_api_ids = list(str(code) for code in request.user.cart_items.filter(api_product_code__isnull=False).values_list('api_product_code', flat=True))
        cart_count = request.user.cart_items.count()
    
    # Pagination
    items_per_page = int(request.GET.get('per_page', 12))
    if items_per_page not in [8, 12, 24, 48]:
        items_per_page = 12
    
    paginator = Paginator(processed_products, items_per_page)
    page_number = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    return render(request, 'home.html', {
        'page_obj': page_obj,
        'wishlist_ids': wishlist_ids,
        'wishlist_api_ids': wishlist_api_ids,
        'cart_ids': cart_ids,
        'cart_api_ids': cart_api_ids,
        'cart_count': cart_count,
        'items_per_page': items_per_page,
        'current_sort': sort_option,
        'current_category': category_filter,
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
    
    # Get all edited products
    edited_products = EditedAPIProduct.objects.all()
    edited_product_map = {p.original_code: p for p in edited_products}
    
    # Separate custom products and API product codes
    custom_products = []
    api_product_codes = []
    
    for item in wishlist_items:
        if item.product:  # Custom product
            custom_products.append(item)
        elif item.api_product_code:  # API product
            api_product_codes.append(str(item.api_product_code))
    
    # Fetch API product details and merge with edited data
    api_products = []
    if api_product_codes:
        api_url = "https://sysmacsynctoolapi.imcbs.com/api/upload-products/"
        try:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            all_api_products = response.json()
            
            # Find matching products by code
            for product in all_api_products:
                product_code = str(product.get('code', ''))
                if product_code in api_product_codes:
                    # Get edited version if exists
                    edited_product = edited_product_map.get(product_code)
                    
                    # Create processed product data
                    processed_product = {
                        'code': product_code,
                        'name': product.get('name', 'Unknown Product'),
                        'category': product.get('catagory', ''),
                        'price': str(Decimal(product.get('price', '0.00'))),
                        'original_price': str(Decimal(product.get('original_price', '0.00'))),
                        'image': product.get('image', ''),
                        'edited_name': edited_product.name if edited_product else None,
                        'edited_image': edited_product.image if edited_product else None,
                        'edited_price': str(edited_product.price) if edited_product else None,
                        'api_product_price': str(edited_product.price) if edited_product else str(Decimal(product.get('price', '0.00'))),
                    }
                    api_products.append(processed_product)
                    
        except requests.RequestException as e:
            print(f"Error fetching API products: {str(e)}")
            api_products = []
    
    # Get cart information
    cart_ids = []
    cart_api_ids = []
    if request.user.is_authenticated:
        cart_ids = list(request.user.cart_items.filter(product__isnull=False)
                      .values_list('product_id', flat=True))
        cart_api_ids = list(request.user.cart_items.filter(api_product_code__isnull=False)
                      .values_list('api_product_code', flat=True))
    
    context = {
        'wishlist_items': custom_products,
        'api_products': api_products,
        'cart_count': request.user.cart_items.count(),
        'cart_ids': cart_ids,
        'cart_api_ids': cart_api_ids,
    }
    
    return render(request, 'wishlist.html', context)
from django.views.decorators.http import require_POST, require_GET
from django.http import JsonResponse
import json
import logging

logger = logging.getLogger(__name__)

@require_POST
@login_required

def add_to_wishlist(request, product_id):
    """Handle both custom and API product additions"""
    try:
        data = json.loads(request.body) if request.body else {}
        is_custom = data.get('is_custom', False)
        
        if is_custom:
            product = CustomProduct.objects.get(id=product_id)
            Wishlist.objects.get_or_create(
                user=request.user, 
                product=product
            )
        else:
            # For API products, ensure consistent formatting
            # Pad with leading zeros to match API format (assuming 5-digit codes)
            formatted_code = product_id.zfill(5)
            
            Wishlist.objects.get_or_create(
                user=request.user,
                api_product_code=formatted_code  # Store the formatted code
            )
            
        return JsonResponse({
            'success': True,
            'added': True,
            'message': 'Product added to wishlist'
        })
        
    except Exception as e:
        logger.error(f"Error adding to wishlist: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
@require_POST
@login_required
def remove_from_wishlist(request, product_id):
    """Handle both custom and API product removals"""
    try:
        data = json.loads(request.body) if request.body else {}
        is_custom = data.get('is_custom', False)
        
        if is_custom:
            Wishlist.objects.filter(
                user=request.user,
                product_id=product_id
            ).delete()
        else:
            Wishlist.objects.filter(
                user=request.user,
                api_product_code=product_id
            ).delete()
            
        return JsonResponse({
            'success': True,
            'removed': True,
            'message': 'Product removed from wishlist'
        })
        
    except Exception as e:
        logger.error(f"Error removing from wishlist: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)



@require_GET
@login_required
def check_wishlist_status(request, product_id):
    """Check status for both product types"""
    try:
        is_custom = request.GET.get('is_custom', 'false').lower() == 'true'
        
        if is_custom:
            exists = Wishlist.objects.filter(
                user=request.user,
                product_id=product_id
            ).exists()
        else:
            exists = Wishlist.objects.filter(
                user=request.user,
                api_product_code=product_id
            ).exists()
            
        return JsonResponse({
            'in_wishlist': exists,
            'is_custom': is_custom
        })
        
    except Exception as e:
        logger.error(f"Error checking wishlist status: {str(e)}")
        return JsonResponse({
            'in_wishlist': False,
            'error': str(e)
        }, status=400)


# CART

from decimal import Decimal
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
@login_required
def cart_view(request):
    """Display user's cart with all items and calculations"""
    # Get all cart items for the user
    cart_items = request.user.cart_items.select_related('product').all()
    
    # Get all edited products
    edited_products = EditedAPIProduct.objects.all()
    edited_product_map = {p.original_code: p for p in edited_products}
    
    # Process cart items to include edited data for API products
    processed_cart_items = []
    for item in cart_items:
        if item.api_product_code:
            # For API products, get the latest data
            edited_product = edited_product_map.get(item.api_product_code)
            if edited_product:
                item.api_product_name = edited_product.name
                item.api_product_price = edited_product.price
                item.edited_image = edited_product.image
            
            # Debug: Print API product info
            print(f"API Product Debug:")
            print(f"  - Code: {item.api_product_code}")
            print(f"  - Name: {item.api_product_name}")
            print(f"  - Price: {item.api_product_price}")
        
        elif item.product:
            # For regular products, ensure they have a code field
            print(f"Regular Product Debug:")
            print(f"  - Product ID: {item.product.id}")
            print(f"  - Product Name: {item.product.name}")
            
            # Check if product has a code field
            if hasattr(item.product, 'code'):
                print(f"  - Product Code: {item.product.code}")
            else:
                print(f"  - Product Code: NOT FOUND - using ID as fallback")
                # If no code field, you might want to add one or use ID
                item.product.code = str(item.product.id)
        
        processed_cart_items.append(item)
    
    # Initialize totals
    total_price = Decimal('0.00')
    total_original_price = Decimal('0.00')
    cart_count = 0
    
    for item in processed_cart_items:
        # Get price from the item (handles both custom and API products)
        item_price = item.get_price
        quantity = Decimal(str(item.quantity))
        
        # Calculate totals
        total_price += item_price * quantity
        
        # Handle original price (if available)
        if item.product and hasattr(item.product, 'price'):
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
        'cart_items': processed_cart_items,
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
            total_price += Decimal(str(price)) * item.quantity
            total_original_price += Decimal(str(original_price)) * item.quantity
        else:
            # API product calculations
            price = item.api_product_price
            total_price += Decimal(str(price)) * item.quantity
            total_original_price += Decimal(str(price)) * item.quantity
    
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

@require_POST
@login_required
def update_cart_quantity(request, product_identifier):
    try:
        data = json.loads(request.body)
        quantity = int(data.get('quantity'))
        
        if quantity < 1:
            return JsonResponse({
                'success': False,
                'error': 'Quantity must be at least 1'
            }, status=400)
        
        # Try to find as custom product first (numeric ID)
        try:
            product_id = int(product_identifier)
            cart_item = get_object_or_404(
                CartItem,
                user=request.user,
                product_id=product_id
            )
            item_price = cart_item.product.price
            original_price = getattr(cart_item.product, 'original_price', item_price)
        except (ValueError, Http404):
            # If not a custom product, try as API product
            cart_item = get_object_or_404(
                CartItem,
                user=request.user,
                api_product_code=product_identifier
            )
            item_price = cart_item.api_product_price
            original_price = item_price  # API products might not have discount
        
        # Update quantity
        cart_item.quantity = quantity
        cart_item.save()
        
        # Calculate new totals
        response_data = calculate_cart_totals(request.user)
        
        # Add item-specific price information
        response_data.update({
            'success': True,
            'quantity': quantity,
            'item_price': str(item_price),
            'item_original_price': str(original_price),
            'item_total': str(Decimal(item_price) * quantity),
            'item_original_total': str(Decimal(original_price) * quantity),
        })
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error updating quantity: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while updating quantity'
        }, status=500)

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
        api_products = response.json()
        
        # Get all edited products
        edited_products = EditedAPIProduct.objects.all()
        edited_product_map = {p.original_code: p for p in edited_products}
        
        # Process products to include edited versions
        processed_products = []
        for product in api_products:
            product_code = str(product.get('code', ''))
            edited_product = edited_product_map.get(product_code)
            
            processed_product = {
                'code': product_code,
                'name': product.get('name', 'Unknown Product'),
                # ... other fields ...
                'edited_name': edited_product.name if edited_product else None,
                # ... other edited fields ...
            }
            processed_products.append(processed_product)
            
    except requests.RequestException as e:
        logger.error(f"Error fetching API products: {str(e)}")
        processed_products = []
        messages.error(request, 'Failed to fetch products from API')
    
    return render(request, 'sysmac_products.html', {
        'products': processed_products,
        'edited_products': [p.original_code for p in edited_products]
    })


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

# views.py - Update your edit_custom_product view
@login_required
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
            product = form.save()
            messages.success(request, 'Product updated successfully!')
            return redirect('custom_products')
    else:
        form = CustomProductForm(instance=product)
    
    return render(request, 'edit_custom_product.html', {
        'form': form,
        'action': 'Edit',
        'product': product
    })


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
            api_product = next((p for p in api_products if str(p.get('code')) == str(product_identifier)), None)
            
            if not api_product:
                raise Http404("Product not found")
            
            # Get all edited products
            edited_products = EditedAPIProduct.objects.all()
            edited_product_map = {p.original_code: p for p in edited_products}
            
            # Check if this product has been edited
            edited_product = edited_product_map.get(str(product_identifier))
            
            # Create a processed product with all necessary fields
            product = {
                'code': str(api_product.get('code', '')),
                'name': api_product.get('name', 'Unknown Product'),
                'product': api_product.get('product', ''),
                'catagory': api_product.get('catagory', ''),
                'unit': api_product.get('unit', ''),
                'taxcode': api_product.get('taxcode', ''),
                'company': api_product.get('company', ''),
                'brand': api_product.get('brand', ''),
                'text6': api_product.get('text6', ''),
                'price': api_product.get('price', '0.00'),
                'original_price': api_product.get('original_price', '0.00'),
                'image': api_product.get('image', ''),
                'edited_name': edited_product.name if edited_product else None,
                'edited_product': edited_product.product if edited_product else None,
                'edited_category': edited_product.category if edited_product else None,
                'edited_unit': edited_product.unit if edited_product else None,
                'edited_taxcode': edited_product.tax_code if edited_product else None,
                'edited_company': edited_product.company if edited_product else None,
                'edited_brand': edited_product.brand if edited_product else None,
                'edited_text6': edited_product.text6 if edited_product else None,
                'edited_price': edited_product.price if edited_product else None,
                'edited_image': edited_product.image if edited_product else None,
                'edited_original_price': edited_product.original_price if edited_product else None,
            }
            
            # Use edited values if available, otherwise use original values
            product['display_name'] = edited_product.name if edited_product else product['name']
            product['display_price'] = edited_product.price if edited_product else product['price']
            product['display_original_price'] = edited_product.original_price if edited_product else product['original_price']
            product['display_image'] = edited_product.image if edited_product else product['image']
                
        except requests.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            raise Http404("Could not retrieve products")
    
    # Get all images for the product
    product_images = []
    if is_custom_product:
        # Main image first
        if product.main_image:
            product_images.append({
                'image': product.main_image,
                'is_main': True
            })
        # Then additional images
        product_images.extend([
            {'image': img.image, 'is_main': False}
            for img in product.additional_images.all()
        ])
    else:
        # For API products
        if edited_product and edited_product.image:
            product_images.append({
                'image': edited_product.image,
                'is_main': True
            })
        elif product.get('image'):
            product_images.append({
                'image': product['image'],  # This is a URL
                'is_main': True,
                'is_url': True
            })
        # Additional images for API products
        if edited_product:
            product_images.extend([
                {'image': img.image, 'is_main': False}
                for img in edited_product.additional_images.all()
            ])

    # Handle wishlist and cart status
    in_wishlist = False
    in_cart = False
    cart_quantity = 0
    cart_count = 0
    
    if request.user.is_authenticated:
        if is_custom_product:
            # For custom products
            in_wishlist = Wishlist.objects.filter(
                user=request.user,
                product_id=product.id
            ).exists()
            
            cart_item = CartItem.objects.filter(
                user=request.user,
                product_id=product.id
            ).first()
        else:
            # For API products
            in_wishlist = Wishlist.objects.filter(
                user=request.user,
                api_product_code=product.get('code')
            ).exists()
            
            cart_item = CartItem.objects.filter(
                user=request.user,
                api_product_code=product.get('code')
            ).first()
        
        if cart_item:
            in_cart = True
            cart_quantity = cart_item.quantity
        
        cart_count = request.user.cart_items.count()
    
    context = {
        'product': product,
        'product_images': product_images,
        'in_wishlist': in_wishlist,
        'in_cart': in_cart,
        'cart_quantity': cart_quantity,
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

def sysmac_products(request):
    if not request.user.is_superuser:
        auth_logout(request)
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('login')
    
    api_url = "https://sysmacsynctoolapi.imcbs.com/api/upload-products/"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        api_products = response.json()
        
        processed_products = []
        for product in api_products:
            processed_product = {
                'code': str(product.get('code', '')),
                'name': product.get('name', 'Unknown Product'),
                'product': product.get('product', ''),
                'catagory': product.get('catagory', ''),
                'unit': product.get('unit', ''),
                'taxcode': product.get('taxcode', ''),
                'company': product.get('company', ''),
                'brand': product.get('brand', ''),
                'text6': product.get('text6', ''),
                'price': product.get('price', '0.00'),
                'original_price': product.get('original_price', '0.00')
            }
            processed_products.append(processed_product)
        
        edited_products = EditedAPIProduct.objects.filter(
            original_code__in=[p['code'] for p in processed_products]
        )
        
        edited_map = {p.original_code: p for p in edited_products}
        
        # Merge API products with edited data
        for product in processed_products:
            edited = edited_map.get(product['code'])
            if edited:
                product['edited_name'] = edited.name
                product['edited_product'] = edited.product
                product['edited_category'] = edited.category
                product['edited_unit'] = edited.unit
                product['edited_taxcode'] = edited.tax_code
                product['edited_company'] = edited.company
                product['edited_brand'] = edited.brand
                product['edited_text6'] = edited.text6
                product['edited_price'] = edited.price
                product['edited_image'] = edited.image
                product['original_price'] = edited.original_price or product['original_price']
                
    except requests.RequestException as e:
        print(f"Error fetching API products: {e}")
        processed_products = []
        edited_products = []
    
    return render(request, 'sysmac_products.html', {
        'products': processed_products,
        'edited_products': [p.original_code for p in edited_products]
    })

# Add these new views for editing API products

@login_required
@login_required
def edit_api_product(request, product_code):
    if not request.user.is_superuser:
        auth_logout(request)
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('login')

    # Try to get existing edited product
    try:
        edited_product = EditedAPIProduct.objects.get(original_code=product_code)
        instance = edited_product
    except EditedAPIProduct.DoesNotExist:
        instance = None
        # Fetch from API if no edited version exists
        api_url = "https://sysmacsynctoolapi.imcbs.com/api/upload-products/"
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            api_products = response.json()
            api_product = next((p for p in api_products if str(p.get('code')) == product_code), None)
            
            if api_product:
                initial_data = {
                    'name': api_product.get('name'),
                    'product': api_product.get('product'),
                    'category': api_product.get('catagory'),
                    'unit': api_product.get('unit'),
                    'tax_code': api_product.get('taxcode'),
                    'company': api_product.get('company'),
                    'brand': api_product.get('brand'),
                    'text6': api_product.get('text6'),
                    'price': api_product.get('price', '0.00'),
                    'original_price': api_product.get('original_price', '0.00')
                }
        except requests.RequestException as e:
            logger.error(f"Error fetching API product: {str(e)}")
            api_product = None
            initial_data = {}
            messages.error(request, 'Failed to fetch product details from API')

    if request.method == 'POST':
        form = EditedAPIProductForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            edited_product = form.save(commit=False)
            if not instance:  # New record
                edited_product.original_code = product_code
                # Preserve original price from API if not provided in form
                if api_product and not form.cleaned_data.get('original_price'):
                    edited_product.original_price = api_product.get('original_price', '0.00')
            
            try:
                edited_product.save()
                
                # Handle additional images - only if form is valid and product saved
                if 'additional_images' in request.FILES:
                    for image in request.FILES.getlist('additional_images'):
                        try:
                            ProductImage.objects.create(api_product=edited_product, image=image)
                        except Exception as e:
                            logger.error(f"Error saving additional image: {str(e)}")
                            messages.warning(request, f"Could not save one of the additional images: {str(e)}")
                
                messages.success(request, 'Product edited successfully!')
                return redirect('sysmac_products')
            
            except Exception as e:
                logger.error(f"Error saving product: {str(e)}")
                messages.error(request, f'Error saving product: {str(e)}')
        else:
            messages.error(request, 'Please correct the form errors')
    else:
        if instance:
            form = EditedAPIProductForm(instance=instance)
        else:
            form = EditedAPIProductForm(initial=initial_data)

    context = {
        'form': form,
        'product_code': product_code,
        'action': 'Edit' if instance else 'Add',
        'original_data': api_product if not instance else None
    }
    
    # Add existing additional images to context if editing
    if instance:
        context['additional_images'] = instance.additional_images.all()
    
    return render(request, 'edit_api_product.html', context)

@login_required
def delete_product_image(request, image_id):
    if not request.user.is_superuser:
        messages.error(request, "You don't have permission to delete images")
        return redirect('login')
    
    image = get_object_or_404(ProductImage, id=image_id)
    product_code = image.api_product.original_code
    image.delete()
    messages.success(request, "Image deleted successfully")
    return redirect('edit_api_product', product_code=product_code)





# views.py - Add this new view

@login_required
def delete_product_image(request, image_id):
    if not request.user.is_superuser:
        messages.error(request, "You don't have permission to delete images")
        return redirect('login')
    
    image = get_object_or_404(ProductImage, id=image_id)
    
    # Determine which product this belongs to for redirect
    if image.custom_product:
        product = image.custom_product
        redirect_url = reverse('edit_custom_product', args=[product.id])
    else:
        product = image.api_product
        redirect_url = reverse('edit_api_product', args=[product.original_code])
    
    image.delete()
    messages.success(request, "Image deleted successfully")
    return redirect(redirect_url)


@login_required
def delete_api_product(request, product_code):
    if not request.user.is_superuser:
        auth_logout(request)
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('login')
    
    try:
        product = EditedAPIProduct.objects.get(original_code=product_code)
        product.delete()
        messages.success(request, 'Product deleted successfully!')
    except EditedAPIProduct.DoesNotExist:
        messages.error(request, 'Product not found!')
    except Exception as e:
        logger.error(f"Error deleting API product: {str(e)}")
        messages.error(request, 'Error deleting product')
    
    return redirect('sysmac_products')


from django.db import transaction
import requests
from django.contrib import messages
from .models import Product

@login_required
def sync_products(request):
    if not request.user.is_superuser:
        auth_logout(request)
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('login')
    
    api_url = "https://sysmacsynctoolapi.imcbs.com/api/upload-products/"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        api_products = response.json()
        
        with transaction.atomic():
            # Create or update products
            for api_product in api_products:
                Product.objects.update_or_create(
                    code=str(api_product.get('code', '')),
                    defaults={
                        'name': api_product.get('name', 'Unknown Product'),
                        'product_type': api_product.get('product', ''),
                        'category': api_product.get('catagory', ''),
                        'unit': api_product.get('unit', ''),
                        'tax_code': api_product.get('taxcode', ''),
                        'company': api_product.get('company', ''),
                        'brand': api_product.get('brand', ''),
                        'text6': api_product.get('text6', ''),
                        'price': api_product.get('price', '0.00'),
                        'original_price': api_product.get('original_price', '0.00'),
                        'image': api_product.get('image', ''),
                        'is_active': True
                    }
                )
            
            # Deactivate products not in the API response
            existing_codes = [str(p.get('code', '')) for p in api_products]
            Product.objects.exclude(code__in=existing_codes).update(is_active=False)
            
        messages.success(request, f'Successfully synced {len(api_products)} products')
        return redirect('local_products')
        
    except requests.RequestException as e:
        messages.error(request, f'Failed to sync products: {str(e)}')
        return redirect('local_products')




def privacy_policy(request):
    return render(request, 'privacy_policy.html')

# def terms_and_conditions(request):
#     return render(request, 'Terms and Conditions.html')

def cancellation_refund_policy(request):
    return render(request, 'cancellation_refund_policy.html')

def terms_and_conditions(request):
    return render(request, 'terms_and_conditions.html')

def contact(request):
    return render(request, 'contact.html')



