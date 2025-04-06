from django.urls import path
from . import views
from .views import *

urlpatterns = [
    path('', views.home_view, name='home'),
    path('shop/', views.shop_view, name='shop'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.cart_view, name='cart'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('create-checkout-session/', views.create_checkout_session, name='create_checkout_session'),
    path('update-cart-quantity/', views.update_cart_quantity, name='update_cart_quantity'),
    path('stripe-webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('success/', views.success_view, name='success'),
    path('thank-you/', views.thank_you_view, name='thank_you'),
    path('cart/count/', cart_count_api, name='cart_count_api'),
    path('add-to-cart-ajax/<int:product_id>/', views.add_to_cart_ajax, name='add_to_cart_ajax'),

]
