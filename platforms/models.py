from django.db import models
from django.utils.text import slugify
from django.urls import reverse
from django.contrib.auth import get_user_model


class PlatformType(models.TextChoices):
    WEBSITE = 'website', 'Website'
    WEB_APPLICATION = 'web_application', 'Web Application'
    ECOMMERCE = 'ecommerce', 'E-Commerce'
    API = 'api', 'API'
    INTERNAL_APPLICATION = 'internal_application', 'Internal Application'
    OTHER = 'other', 'Other'


class FrameworkChoice(models.TextChoices):
    DJANGO = 'django', 'Django'
    WAGTAIL = 'wagtail', 'Wagtail'
    WORDPRESS = 'wordpress', 'WordPress'
    LARAVEL = 'laravel', 'Laravel'
    OSCAR = 'oscar', 'Oscar'
    CUSTOM = 'custom', 'Custom'
    OTHER = 'other', 'Other'


class LifecycleStatus(models.TextChoices):
    IDEA = 'idea', 'Idea'
    DEVELOPMENT = 'development', 'Development'
    STAGING = 'staging', 'Staging'
    ACTIVE = 'active', 'Active'
    MAINTENANCE = 'maintenance', 'Maintenance'
    PAUSED = 'paused', 'Paused'
    ARCHIVED = 'archived', 'Archived'


class EnvironmentChoice(models.TextChoices):
    DEVELOPMENT = 'development', 'Development'
    STAGING = 'staging', 'Staging'
    PRODUCTION = 'production', 'Production'


class HostProvider(models.TextChoices):
    DIGITALOCEAN = 'digitalocean', 'DigitalOcean'
    AWS = 'aws', 'AWS'
    GCP = 'gcp', 'Google Cloud'
    AZURE = 'azure', 'Azure'
    LINODE = 'linode', 'Linode / Akamai'
    HETZNER = 'hetzner', 'Hetzner'
    CUSTOM = 'custom', 'Custom / Self-hosted'
    OTHER = 'other', 'Other'


class HostType(models.TextChoices):
    VPS = 'vps', 'VPS'
    DEDICATED = 'dedicated', 'Dedicated Server'
    CONTAINER = 'container', 'Container / PaaS'
    SHARED = 'shared', 'Shared Hosting'
    OTHER = 'other', 'Other'


class RepoProvider(models.TextChoices):
    GITHUB = 'github', 'GitHub'
    GITLAB = 'gitlab', 'GitLab'
    BITBUCKET = 'bitbucket', 'Bitbucket'
    OTHER = 'other', 'Other'


class ServiceType(models.TextChoices):
    WEB = 'web', 'Web Application'
    API = 'api', 'API'
    WORKER = 'worker', 'Background Worker'
    DATABASE = 'database', 'Database'
    CACHE = 'cache', 'Cache'
    QUEUE = 'queue', 'Queue'
    OTHER = 'other', 'Other'


class DeploymentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    DEPLOYING = 'deploying', 'Deploying'
    SUCCESS = 'success', 'Success'
    FAILED = 'failed', 'Failed'
    ROLLED_BACK = 'rolled_back', 'Rolled Back'


class HealthStatus(models.TextChoices):
    HEALTHY = 'healthy', 'Healthy'
    DEGRADED = 'degraded', 'Degraded'
    DOWN = 'down', 'Down'
    UNKNOWN = 'unknown', 'Unknown'


class ActiveStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'


class OwnershipType(models.TextChoices):
    INTERNAL = 'internal', 'Internal'
    CLIENT = 'client', 'Client'


