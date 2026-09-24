"""Integration coverage for the presentation routes and onboarding contracts."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Platform, Host, Repository, Service, Deployment, HealthCheck


class PresentationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='presentation-review')
        cls.platform = Platform.objects.create(name='Atlas', slug='atlas', framework='django')
        cls.host = Host.objects.create(name='Production EU', hostname='host.example.test')
        cls.repo = Repository.objects.create(platform=cls.platform, name='Atlas source', default_branch='main')
        cls.service = Service.objects.create(platform=cls.platform, host=cls.host, name='Atlas app')
        cls.deployment = Deployment.objects.create(platform=cls.platform, service=cls.service, version='v1.2', deployed_at=timezone.now())

    def setUp(self):
        self.client.force_login(self.user)

    def test_inventory_requires_login(self):
        anonymous = Client()
        for route in ('repository_list', 'service_list', 'deployment_list'):
            response = anonymous.get(reverse('platforms:' + route))
            self.assertEqual(response.status_code, 302)
            self.assertIn('/accounts/login/', response.url)

    def test_inventory_links_to_existing_actions(self):
        for route, text, action in (
            ('repository_list', 'Atlas source', reverse('platforms:repository_edit', kwargs={'slug':'atlas','pk':self.repo.pk})),
            ('service_list', 'Atlas app', reverse('platforms:service_edit', kwargs={'slug':'atlas','pk':self.service.pk})),
            ('deployment_list', 'v1.2', self.platform.get_absolute_url()+'#deployments'),
        ):
            response = self.client.get(reverse('platforms:'+route))
            self.assertContains(response, text)
            self.assertContains(response, action)
            self.assertContains(response, self.platform.get_absolute_url())

    def test_deployment_inventory_orders_and_paginates(self):
        for index in range(51):
            Deployment.objects.create(platform=self.platform, version=f'build-{index}', deployed_at=timezone.now())
        response = self.client.get(reverse('platforms:deployment_list'))
        self.assertEqual(len(response.context['page_obj']),50)
        self.assertContains(response, 'build-50')
        self.assertContains(response, '?page=2')
        response = self.client.get(reverse('platforms:deployment_list'), {'page':2})
        self.assertEqual(len(response.context['page_obj']),2)

    def test_dashboard_activity_is_chronological_and_persisted(self):
        HealthCheck.objects.create(platform=self.platform, endpoint='https://example.test', status='down', checked_at=timezone.now())
        response = self.client.get(reverse('platforms:dashboard'))
        events = response.context['recent_activity']
        self.assertEqual(events[0]['kind'], 'Health')
        self.assertEqual({event['kind'] for event in events}, {'Platform','Deployment','Health'})
        self.assertContains(response, 'issue-danger')
        self.assertContains(response, 'Health check failing')

    def test_review_displays_host_name_and_readable_choices(self):
        session = self.client.session
        session['platform_wizard'] = {
            'step1': {'name':'Review app','slug':'review-app','platform_type':'internal_application','lifecycle_status':'development'},
            'step2': {'framework':'wordpress','default_environment':'development'},
            'step4': {'host_option':'existing','host_id':self.host.pk},
            'step6': {'service_name':'WordPress','service_type':'web','service_environment':'development'},
        }
        session.save()
        response = self.client.get(reverse('platforms:wizard_step',kwargs={'step':7}))
        self.assertContains(response, 'Production EU')
        self.assertContains(response, 'Internal Application')
        self.assertContains(response, 'WordPress')
        self.assertContains(response, 'Not configured yet')

    def test_optional_wizard_flow_preserves_backend_defaults(self):
        self.client.get(reverse('platforms:wizard_start'))
        steps = [
            {'name':'Minimal UI platform','slug':'','platform_type':'website','lifecycle_status':'development'},
            {'framework':'django','default_environment':'development'},
            {'repo_option':'none'},
            {'host_option':'none'},
            {'domain_option':'none'},
            {'service_name':'Django app','service_type':'web','service_environment':'development'},
        ]
        for number, data in enumerate(steps, 1):
            url = reverse('platforms:wizard_step',kwargs={'step':number})
            self.assertEqual(self.client.get(url).status_code,200)
            self.assertEqual(self.client.post(url,data).status_code,302)
        response = self.client.post(reverse('platforms:wizard_complete'))
        platform = Platform.objects.get(slug='minimal-ui-platform')
        self.assertRedirects(response,platform.get_absolute_url())
        self.assertFalse(platform.repositories.exists())
        self.assertFalse(platform.domains.exists())
        self.assertEqual(platform.services.get().environment,'development')

    def test_forms_render_accessible_error_associations(self):
        response = self.client.post(reverse('platforms:wizard_step',kwargs={'step':1}), {'name':'','platform_type':'website','lifecycle_status':'development'})
        self.assertContains(response, 'for="id_name"')
        self.assertContains(response, 'id="id_name_error"')
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'Please check the highlighted fields.')

    def test_logout_uses_csrf_protected_post(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.get(reverse('platforms:dashboard'))
        self.assertContains(response, 'method="post" action="/accounts/logout/"')
        self.assertEqual(client.post(reverse('logout')).status_code,403)
        token = client.cookies['csrftoken'].value
        response = client.post(reverse('logout'), {'csrfmiddlewaretoken':token})
        self.assertIn(response.status_code,(200,302))
        self.assertNotIn('_auth_user_id', client.session)

    def test_empty_filter_result_offers_clear_not_create(self):
        response = self.client.get(reverse('platforms:platform_list'),{'q':'no-such-platform'})
        self.assertContains(response, 'No platforms match these filters')
        self.assertContains(response, 'Clear all filters')
