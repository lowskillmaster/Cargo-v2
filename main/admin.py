from django.contrib import admin
from .models import Category, Product, CategorySpecification, ProductSpecification, ProductImage, Review

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

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'rating', 'is_approved', 'created_at', 'updated_at']
    list_filter = ['is_approved', 'rating', 'created_at', 'product__category']
    search_fields = ['product__name', 'user__username', 'comment']
    list_editable = ['is_approved']
    actions = ['approve_reviews', 'disapprove_reviews']
    date_hierarchy = 'created_at'

    def approve_reviews(self, request, queryset):
        queryset.update(is_approved=True)
        self.message_user(request, "Выбранные отзывы одобрены.")
    approve_reviews.short_description = "Одобрить выбранные отзывы"

    def disapprove_reviews(self, request, queryset):
        queryset.update(is_approved=False)
        self.message_user(request, "Выбранные отзывы отклонены.")
    disapprove_reviews.short_description = "Отклонить выбранные отзывы"
