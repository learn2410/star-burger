from collections import defaultdict,namedtuple

from django import forms
from django.shortcuts import redirect, render
from django.views import View
from django.urls import reverse_lazy
from django.contrib.auth.decorators import user_passes_test

from django.contrib.auth import authenticate, login
from django.contrib.auth import views as auth_views
from django.db.models import Sum,F,Q,Subquery
from geopy import distance,location,Yandex,Point

from foodcartapp.models import Product, Restaurant,Order,RestaurantMenuItem
from geocoder.models import Location,add_geocoder_addresses
from django.utils.crypto import get_random_string

class Login(forms.Form):
    username = forms.CharField(
        label='Логин', max_length=75, required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Укажите имя пользователя'
        })
    )
    password = forms.CharField(
        label='Пароль', max_length=75, required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите пароль'
        })
    )


class LoginView(View):
    def get(self, request, *args, **kwargs):
        form = Login()
        return render(request, "login.html", context={
            'form': form
        })

    def post(self, request):
        form = Login(request.POST)

        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                if user.is_staff:  # FIXME replace with specific permission
                    return redirect("restaurateur:RestaurantView")
                return redirect("start_page")

        return render(request, "login.html", context={
            'form': form,
            'ivalid': True,
        })


class LogoutView(auth_views.LogoutView):
    next_page = reverse_lazy('restaurateur:login')


def is_manager(user):
    return user.is_staff  # FIXME replace with specific permission


@user_passes_test(is_manager, login_url='restaurateur:login')
def view_products(request):
    restaurants = list(Restaurant.objects.order_by('name'))
    products = list(Product.objects.prefetch_related('menu_items'))

    default_availability = {restaurant.id: False for restaurant in restaurants}
    products_with_restaurants = []
    for product in products:

        availability = {
            **default_availability,
            **{item.restaurant_id: item.availability for item in product.menu_items.all()},
        }
        orderer_availability = [availability[restaurant.id] for restaurant in restaurants]

        products_with_restaurants.append(
            (product, orderer_availability)
        )

    return render(request, template_name="products_list.html", context={
        'products_with_restaurants': products_with_restaurants,
        'restaurants': restaurants,
    })


@user_passes_test(is_manager, login_url='restaurateur:login')
def view_restaurants(request):
    return render(request, template_name="restaurants_list.html", context={
        'restaurants': Restaurant.objects.all(),
    })

# def get_location(address):
#     location,created = Location.objects.get_or_create(address=address)
#     return location.lon,location.lat

def who_can_cook_orders():
    used_addresses = set()
    product_in_restaurants = defaultdict(set)
    restaurant_address = {}
    for restaurant, product, address in RestaurantMenuItem.objects.filter(availability=True).select_related('restaurant')\
        .values_list('restaurant__name', 'product_id','restaurant__address'):
        product_in_restaurants[product].add(restaurant)
        if restaurant not in restaurant_address:
            restaurant_address.update({restaurant: address})
            used_addresses.add(address)
    ordered_products = defaultdict(set)
    order_address = {}
    for order, product, address in Order.objects \
        .select_related('basket').filter(status='START').values_list('id', 'basket__product_id', 'address'):
        ordered_products[order].add(product)
        if order not in order_address:
            order_address.update({order: address})
            used_addresses.add(address)
    geo_addresses={}
    for address,lon,lat in Location.objects.filter(address__in=list(used_addresses)).values_list('address','lon','lat'):
        geo_addresses.update({address:(lon,lat)})
        used_addresses.discard(address)
    if len(used_addresses)>0:
        new_geo_addresses = add_geocoder_addresses(used_addresses)
        geo_addresses.update(new_geo_addresses)
    can_cook = {}
    Resraurant_location = namedtuple('Resraurant_location', 'name distance')
    for order, products in ordered_products.items():
        can_cook.update({order: list(set.intersection(*[product_in_restaurants[product] for product in products]))})
        for n, restaurant in enumerate(can_cook[order]):
            if restaurant_address[restaurant] in geo_addresses:
                restaurant_location=geo_addresses[restaurant_address[restaurant]]
            else:
                location = Location.objects.create(address=restaurant_address[restaurant])
                restaurant_location=(location.lon,location.lat)
            if order_address[order] in geo_addresses:
                order_location = geo_addresses[order_address[order]]
            else:
                location = Location.objects.create(address=order_address[order])
                order_location=(location.lon,location.lat)
            spacing=distance.distance(order_location, restaurant_location).km
            can_cook[order][n] = Resraurant_location(restaurant,spacing)
        can_cook[order].sort(key=lambda r: r.distance)
    return can_cook

@user_passes_test(is_manager, login_url='restaurateur:login')
def view_orders(request):
    fields = ('id', 'status', 'phonenumber', 'address', 'comment', 'restaurant__name')
    can_cook = who_can_cook_orders()
    orders = list(Order.objects.filter(status__in=("START","WORK")) \
        .select_related('restaurant', 'basket') \
        .order_by('status','id') \
        .values(*fields))
        # .annotate(cost=Sum(F('basket__cost') * F('basket__quantity')))
    for order in orders:
        order.update({'cancook': can_cook[order['id']] if order['id'] in can_cook else []})
    return render(request, template_name='order_items.html', context={'orders':orders})
