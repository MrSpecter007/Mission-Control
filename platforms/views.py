from datetime import datetime, timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify

from .forms import (
    PlatformEditForm, ClientForm, MonitoredURLForm,
    WizardStep1Form, WizardStep2Form, WizardStep3Form,
    WizardStep4Form, WizardStep5Form, WizardStep6Form,
    RepositoryForm, HostForm, ServiceForm, DomainForm, DeploymentForm,
    PlatformCredentialForm, ActivityEntryForm,
)
from .models import (
    Platform, Repository, Host, Service, Domain, Deployment, HealthCheck,
    LifecycleStatus, HealthStatus, DeploymentStatus, EnvironmentChoice,
    NewsItem, NewsItemSourceType, Client, MonitoredURL, DependencySnapshot,
    PlatformCredential, ActivityEntry, ActivityType,
)
from .services import run_health_check, get_default_service_name


def _log_activity(platform, title, activity_type, description='', is_milestone=False, user=None, ref_url=''):
    """Silently create an ActivityEntry. Failures are swallowed to avoid breaking callers."""
    try:
        from django.utils import timezone
        ActivityEntry.objects.create(
            platform=platform,
            title=title,
            activity_type=activity_type,
            description=description,
            is_milestone=is_milestone,
            occurred_at=timezone.now(),
            created_by=user,
            ref_url=ref_url,
        )
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Dashboard                                                                    #
# --------------------------------------------------------------------------- #

@login_required
def dashboard(request):
    platforms = Platform.objects.all()
    total = platforms.count()
    active_count = platforms.filter(lifecycle_status=LifecycleStatus.ACTIVE).count()
    development_count = platforms.filter(lifecycle_status=LifecycleStatus.DEVELOPMENT).count()

    healthy_count = 0
    degraded_count = 0
    down_count = 0
    unknown_count = 0

    platform_summaries = []
    for p in platforms.prefetch_related('domains', 'services', 'health_checks', 'deployments'):
        health = p.health_status
        if health == HealthStatus.HEALTHY:
            healthy_count += 1
        elif health == HealthStatus.DEGRADED:
            degraded_count += 1
        elif health == HealthStatus.DOWN:
            down_count += 1
        else:
            unknown_count += 1

        primary_domain = p.primary_domain
        host = None
        svc = p.services.filter(host__isnull=False).select_related('host').first()
        if svc:
            host = svc.host

        platform_summaries.append({
            'platform': p,
            'framework': p.framework_display,
            'lifecycle': p.get_lifecycle_status_display(),
            'primary_domain': primary_domain,
            'host': host,
            'health_status': health,
            'latest_deployment': p.latest_deployment,
            'attention': p.needs_attention(),
        })

    needs_attention = [s for s in platform_summaries if s['attention']]
    recent_platforms = sorted(platform_summaries, key=lambda x: x['platform'].created_at, reverse=True)[:5]

    # A bounded, chronological activity feed using persisted events only.
    recent_activity = [
        {'kind': 'Platform', 'platform': p, 'detail': 'Platform created', 'at': p.created_at}
        for p in Platform.objects.order_by('-created_at')[:5]
    ]
    recent_activity.extend(
        {'kind': 'Deployment', 'platform': d.platform, 'detail': f'{d.get_status_display()} · {d.version or "Version not recorded"}', 'at': d.deployed_at}
        for d in Deployment.objects.select_related('platform').order_by('-deployed_at')[:5]
    )
    recent_activity.extend(
        {'kind': 'Health', 'platform': h.platform, 'detail': h.get_status_display(), 'at': h.checked_at}
        for h in HealthCheck.objects.select_related('platform').order_by('-checked_at')[:5]
    )
    recent_activity.sort(key=lambda event: event['at'], reverse=True)

    recent_updates = (
        NewsItem.objects
        .select_related('platform')
        .order_by('-published_at')[:8]
    )

    recent_log_entries = (
        ActivityEntry.objects
        .select_related('platform')
        .order_by('-occurred_at')[:5]
    )

    context = {
        'recent_activity': recent_activity[:8],
        'recent_updates': recent_updates,
        'recent_log_entries': recent_log_entries,
        'total': total,
        'active_count': active_count,
        'development_count': development_count,
        'healthy_count': healthy_count,
        'degraded_count': degraded_count,
        'down_count': down_count,
        'unknown_count': unknown_count,
        'needs_attention': needs_attention,
        'recent_platforms': recent_platforms,
        'platform_summaries': platform_summaries,
    }
    return render(request, 'platforms/dashboard.html', context)


# --------------------------------------------------------------------------- #
# Platform list / search / filter                                              #
# --------------------------------------------------------------------------- #

