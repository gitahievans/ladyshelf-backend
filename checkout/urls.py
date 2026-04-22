from django.urls import path

from checkout.views import CheckoutOrderCreateView, CheckoutQuoteView, PickupInfoView

urlpatterns = [
    path("quote", CheckoutQuoteView.as_view(), name="checkout-quote"),
    path("orders", CheckoutOrderCreateView.as_view(), name="checkout-orders"),
    path("pickup-info", PickupInfoView.as_view(), name="checkout-pickup-info"),
]
