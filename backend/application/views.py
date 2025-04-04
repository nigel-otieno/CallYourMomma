# views.py
from django.shortcuts import render, redirect, get_object_or_404
from .models import *
from django.conf import settings
import stripe
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.views.decorators.http import require_POST


stripe.api_key = settings.STRIPE_SECRET_KEY

def home_view(request):
    products = Product.objects.all()[:3]
    return render(request, 'application/home.html', {'products': products})

def shop_view(request):
    products = Product.objects.all()
    return render(request, 'application/shop.html', {'products': products})

def success_view(request):
    CartItem.objects.filter(user=request.user).delete()
    return render(request, 'application/success.html')

def cancel_view(request):
    return render(request, 'application/cancel.html')


def get_user_cart(request):
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart, _ = Cart.objects.get_or_create(session_key=session_key, user=None)
    return cart

def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = get_user_cart(request)
    cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    return redirect('cart')

def cart_view(request):
    cart = get_user_cart(request)
    cart_items = CartItem.objects.filter(cart=cart)
    total = sum(item.total_price for item in cart_items)

    return render(request, 'application/cart.html', {
        'cart_items': cart_items,
        'total': total,  # 🔥 fix: use the key your template expects
    })


def checkout_view(request):
    cart = get_user_cart(request)
    cart_items = CartItem.objects.filter(cart=cart)
    if request.method == 'POST':
        # dummy redirect for now
        return redirect('thank_you')
    return render(request, 'application/checkout.html', {
        'cart_items': cart_items
    })


@csrf_exempt
def create_checkout_session(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Optional: identify user/cart from session or database
    cart_id = request.session.get('cart_id')
    if not cart_id:
        return JsonResponse({'error': 'Cart not found'}, status=404)

    cart_items = CartItem.objects.filter(cart_id=cart_id)
    line_items = [
        {
            'price_data': {
                'currency': 'usd',
                'unit_amount': int(item.product.price * 100),
                'product_data': {
                    'name': item.product.name,
                },
            },
            'quantity': item.quantity,
        }
        for item in cart_items
    ]

    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=line_items,
        mode='payment',
        success_url='http://localhost:8000/success/',
        cancel_url='http://localhost:8000/cancel/',
    )

    return JsonResponse({'id': session.id})

@require_POST
def update_cart_quantity(request):
    item_id = request.POST.get('item_id')
    action = request.POST.get('action')

    try:
        item = CartItem.objects.get(id=item_id)
        if action == 'increase':
            item.quantity += 1
        elif action == 'decrease' and item.quantity > 1:
            item.quantity -= 1
        item.save()
        return JsonResponse({'status': 'ok', 'new_quantity': item.quantity})
    except CartItem.DoesNotExist:
        return JsonResponse({'status': 'error'}, status=404)