@login_required
def platform_list(request):
    qs = Platform.objects.all()

    q = request.GET.get('q', '').strip()
    lifecycle = request.GET.get('lifecycle', '')
    framework = request.GET.get('framework', '')
    health = request.GET.get('health', '')

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q) | Q(slug__icontains=q))
    if lifecycle:
        qs = qs.filter(lifecycle_status=lifecycle)
    if framework:
        qs = qs.filter(framework=framework)

    platform_data = []
    for p in qs.prefetch_related('domains', 'services', 'health_checks'):
        health_status = p.health_status
        if health and health_status != health:
            continue
        platform_data.append({'platform': p, 'health_status': health_status, 'attention': p.needs_attention()})

    context = {
        'platform_data': platform_data,
        'q': q,
        'selected_lifecycle': lifecycle,
        'selected_framework': framework,
        'selected_health': health,
        'lifecycle_choices': LifecycleStatus.choices,
        'framework_choices': Platform._meta.get_field('framework').choices,
        'health_choices': HealthStatus.choices,
    }
    return render(request, 'platforms/platform_list.html', context)


# --------------------------------------------------------------------------- #
# Platform detail                                                              #
# --------------------------------------------------------------------------- #

@login_required
def platform_detail(request, slug):
    platform = get_object_or_404(Platform, slug=slug)
    repositories = platform.repositories.all()
    domains = platform.domains.all()
    services = platform.services.select_related('host').all()
    health_checks = platform.health_checks.all()[:20]
    latest_health = platform.latest_health_check

    platform_news = (
        NewsItem.objects
        .filter(platform=platform)
        .order_by('-published_at')[:15]
    )
    monitored_urls = platform.monitored_urls.all()
    monitored_url_form = MonitoredURLForm()

    credentials = platform.credentials.all()
    credential_form = PlatformCredentialForm()

    activity_entries = (
        platform.activity_entries
        .select_related('created_by')
        .order_by('-occurred_at')[:10]
    )
    activity_form = ActivityEntryForm(initial={'platform': platform})

    dep_snapshots = DependencySnapshot.objects.filter(
        repository__platform=platform, scanned_at__isnull=False
    ).exclude(dependencies=[]).select_related('repository')
    platform_deps = []
    for snap in dep_snapshots:
        for dep in snap.dependencies:
            platform_deps.append({
                'manifest': snap.manifest_path,
                'ecosystem': snap.ecosystem,
                'status': _dep_status(dep),
                **dep,
            })
    platform_deps.sort(key=lambda r: (_DEP_STATUS_ORDER.get(r['status'], 5), r['name']))

    context = {
        'platform': platform,
        'repositories': repositories,
        'domains': domains,
        'services': services,
        'health_checks': health_checks,
        'latest_health': latest_health,
        'health_status': platform.health_status,
        'attention': platform.needs_attention(),
        'platform_news': platform_news,
        'monitored_urls': monitored_urls,
        'monitored_url_form': monitored_url_form,
        'platform_deps': platform_deps,
        'credentials': credentials,
        'credential_form': credential_form,
        'activity_entries': activity_entries,
        'activity_form': activity_form,
    }
    return render(request, 'platforms/platform_detail.html', context)


@login_required
def platform_edit(request, slug):
    platform = get_object_or_404(Platform, slug=slug)
    if request.method == 'POST':
        old_lifecycle = platform.lifecycle_status
        form = PlatformEditForm(request.POST, instance=platform)
        if form.is_valid():
            form.save()
            if platform.lifecycle_status != old_lifecycle:
                _log_activity(
                    platform=platform,
                    title=f'Lifecycle changed to {platform.get_lifecycle_status_display()}',
                    activity_type=ActivityType.OPERATIONS,
                    description=f'Status changed from {LifecycleStatus(old_lifecycle).label} to {platform.get_lifecycle_status_display()}.',
                    user=request.user,
                )
            messages.success(request, 'Platform updated.')
            return redirect('platforms:platform_detail', slug=platform.slug)
    else:
        form = PlatformEditForm(instance=platform)
    return render(request, 'platforms/platform_edit.html', {'platform': platform, 'form': form})


@login_required
def platform_archive(request, slug):
    platform = get_object_or_404(Platform, slug=slug)
    if request.method == 'POST':
        platform.lifecycle_status = LifecycleStatus.ARCHIVED
        platform.save(update_fields=['lifecycle_status', 'updated_at'])
        messages.success(request, f'"{platform.name}" archived.')
        return redirect('platforms:platform_list')
    return render(request, 'platforms/platform_confirm_archive.html', {'platform': platform})


# --------------------------------------------------------------------------- #
# Health checks                                                                #
# --------------------------------------------------------------------------- #

