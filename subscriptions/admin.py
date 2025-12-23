from django.contrib import admin
from .models import Subscribers, SubscriptionPlans

class SubscriptionPlansAdmin(admin.ModelAdmin):
    list_display = ('plan_name', 'price')
    search_fields = ('plan_name',)
admin.site.register(SubscriptionPlans, SubscriptionPlansAdmin)

class SubscribersAdmin(admin.ModelAdmin):
    list_display = ('trader', 'plan', 'ecocash_number', 'subscribed_on', 'active', 'expiry_date')
    search_fields = ('trader__username', 'ecocash_number')
    list_filter = ('active', 'plan__plan_name')
admin.site.register(Subscribers, SubscribersAdmin)