from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('two_factor.urls')),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('platforms.urls', namespace='platforms')),
]
