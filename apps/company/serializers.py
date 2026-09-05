"""
Serializers for the ``company`` app -- Company Administration.

``CompanyProfileSerializer`` is the read/update representation of the single
system-wide company record (``company_details`` table). Because this system
is built for exactly one company (Cedar Construction), the API offers only
view (GET) and update (PATCH) -- never create/list-of-many/delete.

Per the project decision (Option B), the company API is text-only: ``logo``
and ``currency`` are read-only here. The logo is changed from the web form
page (which uploads to Supabase and stores the public URL), and currency is
fixed at USD, so neither is writable through the API.
"""
from rest_framework import serializers

from .models import CompanyProfile


class CompanyProfileSerializer(serializers.ModelSerializer):
    """View/update the single company identity record."""

    class Meta:
        model = CompanyProfile
        fields = [
            "id",
            "name",
            "registration_number",
            "address",
            "phone",
            "email",
            "website",
            "tax_information",
            "currency",
            "logo",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "currency",
            "logo",
            "created_at",
            "updated_at",
        ]
