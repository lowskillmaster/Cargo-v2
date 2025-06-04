from django.utils.text import slugify
import re
import os
import logging

logger = logging.getLogger(__name__)

def extract_brand_and_name(product_name):
    """
    Извлекает бренд и название из строки.
    Возвращает кортеж: (brand, name)
    """
    brands = ['TECNO', 'Samsung', 'Apple', 'Xiaomi', 'Huawei', 'Oppo', 'Realme']
    for brand in brands:
        if product_name.lower().startswith(brand.lower()):
            return brand, product_name[len(brand):].strip()
    return 'Unknown', product_name

def generate_slug(name):
    """
    Генерирует slug из названия, используя только латиницу.
    """
    cyrillic_to_latin = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh',
        'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
        'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
        'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ы': 'y', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    name_latin = ''.join(cyrillic_to_latin.get(c, c) for c in name.lower())
    name_latin = re.sub(r'[^a-z0-9\s]', '', name_latin)
    return slugify(name_latin, allow_unicode=False)

def generate_folder_name(product_name):
    """
    Генерирует имя папки на основе полного названия товара, включая бренд и 'Смартфон'.
    """
    return generate_slug(product_name)

def parse_specification(spec_string):
    """
    Разбирает строку характеристики на список характеристик (name, value, data_type).
    Возвращает список кортежей: [(name, value, data_type), ...]
    """
    specs = []
    logger.debug(f'Parsing specification: {spec_string}')

    if 'память' in spec_string.lower():
        if 'оперативная' in spec_string.lower() and 'встроенная' in spec_string.lower():
            parts = spec_string.split(', ', 1)
            if len(parts) == 2:
                ram_part = parts[0].strip()
                storage_part = parts[1].strip()
                if ram_part.startswith('Память оперативная'):
                    ram_value = ram_part[len('Память оперативная '):].strip()
                    ram_data_type = 'number' if re.match(r'^\d+\s*ГБ$', ram_value) else 'text'
                    specs.append(('Память оперативная', ram_value, ram_data_type))
                if storage_part.startswith('встроенная'):
                    storage_value = storage_part[len('встроенная'):].strip()
                    storage_data_type = 'number' if re.match(r'^\d+\s*ГБ$', storage_value) else 'text'
                    specs.append(('Память встроенная', storage_value, storage_data_type))
        elif 'встроенная' in spec_string.lower():
            if spec_string.startswith('Память встроенная'):
                storage_value = spec_string[len('Память встроенная '):].strip()
                storage_data_type = 'number' if re.match(r'^\d+\s*ГБ$', storage_value) else 'text'
                specs.append(('Память встроенная', storage_value, storage_data_type))
        return specs

    name_patterns = [
        (r'^Экран\b|Screen\b', 'Экран'),
        (r'^Процессор\b|Processor\b', 'Модель процессора'),
        (r'^Аккумулятор\b', 'Аккумулятор'),
        (r'^Поддержка сетей\b', 'Поддержка сетей'),
        (r'^Сканер отпечатка пальцев\b', 'Сканер отпечатка пальцев'),
        (r'^Размеры \(ШхВхТ\)\b', 'Размеры (ШхВхТ)')
    ]
    for pattern, name in name_patterns:
        if re.match(pattern, spec_string, re.IGNORECASE):
            match = re.match(pattern, spec_string, re.IGNORECASE)
            value_start = match.end() + 1
            value = spec_string[value_start:].strip()
            data_type = 'text'
            if re.match(r'^\d+(\.\d+)?$', value) or re.match(r'^\d+\s*(ГБ|мAч|мм|")$', value):
                data_type = 'number'
            elif value.lower() in ['true', 'false', 'yes', 'no', '1', '0', 'есть', 'нет']:
                data_type = 'boolean'
                value = 'true' if value.lower() in ['true', 'yes', '1', 'есть'] else 'false'
            specs.append((name, value, data_type))
            break
    else:
        logger.warning(f'Unrecognized specification format: {spec_string}')
        parts = spec_string.split(',', 1) if ',' in spec_string else spec_string.split(':', 1)
        if len(parts) == 1:
            parts = spec_string.split(' ', 1)
        name = parts[0].strip()
        value = parts[1].strip() if len(parts) > 1 else ''
        data_type = 'text'
        if re.match(r'^\d+(\.\d+)?$', value) or re.match(r'^\d+\s*(ГБ|мAч|мм|")$', value):
            data_type = 'number'
        elif value.lower() in ['true', 'false', 'yes', 'no', '1', '0', 'есть', 'нет']:
            data_type = 'boolean'
            value = 'true' if value.lower() in ['true', 'yes', '1', 'есть'] else 'false'
        specs.append((name, value, data_type))

    return specs

def generate_description(specs):
    """
    Генерирует описание товара на основе списка кортежей (name, value, data_type).
    """
    description_parts = []
    for name, value, _ in specs:
        if name == 'Экран':
            description_parts.append(f"Экран: {value}")
        elif name == 'Модель процессора':
            description_parts.append(f"Процессор: {value}")
        elif name == 'Память оперативная':
            description_parts.append(f"Оперативная память: {value}")
        elif name == 'Память встроенная':
            description_parts.append(f"Встроенная память: {value}")
        elif name == 'Аккумулятор':
            description_parts.append(f"Аккумулятор: {value}")
        elif name == 'Поддержка сетей':
            description_parts.append(f"Сети: {value}")
        elif name == 'Сканер отпечатка пальцев':
            description_parts.append(f"Сканер отпечатка пальцев: {value}")
        elif name == 'Размеры (ШхВхТ)':
            description_parts.append(f"Размеры: {value}")
    return '. '.join(description_parts) + '.' if description_parts else 'Описание отсутствует.'