@login_required
def run_platform_health_check(request, slug):
    platform = get_object_or_404(Platform, slug=slug)
    if request.method == 'POST':
        prev_status = platform.health_status
        check = run_health_check(platform)
        status_label = check.get_status_display()
        if check.status == HealthStatus.HEALTHY:
            messages.success(request, f'Health check passed — {status_label}')
        elif check.status in (HealthStatus.DEGRADED, HealthStatus.DOWN):
            messages.warning(request, f'Health check issue — {status_label}: {check.error_info}')
        else:
            messages.info(request, f'Health check complete — {status_label}')
        if check.status != prev_status:
            if check.status == HealthStatus.DOWN:
                atype = ActivityType.INCIDENT
                desc = f'Health check failed: {check.error_info or status_label}. Previous status: {prev_status}.'
            elif check.status == HealthStatus.HEALTHY and prev_status in (HealthStatus.DOWN, HealthStatus.DEGRADED):
                atype = ActivityType.OPERATIONS
                desc = f'Platform recovered from {prev_status} to {status_label}.'
            else:
                atype = ActivityType.MAINTENANCE
                desc = f'Health status changed from {prev_status} to {status_label}.'
            _log_activity(
                platform=platform,
                title=f'Health status changed to {status_label}',
                activity_type=atype,
                description=desc,
            )
    return redirect('platforms:platform_detail', slug=slug)


# --------------------------------------------------------------------------- #
# Repository CRUD                                                              #
# --------------------------------------------------------------------------- #

@login_required
def repository_add(request, slug):
    platform = get_object_or_404(Platform, slug=slug)
    if request.method == 'POST':
        form = RepositoryForm(request.POST)
        if form.is_valid():
            repo = form.save(commit=False)
            repo.platform = platform
            repo.save()
            messages.success(request, 'Repository added.')
            return redirect('platforms:platform_detail', slug=slug)
    else:
        form = RepositoryForm()
    return render(request, 'platforms/repository_form.html', {'platform': platform, 'form': form})


@login_required
def repository_edit(request, slug, pk):
    platform = get_object_or_404(Platform, slug=slug)
    repo = get_object_or_404(Repository, pk=pk, platform=platform)
    if request.method == 'POST':
        form = RepositoryForm(request.POST, instance=repo)
        if form.is_valid():
            form.save()
            messages.success(request, 'Repository updated.')
            return redirect('platforms:platform_detail', slug=slug)
    else:
        form = RepositoryForm(instance=repo)
    return render(request, 'platforms/repository_form.html', {'platform': platform, 'form': form, 'repo': repo})


# --------------------------------------------------------------------------- #
# Host CRUD                                                                    #
# --------------------------------------------------------------------------- #

@login_required
def host_list(request):
    hosts = Host.objects.all()
    return render(request, 'platforms/host_list.html', {'hosts': hosts})


@login_required
def host_create(request):
    if request.method == 'POST':
        form = HostForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Host created.')
            return redirect('platforms:host_list')
    else:
        form = HostForm()
    return render(request, 'platforms/host_form.html', {'form': form})


@login_required
def host_edit(request, pk):
    host = get_object_or_404(Host, pk=pk)
    if request.method == 'POST':
        form = HostForm(request.POST, instance=host)
        if form.is_valid():
            form.save()
            messages.success(request, 'Host updated.')
            return redirect('platforms:host_list')
    else:
        form = HostForm(instance=host)
    return render(request, 'platforms/host_form.html', {'form': form, 'host': host})


# --------------------------------------------------------------------------- #
# Service CRUD                                                                 #
# --------------------------------------------------------------------------- #

@login_required
def service_add(request, slug):
    platform = get_object_or_404(Platform, slug=slug)
    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            svc = form.save(commit=False)
            svc.platform = platform
            svc.save()
            _log_activity(
                platform=platform,
                title=f'Service added: {svc.name}',
                activity_type=ActivityType.INFRASTRUCTURE,
                description=f'{svc.get_service_type_display()} service "{svc.name}" configured on {platform.name}.',
                user=request.user,
            )
            messages.success(request, 'Service added.')
            return redirect('platforms:platform_detail', slug=slug)
    else:
        form = ServiceForm()
    return render(request, 'platforms/service_form.html', {'platform': platform, 'form': form})


@login_required
def service_edit(request, slug, pk):
    platform = get_object_or_404(Platform, slug=slug)
    svc = get_object_or_404(Service, pk=pk, platform=platform)
    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=svc)
        if form.is_valid():
            form.save()
            messages.success(request, 'Service updated.')
            return redirect('platforms:platform_detail', slug=slug)
    else:
        form = ServiceForm(instance=svc)
    return render(request, 'platforms/service_form.html', {'platform': platform, 'form': form, 'service': svc})


