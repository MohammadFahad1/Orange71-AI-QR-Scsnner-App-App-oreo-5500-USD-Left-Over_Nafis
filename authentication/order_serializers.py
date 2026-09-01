from rest_framework import serializers


class ItemDetailsSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    size = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    sku = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    slug = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    permalink = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    price = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    regular_price = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    sale_price = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    stock_status = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    image = serializers.CharField(allow_blank=True, allow_null=True, required=False)


class LineItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    product_id = serializers.IntegerField(allow_null=True)
    quantity = serializers.IntegerField()
    total = serializers.CharField()
    size = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    item_details = ItemDetailsSerializer(allow_null=True)


class OrderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
    total = serializers.CharField()
    currency = serializers.CharField()
    date_created = serializers.DateTimeField()
    sizes = serializers.ListField(child=serializers.CharField(), required=False)
    line_items = LineItemSerializer(many=True)


class SimpleItemSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False, allow_null=True)
    product_id = serializers.IntegerField(required=False, allow_null=True)
    name = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    size = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    price = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    total = serializers.CharField(allow_blank=True, allow_null=True, required=False)


class SimpleOrderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    date_created = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    total = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    currency = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    membersip_type = serializers.CharField()
    member_since = serializers.DateTimeField()
    items = SimpleItemSerializer(many=True)

