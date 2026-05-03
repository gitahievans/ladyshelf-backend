from django.urls import path

from orders.views import AccountOrderCancellationView, AccountOrderListView

urlpatterns = [
    path("orders", AccountOrderListView.as_view(), name="account-orders"),
    path(
        "orders/<str:order_number>/cancellations",
        AccountOrderCancellationView.as_view(),
        name="account-order-cancellations",
    ),
]
