from django.conf import settings
from django.contrib import admin
from django.shortcuts import reverse, redirect
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.http import is_safe_url,url_has_allowed_host_and_scheme

from .models import Basket
from .models import Order
from .models import Product
from .models import ProductCategory
from .models import Restaurant
from .models import RestaurantMenuItem


class RestaurantMenuItemInline(admin.TabularInline):
    model = RestaurantMenuItem
    extra = 0




@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    search_fields = [
        'name',
        'address',
        'contact_phone',
    ]
    list_display = [
        'name',
        'address',
        'contact_phone',
    ]
    inlines = [
        RestaurantMenuItemInline
    ]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'get_image_list_preview',
        'name',
        'category',
        'price',
    ]
    list_display_links = [
        'name',
    ]
    list_filter = [
        'category',
    ]
    search_fields = [
        # FIXME SQLite can not convert letter case for cyrillic words properly, so search will be buggy.
        # Migration to PostgreSQL is necessary
        'name',
        'category__name',
    ]

    inlines = [
        RestaurantMenuItemInline
    ]
    fieldsets = (
        ('Общее', {
            'fields': [
                'name',
                'category',
                'image',
                'get_image_preview',
                'price',
            ]
        }),
        ('Подробно', {
            'fields': [
                'special_status',
                'description',
            ],
            'classes': [
                'wide'
            ],
        }),
    )

    readonly_fields = [
        'get_image_preview',
    ]

    class Media:
        css = {
            "all": (
                static("admin/foodcartapp.css")
            )
        }

    def get_image_preview(self, obj):
        if not obj.image:
            return 'выберите картинку'
        return format_html('<img src="{url}" style="max-height: 200px;"/>', url=obj.image.url)

    get_image_preview.short_description = 'превью'

    def get_image_list_preview(self, obj):
        if not obj.image or not obj.id:
            return 'нет картинки'
        edit_url = reverse('admin:foodcartapp_product_change', args=(obj.id,))
        return format_html('<a href="{edit_url}"><img src="{src}" style="max-height: 50px;"/></a>', edit_url=edit_url,
                           src=obj.image.url)

    get_image_list_preview.short_description = 'превью'


@admin.register(ProductCategory)
class ProductAdmin(admin.ModelAdmin):
    pass

class BasketInline(admin.TabularInline):
    model = Basket
    extra = 0
    fields = ('order','product','quantity','cost')
    readonly_fields = ('cost',)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    search_fields = ['id', 'firstname', 'lastname', 'phonenumber', 'address']
    ordering = ['id']
    inlines = [BasketInline]
    pass

    def save_formset(self, request, form, formset, change):
        for inline_form in formset.forms:
            if inline_form.has_changed():
                inline_form.instance.fix_cost()
        super().save_formset(request, form, formset, change)

    def save_model(self, request, obj, form, change):
        if obj.status=='START' and obj.restaurant:
            obj.status='WORK'
        super().save_model(request, obj, form, change)

    def response_post_save_change(self, request, obj):
        if "next" in request.GET and url_has_allowed_host_and_scheme(request.GET['next'], settings.ALLOWED_HOSTS):
            return redirect(request.GET['next'])
        return super().response_post_save_change(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        '''limit the choice of restaurants to those who can cook'''
        if db_field.name == "restaurant":
            path = str(request.path).split('/')
            if path[-2] == 'change':
                filter = Order.objects.get(pk=int(path[-3])).can_cook()
                kwargs["queryset"] = Restaurant.objects.filter(id__in=filter)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
