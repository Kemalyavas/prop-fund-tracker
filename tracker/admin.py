from django.contrib import admin
from .models import FundingProvider, ChallengeType, UserChallenge, Trade, WithdrawalRequest

class FundingProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'website')
    search_fields = ('name',)

class ChallengeTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider', 'account_size', 'price', 'profit_target', 'duration_days')
    list_filter = ('provider',)
    search_fields = ('name', 'provider__name')

class UserChallengeAdmin(admin.ModelAdmin):
    list_display = ('user', 'challenge_type', 'status', 'start_date', 'current_balance')
    list_filter = ('status', 'challenge_type__provider')
    search_fields = ('user__username', 'challenge_type__name')

class TradeAdmin(admin.ModelAdmin):
    list_display = ('user', 'challenge', 'symbol', 'trade_type', 'entry_date', 'profit_loss')
    list_filter = ('trade_type', 'symbol')
    search_fields = ('user__username', 'symbol')

class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'challenge', 'amount', 'status', 'request_date')
    list_filter = ('status',)
    search_fields = ('user__username',)

admin.site.register(FundingProvider, FundingProviderAdmin)
admin.site.register(ChallengeType, ChallengeTypeAdmin)
admin.site.register(UserChallenge, UserChallengeAdmin)
admin.site.register(Trade, TradeAdmin)
admin.site.register(WithdrawalRequest, WithdrawalRequestAdmin)