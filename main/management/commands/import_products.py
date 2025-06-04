import os
import json
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from main.management.parser.product_importer import add_products_from_parsed_data
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
	help = 'Импортирует товары из HTML и JSON файлов в базу данных'

	def add_arguments(self, parser):
		parser.add_argument('--category', type=str, required=True, help='Название категории (например, Телефоны)')
		parser.add_argument('--html_file', type=str, required=True, help='Путь к HTML файлу с данными товаров')

	def handle(self, *args, **kwargs):
		category_name = kwargs['category']
		html_file = kwargs['html_file']

		if not os.path.exists(html_file):
			logger.error(f'HTML file {html_file} does not exist')
			self.stdout.write(self.style.ERROR(f'HTML file {html_file} does not exist'))
			return

		try:
			with open(html_file, 'r', encoding='utf-8') as f:
				soup = BeautifulSoup(f, 'html.parser')

			products_data = []
			product_blocks = soup.find_all("div", {
				"class": "e59n8xw0 app-catalog-4zpz15-StyledGridItem--StyledGridItem-GridItem--WrappedGridItem e1uawgvp0"})

			for block in product_blocks:
				name = block.find("div", class_="app-catalog-18v0w1v-StyledName").find('a').get_text(strip=True)
				specs_div = block.find("div", class_="app-catalog-5db2k7-StyledDescriptionWrapper ep3n5630")
				specs = specs_div.find_all("li",
				                           class_="app-catalog-5kkfdq-components--PropertiesItem ekqg32y1")

				specs = [spec.text.replace('\xa0', ' ') for spec in specs]

				product_data = [name] + specs
				products_data.append(product_data)

			json_files = {
				'citilink': 'main/management/data/citilink_price_rating.json',
				'eldorado': 'main/management/data/eldorado_price_rating.json',
				'yandex': 'main/management/data/yandex_price_rating.json'
			}

			for product_data in products_data:
				full_name = product_data[0]
				product_data.append({})  # Добавляем пустой словарь для marketplace_data

				for marketplace, json_file in json_files.items():
					if os.path.exists(json_file):
						with open(json_file, 'r', encoding='utf-8') as f:
							marketplace_data = json.load(f)
							# Проверяем, есть ли товар в JSON по полному имени
							if full_name in marketplace_data:
								product_data[-1][marketplace] = {
									'price': marketplace_data[full_name]['цена'],
									'rating': marketplace_data[full_name]['рейтинг'],
									'url': marketplace_data[full_name]['url']
								}
							else:
								logger.warning(f'Товар "{full_name}" не найден в {json_file}')
					else:
						logger.warning(f'JSON file {json_file} not found')

			add_products_from_parsed_data(products_data, category_name)
			self.stdout.write(self.style.SUCCESS(f'Successfully imported products for category {category_name}'))

		except Exception as e:
			logger.error(f'Error importing products: {e}')
			self.stdout.write(self.style.ERROR(f'Error importing products: {e}'))