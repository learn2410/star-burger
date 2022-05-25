from django.http import JsonResponse
from django.templatetags.static import static
import json
from rest_framework.decorators import api_view
from rest_framework.response import Response


from .models import Product,Order,Basket


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

def is_order_ok(checked_order):
    order=checked_order.copy()
    #--check fields
    required_fields = {"products", "firstname", "lastname", "phonenumber", "address"}
    if set(order.keys()) != required_fields:
        absent_fields = required_fields.difference(set(order.keys()))
        return f'no required fields {str(absent_fields)}'
    #--check fields no None
    for key in required_fields:
        if order[key] is None:
            return f"field '{key}' is None"
    products=order.pop('products')
    #--check list and fields in products
    if not isinstance(products, list):
        return "'products' data type is not list"
    if len(products)==0:
        return 'list of products empty'
    for product in products:
        if not isinstance(product, dict):
            return 'one element type of products is not dict'
        if set(product.keys()) != {"product","quantity"}:
            return 'one element of products is not content required field'
    #-- check types in order
    for key,value in order.items():
        if not isinstance(value,str):
            return f"'{key}' data type is not str"
    #-- check types in products
    for product in products:
        for key,value in product.items():
            if not isinstance(value, int):
                return f"'{key}' in [products] data type is not int"
    #-- if all ok
    return ''

@api_view(['POST'])
def register_order(request):
    try:
        order=request.data
    except ValueError:
        return JsonResponse({
            'error': 'order request error',
        })

    order_error=is_order_ok(order)
    if order_error:
        return Response({'error':order_error})
    products=order.pop('products')

    if len(products)==0:
        return JsonResponse({
            'error': 'no products in order',
        })
    order=Order(**order)
    order.save()
    bulk_list=[Basket(order_id=order.id,quantity=product['quantity'],product_id=product['product'])
        for product in products]
    Basket.objects.bulk_create(bulk_list)
    return Response({})
