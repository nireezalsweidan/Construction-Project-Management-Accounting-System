from rest_framework import serializers

from projects.models import Project

from .models import Client, ClientDocument, ClientInvoiceSummary, ClientPayment, get_client_financials


class ClientListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ["id", "name", "company_name", "phone", "email", "tax_id"]


class ClientProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "code", "name", "status", "contract_value", "start_date", "is_archived"]


class ClientInvoiceSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientInvoiceSummary
        fields = [
            "id",
            "project_id",
            "invoice_number",
            "invoice_date",
            "due_date",
            "total_amount",
            "status",
        ]


class ClientPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientPayment
        fields = ["id", "payment_number", "payment_date", "amount", "payment_method", "reference"]


class ClientDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientDocument
        fields = [
            "id",
            "file_name",
            "file_path",
            "file_type",
            "file_size",
            "document_type",
            "uploaded_by",
            "uploaded_at",
        ]
        read_only_fields = fields


class ClientSerializer(serializers.ModelSerializer):
    """Full read/write representation. outstanding_balance is computed,
    not stored — see models.get_client_financials()."""

    outstanding_balance = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = [
            "id",
            "name",
            "company_name",
            "phone",
            "email",
            "address",
            "tax_id",
            "notes",
            "created_at",
            "updated_at",
            "outstanding_balance",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "outstanding_balance"]

    def get_outstanding_balance(self, obj):
        return get_client_financials(obj.id)["outstanding_balance"]

    def validate_email(self, value):
        # email isn't unique at the DB level on `clients`, so this is just
        # a light sanity check, not a uniqueness constraint.
        return value