class Client(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    website = models.URLField(blank=True)
    industry = models.CharField(max_length=100, blank=True)
    contact_name = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('platforms:client_detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Platform(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    platform_type = models.CharField(
        max_length=30,
        choices=PlatformType.choices,
        default=PlatformType.WEBSITE,
    )
    framework = models.CharField(
        max_length=30,
        choices=FrameworkChoice.choices,
        default=FrameworkChoice.OTHER,
    )
    framework_other = models.CharField(max_length=100, blank=True, default='')
    ownership_type = models.CharField(
        max_length=20,
        choices=OwnershipType.choices,
        default=OwnershipType.INTERNAL,
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='platforms',
    )
    lifecycle_status = models.CharField(
        max_length=20,
        choices=LifecycleStatus.choices,
        default=LifecycleStatus.DEVELOPMENT,
    )
    default_environment = models.CharField(
        max_length=20,
        choices=EnvironmentChoice.choices,
        default=EnvironmentChoice.DEVELOPMENT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('platforms:platform_detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def framework_display(self) -> str:
        if self.framework == FrameworkChoice.OTHER and self.framework_other:
            return self.framework_other
        return self.get_framework_display()

    @property
    def primary_domain(self):
        return self.domains.filter(is_primary=True).first()

    @property
    def primary_host(self):
        return self.services.filter(host__isnull=False).first()

    @property
    def latest_deployment(self):
        return self.deployments.order_by('-deployed_at').first()

    @property
    def latest_health_check(self):
        return self.health_checks.order_by('-checked_at').first()

    @property
    def health_status(self):
        check = self.latest_health_check
        if check:
            return check.status
        return HealthStatus.UNKNOWN

    def needs_attention(self):
        issues = []
        if self.lifecycle_status in (LifecycleStatus.ACTIVE, LifecycleStatus.STAGING):
            if not self.repositories.exists():
                issues.append('No repository configured')
            if not self.domains.exists():
                issues.append('No domain configured')
        if not self.services.exists():
            issues.append('No services configured')
        latest = self.latest_health_check
        if latest and latest.status == HealthStatus.DOWN:
            issues.append('Health check failing')
        latest_deploy = self.latest_deployment
        if latest_deploy and latest_deploy.status == DeploymentStatus.FAILED:
            issues.append('Latest deployment failed')
        return issues


class Repository(models.Model):
    platform = models.ForeignKey(
        Platform, on_delete=models.CASCADE, related_name='repositories'
    )
    name = models.CharField(max_length=200)
    provider = models.CharField(
        max_length=20,
        choices=RepoProvider.choices,
        default=RepoProvider.GITHUB,
    )
    url = models.URLField(blank=True)
    default_branch = models.CharField(max_length=100, default='main')
    local_path = models.CharField(max_length=500, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ActiveStatus.choices,
        default=ActiveStatus.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'repositories'

    def __str__(self):
        return self.name


class Host(models.Model):
    name = models.CharField(max_length=200)
    provider = models.CharField(
        max_length=20,
        choices=HostProvider.choices,
        default=HostProvider.OTHER,
    )
    hostname = models.CharField(max_length=253, blank=True)
    environment = models.CharField(
        max_length=20,
        choices=EnvironmentChoice.choices,
        default=EnvironmentChoice.PRODUCTION,
    )
    host_type = models.CharField(
        max_length=20,
        choices=HostType.choices,
        default=HostType.VPS,
    )
    os_info = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('decommissioned', 'Decommissioned'),
        ],
        default='active',
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Service(models.Model):
    platform = models.ForeignKey(
        Platform, on_delete=models.CASCADE, related_name='services'
    )
    host = models.ForeignKey(
        Host, on_delete=models.SET_NULL, null=True, blank=True, related_name='services'
    )
    name = models.CharField(max_length=200)
    service_type = models.CharField(
        max_length=20,
        choices=ServiceType.choices,
        default=ServiceType.WEB,
    )
    runtime_identifier = models.CharField(max_length=200, blank=True)
    port = models.PositiveIntegerField(null=True, blank=True)
    environment = models.CharField(
        max_length=20,
        choices=EnvironmentChoice.choices,
        default=EnvironmentChoice.PRODUCTION,
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('running', 'Running'),
            ('stopped', 'Stopped'),
            ('unknown', 'Unknown'),
        ],
        default='unknown',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.platform.name})'


class Domain(models.Model):
    platform = models.ForeignKey(
        Platform, on_delete=models.CASCADE, related_name='domains'
    )
    hostname = models.CharField(max_length=253)
    environment = models.CharField(
        max_length=20,
        choices=EnvironmentChoice.choices,
        default=EnvironmentChoice.PRODUCTION,
    )
    is_primary = models.BooleanField(default=False)
    ssl_enabled = models.BooleanField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('pending', 'Pending'),
        ],
        default='active',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_primary', 'hostname']

    def __str__(self):
        return self.hostname

    @staticmethod
    def _normalize_hostname(value: str) -> str:
        value = value.lower().strip().rstrip('/')
        for prefix in ('https://', 'http://'):
            if value.startswith(prefix):
                value = value[len(prefix):]
                break
        return value

    def clean(self):
        self.hostname = self._normalize_hostname(self.hostname)

    def save(self, *args, **kwargs):
        self.hostname = self._normalize_hostname(self.hostname)
        super().save(*args, **kwargs)

    @property
    def url(self):
        scheme = 'https' if self.ssl_enabled else 'http'
        return f'{scheme}://{self.hostname}'


