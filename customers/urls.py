from django.urls import path

from customers.views import AddressDetailView, AddressListCreateView, MeView

urlpatterns = [
    path("me", MeView.as_view(), name="account-me"),
    path("addresses", AddressListCreateView.as_view(), name="account-addresses"),
    path("addresses/<int:pk>", AddressDetailView.as_view(), name="account-address-detail"),
]
