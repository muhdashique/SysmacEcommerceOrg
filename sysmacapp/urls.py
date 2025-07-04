from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('google-auth/', views.google_auth, name='google_auth'),
    path('logout/', views.logout_view, name='logout'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('user-dashboard/', views.user_dashboard, name='user_dashboard'),
    path('sysmac-products/', views.sysmac_products, name='sysmac_products'),
    path('custom-products/', views.custom_products, name='custom_products'),
    path('custom-products/add/', views.add_custom_product, name='add_custom_product'),
    path('custom-products/edit/<int:product_id>/', views.edit_custom_product, name='edit_custom_product'),
    path('custom-products/delete/<int:product_id>/', views.delete_custom_product, name='delete_custom_product'),
    path('cart/', views.cart_view, name='cart'),
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/add/<int:product_id>/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/<int:product_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),   
    path('products/<product_identifier>/', views.product_detail, name='product_detail'),
    path('cart/add-api/<str:product_code>/', views.add_api_product_to_cart, name='add_api_product_to_cart'),
    path('cart/remove/<str:product_code>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/remove-api/<str:product_code>/', views.remove_api_product_from_cart, name='remove_api_from_cart'),
    path('cart/update/<int:product_id>/', views.update_cart_quantity, name='update_cart_quantity'),
    path('cart/check-api/<str:product_code>/', views.check_cart_status_api, name='check_cart_status_api'),
    
    path('wishlist/check-api/<str:product_code>/', views.check_wishlist_status_api, name='check_wishlist_status_api'),

#  path('wishlist/add/<str:product_id>/', views.add_to_wishlist, name='add_to_wishlist'),
    # path('wishlist/remove/<str:product_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    path('wishlist/check/<str:product_id>/', views.check_wishlist_status, name='check_wishlist_status'),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)