# cart/templatetags/cart_tags.py
from django import template
from ..models import Cart

register = template.Library()

@register.filter
def cart_item_count(request):
    user = request.user if request.user.is_authenticated else None
    session_key = request.session.session_key

    cart = Cart.objects.filter(user=user).first() if user else Cart.objects.filter(session_key=session_key).first()
    if not cart:
        return 0
    return sum(item.quantity for item in cart.items.all())
