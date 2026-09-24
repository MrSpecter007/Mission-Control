from django.contrib import admin
from .models import (
    Platform, Repository, Host, Service, Domain, Deployment, HealthCheck,
    NewsItem, FrameworkVersion, RepositoryState, DependencySnapshot, Client,
    ActivityEntry,
)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'industry', 'contact_name', 'contact_email', 'created_at']
    search_fields = ['name', 'contact_name', 'contact_email']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Platform)
class PlatformAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'ownership_type', 'client', 'platform_type', 'framework', 'lifecycle_status', 'created_at']
    list_filter = ['lifecycle_status', 'framework', 'platform_type', 'ownership_type']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    raw_id_fields = ['client']


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'platform', 'provider', 'url', 'default_branch']
    list_filter = ['provider', 'status']
    raw_id_fields = ['platform']


@admin.register(Host)
class HostAdmin(admin.ModelAdmin):
    list_display = ['name', 'provider', 'hostname', 'environment', 'host_type', 'status']
    list_filter = ['provider', 'environment', 'status']


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'platform', 'service_type', 'host', 'environment', 'status']
    list_filter = ['service_type', 'environment', 'status']
    raw_id_fields = ['platform', 'host']


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ['hostname', 'platform', 'environment', 'is_primary', 'ssl_enabled', 'status']
    list_filter = ['environment', 'is_primary', 'status']
    raw_id_fields = ['platform']


@admin.register(Deployment)
class DeploymentAdmin(admin.ModelAdmin):
    list_display = ['platform', 'version', 'environment', 'status', 'deployed_at']
    list_filter = ['status', 'environment']
    raw_id_fields = ['platform', 'service']


@admin.register(HealthCheck)
class HealthCheckAdmin(admin.ModelAdmin):
    list_display = ['platform', 'status', 'http_status', 'response_time_ms', 'checked_at']
    list_filter = ['status']
    raw_id_fields = ['platform', 'service']
    readonly_fields = ['checked_at']


@admin.register(NewsItem)
class NewsItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'source_type', 'platform', 'published_at', 'fetched_at']
    list_filter = ['source_type', 'is_read']
    search_fields = ['title', 'body']
    raw_id_fields = ['platform']
    readonly_fields = ['fetched_at']
    date_hierarchy = 'published_at'


@admin.register(FrameworkVersion)
class FrameworkVersionAdmin(admin.ModelAdmin):
    list_display = ['framework', 'latest_version', 'checked_at']
    readonly_fields = ['checked_at']


@admin.register(RepositoryState)
class RepositoryStateAdmin(admin.ModelAdmin):
    list_display = ['repository', 'last_checked_sha', 'last_deployed_sha', 'last_checked_at']
    raw_id_fields = ['repository']
    readonly_fields = ['last_checked_at']


@admin.register(DependencySnapshot)
class DependencySnapshotAdmin(admin.ModelAdmin):
    list_display = ['repository', 'manifest_path', 'ecosystem', 'scanned_at']
    list_filter = ['ecosystem']
    raw_id_fields = ['repository']
    readonly_fields = ['scanned_at']


@admin.register(ActivityEntry)
class ActivityEntryAdmin(admin.ModelAdmin):
    list_display = ['title', 'activity_type', 'platform', 'is_milestone', 'occurred_at', 'created_by']
    list_filter = ['activity_type', 'is_milestone', 'platform']
    search_fields = ['title', 'description']
    raw_id_fields = ['platform', 'created_by']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'occurred_at'