# --------------------------------------------------------------------------- #
# Domain CRUD                                                                  #
# --------------------------------------------------------------------------- #

@login_required
def domain_add(request, slug):
    platform = get_object_or_404(Platform, slug=slug)
    if request.method == 'POST':
        form = DomainForm(request.POST)
        if form.is_valid():
            domain = form.save(commit=False)
            domain.platform = platform
            domain.save()
            _log_activity(
                platform=platform,
                title=f'Domain added: {domain.hostname}',
                activity_type=ActivityType.INFRASTRUCTURE,
                description=f'Domain "{domain.hostname}" ({domain.get_environment_display()}) added to {platform.name}.',
                user=request.user,
            )
            messages.success(request, 'Domain added.')
            return redirect('platforms:platform_detail', slug=slug)
    else:
        form = DomainForm()
    return render(request, 'platforms/domain_form.html', {'platform': platform, 'form': form})


@login_required
def domain_edit(request, slug, pk):
    platform = get_object_or_404(Platform, slug=slug)
    domain = get_object_or_404(Domain, pk=pk, platform=platform)
    if request.method == 'POST':
        form = DomainForm(request.POST, instance=domain)
        if form.is_valid():
            form.save()
            messages.success(request, 'Domain updated.')
            return redirect('platforms:platform_detail', slug=slug)
    else:
        form = DomainForm(instance=domain)
    return render(request, 'platforms/domain_form.html', {'platform': platform, 'form': form, 'domain': domain})


# --------------------------------------------------------------------------- #
# Deployment CRUD                                                              #
# --------------------------------------------------------------------------- #

