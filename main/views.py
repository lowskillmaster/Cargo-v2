from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.http import QueryDict
from .models import Product, Category, CategorySpecification, ProductSpecification
from django.urls import reverse
from django.db.models import Q, Case, When, DecimalField, Value, F, Count
from django.db.models.functions import Cast, Coalesce
from cart.forms import CartAddProductForm
import logging
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank

logger = logging.getLogger(__name__)

def popular_list(request):
    products = Product.objects.filter(available=True)[:7]
    return render(request, 'index/index.html', {'products': products})

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, available=True)
    cart_product_form = CartAddProductForm
    return render(request, 'product/detail.html', {'product': product, 'cart_product_form': cart_product_form})


def product_list(request, category_slug=None):
    page = request.GET.get('page', 1)
    category = None
    categories = Category.objects.all()
    products = Product.objects.filter(available=True)
    specifications = []
    spec_values = {}
    filter_params = QueryDict('', mutable=True)
    all_products = []

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)
        specifications = CategorySpecification.objects.filter(category=category)
        all_products = products  # Store all products for name filter

        # Collect unique values for each specification
        for spec in specifications:
            values = ProductSpecification.objects.filter(
                product__category=category,
                specification=spec
            ).values_list('value', flat=True).distinct()
            # Sort numerically for RAM/ROM, alphabetically for others
            spec_values[spec.id] = sorted(
                values,
                key=lambda x: float(x) if (spec.name in ['RAM', 'ROM'] and x.replace('.', '', 1).isdigit()) else x
            )
            logger.debug(f"Spec {spec.name} values: {spec_values[spec.id]}")

        # Apply price filter (using sell_price)
        price_min = request.GET.get('price_min')
        price_max = request.GET.get('price_max')
        if price_min or price_max:
            try:
                # Annotate products with sell_price, handling NULL in discount
                products = products.annotate(
                    effective_discount=Cast(Coalesce('discount', Value(0)), DecimalField(max_digits=5, decimal_places=2)),
                    sell_price=Case(
                        When(effective_discount=0, then=Cast('price', DecimalField(max_digits=10, decimal_places=2))),
                        default=Cast('price', DecimalField(max_digits=10, decimal_places=2)) * (1 - F('effective_discount') / 100),
                        output_field=DecimalField(max_digits=10, decimal_places=2)
                    )
                )
                if price_min:
                    price_min = float(price_min)
                    products = products.filter(sell_price__gte=price_min)
                    filter_params['price_min'] = price_min
                    logger.debug(f"Applied price filter: min={price_min}")
                if price_max:
                    price_max = float(price_max)
                    products = products.filter(sell_price__lte=price_max)
                    filter_params['price_max'] = price_max
                    logger.debug(f"Applied price filter: max={price_max}")
                # Log product prices for debugging
                for product in products:
                    logger.debug(f"Product: {product.name}, price: {product.price}, discount: {product.discount}, sell_price: {product.sell_price}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid price input: min={price_min}, max={price_max}, error={str(e)}")

        # Apply product name filter (checkboxes, multiple values)
        product_names = request.GET.getlist('product_name')
        if product_names:
            products = products.filter(name__in=product_names)
            filter_params.setlist('product_name', product_names)
            logger.debug(f"Applied product name filter: names={product_names}")

        # Apply specification filters
        valid_filters = 0
        for spec in specifications:
            param = f'spec_{spec.id}'
            if spec.data_type == 'boolean':
                value = request.GET.get(param)
                if value in ['true', 'false']:
                    subquery = ProductSpecification.objects.filter(
                        specification=spec,
                        value__iexact=value
                    )
                    products = products.filter(id__in=subquery.values_list('product_id', flat=True))
                    filter_params[param] = value
                    valid_filters += 1
                    logger.debug(f"Applied boolean filter: {spec.name} = {value}, matches: {subquery.count()}")
            else:
                # Handle multiple selections for text specifications (including RAM/ROM)
                values = [v for v in request.GET.getlist(param) if v]  # Ignore empty values
                if values:
                    subquery = ProductSpecification.objects.filter(
                        specification=spec,
                        value__in=values
                    )
                    products = products.filter(id__in=subquery.values_list('product_id', flat=True))
                    filter_params.setlist(param, values)
                    valid_filters += 1
                    logger.debug(f"Applied text filter: {spec.name} in {values}, matches: {subquery.count()}")

        logger.debug(f"Total valid filters applied: {valid_filters}")
        logger.debug(f"Filtered products count: {products.count()}")
        logger.debug(f"Filtered product names: {[p.name for p in products]}")

    paginator = Paginator(products, 3)
    try:
        current_page = paginator.page(int(page))
    except:
        current_page = paginator.page(1)

    # Prepare filter parameters for pagination links
    filter_params_str = filter_params.urlencode()

    return render(request, 'product/list.html', {
        'category': category,
        'categories': categories,
        'products': current_page,
        'slug_url': category_slug,
        'specifications': specifications,
        'spec_values': spec_values,
        'filter_params': filter_params_str,
        'all_products': all_products
    })


def search(request):
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    brand = request.GET.get('brand', '')
    page = request.GET.get('page', 1)

    # Базовый набор продуктов
    products = Product.objects.filter(available=True).select_related('category').prefetch_related('images',
                                                                                                  'specifications')

    # Поиск
    if query:
        search_query = SearchQuery(query)
        search_vector = SearchVector('name', weight='A') + \
                        SearchVector('description', weight='B') + \
                        SearchVector('brand', weight='B') + \
                        SearchVector('specifications__value', weight='C')

        products = products.annotate(
            search=search_vector,
            rank=SearchRank(search_vector, search_query)
        ).filter(
            Q(search=search_query) |
            Q(specifications__value__icontains=query)
        ).order_by('-rank')

    # Фильтры
    if category_slug:
        products = products.filter(category__slug=category_slug)

    if min_price:
        try:
            products = products.filter(price__gte=float(min_price))
        except ValueError:
            pass

    if max_price:
        try:
            products = products.filter(price__lte=float(max_price))
        except ValueError:
            pass

    if brand:
        products = products.filter(brand__iexact=brand)

    # Получение всех категорий и брендов для фильтров
    categories = Category.objects.all()
    brands = Product.objects.values('brand').annotate(count=Count('brand')).order_by('brand')

    # Пагинация
    paginator = Paginator(products, 12)  # 12 продуктов на страницу
    page_obj = paginator.get_page(page)

    context = {
        'query': query,
        'products': page_obj,
        'categories': categories,
        'brands': brands,
        'category_slug': category_slug,
        'min_price': min_price,
        'max_price': max_price,
        'brand': brand,
        'page_obj': page_obj,
    }
    return render(request, 'search_results.html', context)