from django.core.files import File
from main.models import Category, Product, CategorySpecification, ProductSpecification, ProductImage
from main.management.utils.helpers import extract_brand_and_name, generate_slug, parse_specification, \
	generate_description, generate_folder_name
import os
import logging
from django.conf import settings
import shutil

logger = logging.getLogger(__name__)


def add_products_from_parsed_data(products_data, category_name):
	category, _ = Category.objects.get_or_create(name=category_name, slug=generate_slug(category_name))

	for product_data in products_data:
		try:
			full_name = product_data[0]
			brand, name = extract_brand_and_name(full_name)
			slug = generate_slug(name)
			specs = product_data[1:-1]  # Исключаем имя и данные маркетплейсов
			marketplace_data = product_data[-1]  # Последний элемент — данные маркетплейсов
			parsed_specs = [parse_specification(spec)[0] for spec in specs]
			description = generate_description(parsed_specs)

			# Вычисляем минимальную цену
			prices = [data['цена'] for data in marketplace_data.values() if 'цена' in data]
			if not prices:
				logger.warning(f'Не найдены цены для {full_name}')
				price = 0.00
			else:
				price = min(prices)

			product, created = Product.objects.get_or_create(
				category=category,
				name=name,
				slug=slug,
				defaults={
					'brand': brand,
					'price': price,
					'description': description,
					'available': True,
					'marketplace_data': marketplace_data
				}
			)

			if not created:
				product.price = price
				product.description = description
				product.marketplace_data = marketplace_data
				product.save()

			for spec in specs:
				for spec_name, spec_value, data_type in parse_specification(spec):
					category_spec, _ = CategorySpecification.objects.get_or_create(
						category=category,
						name=spec_name,
						defaults={'data_type': data_type}
					)
					ProductSpecification.objects.get_or_create(
						product=product,
						specification=category_spec,
						value=spec_value
					)

			# Добавляем изображения
			folder_name = generate_folder_name(full_name)
			logger.debug(f'Сгенерировано имя папки для {full_name}: {folder_name}')
			source_folder = os.path.join(settings.PARSED_IMAGES_ROOT, folder_name)
			dest_folder = os.path.join(settings.MEDIA_ROOT, 'products', folder_name)
			os.makedirs(dest_folder, exist_ok=True)

			for i in range(1, 7):
				source_img = os.path.join(source_folder, f'{folder_name}_{i}.jpg')
				dest_img = os.path.join(dest_folder, f'image{i}.jpg')
				if os.path.exists(source_img):
					shutil.copy2(source_img, dest_img)
					with open(dest_img, 'rb') as f:
						image_obj, img_created = ProductImage.objects.get_or_create(
							product=product,
							image=File(f, name=f'image{i}.jpg')
						)
						# Устанавливаем основное изображение, если оно не задано
						if img_created and i == 1 and not product.image:
							product.image = File(f, name=f'image{i}.jpg')
							product.save()
				else:
					logger.debug(f'Изображение не найдено: {source_img}')
		except Exception as e:
			logger.error(f'Ошибка при обработке товара {full_name}: {e}')