class Deployment(models.Model):
    platform = models.ForeignKey(
        Platform, on_delete=models.CASCADE, related_name='deployments'
    )
    service = models.ForeignKey(
        Service, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='deployments'
    )
    environment = models.CharField(
        max_length=20,
        choices=EnvironmentChoice.choices,
        default=EnvironmentChoice.PRODUCTION,
    )
    version = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=20,
        choices=DeploymentStatus.choices,
        default=DeploymentStatus.SUCCESS,
    )
    deployed_at = models.DateTimeField()
    deployed_by = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-deployed_at']

    def __str__(self):
        return f'{self.platform.name} @ {self.version or "unknown"} ({self.deployed_at:%Y-%m-%d})'


class HealthCheck(models.Model):
    platform = models.ForeignKey(
        Platform, on_delete=models.CASCADE, related_name='health_checks'
    )
    service = models.ForeignKey(
        Service, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='health_checks'
    )
    endpoint = models.URLField()
    status = models.CharField(
        max_length=20,
        choices=HealthStatus.choices,
        default=HealthStatus.UNKNOWN,
    )
    http_status = models.PositiveIntegerField(null=True, blank=True)
    response_time_ms = models.FloatField(null=True, blank=True)
    checked_at = models.DateTimeField()
    error_info = models.TextField(blank=True)
    url_results = models.JSONField(default=list, blank=True)
    homepage_preview = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-checked_at']

    def __str__(self):
        return f'{self.platform.name} — {self.status} at {self.checked_at:%Y-%m-%d %H:%M}'


# ---------------------------------------------------------------------------
class MonitoredURL(models.Model):
    platform = models.ForeignKey(Platform, on_delete=models.CASCADE, related_name='monitored_urls')
    path = models.CharField(max_length=500, help_text='Path from domain root, e.g. /admin/ or /shop/')
    label = models.CharField(max_length=100)
    is_critical = models.BooleanField(default=False, help_text='If down, marks the platform as DOWN')
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'label']
        unique_together = [['platform', 'path']]

    def __str__(self):
        return f'{self.platform.name}: {self.label} ({self.path})'


# Credentials
# ---------------------------------------------------------------------------

class CredentialKind(models.TextChoices):
    ADMIN_PANEL = 'admin_panel', 'Admin panel'
    HOSTING = 'hosting', 'Hosting panel'
    SSH = 'ssh', 'SSH / Server'
    FTP = 'ftp', 'FTP / SFTP'
    DATABASE = 'database', 'Database'
    API = 'api', 'API key'
    OTHER = 'other', 'Other'


class PlatformCredential(models.Model):
    platform = models.ForeignKey(Platform, on_delete=models.CASCADE, related_name='credentials')
    label = models.CharField(max_length=200)
    kind = models.CharField(max_length=20, choices=CredentialKind.choices, default=CredentialKind.ADMIN_PANEL)
    url = models.URLField(blank=True)
    username = models.CharField(max_length=200, blank=True)
    password_encrypted = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['kind', 'label']

    def __str__(self):
        return f'{self.platform.name} — {self.label}'

    def set_password(self, plaintext: str):
        from .crypto import encrypt
        self.password_encrypted = encrypt(plaintext)

    def get_password(self) -> str:
        from .crypto import decrypt
        return decrypt(self.password_encrypted)


