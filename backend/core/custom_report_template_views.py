from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.models import CustomReportTemplate
from core.serializers import BaseModelSerializer
from core.permissions import IsGlobalAdmin


class CustomReportTemplateSerializer(BaseModelSerializer):
    class Meta:
        model = CustomReportTemplate
        fields = '__all__'


class CustomReportTemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsGlobalAdmin]
    serializer_class = CustomReportTemplateSerializer
    queryset = CustomReportTemplate.objects.all()

    def get_queryset(self):
        user = self.request.user
        if not getattr(user, "is_superuser", False) and getattr(user, "platform_role", "") not in ["superadmin", "webadmin", "admin"]:
            return CustomReportTemplate.objects.none()
        return super().get_queryset()

    @action(detail=False, methods=['get'], url_path=r'by-type/(?P<report_type>[^/]+)')
    def get_by_type(self, request, report_type=None):
        tmpl = CustomReportTemplate.objects.filter(report_type=report_type, is_active=True).first()
        if not tmpl:
            # Seed default instance if none exists
            tmpl = CustomReportTemplate.objects.create(
                report_type=report_type,
                title="Compliance Audit Report" if report_type == "compliance" else "Intermediary Compliance Dossier",
                header_text="CONFIDENTIAL - FOR INTERNAL USE ONLY",
                footer_text="Enterprise Compliance Platform",
                company_name="Enterprise Compliance Organization",
                primary_color="#4f46e5",
                show_executive_summary=True,
                show_findings=True,
                show_evidence_details=True,
                show_activity_history=True,
                is_active=True
            )
        serializer = self.get_serializer(tmpl)
        return Response(serializer.data)
