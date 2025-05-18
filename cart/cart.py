from django.conf import settings
from .models import CartItem
from main.models import Product

class Cart:
    def __init__(self, request):
        self.request = request
        self.session = request.session
        self.user = request.user if request.user.is_authenticated else None
        self.session_key = self.session.session_key
        if not self.session_key:
            self.session.create()
            self.session_key = self.session.session_key

    def add(self, product, quantity=1, override_quantity=False):
        if self.user:
            cart_item, created = CartItem.objects.get_or_create(
                user=self.user,
                product=product,
                defaults={'quantity': quantity}
            )
            if not created:
                if override_quantity:
                    cart_item.quantity = quantity
                else:
                    cart_item.quantity += quantity
                cart_item.save()
        else:
            cart_item, created = CartItem.objects.get_or_create(
                session_key=self.session_key,
                product=product,
                defaults={'quantity': quantity}
            )
            if not created:
                if override_quantity:
                    cart_item.quantity = quantity
                else:
                    cart_item.quantity += quantity
                cart_item.save()

    def remove(self, product):
        if self.user:
            CartItem.objects.filter(user=self.user, product=product).delete()
        else:
            CartItem.objects.filter(session_key=self.session_key, product=product).delete()

    def get_items(self):
        if self.user:
            return CartItem.objects.filter(user=self.user).select_related('product')
        return CartItem.objects.filter(session_key=self.session_key).select_related('product')

    def clear(self):
        if self.user:
            CartItem.objects.filter(user=self.user).delete()
        else:
            CartItem.objects.filter(session_key=self.session_key).delete()

    def __len__(self):
        return sum(item.quantity for item in self.get_items())