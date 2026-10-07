import json
from datetime import timedelta
from django.db.models import Count, Sum
from django.utils import timezone
from authentication.models import (
    User,
    RingExchangeRequest,
    RefundRequest,
    Support,
    AmbassadorBooking,
)
from chat.models import Message, UserConnection, CreditPurchase


def dashboard_callback(request, context):
    """
    Callback function for Django Unfold dashboard to inject KPI metrics,
    analytics chart data, and recent activity logs into template context.
    """
    try:
        now = timezone.now()

        # Core Metrics
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        
        pending_exchanges = RingExchangeRequest.objects.filter(
            status__in=['pending', 'payment_pending', 'user_shipped']
        ).count()
        
        pending_refunds = RefundRequest.objects.filter(
            status__in=['requested', 'ring_shipped']
        ).count()
        
        completed_purchases = CreditPurchase.objects.filter(status='completed')
        total_revenue_cents = completed_purchases.aggregate(total=Sum('amount_paid'))['total'] or 0
        total_revenue_usd = f"${total_revenue_cents / 100:.2f}"
        
        total_connections = UserConnection.objects.filter(status='connected').count()
        total_messages = Message.objects.count()
        pending_support = Support.objects.count()

        # --- Analytics Datasets for Charts ---

        # 1. User Signups Over Last 7 Days
        last_7_days = [now.date() - timedelta(days=i) for i in range(6, -1, -1)]
        day_labels = [d.strftime('%b %d') for d in last_7_days]
        user_counts = []
        for day in last_7_days:
            user_counts.append(User.objects.filter(date_joined__date=day).count())

        # 2. Ring Exchange Status Distribution
        exchange_keys = ['pending', 'payment_pending', 'approved', 'user_shipped', 'completed', 'cancelled']
        exchange_display_labels = ['Pending', 'Payment Pending', 'Approved', 'User Shipped', 'Completed', 'Cancelled']
        exchange_counts = [RingExchangeRequest.objects.filter(status=k).count() for k in exchange_keys]

        # 3. Refund Status Distribution
        refund_keys = ['requested', 'ring_shipped', 'ring_received', 'refund_processed', 'rejected']
        refund_display_labels = ['Requested', 'User Shipped', 'Ring Received', 'Processed', 'Rejected']
        refund_counts = [RefundRequest.objects.filter(status=k).count() for k in refund_keys]

        # 4. Credit Package Sales Revenue Breakdown
        package_stats = (
            CreditPurchase.objects.filter(status='completed')
            .values('package__name')
            .annotate(total_sales=Count('id'), total_amount=Sum('amount_paid'))
            .order_by('-total_amount')[:5]
        )
        
        package_labels = [item['package__name'] or 'Custom Package' for item in package_stats]
        package_values = [round((item['total_amount'] or 0) / 100, 2) for item in package_stats]
        
        if not package_labels:
            package_labels = ['Basic Pack', 'Pro Pack', 'VIP Bundle']
            package_values = [0, 0, 0]

        recent_exchanges = RingExchangeRequest.objects.select_related('user').order_by('-created_at')[:5]
        recent_refunds = RefundRequest.objects.select_related('user').order_by('-created_at')[:5]
        recent_purchases = CreditPurchase.objects.select_related('user', 'package').order_by('-created_at')[:5]

        context.update({
            'kpi': {
                'total_users': total_users,
                'active_users': active_users,
                'pending_exchanges': pending_exchanges,
                'pending_refunds': pending_refunds,
                'total_revenue': total_revenue_usd,
                'total_connections': total_connections,
                'total_messages': total_messages,
                'pending_support': pending_support,
            },
            'charts': {
                'day_labels': json.dumps(day_labels),
                'user_counts': json.dumps(user_counts),
                'exchange_labels': json.dumps(exchange_display_labels),
                'exchange_counts': json.dumps(exchange_counts),
                'refund_labels': json.dumps(refund_display_labels),
                'refund_counts': json.dumps(refund_counts),
                'package_labels': json.dumps(package_labels),
                'package_values': json.dumps(package_values),
            },
            'recent_exchanges': recent_exchanges,
            'recent_refunds': recent_refunds,
            'recent_purchases': recent_purchases,
        })
    except Exception as e:
        context.update({
            'kpi': {
                'total_users': 0,
                'active_users': 0,
                'pending_exchanges': 0,
                'pending_refunds': 0,
                'total_revenue': '$0.00',
                'total_connections': 0,
                'total_messages': 0,
                'pending_support': 0,
            },
            'charts': {
                'day_labels': json.dumps([]),
                'user_counts': json.dumps([]),
                'exchange_labels': json.dumps([]),
                'exchange_counts': json.dumps([]),
                'refund_labels': json.dumps([]),
                'refund_counts': json.dumps([]),
                'package_labels': json.dumps([]),
                'package_values': json.dumps([]),
            },
            'recent_exchanges': [],
            'recent_refunds': [],
            'recent_purchases': [],
        })
    return context


def dashboard_context_processor(request):
    """
    Context processor to ensure dashboard stats and charts are always available
    when rendering the admin dashboard index page.
    """
    if request.path.rstrip('/') in ['/admin', '/admin/index']:
        context = {}
        return dashboard_callback(request, context)
    return {}
