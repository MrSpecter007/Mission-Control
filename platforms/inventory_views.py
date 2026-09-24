from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from .models import Repository, Service, Deployment


PAGE_SIZE = 50


@login_required
def repository_list(request):
    qs = Repository.objects.select_related('platform').order_by('platform__name', 'name')
    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'platforms/repository_list.html', {'page_obj': page_obj})


@login_required
def service_list(request):
    qs = Service.objects.select_related('platform', 'host').order_by('platform__name', 'name')
    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'platforms/service_list.html', {'page_obj': page_obj})


@login_required
def deployment_list(request):
    qs = Deployment.objects.select_related('platform', 'service').order_by('-deployed_at')
    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'platforms/deployment_list.html', {'page_obj': page_obj})
