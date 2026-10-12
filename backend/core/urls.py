from .views import *
from core.intermediary_compliance_views import (
    IntermediaryFolderViewSet,
    IntermediaryAssignmentViewSet,
    IntermediaryPartnerReportViewSet,
    IntermediaryReportGenerationView,
    IntermediaryScopesView,
    IntermediaryPendingStatusView,
    IntermediaryReportPdfView,
    IntermediaryGeneratedReportViewSet,
)
from core.control_assignment_views import ControlAssignmentViewSet
from core.custom_email_template_views import CustomEmailTemplateViewSet
from core.evidence_management_views import (
    EvidenceSubmitView,
    EvidenceReviewActionView,
    EvidenceRepositoryView,
    EvidenceCopyView,
    EvidenceDeleteView,
)
from core.report_generation_views import (
    ControlAssignmentReportSummaryView,
    ControlAssignmentReportControlsView,
)
from core.notification_views import (
    NotificationListView,
    NotificationUnreadCountView,
    NotificationMarkReadView,
    NotificationMarkAllReadView,
    NotificationMarkReadByTaskView,
)
from core.escalation_views import (
    EscalationRuleViewSet,
    EscalationManualTriggerView,
    EscalationLogListView,
    EscalationAdminUsersView,
    EscalationScheduleView,
)
from sec_intel.views import SecurityAdvisoryViewSet, CWEViewSet
from tprm.views import (
    EntityViewSet,
    RepresentativeViewSet,
    SolutionViewSet,
    EntityAssessmentViewSet,
    ContractViewSet,
)
from library.views import (
    LibraryDraftViewSet,
    MappingLibrariesList,
    StoredLibraryViewSet,
    LoadedLibraryViewSet,
)
from custom_fields.views import CustomFieldDefinitionViewSet
import importlib
from .audit_views import AuditLogViewSet


from django.urls import include, path
from rest_framework import routers

from django.conf import settings
from core.control_assignment_views import ControlAssignmentViewSet
from core.custom_email_template_views import CustomEmailTemplateViewSet
from core.custom_report_template_views import CustomReportTemplateViewSet

router = routers.DefaultRouter()
router.register(r"custom-email-templates", CustomEmailTemplateViewSet, basename="custom-email-templates")
router.register(r"custom-report-templates", CustomReportTemplateViewSet, basename="custom-report-templates")
router.register(r"control-assignments", ControlAssignmentViewSet, basename="control-assignments")
router.register(r"escalation-rules", EscalationRuleViewSet, basename="escalation-rules")
router.register(r"intermediary-compliance/repository", IntermediaryFolderViewSet, basename="intermediary-repository")
router.register(r"intermediary-compliance/assignments", IntermediaryAssignmentViewSet, basename="intermediary-assignments")
router.register(r"intermediary-compliance/partner-reports", IntermediaryPartnerReportViewSet, basename="intermediary-partner-reports")
router.register(r"intermediary-compliance/generated-reports", IntermediaryGeneratedReportViewSet, basename="intermediary-generated-reports")
router.register(r"folders", FolderViewSet, basename="folders")
router.register(
    r"custom-fields",
    CustomFieldDefinitionViewSet,
    basename="custom-fields",
)
router.register(r"entities", EntityViewSet, basename="entities")
router.register(
    r"entity-assessments", EntityAssessmentViewSet, basename="entity-assessments"
)
router.register(r"solutions", SolutionViewSet, basename="solutions")
router.register(r"representatives", RepresentativeViewSet, basename="representatives")
router.register(r"contracts", ContractViewSet, basename="contracts")
router.register(r"perimeters", PerimeterViewSet, basename="perimeters")
router.register(r"risk-matrices", RiskMatrixViewSet, basename="risk-matrices")
router.register(r"vulnerabilities", VulnerabilityViewSet, basename="vulnerabilities")
router.register(r"risk-assessments", RiskAssessmentViewSet, basename="risk-assessments")
router.register(r"threats", ThreatViewSet, basename="threats")
router.register(
    r"security-advisories", SecurityAdvisoryViewSet, basename="security-advisories"
)
router.register(r"cwes", CWEViewSet, basename="cwes")
router.register(r"risk-scenarios", RiskScenarioViewSet, basename="risk-scenarios")
router.register(r"applied-controls", AppliedControlViewSet, basename="applied-controls")
router.register(r"policies", PolicyViewSet, basename="policies")
router.register(r"risk-acceptances", RiskAcceptanceViewSet, basename="risk-acceptances")
router.register(r"validation-flows", ValidationFlowViewSet, basename="validation-flows")
router.register(
    r"reference-controls", ReferenceControlViewSet, basename="reference-controls"
)
router.register(
    r"asset-capabilities", AssetCapabilityViewSet, basename="asset-capabilities"
)
router.register(r"assets", AssetViewSet, basename="assets")
router.register(r"asset-class", AssetClassViewSet, basename="asset-class")

