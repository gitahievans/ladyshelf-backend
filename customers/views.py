from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from customers.models import Address
from customers.serializers import AddressSerializer, CustomerProfileSerializer


class MeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "account"

    def get(self, request):
        serializer = CustomerProfileSerializer(request.user)
        return Response(serializer.data)


class AddressListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AddressSerializer
    throttle_scope = "account"

    def get_queryset(self):
        return Address.objects.filter(customer=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["customer"] = self.request.user
        return context


class AddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AddressSerializer
    throttle_scope = "account"

    def get_queryset(self):
        return Address.objects.filter(customer=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["customer"] = self.request.user
        return context

