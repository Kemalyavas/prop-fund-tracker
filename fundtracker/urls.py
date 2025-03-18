from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),  # admin URL'si burada doğru
    path('', include('tracker.urls')),  # uygulama URL'lerini dahil et
    # Django authentication için url'ler (opsiyonel)
    path('accounts/', include('django.contrib.auth.urls')),
]