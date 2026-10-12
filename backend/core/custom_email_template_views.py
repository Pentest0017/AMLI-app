from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from core.models import CustomEmailTemplate
from core.serializers import BaseModelSerializer
from core.permissions import IsGlobalAdmin
from core.notification_service import (
    TEMPLATE_REGISTRY,
    validate_template_placeholders,
    render_custom_or_default_template,
    render_official_html_email,
)


class CustomEmailTemplateSerializer(BaseModelSerializer):
    class Meta:
        model = CustomEmailTemplate
        fields = '__all__'

    def validate(self, attrs):
        template_key = attrs.get('template_key') or (self.instance.template_key if self.instance else None)
        body = attrs.get('body') or (self.instance.body if self.instance else '')
        if template_key and body:
            is_valid, err_msg = validate_template_placeholders(template_key, body)
            if not is_valid:
                raise serializers.ValidationError({'body': err_msg})
        return attrs


class CustomEmailTemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsGlobalAdmin]
    serializer_class = CustomEmailTemplateSerializer
    queryset = CustomEmailTemplate.objects.all()

    @action(detail=False, methods=['get'], url_path='available')
    def available_templates(self, request):
        result = []
        for key, meta in TEMPLATE_REGISTRY.items():
            overrides = list(
                CustomEmailTemplate.objects.filter(template_key=key, is_active=True).values_list('language', flat=True)
            )
            result.append({
                'template_key': key,
                'name': meta['name'],
                'category': meta['category'],
                'description': meta['description'],
                'mandatory_variables': meta['mandatory'],
                'variables': meta['mandatory'] + meta['optional'],
                'overrides': overrides,
            })
        return Response(result)

    @action(detail=False, methods=['get'], url_path=r'default/(?P<key>[^/]+)/(?P<lang>[^/]+)')
    def default_template(self, request, key=None, lang=None):
        meta = TEMPLATE_REGISTRY.get(key)
        if not meta:
            return Response({'detail': 'Template key not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'template_key': key,
            'language': lang or 'en',
            'subject': meta['default_subject'],
            'body': meta['default_body'],
            'mandatory_variables': meta['mandatory'],
        })

    @action(detail=False, methods=['post'], url_path='send-test')
    def send_test_email(self, request):
        template_key = request.data.get('template_key', 'control_assignment')
        recipient_email = request.data.get('recipient_email') or request.user.email
        language = request.data.get('language', 'en')

        meta = TEMPLATE_REGISTRY.get(template_key)
        if not meta:
            return Response({'detail': 'Invalid template key'}, status=status.HTTP_400_BAD_REQUEST)

        base_url = getattr(settings, 'CISO_ASSISTANT_URL', 'https://localhost:8443')
        sample_vars = {
            'user_name': request.user.first_name or request.user.email.split('@')[0],
            'spoc_name': request.user.first_name or 'Jane Doe',
            'supervisor_name': 'Senior Supervisor',
            'second_supervisor_name': 'Department Head',
            'controls_list': (
                '• [1.1] Exception Management (Framework: Irdai Audit Checklist V2) - Due: 15 Sep 2026\n'
                '• [2.1] Security Log Monitoring (Framework: Irdai Audit Checklist V2) - Due: 18 Sep 2026'
            ),
            'due_date': '15 Sep 2026',
            'l2_deadline': '20 Sep 2026',
            'l3_final_deadline': '25 Sep 2026',
            'action_url': f'{base_url}/compliance/evidences',
            'login_url': f'{base_url}/login',
            'reset_url': f'{base_url}/reset-password?token=sample_token_123',
            'temporary_password': 'TempPassword123!',
            'partner_name': 'Acme Partner Services',
            'report_title': 'Quarterly Security Audit Report 2026',
            'reviewer_feedback': 'Please attach section 4.2 architecture diagram and re-upload.',
            'domain_name': 'Information Security & Risk Management',
            'total_controls': '2',
        }

        try:
            subject, body = render_custom_or_default_template(template_key, sample_vars, language=language)
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@ciso.assistant')

            clean_subject = f'[TEST EMAIL] {subject}'
            html_body = render_official_html_email(
                title=clean_subject,
                message=body.replace('\n', '<br>'),
                action_url=sample_vars.get('action_url', base_url),
            )

            msg = EmailMultiAlternatives(
                subject=clean_subject,
                body=f'{clean_subject}\n\n{body}\n\nLink: ' + sample_vars.get('action_url', base_url),
                from_email=from_email,
                to=[recipient_email],
            )
            msg.attach_alternative(html_body, 'text/html')
            msg.send(fail_silently=False)

            return Response({
                'detail': f'Test email successfully dispatched to {recipient_email}',
                'template_key': template_key,
                'rendered_subject': subject,
                'rendered_body': body,
            })
        except Exception as e:
            return Response({'detail': f'Failed to send test email: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
