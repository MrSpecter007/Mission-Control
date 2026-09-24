from django import forms
from django.utils.text import slugify
from .models import (
    Platform, Repository, Host, Service, Domain, Deployment, Client, MonitoredURL,
    PlatformCredential, CredentialKind,
    ActivityEntry, ActivityType,
    PlatformType, FrameworkChoice, LifecycleStatus, EnvironmentChoice,
    HostProvider, HostType, RepoProvider, ServiceType, DeploymentStatus,
    OwnershipType,
)


class ClientForm(forms.ModelForm):
    slug = forms.SlugField(
        required=False,
        help_text='Leave blank to auto-generate from the name.',
    )

    class Meta:
        model = Client
        fields = ['name', 'slug', 'website', 'industry', 'contact_name', 'contact_email', 'contact_phone', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 4}),
            'website': forms.URLInput(attrs={'placeholder': 'https://example.com'}),
        }
        help_texts = {
            'website': 'Full HTTPS address — must start with https://',
        }

    def clean_slug(self):
        slug = self.cleaned_data.get('slug') or slugify(self.cleaned_data.get('name', ''))
        qs = Client.objects.filter(slug=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A client with this slug already exists.')
        return slug

    def clean_website(self):
        url = self.cleaned_data.get('website', '').strip()
        if url and not url.startswith('https://'):
            raise forms.ValidationError('Website must start with https://')
        return url


class PlatformForm(forms.ModelForm):
    class Meta:
        model = Platform
        fields = ['name', 'slug', 'description', 'platform_type', 'lifecycle_status']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        qs = Platform.objects.filter(slug=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A platform with this slug already exists.')
        return slug


class MonitoredURLForm(forms.ModelForm):
    class Meta:
        model = MonitoredURL
        fields = ['label', 'path', 'is_critical']
        widgets = {
            'path': forms.TextInput(attrs={'placeholder': '/admin/'}),
        }
        help_texts = {
            'path': 'Relative path from the domain root, e.g. /shop/ or /admin/',
            'is_critical': 'If this URL is down, the platform health is marked as DOWN',
        }


class PlatformEditForm(forms.ModelForm):
    class Meta:
        model = Platform
        fields = [
            'name', 'slug', 'description', 'platform_type',
            'framework', 'framework_other', 'lifecycle_status', 'default_environment',
            'ownership_type', 'client',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'framework_other': forms.TextInput(attrs={'placeholder': 'e.g. Flask, Next.js, Rails…'}),
        }
        labels = {
            'framework_other': 'Specify framework',
            'client': 'Client',
        }
        help_texts = {
            'client': 'Required when ownership type is "Client".',
        }

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        qs = Platform.objects.filter(slug=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A platform with this slug already exists.')
        return slug


# --- Wizard step forms ---

class WizardStep1Form(forms.Form):
    name = forms.CharField(max_length=200)
    slug = forms.SlugField(max_length=200, required=False, help_text='Leave blank to auto-generate')
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    platform_type = forms.ChoiceField(choices=PlatformType.choices)
    lifecycle_status = forms.ChoiceField(choices=LifecycleStatus.choices, initial=LifecycleStatus.DEVELOPMENT)

    def clean(self):
        cleaned = super().clean()
        name = cleaned.get('name', '')
        slug = cleaned.get('slug', '').strip()
        if not slug and name:
            slug = slugify(name)
        cleaned['slug'] = slug
        if slug:
            existing_id = self.initial.get('platform_id')
            qs = Platform.objects.filter(slug=slug)
            if existing_id:
                qs = qs.exclude(pk=existing_id)
            if qs.exists():
                self.add_error('slug', 'A platform with this slug already exists.')
        return cleaned


class WizardStep2Form(forms.Form):
    framework = forms.ChoiceField(choices=FrameworkChoice.choices, initial=FrameworkChoice.OTHER)
    framework_other = forms.CharField(
        required=False,
        max_length=100,
        label='Specify framework',
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Flask, Next.js, Rails…'}),
    )
    default_environment = forms.ChoiceField(
        choices=EnvironmentChoice.choices,
        initial=EnvironmentChoice.DEVELOPMENT,
        label='Default Environment',
    )


class WizardStep3Form(forms.Form):
    REPO_CHOICE_NONE = 'none'
    REPO_CHOICE_NEW = 'new'

    repo_option = forms.ChoiceField(
        choices=[
            (REPO_CHOICE_NONE, 'No repository yet'),
            (REPO_CHOICE_NEW, 'Add repository'),
        ],
        widget=forms.RadioSelect,
        initial=REPO_CHOICE_NONE,
    )
    repo_name = forms.CharField(max_length=200, required=False)
    repo_provider = forms.ChoiceField(choices=RepoProvider.choices, required=False, initial=RepoProvider.GITHUB)
    repo_url = forms.URLField(required=False)
    repo_default_branch = forms.CharField(max_length=100, required=False, initial='main')

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('repo_option') == self.REPO_CHOICE_NEW:
            if not cleaned.get('repo_name'):
                self.add_error('repo_name', 'Repository name is required.')
        return cleaned


class WizardStep4Form(forms.Form):
    HOST_CHOICE_NONE = 'none'
    HOST_CHOICE_EXISTING = 'existing'
    HOST_CHOICE_NEW = 'new'

    host_option = forms.ChoiceField(
        choices=[
            (HOST_CHOICE_NONE, 'No host configured yet'),
            (HOST_CHOICE_EXISTING, 'Choose existing host'),
            (HOST_CHOICE_NEW, 'Create new host'),
        ],
        widget=forms.RadioSelect,
        initial=HOST_CHOICE_NONE,
    )
    host_id = forms.ModelChoiceField(queryset=Host.objects.filter(status='active'), required=False, empty_label='— select —')
    host_name = forms.CharField(max_length=200, required=False)
    host_provider = forms.ChoiceField(choices=HostProvider.choices, required=False, initial=HostProvider.OTHER)
    host_hostname = forms.CharField(max_length=253, required=False, label='Hostname / IP')
    host_environment = forms.ChoiceField(
        choices=EnvironmentChoice.choices, required=False, initial=EnvironmentChoice.PRODUCTION
    )
    host_type = forms.ChoiceField(choices=HostType.choices, required=False, initial=HostType.VPS)

    def clean(self):
        cleaned = super().clean()
        opt = cleaned.get('host_option')
        if opt == self.HOST_CHOICE_EXISTING and not cleaned.get('host_id'):
            self.add_error('host_id', 'Please select an existing host.')
        if opt == self.HOST_CHOICE_NEW and not cleaned.get('host_name'):
            self.add_error('host_name', 'Host name is required.')
        return cleaned


class WizardStep5Form(forms.Form):
    DOMAIN_CHOICE_NONE = 'none'
    DOMAIN_CHOICE_ADD = 'add'

    domain_option = forms.ChoiceField(
        choices=[
            (DOMAIN_CHOICE_NONE, 'No domain yet'),
            (DOMAIN_CHOICE_ADD, 'Add domain(s)'),
        ],
        widget=forms.RadioSelect,
        initial=DOMAIN_CHOICE_NONE,
    )
    primary_domain = forms.CharField(max_length=253, required=False, label='Primary domain')
    extra_domains = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
        label='Additional domains (one per line)',
    )
    domain_environment = forms.ChoiceField(
        choices=EnvironmentChoice.choices,
        initial=EnvironmentChoice.PRODUCTION,
        label='Environment',
        required=False,
    )
    ssl_enabled = forms.NullBooleanField(
        widget=forms.Select(choices=[('', 'Unknown'), ('True', 'Yes'), ('False', 'No')]),
        required=False,
        label='SSL / HTTPS',
    )

    def clean_primary_domain(self):
        val = self.cleaned_data.get('primary_domain', '').strip().lower().rstrip('/')
        return val

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('domain_option') == self.DOMAIN_CHOICE_ADD:
            if not cleaned.get('primary_domain'):
                self.add_error('primary_domain', 'Primary domain is required.')
        return cleaned


class WizardStep6Form(forms.Form):
    # Services are auto-generated; user can adjust name/type
    service_name = forms.CharField(max_length=200, required=False)
    service_type = forms.ChoiceField(choices=ServiceType.choices, required=False)
    service_environment = forms.ChoiceField(
        choices=EnvironmentChoice.choices,
        required=False,
        initial=EnvironmentChoice.PRODUCTION,
    )
    skip_service = forms.BooleanField(required=False, label='Skip default service creation')


# --- Supporting CRUD forms ---

class RepositoryForm(forms.ModelForm):
    class Meta:
        model = Repository
        fields = ['name', 'provider', 'url', 'default_branch', 'local_path', 'status']


class HostForm(forms.ModelForm):
    class Meta:
        model = Host
        fields = ['name', 'provider', 'hostname', 'environment', 'host_type', 'os_info', 'status', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 3})}


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name', 'service_type', 'host', 'environment', 'runtime_identifier', 'port', 'status']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['host'].queryset = Host.objects.filter(status='active')
        self.fields['host'].required = False