router.register(r"actors", ActorViewSet, basename="actors")

router.register(r"teams", TeamViewSet, basename="teams")

router.register(r"users", UserViewSet, basename="users")
router.register(r"user-groups", UserGroupViewSet, basename="user-groups")
router.register(r"idp-groups", IdPGroupViewSet, basename="idp-groups")
router.register(r"role-assignments", RoleAssignmentViewSet, basename="role-assignments")

from iam.views import FeatureToggleViewSet
router.register(r"feature-toggles", FeatureToggleViewSet, basename="feature-toggles")
router.register(r"frameworks", FrameworkViewSet, basename="frameworks")
router.register(r"evidences", EvidenceViewSet, basename="evidences")
router.register(
    r"evidence-revisions", EvidenceRevisionViewSet, basename="evidence-revisions"
)
router.register(
    r"compliance-assessments",
    ComplianceAssessmentViewSet,
    basename="compliance-assessments",
)
router.register(
    r"campaigns",
    CampaignViewSet,
    basename="campaigns",
)
router.register(
    r"organisation-objectives",
    OrganisationObjectiveViewSet,
    basename="organisation-objectives",
)
router.register(
    r"organisation-issues",
    OrganisationIssueViewSet,
    basename="organisation-issues",
)
router.register(r"requirement-nodes", RequirementViewSet, basename="requirement-nodes")
router.register(
    r"requirement-assessments",
    RequirementAssessmentViewSet,
    basename="requirement-assessments",
)
router.register(
    r"requirement-assignments",
    RequirementAssignmentViewSet,
    basename="requirement-assignments",
)
router.register(r"stored-libraries", StoredLibraryViewSet, basename="stored-libraries")
router.register(r"loaded-libraries", LoadedLibraryViewSet, basename="loaded-libraries")
router.register(r"library-drafts", LibraryDraftViewSet, basename="library-drafts")
router.register(
    r"requirement-mapping-sets",
    RequirementMappingSetViewSet,
    basename="requirement-mapping-sets",
)
router.register(
    r"filtering-labels",
    FilteringLabelViewSet,
    basename="filtering-labels",
)
router.register(
    r"library-filtering-labels",
    LibraryFilteringLabelViewSet,
    basename="library-filtering-labels",
)
router.register(
    r"security-exceptions",
    SecurityExceptionViewSet,
    basename="security-exceptions",
)
router.register(
    r"findings-assessments", FindingsAssessmentViewSet, basename="findings-assessments"
)
router.register(r"findings", FindingViewSet, basename="findings")
router.register(r"incidents", IncidentViewSet, basename="incidents")
router.register(r"timeline-entries", TimelineEntryViewSet, basename="timeline-entries")
router.register(r"comments", CommentViewSet, basename="comments")
router.register(r"task-templates", TaskTemplateViewSet, basename="task-templates")
router.register(r"task-nodes", TaskNodeViewSet, basename="task-nodes")
router.register(r"terminologies", TerminologyViewSet, basename="terminologies")
router.register(
    r"object-classifications",
    ObjectClassificationViewSet,
    basename="object-classifications",
)
router.register(
    r"classification-levels",
    ClassificationLevelViewSet,
    basename="classification-levels",
)
router.register(r"questions", QuestionViewSet, basename="questions")
router.register(r"question-choices", QuestionChoiceViewSet, basename="question-choices")
router.register(r"answers", AnswerViewSet, basename="answers")
router.register(r"presets", PresetViewSet, basename="presets")
router.register(r"audit-logs", AuditLogViewSet, basename="audit-logs")

if not any(r[2] == "intermediary-repository" for r in router.registry):
    router.register(r"intermediary-compliance/repository", IntermediaryFolderViewSet, basename="intermediary-repository")