# Activity Log
# ---------------------------------------------------------------------------

class ActivityType(models.TextChoices):
    DEVELOPMENT = 'development', 'Development'
    DEPLOYMENT = 'deployment', 'Deployment'
    INFRASTRUCTURE = 'infrastructure', 'Infrastructure'
    CONFIGURATION = 'configuration', 'Configuration'
    MAINTENANCE = 'maintenance', 'Maintenance'
    CONTENT = 'content', 'Content'
    OPERATIONS = 'operations', 'Operations'
    DECISION = 'decision', 'Decision'
    INCIDENT = 'incident', 'Incident'
    MILESTONE = 'milestone', 'Milestone'
    OTHER = 'other', 'Other'


class ActivityEntry(models.Model):
    platform = models.ForeignKey(
        'Platform', on_delete=models.CASCADE,
        related_name='activity_entries',
        null=True, blank=True,
    )
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    activity_type = models.CharField(
        max_length=20,
        choices=ActivityType.choices,
        default=ActivityType.OTHER,
    )
    occurred_at = models.DateTimeField()
    is_milestone = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        get_user_model(), on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='activity_entries',
    )
    ref_url = models.URLField(blank=True, help_text='Commit, PR, or external reference URL')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-occurred_at']
        verbose_name = 'activity entry'
        verbose_name_plural = 'activity entries'

    def __str__(self):
        return self.title


# News & Updates
# ---------------------------------------------------------------------------

class NewsItemSourceType(models.TextChoices):
    GITHUB_COMMIT = 'github_commit', 'GitHub Commits'
    GITHUB_RELEASE = 'github_release', 'GitHub Release'
    FRAMEWORK_RELEASE = 'framework_release', 'Framework Release'
    HEALTH_EVENT = 'health_event', 'Health Event'
    DEPLOYMENT_LAG = 'deployment_lag', 'Deployment Lag'
    DEPENDENCY_OUTDATED = 'dependency_outdated', 'Dependency Outdated'


class NewsItem(models.Model):
    platform = models.ForeignKey(
        Platform, on_delete=models.CASCADE,
        null=True, blank=True, related_name='news_items',
    )
    source_type = models.CharField(max_length=30, choices=NewsItemSourceType.choices)
    title = models.CharField(max_length=500)
    body = models.TextField(blank=True)
    url = models.URLField(blank=True)
    published_at = models.DateTimeField()
    fetched_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    source_ref = models.CharField(max_length=200, blank=True)
    framework = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ['-published_at']

    def __str__(self):
        return self.title

    SOURCE_ICONS = {
        'github_commit': '⌘',
        'github_release': '↑',
        'framework_release': '★',
        'health_event': '◎',
        'deployment_lag': '⚑',
        'dependency_outdated': '↺',
    }

    @property
    def source_icon(self):
        return self.SOURCE_ICONS.get(self.source_type, '•')


class FrameworkVersion(models.Model):
    framework = models.CharField(max_length=30, unique=True)
    latest_version = models.CharField(max_length=50, blank=True)
    release_url = models.URLField(blank=True)
    checked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.framework} {self.latest_version}'


class RepositoryState(models.Model):
    repository = models.OneToOneField(
        Repository, on_delete=models.CASCADE, related_name='state',
    )
    last_checked_sha = models.CharField(max_length=40, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_deployed_sha = models.CharField(max_length=40, blank=True)

    def __str__(self):
        return f'State for {self.repository.name}'


class DependencySnapshot(models.Model):
    repository = models.ForeignKey(
        Repository, on_delete=models.CASCADE, related_name='dependency_snapshots',
    )
    manifest_path = models.CharField(max_length=200)
    manifest_sha = models.CharField(max_length=40, blank=True)
    ecosystem = models.CharField(max_length=20, blank=True)
    dependencies = models.JSONField(default=list)
    scanned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [['repository', 'manifest_path']]

    def __str__(self):
        return f'{self.repository.name}/{self.manifest_path}'
