from django.db import models

# Create your models here.
from django.db import models
from django.urls import reverse
from django.core.exceptions import ValidationError


# Категория товаров
class Category(models.Model):
	name = models.CharField(max_length=100, unique=True)
	slug = models.SlugField(max_length=100, unique=True)

	class Meta:
		ordering = ['name']
		indexes = [models.Index(fields=['name'])]
		verbose_name = 'category'
		verbose_name_plural = 'categories'

	def get_absolute_url(self):
		return reverse('main:product_list_by_category', args=[self.slug])

	def __str__(self):
		return self.name


# Характеристики, специфичные для категории
class CategorySpecification(models.Model):
	category = models.ForeignKey(
		Category,
		related_name='specifications',
		on_delete=models.CASCADE
	)
	name = models.CharField(max_length=100)  # Например, "Объем памяти"
	data_type = models.CharField(
		max_length=20,
		choices=[
			('text', 'Text'),
			('number', 'Number'),
			('boolean', 'Boolean'),
		],
		default='text'
	)

	class Meta:
		ordering = ['name']
		indexes = [models.Index(fields=['name'])]
		verbose_name = 'category specification'
		verbose_name_plural = 'category specifications'
		constraints = [
			models.UniqueConstraint(
				fields=['category', 'name'],
				name='unique_category_specification'
			)
		]

	def __str__(self):
		return f"{self.name} ({self.category.name})"

	def clean(self):
		# Проверка, чтобы убедиться, что имя характеристики уникально в пределах категории
		if CategorySpecification.objects.filter(
				category=self.category,
				name=self.name
		).exclude(pk=self.pk).exists():
			raise ValidationError(f"Характеристика '{self.name}' уже существует в категории '{self.category.name}'.")


# Товар
class Product(models.Model):
	category = models.ForeignKey(
		Category,
		related_name='products',
		on_delete=models.CASCADE
	)
	name = models.CharField(max_length=100, unique=True)
	slug = models.SlugField(max_length=100, unique=True)
	image = models.ImageField(upload_to='products/%Y/%m/%d/', blank=True)
	description = models.TextField(blank=True)
	price = models.DecimalField(max_digits=10, decimal_places=2)
	available = models.BooleanField(default=True)
	created = models.DateTimeField(auto_now_add=True)
	updated = models.DateTimeField(auto_now=True)
	discount = models.DecimalField(max_digits=4, decimal_places=2, default=0.00)
	brand = models.CharField(max_length=100)
	class Meta:
		ordering = ['name']
		indexes = [
			models.Index(fields=['id', 'slug']),
			models.Index(fields=['name']),
			models.Index(fields=['-created']),
		]
		verbose_name = 'product'
		verbose_name_plural = 'products'

	def __str__(self):
		return self.name

	def get_absolute_url(self):
		return reverse('main:product_detail', args=[self.slug])

	def sell_price(self):
		if self.discount:
			return round(self.price - self.price * (self.discount / 100), 2)
		return self.price

	def clean(self):
		# Проверка, что discount находится в разумных пределах (0-100%)
		if self.discount < 0 or self.discount > 100:
			raise ValidationError("Discount must be between 0 and 100.")


# Значение характеристики для конкретного товара
class ProductSpecification(models.Model):
	product = models.ForeignKey(
		Product,
		related_name='specifications',
		on_delete=models.CASCADE
	)
	specification = models.ForeignKey(
		CategorySpecification,
		on_delete=models.CASCADE
	)
	value = models.CharField(max_length=100)

	class Meta:
		verbose_name = 'product specification'
		verbose_name_plural = 'product specifications'
		constraints = [
			models.UniqueConstraint(
				fields=['product', 'specification'],
				name='unique_product_specification'
			)
		]

	def __str__(self):
		return f"{self.specification.name}: {self.value} ({self.product.name})"

	def clean(self):
		# Проверка соответствия категории товара и характеристики
		if self.specification.category != self.product.category:
			raise ValidationError(
				f"Характеристика '{self.specification.name}' не относится к категории '{self.product.category.name}'."
			)
		# Валидация значения в зависимости от типа данных
		if self.specification.data_type == 'number':
			try:
				float(self.value)
			except ValueError:
				raise ValidationError(f"Значение '{self.value}' должно быть числом.")
		elif self.specification.data_type == 'boolean':
			if self.value.lower() not in ['true', 'false', 'yes', 'no', '1', '0']:
				raise ValidationError(f"Значение '{self.value}' должно быть булевым (true/false, yes/no, 1/0).")


class ProductImage(models.Model):
	product = models.ForeignKey(Product, related_name='images',
	                            on_delete=models.CASCADE)
	image = models.ImageField(upload_to='products/%Y/%m/%d', blank=True)

	def __str__(self):
		return f'{self.product.name} - {self.image.name}'



class Comparison(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='comparisons'
    )
    session_key = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='comparisons'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'comparison'
        verbose_name_plural = 'comparisons'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'product'],
                name='unique_user_product_comparison'
            ),
            models.UniqueConstraint(
                fields=['session_key', 'product'],
                condition=models.Q(user__isnull=True),
                name='unique_session_product_comparison'
            )
        ]

    def __str__(self):
        return f"Comparison: {self.product.name} ({self.user or self.session_key})"