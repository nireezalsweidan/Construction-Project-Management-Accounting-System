from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from rest_framework.test import APIClient
from clients.testing import WithClientsTableMixin
from projects.testing import WithProjectsTableMixin
from contractors.testing import WithContractorsTableMixin
from contractors.tests import make_contractor, make_project

class Debug(WithProjectsTableMixin, WithClientsTableMixin, WithContractorsTableMixin, TestCase):
    def test_dbg(self):
        u = DjangoUser.objects.create_user(username='o', password='x')
        c = APIClient(); c.force_authenticate(user=u)
        make_project()
        make_contractor()
        make_contractor(name='Bravo Welding')
        import json
        r = c.get('/api/contractors/', {'search': 'Skyline'})
        print('STATUS', r.status_code)
        print('DATA', json.dumps(r.data))
