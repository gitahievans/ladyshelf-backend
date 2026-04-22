from rest_framework import serializers

from wishlist.models import WishlistItem


class WishlistItemSerializer(serializers.ModelSerializer):
    productId = serializers.CharField(source="product.external_id")

    class Meta:
        model = WishlistItem
        fields = ("productId", "created_at")


class WishlistMutationSerializer(serializers.Serializer):
    productId = serializers.CharField()
