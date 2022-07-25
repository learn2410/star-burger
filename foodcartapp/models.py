from collections import defaultdict, namedtuple

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from geopy import distance
from phonenumber_field.modelfields import PhoneNumberField

from geocoder.models import Location, add_geocoder_addresses


class Restaurant(models.Model):
    name = models.CharField(
        'название',
        max_length=50
    )
    address = models.CharField(
        'адрес',
        max_length=100,
        blank=True,
    )
    contact_phone = models.CharField(
        'контактный телефон',
        max_length=50,
        blank=True,
    )

    class Meta:
        verbose_name = 'ресторан'
        verbose_name_plural = 'рестораны'

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def available(self):
        products = (
            RestaurantMenuItem.objects
                .filter(availability=True)
                .values_list('product')
        )
        return self.filter(pk__in=products)


class ProductCategory(models.Model):
    name = models.CharField(
        'название',
        max_length=50
    )

    class Meta:
        verbose_name = 'категория'
        verbose_name_plural = 'категории'

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(
        'название',
        max_length=50
    )
    category = models.ForeignKey(
        ProductCategory,
        verbose_name='категория',
        related_name='products',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    price = models.DecimalField(
        'цена',
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    image = models.ImageField(
        'картинка'
    )
    special_status = models.BooleanField(
        'спец.предложение',
        default=False,
        db_index=True,
    )
    description = models.TextField(
        'описание',
        blank=True,
    )

    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = 'товар'
        verbose_name_plural = 'товары'

    def __str__(self):
        return self.name


class RestaurantMenuItem(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        related_name='menu_items',
        verbose_name="ресторан",
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='menu_items',
        verbose_name='продукт',
    )
    availability = models.BooleanField(
        'в продаже',
        default=True,
        db_index=True
    )

    class Meta:
        verbose_name = 'пункт меню ресторана'
        verbose_name_plural = 'пункты меню ресторана'
        unique_together = [
            ['restaurant', 'product']
        ]

    def __str__(self):
        return f"{self.restaurant.name} - {self.product.name}"


class OrderQuerySet(models.QuerySet):
    def calc_can_cook(self):
        """
        Calulate which restaurant can cook orders in current Order queryset
        return: dict like this:
            {order_id:[restaurant_id,restaurant_id,...] , order_id:[], ...}
        """
        product_in_restaurants = defaultdict(set)
        restaurant_query = RestaurantMenuItem.objects \
            .filter(availability=True) \
            .select_related('restaurant') \
            .values_list('restaurant_id', 'product_id')
        for restaurant, product in restaurant_query:
            product_in_restaurants[product].add(restaurant)
        ordered_products = defaultdict(set)
        orders_query = self.select_related('products') \
            .values_list('id', 'products__product_id')
        for order, product in orders_query:
            ordered_products[order].add(product)
        can_cook = {}
        for order, products in ordered_products.items():
            can_cook.update({
                order: list(set.intersection(*[product_in_restaurants[product] for product in products]))
            })
        return can_cook

    def can_cook_with_distance(self, restaurant_by_name=True):
        """
        Used calc_can_cook() and return: dict like this:
            {order_id:[namedtuple(name,distance), ...] , order_id:[], ...}
        where 'name' mean restaurant name, if restaurant_by_name=True else  restaurant id
              'distance' - distance between addresses order and restaurant
        """
        can_cook = self.calc_can_cook()
        restaurant_ids = list(set.union(*[set(restaurant) for restaurant in can_cook.values()]))
        restaurants_raw = Restaurant.objects.filter(id__in=restaurant_ids).values('id', 'address', 'name')
        restaurants_names = {restaurant['id']: restaurant['name'] for restaurant in restaurants_raw}
        restaurants_addreses = {restaurant['id']: restaurant['address'] for restaurant in restaurants_raw}
        order_ids = can_cook.keys()
        orders = Order.objects.filter(id__in=order_ids).values('id', 'address')
        orders_addresses = {order['id']: order['address'] for order in orders}
        used_addresses = set(list(orders_addresses.values()) + list(restaurants_addreses.values()))

        geo_addresses = {}
        geo_query = Location.objects \
            .filter(address__in=list(used_addresses)) \
            .values_list('address', 'lon', 'lat')
        for address, lon, lat in geo_query:
            geo_addresses.update({address: (lon, lat)})
            used_addresses.discard(address)
        if len(used_addresses) > 0:
            new_geo_addresses = add_geocoder_addresses(used_addresses)
            geo_addresses.update(new_geo_addresses)

        new_can_cook = {}
        Resraurant_location = namedtuple('Resraurant_location', 'name distance')
        restaurant_locations = {restaurant: geo_addresses[address]
                                for restaurant, address in restaurants_addreses.items()}
        for order, restaurants in can_cook.items():
            order_location = geo_addresses[orders_addresses[order]]
            new_can_cook.update({order: []})
            for restaurant in restaurants:
                new_can_cook[order].append(Resraurant_location(
                    restaurants_names[restaurant] if restaurant_by_name else restaurant,
                    distance.distance(order_location, restaurant_locations[restaurant]).km)
                    )
            if len(new_can_cook[order]) > 0:
                new_can_cook[order].sort(key=lambda r: r[1])
        return new_can_cook


class Order(models.Model):
    STATUSES = (
        ("START", "принят"),
        ("WORK", "в работе"),
        ("CANCEL", "отменен"),
        ("FINISH", "завершен"),
    )
    PAYMENTS = (
        ("CASH", "наличные"),
        ("ELEСTRON", "безналичные"),
        ("UNDEFINED", "-не указано"),
    )
    status = models.CharField("Статус", max_length=10, db_index=True, choices=STATUSES, default="START")
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='orders',
                                   verbose_name='Готовит', blank=True, null=True, default=None)
    payment = models.CharField("Оплата", max_length=10, db_index=True, choices=PAYMENTS, default="UNDEFINED")
    firstname = models.CharField('Имя', max_length=50, db_index=True)
    lastname = models.CharField('Фамилия', max_length=50, db_index=True)
    phonenumber = PhoneNumberField('Телефон', db_index=True)
    address = models.CharField('Адрес', max_length=100, db_index=True)
    comment = models.TextField('Комментарий', blank=True)
    registrated = models.DateTimeField('Время регистрации', default=timezone.now)
    called = models.DateTimeField('Время созвона', null=True, blank=True)
    delivered = models.DateTimeField('Время доставки', null=True, blank=True)

    objects = OrderQuerySet.as_manager()

    class Meta:
        verbose_name = 'заказ'
        verbose_name_plural = 'заказы'

    def __str__(self):
        return (f'{self.id} ({self.firstname} {self.lastname} тел.{self.phonenumber}, {self.address})')


class OrderedProduct(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='products', verbose_name='Заказ')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='ordered_products',
                                verbose_name='Продукт')
    quantity = models.PositiveIntegerField(
        verbose_name='Количество',
        validators=[MinValueValidator(1)],
        default=1,
    )
    cost = models.DecimalField(
        'зафиксированная цена',
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        verbose_name = 'в заказе'
        verbose_name_plural = 'в заказе'
        unique_together = [
            ['order', 'product']
        ]

    def __str__(self):
        return f"{self.product.name} - {self.quantity} шт. (заказ № {self.order.pk} )"
