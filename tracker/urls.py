from django.urls import path
from . import views
from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy
from tracker.views import RegisterView, custom_logout, check_auth

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('challenge/<int:challenge_id>/', views.challenge_detail, name='challenge_detail'),
    path('challenge/add/', views.add_challenge, name='add_challenge'),
    path('challenge/<int:challenge_id>/trade/add/', views.add_trade, name='add_trade'),
    path('challenge/<int:challenge_id>/withdrawal/', views.request_withdrawal, name='request_withdrawal'),
    path('statistics/', views.trading_statistics, name='trading_statistics'),
    path('check-auth/', check_auth, name='check_auth'),
    path('challenge/<int:challenge_id>/delete/', views.delete_challenge, name='delete_challenge'),
    path('trades/', views.trades_list, name='trades_list'),
    path('profile/', views.user_profile, name='user_profile'),
    path('change-password/', views.change_password, name='password_change'),
    path('register/', RegisterView.as_view(), name='register'),
    path('logout/', custom_logout, name='logout'),
    path('trade/<int:trade_id>/update/', views.update_trade, name='update_trade'),
]