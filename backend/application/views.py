# views.py
from django.shortcuts import render, redirect, get_object_or_404, HttpResponse
from .models import *
from django.conf import settings
import stripe
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
import json
from django.core.mail import send_mail
from django.template.loader import render_to_string

stripe.api_key = settings.STRIPE_SECRET_KEY

def home_view(request):
    products = Product.objects.all()[:3]
    return render(request, 'application/home.html', {'products': products})

def shop_view(request):
    products = Product.objects.all()
    return render(request, 'application/shop.html', {'products': products})

def success_view(request):
    session_id = request.GET.get("session_id")
    if not session_id:
        return redirect("home")

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        customer = session.get("customer_details", {})
        address = customer.get("address", {})

        request.session["checkout_info"] = {
            "name": customer.get("name"),
            "email": customer.get("email"),
            "address": {
                "line1": address.get("line1"),
                "line2": address.get("line2"),
                "city": address.get("city"),
                "state": address.get("state"),
                "postal_code": address.get("postal_code"),
                "country": address.get("country"),
            },
        }

    except Exception as e:
        print("Stripe session fetch failed:", str(e))
        return redirect("home")

    return redirect("thank_you")



def cancel_view(request):
    return render(request, 'application/cancel.html')

def thank_you_view(request):
    info = request.session.get("checkout_info", {})
    cart = get_user_cart(request)
    cart_items = CartItem.objects.filter(cart=cart)

    items = [
        {
            "name": f"{item.product.name} - {item.get_variant_display()}",
            "quantity": item.quantity,
            "amount": item.total_price,
        }
        for item in cart_items
    ]
    total = sum(item["amount"] for item in items)

    context = {
        "name": info.get("name"),
        "email": info.get("email"),
        "address": info.get("address"),
        "items": items,
        "total": total,
    }

    # optionally clear cart items now that the order is shown
    cart_items.delete()

    return render(request, "application/thank_you.html", context)

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

@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = get_user_cart(request)
    variant = request.POST.get('variant', 'MILD')

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        variant=variant
    )
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
        'total': total,
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
                    'name': f"{item.product.name} - {item.get_variant_display()}",
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
        success_url=f"http://localhost:8000/success/?session_id={{CHECKOUT_SESSION_ID}}",  # ✅ Stripe replaces this
        cancel_url='http://localhost:8000/cancel/',
        shipping_address_collection={
            'allowed_countries': ['US', 'CA']
        },
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

            cart_items.delete()

        except Cart.DoesNotExist:
            return HttpResponse(status=404)

    return HttpResponse(status=200)

def cart_count_api(request):
    user = request.user if request.user.is_authenticated else None
    session_key = request.session.session_key

    cart = Cart.objects.filter(user=user).first() if user else Cart.objects.filter(session_key=session_key).first()
    count = sum(item.quantity for item in cart.items.all()) if cart else 0
    return JsonResponse({"count": count})

@require_GET
def add_to_cart_ajax(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    variant = request.GET.get('variant', 'MILD')
    cart = get_user_cart(request)

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        variant=variant
    )
    if not created:
        cart_item.quantity += 1
        cart_item.save()

    count = sum(item.quantity for item in cart.items.all())
    return JsonResponse({"status": "ok", "count": count})

@require_POST
def update_cart_variant(request):
    item_id = request.POST.get("item_id")
    variant = request.POST.get("variant")
    try:
        item = CartItem.objects.get(id=item_id)
        item.variant = variant
        item.save()
        return JsonResponse({"status": "ok"})
    except CartItem.DoesNotExist:
        return JsonResponse({"status": "error"}, status=404)

@require_POST
def remove_from_cart(request):
    item_id = request.POST.get("item_id")
    try:
        item = CartItem.objects.get(id=item_id)
        item.delete()
        return JsonResponse({'status': 'ok'})
    except CartItem.DoesNotExist:
        return JsonResponse({'status': 'error'}, status=404)
