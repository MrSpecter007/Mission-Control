from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
import two_factor.urls as _tf_urls

# django-two-factor-auth uses old patterns() format: ['app_name', [patterns]]
# Django 6 rejects strings in urlpatterns — extract just the URL list
_raw = list(_tf_urls.urlpatterns)
_tf_url_list = _raw[1] if _raw and isinstance(_raw[0], str) else _raw

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include((_tf_url_list, 'two_factor'))),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('platforms.urls', namespace='platforms')),
]
