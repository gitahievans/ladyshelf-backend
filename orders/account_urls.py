from django.urls import path

from orders.views import AccountOrderListView

urlpatterns = [
    path("orders", AccountOrderListView.as_view(), name="account-orders"),
]