@login_required
def deployment_add(request, slug):
    platform = get_object_or_404(Platform, slug=slug)
    if request.method == 'POST':
        form = DeploymentForm(request.POST, platform=platform)
        if form.is_valid():
            deploy = form.save(commit=False)
            deploy.platform = platform
            deploy.save()
            messages.success(request, 'Deployment recorded.')
            return redirect('platforms:platform_detail', slug=slug)
    else:
        initial = {'deployed_at': datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M')}
        form = DeploymentForm(platform=platform, initial=initial)
    return render(request, 'platforms/deployment_form.html', {'platform': platform, 'form': form})


# --------------------------------------------------------------------------- #
# Onboarding Wizard                                                            #
# --------------------------------------------------------------------------- #

WIZARD_STEPS = 7
@login_required
def service_delete(request, slug, pk):
    platform = get_object_or_404(Platform, slug=slug)
    svc = get_object_or_404(Service, pk=pk, platform=platform)
    if request.method == 'POST':
        name = svc.name
        svc.delete()
        messages.success(request, f'Service "{name}" deleted.')
    return redirect('platforms:platform_detail', slug=slug)


@login_required
def domain_delete(request, slug, pk):
    platform = get_object_or_404(Platform, slug=slug)
    domain = get_object_or_404(Domain, pk=pk, platform=platform)
    if request.method == 'POST':
        hostname = domain.hostname
        domain.delete()
        messages.success(request, f'Domain "{hostname}" removed.')
    return redirect('platforms:platform_detail', slug=slug)


@login_required
def repository_delete(request, slug, pk):
    platform = get_object_or_404(Platform, slug=slug)
    repo = get_object_or_404(Repository, pk=pk, platform=platform)
    if request.method == 'POST':
        name = repo.name
        repo.delete()
        messages.success(request, f'Repository "{name}" disconnected.')
    return redirect('platforms:platform_detail', slug=slug)


@login_required
def deployment_delete(request, slug, pk):
    platform = get_object_or_404(Platform, slug=slug)
    from .models import Deployment
    deploy = get_object_or_404(Deployment, pk=pk, platform=platform)
    if request.method == 'POST':
        deploy.delete()
        messages.success(request, 'Deployment record deleted.')
    return redirect('platforms:platform_detail', slug=slug)


WIZARD_SESSION_KEY = 'platform_wizard'


def _wizard_data(request):
    return request.session.get(WIZARD_SESSION_KEY, {})


def _save_wizard_data(request, data):
    request.session[WIZARD_SESSION_KEY] = data
    request.session.modified = True


def _clear_wizard(request):
    request.session.pop(WIZARD_SESSION_KEY, None)
    request.session.modified = True


def _serialize_step_data(cleaned_data: dict) -> dict:
    """Convert model instances to PKs so the data is JSON-serializable for the session."""
    from django.db.models import Model
    result = {}
    for key, value in cleaned_data.items():
        if isinstance(value, Model):
            result[key] = value.pk
        else:
            result[key] = value
    return result


@login_required
def wizard_start(request):
    _clear_wizard(request)
    return redirect('platforms:wizard_step', step=1)


@login_required
def wizard_step(request, step):
    step = int(step)
    if step < 1 or step > WIZARD_STEPS:
        return redirect('platforms:wizard_step', step=1)

    data = _wizard_data(request)

    # Guard: must complete prior steps before jumping ahead
    if step > 1 and 'step1' not in data:
        return redirect('platforms:wizard_step', step=1)

    form_class = {
        1: WizardStep1Form,
        2: WizardStep2Form,
        3: WizardStep3Form,
        4: WizardStep4Form,
        5: WizardStep5Form,
        6: WizardStep6Form,
        7: None,  # review step
    }[step]

    if step == 7:
        return _wizard_review(request, data)

    if request.method == 'POST':
        form = form_class(request.POST)
        if form.is_valid():
            step_data = _serialize_step_data(form.cleaned_data)
            data[f'step{step}'] = step_data
            _save_wizard_data(request, data)
            if step == 6:
                return redirect('platforms:wizard_step', step=7)
            return redirect('platforms:wizard_step', step=step + 1)
    else:
        initial = data.get(f'step{step}', {})
        # Pre-populate slug from name on step 1
        if step == 1 and not initial:
            initial = {'lifecycle_status': 'development'}
        # Pre-populate service defaults from framework on step 6
        if step == 6 and not initial:
            framework = data.get('step2', {}).get('framework', 'other')
            svc_name, svc_type = get_default_service_name(framework)
            initial = {
                'service_name': svc_name,
                'service_type': svc_type,
                'service_environment': data.get('step2', {}).get('default_environment', 'production'),
            }
        form = form_class(initial=initial)

    context = {
        'form': form,
        'step': step,
        'total_steps': WIZARD_STEPS,
        'wizard_data': data,
        'step_names': [
            'Platform', 'Technology', 'Repository',
            'Hosting', 'Domains', 'Services', 'Review',
        ],
    }
    return render(request, f'platforms/wizard/step{step}.html', context)


def _wizard_review(request, data):
    step2 = data.get('step2', {})
    step3 = data.get('step3', {})
    step4 = data.get('step4', {})
    step5 = data.get('step5', {})
    step6 = data.get('step6', {})

    # Resolve host display
    host_display = None
    host_option = step4.get('host_option', 'none')
    if host_option == 'existing' and step4.get('host_id'):
        host_display = Host.objects.filter(pk=step4['host_id']).values_list('name', flat=True).first()
    elif host_option == 'new':
        host_display = step4.get('host_name', '')

    # Resolve domains
    domains_preview = []
    if step5.get('domain_option') == 'add' and step5.get('primary_domain'):
        domains_preview.append(step5['primary_domain'] + ' (primary)')
        extras = [d.strip() for d in step5.get('extra_domains', '').split('\n') if d.strip()]
        domains_preview.extend(extras)

    # Resolve service
    service_preview = None
    if not step6.get('skip_service'):
        service_preview = step6.get('service_name') or 'Web Application'

    context = {
        'step': 7,
        'total_steps': WIZARD_STEPS,
        'wizard_data': data,
        'step_names': [
            'Platform', 'Technology', 'Repository',
            'Hosting', 'Domains', 'Services', 'Review',
        ],
        'step1': data.get('step1', {}),
        'step2': step2,
        'step3': step3,
        'step4': step4,
        'step5': step5,
        'step6': step6,
        'host_display': host_display,
        'domains_preview': domains_preview,
        'service_preview': service_preview,
        'repo_option': step3.get('repo_option', 'none'),
        'host_option': host_option,
    }
    return render(request, 'platforms/wizard/step7.html', context)


@login_required
@transaction.atomic
def wizard_complete(request):
    if request.method != 'POST':
        return redirect('platforms:wizard_step', step=1)

    data = _wizard_data(request)
    if 'step1' not in data:
        messages.error(request, 'Wizard session expired. Please start again.')
        return redirect('platforms:wizard_start')

    step1 = data['step1']
    step2 = data.get('step2', {})
    step3 = data.get('step3', {})
    step4 = data.get('step4', {})
    step5 = data.get('step5', {})
    step6 = data.get('step6', {})

    # Create Platform
    slug = step1.get('slug') or slugify(step1['name'])
    # Ensure unique slug
    base_slug = slug
    counter = 1
    while Platform.objects.filter(slug=slug).exists():
        slug = f'{base_slug}-{counter}'
        counter += 1

    platform = Platform.objects.create(
        name=step1['name'],
        slug=slug,
        description=step1.get('description', ''),
        platform_type=step1.get('platform_type', 'website'),
        lifecycle_status=step1.get('lifecycle_status', 'development'),
        framework=step2.get('framework', 'other'),
        framework_other=step2.get('framework_other', ''),
        default_environment=step2.get('default_environment', 'development'),
    )

    # Repository
    if step3.get('repo_option') == 'new' and step3.get('repo_name'):
        Repository.objects.create(
            platform=platform,
            name=step3['repo_name'],
            provider=step3.get('repo_provider', 'github'),
            url=step3.get('repo_url', ''),
            default_branch=step3.get('repo_default_branch', 'main') or 'main',
        )

    # Host
    host = None
    host_option = step4.get('host_option', 'none')
    if host_option == 'existing':
        host_id = step4.get('host_id')
        if host_id:
            host = Host.objects.filter(pk=host_id).first()
    elif host_option == 'new' and step4.get('host_name'):
        host = Host.objects.create(
            name=step4['host_name'],
            provider=step4.get('host_provider', 'other'),
            hostname=step4.get('host_hostname', ''),
            environment=step4.get('host_environment', 'production'),
            host_type=step4.get('host_type', 'vps'),
        )

    # Domains
    if step5.get('domain_option') == 'add' and step5.get('primary_domain'):
        env = step5.get('domain_environment', 'production') or 'production'
        ssl = step5.get('ssl_enabled')

        Domain.objects.create(
            platform=platform,
            hostname=step5['primary_domain'].lower().strip().rstrip('/'),
            environment=env,
            is_primary=True,
            ssl_enabled=ssl,
        )
        extras = [d.strip() for d in step5.get('extra_domains', '').split('\n') if d.strip()]
        for extra in extras:
            Domain.objects.create(
                platform=platform,
                hostname=extra.lower().strip().rstrip('/'),
                environment=env,
                is_primary=False,
                ssl_enabled=ssl,
            )

    # Default service
    if not step6.get('skip_service'):
        svc_name = step6.get('service_name')
        svc_type = step6.get('service_type')
        svc_env = step6.get('service_environment', 'production') or 'production'

        if not svc_name or not svc_type:
            svc_name, svc_type = get_default_service_name(step2.get('framework', 'other'))

        Service.objects.create(
            platform=platform,
            host=host,
            name=svc_name,
            service_type=svc_type,
            environment=svc_env,
        )

    _clear_wizard(request)
    _log_activity(
        platform=platform,
        title=f'{platform.name} added to Mission Control',
        activity_type=ActivityType.OPERATIONS,
        description=f'Platform created with lifecycle status "{platform.get_lifecycle_status_display()}".',
        user=request.user,
    )
    messages.success(request, f'"{platform.name}" has been created successfully!')
    return redirect('platforms:platform_detail', slug=platform.slug)


# --------------------------------------------------------------------------- #
# Updates feed                                                                 #
# --------------------------------------------------------------------------- #

@login_required
def updates_list(request):
    qs = NewsItem.objects.select_related('platform').order_by('-published_at')

    platform_slug = request.GET.get('platform', '')
    source_type = request.GET.get('source', '')

    if platform_slug:
        qs = qs.filter(platform__slug=platform_slug)
    if source_type:
        qs = qs.filter(source_type=source_type)

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'platforms': Platform.objects.order_by('name'),
        'selected_platform': platform_slug,
        'selected_source': source_type,
        'source_choices': NewsItemSourceType.choices,
    }
    return render(request, 'platforms/updates_list.html', context)


