# views.py
from django.shortcuts import render, redirect, get_object_or_404, HttpResponse
from .models import *
from django.conf import settings
import stripe
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET

stripe.api_key = settings.STRIPE_SECRET_KEY

def home_view(request):
    products = Product.objects.all()[:3]
    return render(request, 'application/home.html', {'products': products})

def shop_view(request):
    products = Product.objects.all()
    return render(request, 'application/shop.html', {'products': products})

def success_view(request):
    cart = get_user_cart(request)
    CartItem.objects.filter(cart=cart).delete()
    return redirect('thank_you')

def cancel_view(request):
    return render(request, 'application/cancel.html')

def thank_you_view(request):
    return render(request, 'application/thank_you.html')


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
    total = sum(item.total_price for item in cart_items)

    return render(request, 'application/checkout.html', {
        'cart_items': cart_items,
        'total': total,
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY
    })


@csrf_exempt
def create_checkout_session(request):
    cart = get_user_cart(request)
    cart_items = CartItem.objects.filter(cart=cart)

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
    metadata={
        'cart_id': str(cart.id),
    }
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
    
@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        cart_id = session['metadata'].get('cart_id')
        try:
            cart = Cart.objects.get(id=cart_id)
            cart_items = CartItem.objects.filter(cart=cart)

            # Send confirmation email
            if cart.user and cart.user.email:
                message = render_to_string('application/email_receipt.html', {
                    'user': cart.user,
                    'cart_items': cart_items,
                    'total': sum(item.total_price for item in cart_items)
                })
                send_mail(
                    subject='Your CallYourMomma Order Confirmation',
                    message='',
                    from_email='noreply@callyourmomma.com',
                    recipient_list=[cart.user.email],
                    html_message=message
                )

            cart_items.delete()  # Clear the cart after processing

        except Cart.DoesNotExist:
            return HttpResponse(status=404)

    return HttpResponse(status=200)

def thank_you_view(request):
    cart = get_user_cart(request)
    cart_items = CartItem.objects.filter(cart=cart)
    total = sum(item.total_price for item in cart_items)

    if request.user.is_authenticated and request.user.email:
        message = render_to_string('application/email_receipt.html', {
            'user': request.user,
            'cart_items': cart_items,
            'total': total
        })
        send_mail(
            subject='Your CallYourMomma Order Confirmation',
            message='',
            from_email='noreply@callyourmomma.com',
            recipient_list=[request.user.email],
            html_message=message
        )

    return render(request, 'application/thank_you.html', {
        'cart_items': cart_items,
        'total': total
    })

def cart_count_api(request):
    user = request.user if request.user.is_authenticated else None
    session_key = request.session.session_key

    cart = Cart.objects.filter(user=user).first() if user else Cart.objects.filter(session_key=session_key).first()
    count = sum(item.quantity for item in cart.items.all()) if cart else 0
    return JsonResponse({"count": count})

@require_GET
def add_to_cart_ajax(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = get_user_cart(request)
    cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not created:
        cart_item.quantity += 1
        cart_item.save()

    count = sum(item.quantity for item in cart.items.all())
    return JsonResponse({"status": "ok", "count": count})