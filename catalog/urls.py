from django.urls import path

from catalog.views import CategoryListView, ProductDetailView, ProductListView

urlpatterns = [
    path("categories", CategoryListView.as_view(), name="catalog-categories"),
    path("products", ProductListView.as_view(), name="catalog-products"),
    path("products/<slug:slug>", ProductDetailView.as_view(), name="catalog-product-detail"),
]