# --------------------------------------------------------------------------- #
# Clients                                                                      #
# --------------------------------------------------------------------------- #

@login_required
def client_list(request):
    clients = Client.objects.prefetch_related('platforms').order_by('name')
    return render(request, 'platforms/client_list.html', {'clients': clients})


@login_required
def client_detail(request, slug):
    client = get_object_or_404(Client, slug=slug)
    platforms = client.platforms.order_by('name')
    return render(request, 'platforms/client_detail.html', {'client': client, 'platforms': platforms})


@login_required
def client_add(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            messages.success(request, f'Client "{client.name}" added.')
            return redirect('platforms:client_detail', slug=client.slug)
    else:
        form = ClientForm()
    return render(request, 'platforms/client_form.html', {'form': form, 'is_new': True})


@login_required
def client_edit(request, slug):
    client = get_object_or_404(Client, slug=slug)
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, f'Client "{client.name}" updated.')
            return redirect('platforms:client_detail', slug=client.slug)
    else:
        form = ClientForm(instance=client)
    return render(request, 'platforms/client_form.html', {'form': form, 'client': client, 'is_new': False})


# --------------------------------------------------------------------------- #
# Monitored URLs                                                               #
# --------------------------------------------------------------------------- #

@login_required
def monitored_url_add(request, slug):
    platform = get_object_or_404(Platform, slug=slug)
    if request.method == 'POST':
        form = MonitoredURLForm(request.POST)
        if form.is_valid():
            mu = form.save(commit=False)
            mu.platform = platform
            mu.save()
            messages.success(request, f'Monitoring added for {mu.label}.')
        else:
            messages.error(request, 'Could not add monitored URL — check the form.')
    return redirect('platforms:platform_detail', slug=slug)


