from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from two_factor.urls import urlpatterns as tf_urls

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include((tf_urls, 'two_factor'))),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('platforms.urls', namespace='platforms')),
]