if not any(r[2] == "intermediary-assignments" for r in router.registry):
    router.register(r"intermediary-compliance/assignments", IntermediaryAssignmentViewSet, basename="intermediary-assignments")
if not any(r[2] == "intermediary-partner-reports" for r in router.registry):
    router.register(r"intermediary-compliance/partner-reports", IntermediaryPartnerReportViewSet, basename="intermediary-partner-reports")
if not any(r[2] == "intermediary-generated-reports" for r in router.registry):
    router.register(r"intermediary-compliance/generated-reports", IntermediaryGeneratedReportViewSet, basename="intermediary-generated-reports")

ROUTES = settings.ROUTES
MODULES = settings.MODULES.values()

for route in ROUTES:
    view_module = importlib.import_module(ROUTES[route]["viewset"].rsplit(".", 1)[0])
    router.register(
        route,
        getattr(view_module, ROUTES[route]["viewset"].rsplit(".")[-1]),
        basename=ROUTES[route].get("basename"),
    )


from core.control_assignment_views import ControlAssignmentViewSet, AssignmentSettingsView
from core.defaulters_views import DefaultersTrackerView

urlpatterns = [
    path("compliance/defaulters-tracker/", DefaultersTrackerView.as_view(), name="defaulters-tracker"),
    path("escalation-rules/schedule-level/", EscalationScheduleView.as_view(), name="escalation-schedule-level"),
    path("compliance/assignment-settings/", AssignmentSettingsView.as_view(), name="assignment-settings"),
    path("evidence-repository/delete/<uuid:link_id>/", EvidenceDeleteView.as_view(), name="evidence-delete"),
    path("evidence-repository/copy/", EvidenceCopyView.as_view(), name="evidence-copy"),
    path("evidence-repository/", EvidenceRepositoryView.as_view(), name="evidence-repository"),
    path("", include(router.urls)),
    path("iam/", include("iam.urls")),
    path("serdes/", include("serdes.urls")),
    path("data-wizard/", include("data_wizard.urls")),
    path("settings/", include("global_settings.urls")),
    path("user-preferences/", UserPreferencesView.as_view(), name="user-preferences"),
    path("chat/", include("chat.urls")),
    path("ebios-rm/", include("ebios_rm.urls")),
    path("", include("doc_management.urls")),
    path("privacy/", include("privacy.urls")),
    path("resilience/", include("resilience.urls")),
    path("crq/", include("crq.urls")),
    path("pmbok/", include("pmbok.urls")),
    path("metrology/", include("metrology.urls")),
    path("", include("portals.urls")),
    path("csrf/", get_csrf_token, name="get_csrf_token"),
    path("health/", healthcheck, name="healthcheck"),
    path("build/", get_build, name="get_build"),
    path(
        "evidences/<uuid:pk>/upload/",
        UploadAttachmentView.as_view(),
        name="upload",
    ),
    path(
        "evidence-revisions/<uuid:pk>/upload/",
        UploadAttachmentView.as_view(),
        name="upload",
    ),
    path("get_counters/", get_counters_view, name="get_counters_view"),
    path("get_metrics/", get_metrics_view, name="get_metrics_view"),
    path(
        "analytics/export/xlsx/",
        get_analytics_export_xlsx,
        name="get_analytics_export_xlsx",
    ),
    path(
        "get_audits_metrics/", get_audits_metrics_view, name="get_audits_metrics_view"
    ),
    path("get_user_kpis/", get_user_kpis_view, name="get_user_kpis_view"),
    path(
        "get_combined_assessments_status/",
        get_combined_assessments_status_view,
        name="get_combined_assessments_status_view",
    ),
    path(
        "get_governance_calendar_data/",
        get_governance_calendar_data_view,
        name="get_governance_calendar_data_view",
    ),
    path("agg_data/", get_agg_data, name="get_agg_data"),
    path("composer_data/", get_composer_data, name="get_composer_data"),
    path("i18n/", include("django.conf.urls.i18n")),
    path(
        "accounts/oidc/", include("iam.sso.oidc.urls")
    ),  # NOTE: This has to be placed before the allauth urls, otherwise our OIDC login implementation will not be used
    path(
        "accounts/saml/", include("iam.sso.saml.urls")
    ),  # NOTE: This has to be placed before the allauth urls, otherwise our ACS implementation will not be used
    path("accounts/", include("allauth.urls")),
    path("_allauth/", include("allauth.headless.urls")),
    path(
        "requirement-assessments/<uuid:pk>/suggestions/applied-controls/",
        RequirementAssessmentViewSet.create_suggested_applied_controls,
    ),
    path(
        "compliance-assessments/<uuid:pk>/suggestions/applied-controls/",
        ComplianceAssessmentViewSet.create_suggested_applied_controls,
    ),
    path(
        "compliance-assessments/<uuid:pk>/action-plan/",
        ComplianceAssessmentActionPlanList.as_view(),
    ),
    path(
        "compliance-assessments/<uuid:pk>/action-plan/budget-overview/",
        ComplianceAssessmentActionPlanBudgetOverview.as_view(),
    ),
    path(
        "compliance-assessments/<uuid:pk>/evidences-list/",
        ComplianceAssessmentEvidenceList.as_view(),
    ),
    path(
        "risk-assessments/<uuid:pk>/action-plan/",
        RiskAssessmentActionPlanList.as_view(),
    ),
    path(
        "risk-assessments/<uuid:pk>/action-plan/budget-overview/",
        RiskAssessmentActionPlanBudgetOverview.as_view(),
    ),
    path(
        "mapping-libraries/",
        MappingLibrariesList.as_view(),
    ),
    path(
        "folders/<uuid:pk>/users/",
        UserRolesOnFolderList.as_view(),
        name="user-perms-on-folder-list",
    ),
    path(
        "intermediary-compliance/generate-report/",
        IntermediaryReportGenerationView.as_view(),
        name="intermediary-generate-report",
    ),
    path(
        "intermediary-compliance/scopes/",
        IntermediaryScopesView.as_view(),
        name="intermediary-scopes",
    ),
    path(
        "intermediary-compliance/pending-status/",
        IntermediaryPendingStatusView.as_view(),
        name="intermediary-pending-status",
    ),
    path(
        "intermediary-compliance/generate-pdf-report/",
        IntermediaryReportPdfView.as_view(),
        name="intermediary-generate-pdf-report",
    ),
    path("search/", global_search, name="global-search"),
    path("quick-start/", QuickStartView.as_view(), name="quick-start"),
    path("content-types/", ContentTypeListView.as_view(), name="content-types-list"),

    path(
        "task-nodes/<uuid:pk>/evidences/",
        TaskNodeEvidenceList.as_view(),
    ),
    path("evidence-management/submit/", EvidenceSubmitView.as_view(), name="evidence-submit"),
    path("evidence-management/review/<uuid:link_id>/", EvidenceReviewActionView.as_view(), name="evidence-review"),
    path("control-assignments-report/summary/", ControlAssignmentReportSummaryView.as_view(), name="control-report-summary"),
    path("control-assignments-report/controls/", ControlAssignmentReportControlsView.as_view(), name="control-report-controls"),
    path("notifications/", NotificationListView.as_view(), name="notifications-list"),
    path("notifications/unread-count/", NotificationUnreadCountView.as_view(), name="notifications-unread-count"),
    path("notifications/<uuid:notification_id>/read/", NotificationMarkReadView.as_view(), name="notification-mark-read"),
    path("notifications/read-all/", NotificationMarkAllReadView.as_view(), name="notifications-mark-all-read"),
    path("notifications/read-by-task/", NotificationMarkReadByTaskView.as_view(), name="notifications-mark-read-by-task"),
    path("escalation/manual/", EscalationManualTriggerView.as_view(), name="escalation-manual"),
    path("escalation/logs/", EscalationLogListView.as_view(), name="escalation-logs"),
    path("escalation/admin-users/", EscalationAdminUsersView.as_view(), name="escalation-admin-users"),
    path("compliance-assessments/<uuid:pk>/phase-transition/", ComplianceAssessmentPhaseTransitionView.as_view(), name="compliance-phase-transition"),
]

# Additional modules take precedence over the default modules
for index, module in enumerate(MODULES):
    urlpatterns.insert(index, (path(module["path"], include(module["module"]))))

if settings.DEBUG:
    # Browsable API is only available in DEBUG mode
    urlpatterns += [
        path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
    ]
