from django import template
from platforms.models import (
    PlatformType, FrameworkChoice, LifecycleStatus,
    EnvironmentChoice, ServiceType, DeploymentStatus, HealthStatus,
    HostProvider, HostType, RepoProvider,
)

register = template.Library()

_CHOICE_MAPS = {
    'PlatformType': dict(PlatformType.choices),
    'FrameworkChoice': dict(FrameworkChoice.choices),
    'LifecycleStatus': dict(LifecycleStatus.choices),
    'EnvironmentChoice': dict(EnvironmentChoice.choices),
    'ServiceType': dict(ServiceType.choices),
    'DeploymentStatus': dict(DeploymentStatus.choices),
    'HealthStatus': dict(HealthStatus.choices),
    'HostProvider': dict(HostProvider.choices),
    'HostType': dict(HostType.choices),
    'RepoProvider': dict(RepoProvider.choices),
}


@register.filter
def choice_label(value, choice_class_name):
    """Return the human-readable label for a choice value."""
    mapping = _CHOICE_MAPS.get(choice_class_name, {})
    return mapping.get(value, value)


@register.filter
def add_aria_invalid(field):
    """Add aria-invalid=true to a form field's widget attrs when it has errors."""
    if field.errors:
        field.field.widget.attrs['aria-invalid'] = 'true'
        field.field.widget.attrs['aria-describedby'] = f'{field.auto_id}_error'
    return field