class DomainForm(forms.ModelForm):
    class Meta:
        model = Domain
        fields = ['hostname', 'environment', 'is_primary', 'ssl_enabled', 'status']


class DeploymentForm(forms.ModelForm):
    class Meta:
        model = Deployment
        fields = ['environment', 'version', 'status', 'deployed_at', 'deployed_by', 'notes', 'service']
        widgets = {
            'deployed_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, platform=None, **kwargs):
        super().__init__(*args, **kwargs)
        if platform:
            self.fields['service'].queryset = platform.services.all()
        self.fields['service'].required = False


class PlatformCredentialForm(forms.ModelForm):
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=True, attrs={
            'autocomplete': 'new-password',
            'placeholder': 'Leave blank to keep unchanged',
            'class': 'form-control form-control-sm',
        }),
        label='Password / Secret',
    )

    class Meta:
        model = PlatformCredential
        fields = ['label', 'kind', 'url', 'username', 'notes']
        widgets = {
            'label': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'kind': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'url': forms.URLInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'https://example.com/wp-admin/'}),
            'username': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control form-control-sm'}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        pw = self.cleaned_data.get('password', '').strip()
        if pw:
            instance.set_password(pw)
        if commit:
            instance.save()
        return instance


class ActivityEntryForm(forms.ModelForm):
    occurred_at = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local', 'class': 'form-control form-control-sm'},
            format='%Y-%m-%dT%H:%M',
        ),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S'],
    )

    class Meta:
        model = ActivityEntry
        fields = ['platform', 'title', 'activity_type', 'occurred_at', 'is_milestone', 'description', 'ref_url']
        widgets = {
            'platform': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'title': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'activity_type': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control form-control-sm'}),
            'ref_url': forms.URLInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'https://'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.utils import timezone
        self.fields['platform'].required = False
        self.fields['platform'].empty_label = '— Estate-wide —'
        self.fields['platform'].queryset = Platform.objects.all().order_by('name')
        if not self.instance.pk:
            self.fields['occurred_at'].initial = timezone.localtime().strftime('%Y-%m-%dT%H:%M')