@login_required
def monitored_url_delete(request, slug, pk):
    platform = get_object_or_404(Platform, slug=slug)
    mu = get_object_or_404(MonitoredURL, pk=pk, platform=platform)
    if request.method == 'POST':
        label = mu.label
        mu.delete()
        messages.success(request, f'Removed monitoring for {label}.')
    return redirect('platforms:platform_detail', slug=slug)


# --------------------------------------------------------------------------- #
# Credentials                                                                  #
# --------------------------------------------------------------------------- #

@login_required
def credential_add(request, slug):
    platform = get_object_or_404(Platform, slug=slug)
    if request.method == 'POST':
        form = PlatformCredentialForm(request.POST)
        if form.is_valid():
            cred = form.save(commit=False)
            cred.platform = platform
            cred.save()
            messages.success(request, f'Credential "{cred.label}" added.')
        else:
            messages.error(request, 'Could not save credential — check the form.')
    return redirect('platforms:platform_detail', slug=slug)


@login_required
def credential_edit(request, slug, pk):
    platform = get_object_or_404(Platform, slug=slug)
    cred = get_object_or_404(PlatformCredential, pk=pk, platform=platform)
    if request.method == 'POST':
        form = PlatformCredentialForm(request.POST, instance=cred)
        if form.is_valid():
            form.save()
            messages.success(request, f'Credential "{cred.label}" updated.')
        else:
            messages.error(request, 'Could not update credential — check the form.')
    return redirect('platforms:platform_detail', slug=slug)


@login_required
def credential_delete(request, slug, pk):
    platform = get_object_or_404(Platform, slug=slug)
    cred = get_object_or_404(PlatformCredential, pk=pk, platform=platform)
    if request.method == 'POST':
        label = cred.label
        cred.delete()
        messages.success(request, f'Credential "{label}" deleted.')
    return redirect('platforms:platform_detail', slug=slug)


@login_required
def credential_reveal(request, slug, pk):
    """Return decrypted password as JSON — POST only."""
    import json
    from django.http import JsonResponse
    platform = get_object_or_404(Platform, slug=slug)
    cred = get_object_or_404(PlatformCredential, pk=pk, platform=platform)
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    return JsonResponse({'password': cred.get_password()})


# --------------------------------------------------------------------------- #
# Activity Log                                                                 #
# --------------------------------------------------------------------------- #

@login_required
def activity_log(request):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    qs = ActivityEntry.objects.select_related('platform', 'created_by').order_by('-occurred_at')

    selected_platform = request.GET.get('platform', '')
    selected_type = request.GET.get('type', '')
    milestones_only = request.GET.get('milestones', '') == '1'
    selected_user = request.GET.get('user', '')

    if selected_platform:
        qs = qs.filter(platform__slug=selected_platform)
    if selected_type:
        qs = qs.filter(activity_type=selected_type)
    if milestones_only:
        qs = qs.filter(is_milestone=True)
    if selected_user:
        qs = qs.filter(created_by__pk=selected_user)

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    active_user_ids = (
        ActivityEntry.objects
        .filter(created_by__isnull=False)
        .values_list('created_by', flat=True)
        .distinct()
    )
    active_users = User.objects.filter(pk__in=active_user_ids).order_by('username')

    context = {
        'page_obj': page_obj,
        'platforms': Platform.objects.order_by('name'),
        'selected_platform': selected_platform,
        'selected_type': selected_type,
        'milestones_only': milestones_only,
        'selected_user': selected_user,
        'active_users': active_users,
        'type_choices': ActivityType.choices,
    }
    return render(request, 'platforms/activity_log.html', context)


@login_required
def activity_add(request):
    if request.method == 'POST':
        form = ActivityEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.created_by = request.user
            entry.save()
            messages.success(request, f'Activity "{entry.title}" logged.')
            return redirect('platforms:activity_log')
        messages.error(request, 'Could not save activity — check the form.')
    else:
        initial = {}
        platform_slug = request.GET.get('platform', '')
        if platform_slug:
            p = Platform.objects.filter(slug=platform_slug).first()
            if p:
                initial['platform'] = p
        form = ActivityEntryForm(initial=initial)
    return render(request, 'platforms/activity_form.html', {'form': form, 'title': 'Log Activity'})


