"""
Tests for the ``company`` app -- Company Administration / settings page.

Covers the Administration -> Company settings screen: it must be
auth-protected, render the profile form from the ``company_details`` table,
and persist edits back to that table (create when no row exists, update
otherwise).
"""
from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from django.urls import reverse

from .models import DEFAULT_CURRENCY_UUID, CompanyProfile
from .testing import WithCompanyDetailsTableMixin


class CompanySettingsPageTests(WithCompanyDetailsTableMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.url = reverse("company-settings")

    def setUp(self):
        self.user = DjangoUser.objects.create_user(username="owner", password="pass12345")
        self.client.force_login(self.user)

    def test_requires_login(self):
        anonymous = type(self.client)()
        response = anonymous.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_renders_profile_form_for_authenticated_user(self):
        CompanyProfile.objects.create(
            name="Cedar Construction S.A.L.",
            registration_number="CR-20458",
            email="finance@cedarconstruction.com",
            phone="+961 6 445 820",
            currency=DEFAULT_CURRENCY_UUID,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Company settings", content)
        self.assertIn("Company profile", content)
        self.assertIn("Users &amp; roles", content)
        self.assertIn("Cedar Construction S.A.L.", content)
        self.assertIn("CR-20458", content)
        self.assertIn("USD — US Dollar", content)
        self.assertIn("Automatic by financial year", content)

    def test_save_creates_profile_when_no_row_exists(self):
        response = self.client.post(self.url, {
            "name": "Cedar Construction S.A.L.",
            "registration_number": "CR-20458",
            "email": "finance@cedarconstruction.com",
            "phone": "+961 6 445 820",
            "address": "Tripoli, North Lebanon",
            "website": "www.cedarconstruction.com",
            "tax_information": "LB-884291",
        })
        self.assertEqual(response.status_code, 302)
        profile = CompanyProfile.objects.get()
        self.assertEqual(profile.name, "Cedar Construction S.A.L.")
        self.assertEqual(profile.tax_information, "LB-884291")
        self.assertEqual(profile.currency, DEFAULT_CURRENCY_UUID)

    def test_save_updates_existing_profile(self):
        CompanyProfile.objects.create(
            name="Old Name", email="old@example.com", currency=DEFAULT_CURRENCY_UUID,
        )
        response = self.client.post(self.url, {
            "name": "Cedar Construction S.A.L.",
            "registration_number": "CR-20458",
            "email": "finance@cedarconstruction.com",
            "phone": "+961 6 445 820",
        })
        self.assertEqual(response.status_code, 302)
        profile = CompanyProfile.objects.get()
        self.assertEqual(profile.name, "Cedar Construction S.A.L.")
        self.assertEqual(profile.email, "finance@cedarconstruction.com")
        self.assertEqual(CompanyProfile.objects.count(), 1)

    def test_save_requires_company_name(self):
        response = self.client.post(self.url, {"name": "  "})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Company name is required.", response.content.decode())
        self.assertEqual(CompanyProfile.objects.count(), 0)