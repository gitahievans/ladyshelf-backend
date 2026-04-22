from django.urls import path

from wishlist.views import WishlistCollectionView, WishlistItemDetailView

urlpatterns = [
    path("", WishlistCollectionView.as_view(), name="wishlist-collection"),
    path("<str:product_id>", WishlistItemDetailView.as_view(), name="wishlist-item-detail"),
]