@login_required
def platform_activity_add(request, slug):
    """Add an activity entry from the platform detail page (POST only)."""
    platform = get_object_or_404(Platform, slug=slug)
    if request.method == 'POST':
        form = ActivityEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.platform = platform
            entry.created_by = request.user
            entry.save()
            messages.success(request, f'Activity "{entry.title}" logged.')
        else:
            messages.error(request, 'Could not log activity — check the form.')
    return redirect('platforms:platform_detail', slug=slug)


@login_required
def activity_edit(request, pk):
    entry = get_object_or_404(ActivityEntry, pk=pk)
    if request.method == 'POST':
        form = ActivityEntryForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            messages.success(request, f'Activity "{entry.title}" updated.')
            if entry.platform:
                return redirect('platforms:platform_detail', slug=entry.platform.slug)
            return redirect('platforms:activity_log')
        messages.error(request, 'Could not update activity — check the form.')
    else:
        form = ActivityEntryForm(instance=entry)
    return render(request, 'platforms/activity_form.html', {'form': form, 'title': 'Edit Activity', 'entry': entry})


@login_required
def activity_delete(request, pk):
    entry = get_object_or_404(ActivityEntry, pk=pk)
    if request.method == 'POST':
        platform = entry.platform
        title = entry.title
        entry.delete()
        messages.success(request, f'Activity "{title}" deleted.')
        if platform:
            return redirect('platforms:platform_detail', slug=platform.slug)
    return redirect('platforms:activity_log')


# --------------------------------------------------------------------------- #
# Run Updates CTA                                                              #
# --------------------------------------------------------------------------- #

@login_required
def run_updates(request, slug=None):
    if request.method != 'POST':
        return redirect('platforms:updates_list')

    from .updater.runner import run_all

    result = run_all(platform_slug=slug, source=None, dry_run=False)
    created = result.get('created', 0)
    errors = result.get('errors', 0)

    if errors:
        messages.warning(request, f'Updates fetched — {created} new item(s), {errors} error(s). Check server logs.')
    else:
        messages.success(request, f'Updates fetched — {created} new item(s).')

    if slug:
        return redirect('platforms:platform_detail', slug=slug)
    return redirect('platforms:updates_list')


# --------------------------------------------------------------------------- #
# Dependencies                                                                 #
# --------------------------------------------------------------------------- #

def _dep_status(dep: dict) -> str:
    if dep.get('is_deprecated'):
        return 'deprecated'
    if dep.get('is_major_outdated'):
        return 'major_outdated'
    if dep.get('latest_version') and dep.get('pinned_version') != dep.get('latest_version'):
        return 'minor_outdated'
    if not dep.get('latest_version'):
        return 'unknown'
    return 'current'


_DEP_STATUS_ORDER = {'deprecated': 0, 'major_outdated': 1, 'minor_outdated': 2, 'unknown': 3, 'current': 4}


@login_required
def dependencies_list(request):
    snapshots = (
        DependencySnapshot.objects
        .select_related('repository', 'repository__platform')
        .filter(scanned_at__isnull=False)
        .exclude(dependencies=[])
        .order_by('repository__platform__name', 'ecosystem', 'manifest_path')
    )

    platform_slug = request.GET.get('platform', '')
    status_filter = request.GET.get('status', '')
    ecosystem_filter = request.GET.get('ecosystem', '')

    rows = []
    for snap in snapshots:
        if platform_slug and snap.repository.platform.slug != platform_slug:
            continue
        if ecosystem_filter and snap.ecosystem != ecosystem_filter:
            continue
        for dep in snap.dependencies:
            status = _dep_status(dep)
            if status_filter and status != status_filter:
                continue
            rows.append({
                'platform': snap.repository.platform,
                'repo': snap.repository,
                'manifest': snap.manifest_path,
                'ecosystem': snap.ecosystem,
                'scanned_at': snap.scanned_at,
                'status': status,
                **dep,
            })

    rows.sort(key=lambda r: (_DEP_STATUS_ORDER.get(r['status'], 5), r['name']))

    paginator = Paginator(rows, 100)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'total': len(rows),
        'platforms': Platform.objects.order_by('name'),
        'selected_platform': platform_slug,
        'selected_status': status_filter,
        'selected_ecosystem': ecosystem_filter,
        'status_choices': [
            ('deprecated', 'Deprecated'),
            ('major_outdated', 'Major update available'),
            ('minor_outdated', 'Minor update available'),
            ('current', 'Up to date'),
            ('unknown', 'Unknown'),
        ],
        'ecosystem_choices': [('pypi', 'PyPI'), ('npm', 'npm'), ('packagist', 'Packagist'), ('wordpress', 'WordPress')],
    }
    return render(request, 'platforms/dependencies_list.html', context)
