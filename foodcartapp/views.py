from django.http import JsonResponse
from django.templatetags.static import static
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.serializers import ModelSerializer
from django.db.models import F,Subquery,OuterRef
from django.db import transaction
from .models import Product, Order, OrderedProduct


def banners_list_api(request):
    # FIXME move data to db?
    return JsonResponse([
        {
            'title': 'Burger',
            'src': static('burger.jpg'),
            'text': 'Tasty Burger at your door step',
        },
        {
            'title': 'Spices',
            'src': static('food.jpg'),
            'text': 'All Cuisines',
        },
        {
            'title': 'New York',
            'src': static('tasty.jpg'),
            'text': 'Food is incomplete without a tasty dessert',
        }
    ], safe=False, json_dumps_params={
        'ensure_ascii': False,
        'indent': 4,
    })


def product_list_api(request):
    products = Product.objects.select_related('category').available()

    dumped_products = []
    for product in products:
        dumped_product = {
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'special_status': product.special_status,
            'description': product.description,
            'category': {
                'id': product.category.id,
                'name': product.category.name,
            } if product.category else None,
            'image': product.image.url,
            'restaurant': {
                'id': product.id,
                'name': product.name,
            }
        }
        dumped_products.append(dumped_product)
    return JsonResponse(dumped_products, safe=False, json_dumps_params={
        'ensure_ascii': False,
        'indent': 4,
    })


class ProductsSerializer(ModelSerializer):
    class Meta:
        model = OrderedProduct
        fields = ['product', 'quantity']


class OrderSerializer(ModelSerializer):
    products = ProductsSerializer(many=True, allow_empty=False,write_only=True)

    class Meta:
        model = Order
        read_only_fields = ['id']
        fields = ['id','firstname', 'lastname', 'phonenumber', 'address', 'products']


@api_view(['POST'])
@transaction.atomic
def register_order(request):
    serializer = OrderSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serialized_order = {field: serializer.validated_data[field]
                  for field in ['firstname', 'lastname', 'phonenumber', 'address']}
    order = Order.objects.create(**serialized_order)
    basket = [OrderedProduct(order=order, cost=fields['product'].price, **fields)
              for fields in serializer.validated_data['products']]
    OrderedProduct.objects.bulk_create(basket)
    return Response(OrderSerializer(order).data)
