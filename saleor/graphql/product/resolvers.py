from django.db.models import Sum

from ...order import OrderStatus
from ...product import models
from ..channel import ChannelQsContext
from ..utils import get_database_id, get_user_or_app_from_context
from ..utils.filters import filter_by_period
from .filters import (
    filter_attributes_by_product_types,
    filter_products_by_stock_availability,
)


def resolve_attributes(info, qs=None, in_category=None, in_collection=None, **_kwargs):
    qs = qs or models.Attribute.objects.get_visible_to_user(info.context.user)

    if in_category:
        qs = filter_attributes_by_product_types(qs, "in_category", in_category)

    if in_collection:
        qs = filter_attributes_by_product_types(qs, "in_collection", in_collection)

    return qs.distinct()


def resolve_category_by_slug(slug):
    return models.Category.objects.filter(slug=slug).first()


def resolve_categories(info, level=None, **_kwargs):
    qs = models.Category.objects.prefetch_related("children")
    if level is not None:
        qs = qs.filter(level=level)
    return qs.distinct()


def resolve_collection_by_slug(info, slug):
    requestor = get_user_or_app_from_context(info.context)
    return (
        models.Collection.objects.visible_to_user(requestor).filter(slug=slug).first()
    )


def resolve_collections(info, **_kwargs):
    user = info.context.user
    return models.Collection.objects.visible_to_user(user)


def resolve_digital_contents(_info):
    return models.DigitalContent.objects.all()


def resolve_product_by_id(info, id, channel_slug):
    user = info.context.user
    return (
        models.Product.objects.visible_to_user(user, channel_slug=channel_slug)
        .filter(id=id)
        .first()
    )


def resolve_product_by_slug(info, product_slug, channel_slug):
    user = info.context.user
    return (
        models.Product.objects.visible_to_user(user, channel_slug=channel_slug)
        .filter(slug=product_slug)
        .first()
    )


def resolve_products(
    info, stock_availability=None, channel_slug=None, **_kwargs
) -> ChannelQsContext:
    user = get_user_or_app_from_context(info.context)
    qs = models.Product.objects.visible_to_user(user, channel_slug)
    if stock_availability:
        qs = filter_products_by_stock_availability(qs, stock_availability)
    return ChannelQsContext(qs=qs.distinct(), channel_slug=channel_slug)


def resolve_variant_by_id(info, id, channel_slug):
    user = info.context.user
    visible_products = models.Product.objects.visible_to_user(
        user, channel_slug
    ).values_list("pk", flat=True)
    qs = models.ProductVariant.objects.filter(product__id__in=visible_products)
    return qs.filter(pk=id).first()


def resolve_product_types(info, **_kwargs):
    return models.ProductType.objects.all()


def resolve_product_variants(info, ids=None, channel_slug=None) -> ChannelQsContext:
    user = info.context.user
    visible_products = models.Product.objects.visible_to_user(
        user, channel_slug
    ).values_list("pk", flat=True)
    qs = models.ProductVariant.objects.filter(product__id__in=visible_products)
    if ids:
        db_ids = [get_database_id(info, node_id, "ProductVariant") for node_id in ids]
        qs = qs.filter(pk__in=db_ids)
    return ChannelQsContext(qs=qs, channel_slug=channel_slug)


def resolve_report_product_sales(period, channel_slug=None) -> ChannelQsContext:
    qs = models.ProductVariant.objects.all()

    # exclude draft and canceled orders
    exclude_status = [OrderStatus.DRAFT, OrderStatus.CANCELED]
    qs = qs.exclude(order_lines__order__status__in=exclude_status)

    # filter by period
    qs = filter_by_period(qs, period, "order_lines__order__created")

    qs = qs.annotate(quantity_ordered=Sum("order_lines__quantity"))
    qs = qs.filter(quantity_ordered__isnull=False)
    qs = qs.order_by("-quantity_ordered")
    return ChannelQsContext(qs=qs, channel_slug=channel_slug)
