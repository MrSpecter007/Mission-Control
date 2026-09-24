from django.urls import path
from . import views, inventory_views
from .feeds import MilestoneFeed

app_name = 'platforms'

urlpatterns = [
    path('repositories/', inventory_views.repository_list, name='repository_list'),
    path('services/', inventory_views.service_list, name='service_list'),
    path('deployments/', inventory_views.deployment_list, name='deployment_list'),
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Platform list / CRUD
    path('platforms/', views.platform_list, name='platform_list'),
    path('platforms/<slug:slug>/', views.platform_detail, name='platform_detail'),
    path('platforms/<slug:slug>/edit/', views.platform_edit, name='platform_edit'),
    path('platforms/<slug:slug>/archive/', views.platform_archive, name='platform_archive'),
    path('platforms/<slug:slug>/health-check/', views.run_platform_health_check, name='run_health_check'),

    # Wizard
    path('wizard/start/', views.wizard_start, name='wizard_start'),
    path('wizard/<int:step>/', views.wizard_step, name='wizard_step'),
    path('wizard/complete/', views.wizard_complete, name='wizard_complete'),

    # Repository
    path('platforms/<slug:slug>/repositories/add/', views.repository_add, name='repository_add'),
    path('platforms/<slug:slug>/repositories/<int:pk>/edit/', views.repository_edit, name='repository_edit'),

    # Hosts
    path('hosts/', views.host_list, name='host_list'),
    path('hosts/create/', views.host_create, name='host_create'),
    path('hosts/<int:pk>/edit/', views.host_edit, name='host_edit'),

    # Services
    path('platforms/<slug:slug>/services/add/', views.service_add, name='service_add'),
    path('platforms/<slug:slug>/services/<int:pk>/edit/', views.service_edit, name='service_edit'),
    path('platforms/<slug:slug>/services/<int:pk>/delete/', views.service_delete, name='service_delete'),

    # Domains
    path('platforms/<slug:slug>/domains/add/', views.domain_add, name='domain_add'),
    path('platforms/<slug:slug>/domains/<int:pk>/edit/', views.domain_edit, name='domain_edit'),
    path('platforms/<slug:slug>/domains/<int:pk>/delete/', views.domain_delete, name='domain_delete'),

    # Deployments
    path('platforms/<slug:slug>/deployments/add/', views.deployment_add, name='deployment_add'),
    path('platforms/<slug:slug>/deployments/<int:pk>/delete/', views.deployment_delete, name='deployment_delete'),

    # Repositories
    path('platforms/<slug:slug>/repositories/<int:pk>/delete/', views.repository_delete, name='repository_delete'),

    # Updates feed
    path('updates/', views.updates_list, name='updates_list'),

    # Clients
    path('clients/', views.client_list, name='client_list'),
    path('clients/add/', views.client_add, name='client_add'),
    path('clients/<slug:slug>/', views.client_detail, name='client_detail'),
    path('clients/<slug:slug>/edit/', views.client_edit, name='client_edit'),

    # Monitored URLs
    path('platforms/<slug:slug>/monitored-urls/add/', views.monitored_url_add, name='monitored_url_add'),
    path('platforms/<slug:slug>/monitored-urls/<int:pk>/delete/', views.monitored_url_delete, name='monitored_url_delete'),

    # Credentials
    path('platforms/<slug:slug>/credentials/add/', views.credential_add, name='credential_add'),
    path('platforms/<slug:slug>/credentials/<int:pk>/edit/', views.credential_edit, name='credential_edit'),
    path('platforms/<slug:slug>/credentials/<int:pk>/delete/', views.credential_delete, name='credential_delete'),
    path('platforms/<slug:slug>/credentials/<int:pk>/reveal/', views.credential_reveal, name='credential_reveal'),

    # Activity Log
    path('activity/', views.activity_log, name='activity_log'),
    path('activity/milestones.atom', MilestoneFeed(), name='activity_milestone_feed'),
    path('activity/add/', views.activity_add, name='activity_add'),
    path('activity/<int:pk>/edit/', views.activity_edit, name='activity_edit'),
    path('activity/<int:pk>/delete/', views.activity_delete, name='activity_delete'),
    path('platforms/<slug:slug>/activity/add/', views.platform_activity_add, name='platform_activity_add'),

    # Run Updates CTA
    path('updates/run/', views.run_updates, name='run_updates'),
    path('platforms/<slug:slug>/updates/run/', views.run_updates, name='run_platform_updates'),

    # Dependencies
    path('dependencies/', views.dependencies_list, name='dependencies_list'),
]
