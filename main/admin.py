from django.contrib import admin
from .models import Category, Product, CategorySpecification, ProductSpecification, ProductImage

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']
    list_filter = ['name']

@admin.register(CategorySpecification)
class CategorySpecificationAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'data_type']
    list_filter = ['category', 'data_type']
    search_fields = ['name', 'category__name']
    list_select_related = ['category']  # Оптимизация запросов

class ProductSpecificationInline(admin.TabularInline):
    model = ProductSpecification
    extra = 1  # Количество пустых форм для добавления характеристик
    min_num = 0  # Минимальное количество характеристик
    can_delete = True  # Разрешить удаление характеристик

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 5

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'sell_price', 'available', 'created']
    list_filter = ['category', 'available', 'created']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductSpecificationInline, ProductImageInline]
    list_select_related = ['category']  # Оптимизация запросов
    list_editable = ['available']  # Позволяет редактировать поле available прямо в списке
    date_hierarchy = 'created'


@admin.register(ProductSpecification)
class ProductSpecificationAdmin(admin.ModelAdmin):
    list_display = ['product', 'specification', 'value']
    list_filter = ['specification__category', 'specification']
    search_fields = ['product__name', 'specification__name', 'value']
    list_select_related = ['product', 'specification', 'specification__category']

