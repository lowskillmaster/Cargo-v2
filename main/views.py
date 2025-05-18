from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.http import QueryDict
from .models import Product, Category, CategorySpecification, ProductSpecification
from django.urls import reverse
from django.db.models import Q, Case, When, DecimalField, Value, F, Count, Subquery
from django.db.models.functions import Cast, Coalesce
from cart.forms import CartAddProductForm
import logging
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.contrib import messages
from .models import Comparison


logger = logging.getLogger(__name__)



def get_comparisons(request):
    user = request.user if request.user.is_authenticated else None
    session_key = get_session_key(request) if not user else None
    comparisons = Comparison.objects.filter(
        user=user if user else None,
        session_key=session_key if not user else None
    ).select_related('product', 'category')
    return comparisons

def get_session_key(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def popular_list(request):
    products = Product.objects.filter(available=True)[:7]
    comparisons = get_comparisons(request)
    return render(request, 'index/index.html', {
        'products': products,
        'comparisons': comparisons
    })


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, available=True)
    cart_product_form = CartAddProductForm
    comparisons = get_comparisons(request)
    return render(request, 'product/detail.html', {
        'product': product,
        'cart_product_form': cart_product_form,
        'comparisons': comparisons
    })


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
        all_products = products

        for spec in specifications:
            values = ProductSpecification.objects.filter(
                product__category=category,
                specification=spec
            ).values_list('value', flat=True).distinct()
            spec_values[spec.id] = sorted(
                values,
                key=lambda x: float(x) if (spec.name in ['RAM', 'ROM'] and x.replace('.', '', 1).isdigit()) else x
            )

        price_min = request.GET.get('price_min')
        price_max = request.GET.get('price_max')
        if price_min or price_max:
            try:
                products = products.annotate(
                    effective_discount=Cast(Coalesce('discount', Value(0)),
                                            DecimalField(max_digits=5, decimal_places=2)),
                    sell_price=Case(
                        When(effective_discount=0, then=Cast('price', DecimalField(max_digits=10, decimal_places=2))),
                        default=Cast('price', DecimalField(max_digits=10, decimal_places=2)) * (
                                    1 - F('effective_discount') / 100),
                        output_field=DecimalField(max_digits=10, decimal_places=2)
                    )
                )
                if price_min:
                    price_min = float(price_min)
                    products = products.filter(sell_price__gte=price_min)
                    filter_params['price_min'] = price_min
                if price_max:
                    price_max = float(price_max)
                    products = products.filter(sell_price__lte=price_max)
                    filter_params['price_max'] = price_max
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid price input: min={price_min}, max={price_max}, error={str(e)}")

        product_names = request.GET.getlist('product_name')
        if product_names:
            products = products.filter(name__in=product_names)
            filter_params.setlist('product_name', product_names)

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
            else:
                values = [v for v in request.GET.getlist(param) if v]
                if values:
                    subquery = ProductSpecification.objects.filter(
                        specification=spec,
                        value__in=values
                    )
                    products = products.filter(id__in=subquery.values_list('product_id', flat=True))
                    filter_params.setlist(param, values)

    paginator = Paginator(products, 3)
    try:
        current_page = paginator.page(int(page))
    except:
        current_page = paginator.page(1)

    filter_params_str = filter_params.urlencode()
    comparisons = get_comparisons(request)

    return render(request, 'product/list.html', {
        'category': category,
        'categories': categories,
        'products': current_page,
        'slug_url': category_slug,
        'specifications': specifications,
        'spec_values': spec_values,
        'filter_params': filter_params_str,
        'all_products': all_products,
        'comparisons': comparisons
    })


def search(request):
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    brand = request.GET.get('brand', '')
    page = request.GET.get('page', 1)

    products = Product.objects.filter(available=True).select_related('category').prefetch_related('images',
                                                                                                  'specifications')

    if query:
        search_query = SearchQuery(query)
        search_vector = SearchVector('name', weight='A') + \
                        SearchVector('description', weight='B') + \
                        SearchVector('brand', weight='B')
        matching_product_ids = ProductSpecification.objects.filter(
            value__icontains=query
        ).values('product_id').distinct()
        products = products.annotate(
            search=search_vector,
            rank=SearchRank(search_vector, search_query)
        ).filter(
            Q(search=search_query) |
            Q(id__in=Subquery(matching_product_ids))
        ).distinct()

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

    categories = Category.objects.all()
    brands = Product.objects.values('brand').annotate(count=Count('brand')).order_by('brand')
    paginator = Paginator(products, 12)
    page_obj = paginator.get_page(page)
    comparisons = get_comparisons(request)

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
        'comparisons': comparisons
    }
    return render(request, 'search_results.html', context)


def add_to_comparison(request, product_id):
    product = get_object_or_404(Product, id=product_id, available=True)
    user = request.user if request.user.is_authenticated else None
    session_key = get_session_key(request) if not user else None

    comparisons = Comparison.objects.filter(category=product.category)
    if user:
        comparisons = comparisons.filter(user=user)
    else:
        comparisons = comparisons.filter(session_key=session_key)

    if comparisons.count() >= 4:
        messages.error(request, "Нельзя добавить больше 4 товаров для сравнения в одной категории.")
        return redirect('main:product_detail', slug=product.slug)

    comparison, created = Comparison.objects.get_or_create(
        user=user,
        session_key=session_key if not user else None,
        product=product,
        category=product.category
    )
    if created:
        messages.success(request, f"Товар {product.name} добавлен в сравнение.")
    else:
        messages.info(request, f"Товар {product.name} уже в сравнении.")

    return redirect('main:product_detail', slug=product.slug)


def remove_from_comparison(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    user = request.user if request.user.is_authenticated else None
    session_key = get_session_key(request) if not user else None

    comparison = Comparison.objects.filter(
        product=product,
        user=user if user else None,
        session_key=session_key if not user else None
    )
    if comparison.exists():
        comparison.delete()
        messages.success(request, f"Товар {product.name} удален из сравнения.")

    return redirect('main:comparison_list')


def comparison_list(request):
    comparisons = get_comparisons(request)

    comparisons_by_category = {}
    for comp in comparisons:
        category = comp.category
        if category not in comparisons_by_category:
            comparisons_by_category[category] = []
        comparisons_by_category[category].append(comp)

    show_differences = request.GET.get('show_differences', 'false') == 'true'
    differences = {}
    for category, comps in comparisons_by_category.items():
        if len(comps) < 2:
            continue
        specs = CategorySpecification.objects.filter(category=category)
        differences[category] = []
        for spec in specs:
            values = []
            for comp in comps:
                spec_value = comp.product.specifications.filter(specification=spec).first()
                values.append(spec_value.value if spec_value else '-')
            if show_differences and len(set(values)) == 1:
                continue
            differences[category].append({
                'spec': spec,
                'values': values
            })

    return render(request, 'comparison/list.html', {
        'comparisons': comparisons,  # Добавляем comparisons для base.html
        'comparisons_by_category': comparisons_by_category,
        'differences': differences,
        'show_differences': show_differences
    })