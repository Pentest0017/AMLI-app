import io
import os
import base64
import logging
from datetime import datetime
from django.db.models import Q
from django.utils import timezone
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import weasyprint

from core.models import (
    ComplianceAssessment,
    RequirementNode,
    Framework,
    ControlAssignment,
    AssessmentControlSnapshot,
    AuditEvidenceLink,
    RequirementAssessment,
    AssignmentChangeLog,
    User,
)
from core.audit_lifecycle import get_active_evidence_link

logger = logging.getLogger(__name__)


def calculate_control_status(ra, ca, active_link):
    """
    Authoritative single-source-of-truth helper function to calculate control workflow status.
    Shared across /recap API, AuditReportDataCollector, and report PDF rendering.
    
    Status precedence:
    1. NOT_APPLICABLE: if ra is present and ra.result == 'not_applicable'
    2. Active Evidence Link Review Status:
       - PENDING_REVIEW -> PENDING_REVIEW
       - APPROVED -> APPROVED
       - REJECTED -> REJECTED
       - (any other review status or active link present) -> PENDING_EVIDENCE
    3. Assigned SPOC:
       - if ca is present and ca.spoc_user is present -> PENDING_EVIDENCE
    4. Default:
       - NOT_ASSIGNED
    """
    if ra and getattr(ra, "result", None) == "not_applicable":
        return "NOT_APPLICABLE"

    if active_link:
        review_status = getattr(active_link, "review_status", None)
        if review_status == "PENDING_REVIEW":
            return "PENDING_REVIEW"
        elif review_status == "APPROVED":
            return "APPROVED"
        elif review_status == "REJECTED":
            return "REJECTED"
        else:
            return "PENDING_EVIDENCE"

    if ca and getattr(ca, "spoc_user", None):
        return "PENDING_EVIDENCE"

    return "NOT_ASSIGNED"


class AuditReportDataCollector:
    """
    Authoritative single-source-of-truth data collector for a specific audit (ComplianceAssessment).
    Bulk-fetches all related models once to prevent N+1 queries.
    Strictly scopes 100% of data to the selected audit.
    Enforces strict segregation between current active evidence (is_active=True) and historical evidence (is_active=False).
    """

    def __init__(self, assessment_id):
        self.assessment_id = assessment_id
        self.assessment = ComplianceAssessment.objects.select_related(
            "framework", "folder"
        ).filter(id=assessment_id).first()

    def validate_data_integrity(self, active_links):
        """
        Lightweight report data integrity pass.
        Validates that every active link has is_active == True and enforces that at most ONE active link exists per requirement.
        """
        seen_requirements = {}
        for link in active_links:
            if not link.is_active:
                logger.error(f"Data Integrity Error: Inactive link {link.id} found in active_links collection.")

            req_id = link.assessment_control.requirement_node_id if (link.assessment_control and link.assessment_control.requirement_node_id) else None
            if req_id:
                if req_id in seen_requirements:
                    existing_link_id = seen_requirements[req_id]
                    logger.error(
                        f"Data Integrity Violation: Multiple active evidence links detected for requirement {req_id} "
                        f"(Link {existing_link_id} and Link {link.id}). Strict single-active-link invariant violated!"
                    )
                else:
                    seen_requirements[req_id] = link.id

    def collect(self, report_type="full", selected_sections=None):
        if not self.assessment:
            raise ValueError(f"Audit with ID {self.assessment_id} not found.")

        if selected_sections is None:
            selected_sections = [
                "executive_summary",
                "audit_info",
                "scope_framework",
                "compliance_overview",
                "requirement_results",
                "evidence_details",
                "assignments",
                "findings_observations",
                "action_plans",
                "activity_history",
                "appendix",
            ]

        # 1. Audit Metadata
        fw_name = self.assessment.framework.name if self.assessment.framework else "Custom Upload"
        if not self.assessment.framework and hasattr(self.assessment, 'framework_name'):
            fw_name = getattr(self.assessment, 'framework_name', 'Custom Upload')

        metadata = {
            "id": str(self.assessment.id),
            "name": self.assessment.name,
            "description": self.assessment.description or "Not specified",
            "status": self.assessment.status or "In Progress",
            "version": getattr(self.assessment, "version", "1.0"),
            "created_at": self.assessment.created_at.strftime("%d %B %Y, %I:%M %p") if self.assessment.created_at else "Not specified",
            "updated_at": self.assessment.updated_at.strftime("%d %B %Y, %I:%M %p") if self.assessment.updated_at else "Not specified",
            "start_date": self.assessment.start_date.strftime("%d %B %Y") if getattr(self.assessment, "start_date", None) else "Not specified",
            "due_date": self.assessment.due_date.strftime("%d %B %Y") if getattr(self.assessment, "due_date", None) else "Not specified",
            "audit_end_date": self.assessment.audit_end_date.strftime("%d %B %Y") if getattr(self.assessment, "audit_end_date", None) else "Not specified",
            "framework_name": fw_name,
            "framework_version": getattr(self.assessment.framework, "version", "1.0") if self.assessment.framework else "1.0",
            "domain": self.assessment.folder.name if self.assessment.folder else "Not specified",
            "campaign": getattr(self.assessment, "campaign", None) or "Not specified",
            "perimeter": getattr(self.assessment, "perimeter", None) or "All Organizational Scope",
            "author": getattr(self.assessment, "author_email", None) or "System Admin",
            "reviewer": getattr(self.assessment, "reviewer_email", None) or "Lead Reviewer",
            "owner": getattr(self.assessment, "owner_email", None) or "CISO Office",
            "organization": "Enterprise Compliance Organization",
            "generated_at": timezone.now().strftime("%d %B %Y, %I:%M %p"),
        }

        # 2. Scope & Requirement Nodes
        req_assessments = list(RequirementAssessment.objects.filter(
            compliance_assessment=self.assessment,
            requirement__assessable=True
        ).select_related("requirement").order_by("requirement__order_id", "requirement__ref_id"))

        if req_assessments:
            req_nodes = [ra.requirement for ra in req_assessments if ra.requirement]
        elif self.assessment.framework:
            req_nodes = list(RequirementNode.objects.filter(
                framework=self.assessment.framework, assessable=True
            ).order_by("order_id", "ref_id"))
        else:
            snapshots = AssessmentControlSnapshot.objects.filter(
                compliance_assessment=self.assessment, is_active=True
            ).select_related("requirement_node")
            req_nodes = list(set([s.requirement_node for s in snapshots if s.requirement_node]))
            req_nodes.sort(key=lambda r: (r.order_id or 0, r.ref_id or ""))

        req_node_ids = [r.id for r in req_nodes]

        assignments_map = {
            ca.requirement_node_id: ca
            for ca in ControlAssignment.objects.filter(
                requirement_node_id__in=req_node_ids,
                is_active=True
            ).select_related("spoc_user", "reviewer_user").prefetch_related("evidence_requirements")
        }

        req_assessments_map = {
            ra.requirement_id: ra
            for ra in req_assessments
        }

        snapshots = list(AssessmentControlSnapshot.objects.filter(
            compliance_assessment=self.assessment
        ))

        # Active links strictly scoped to this audit and its active requirements (is_active=True)
        active_links = list(AuditEvidenceLink.objects.filter(
            Q(assessment_control__compliance_assessment=self.assessment, assessment_control__requirement_node_id__in=req_node_ids) |
            Q(control_evidence_mapping__control_assignment__in=assignments_map.values()) |
            Q(assessment_control__control_assignment__in=assignments_map.values()),
            is_active=True
        ).select_related("evidence", "evidence_revision", "control_evidence_mapping", "reviewed_by", "assessment_control__requirement_node").distinct().order_by("-created_at"))

        # Map active links per requirement node ID
        active_links_by_req_id = {}
        for link in active_links:
            r_id = None
            if link.assessment_control and link.assessment_control.requirement_node_id:
                r_id = link.assessment_control.requirement_node_id
            elif link.control_evidence_mapping and link.control_evidence_mapping.control_assignment:
                r_id = link.control_evidence_mapping.control_assignment.requirement_node_id
            elif link.assessment_control and link.assessment_control.control_assignment:
                r_id = link.assessment_control.control_assignment.requirement_node_id

            if r_id and r_id in req_node_ids and r_id not in active_links_by_req_id:
                active_links_by_req_id[r_id] = link

        # Historical links strictly scoped to this audit and its requirements (is_active=False)
        historical_links = list(AuditEvidenceLink.all_objects.filter(
            Q(assessment_control__compliance_assessment=self.assessment, assessment_control__requirement_node_id__in=req_node_ids) |
            Q(control_evidence_mapping__control_assignment__in=assignments_map.values()) |
            Q(assessment_control__control_assignment__in=assignments_map.values()),
            is_active=False
        ).select_related("evidence", "evidence_revision", "control_evidence_mapping", "reviewed_by", "assessment_control__requirement_node").distinct().order_by("-created_at"))

        # Run integrity validation pass
        self.validate_data_integrity(active_links)

        # 3. Current Status Breakdown & Control Processing
        status_counts = {
            "NOT_ASSIGNED": 0,
            "PENDING_EVIDENCE": 0,
            "PENDING_REVIEW": 0,
            "APPROVED": 0,
            "REJECTED": 0,
            "NOT_APPLICABLE": 0,
        }

        controls_list = []
        domain_groups = {}
        findings_list = []

        for req in req_nodes:
            ca = assignments_map.get(req.id)
            ra = req_assessments_map.get(req.id)
            active_link = active_links_by_req_id.get(req.id)

            # Resolve domain
            domain_name = "General Security Controls"
            if getattr(req, "parent_urn", None):
                domain_name = req.parent_urn
            elif req.ref_id:
                ref_str = str(req.ref_id).strip()
                if "." in ref_str:
                    domain_name = f"Domain {ref_str.split('.')[0]}"
                elif "-" in ref_str:
                    domain_name = f"Domain {ref_str.split('-')[0]}"
                elif len(ref_str) <= 3 and ref_str.isdigit():
                    domain_name = f"Domain {ref_str}"

            if domain_name not in domain_groups:
                domain_groups[domain_name] = {
                    "domain_name": domain_name,
                    "total": 0,
                    "approved": 0,
                    "pending_review": 0,
                    "pending_evidence": 0,
                    "rejected": 0,
                    "not_assigned": 0,
                    "not_applicable": 0,
                }

            domain_groups[domain_name]["total"] += 1

            # Authoritative current evidence status determination matching /recap
            status_name = calculate_control_status(ra, ca, active_link)
            if status_name == "NOT_APPLICABLE":
                domain_groups[domain_name]["not_applicable"] += 1
            elif status_name == "NOT_ASSIGNED":
                domain_groups[domain_name]["not_assigned"] += 1
            elif status_name == "PENDING_EVIDENCE":
                domain_groups[domain_name]["pending_evidence"] += 1
            elif status_name == "PENDING_REVIEW":
                domain_groups[domain_name]["pending_review"] += 1
            elif status_name == "APPROVED":
                domain_groups[domain_name]["approved"] += 1
            elif status_name == "REJECTED":
                domain_groups[domain_name]["rejected"] += 1

            status_counts[status_name] += 1

            spoc_email = ca.spoc_user.email if (ca and ca.spoc_user) else "Unassigned"
            reviewer_email = ca.reviewer_user.email if (ca and ca.reviewer_user) else "Unassigned"

            evidence_file_name = active_link.evidence.name if (active_link and active_link.evidence) else "No file uploaded"
            feedback_text = active_link.reviewer_feedback if active_link else ""
            obs_text = ra.observation if ra else ""

            # Ensure RequirementAssessment result is synchronized with active link status
            current_result = ra.result if ra else "not_assessed"
            if status_name == "PENDING_REVIEW" and current_result == "non_compliant":
                current_result = "in_review"

            ctrl_entry = {
                "ref_id": req.ref_id or f"REQ-{req.order_id}",
                "name": req.name,
                "description": req.description or "No description provided.",
                "domain": domain_name,
                "spoc": spoc_email,
                "reviewer": reviewer_email,
                "status": status_name,
                "result": current_result,
                "evidence_name": evidence_file_name,
                "feedback": feedback_text,
                "observation": obs_text,
                "due_date": ca.due_date.strftime("%d %b %Y") if (ca and ca.due_date) else "Not set",
            }
            controls_list.append(ctrl_entry)

            # Record Findings ONLY if CURRENT active link status is REJECTED or CURRENT result is non_compliant
            if status_name == "REJECTED" or current_result == "non_compliant":
                findings_list.append({
                    "ref_id": ctrl_entry["ref_id"],
                    "title": ctrl_entry["name"],
                    "domain": domain_name,
                    "spoc": spoc_email,
                    "reviewer": reviewer_email,
                    "evidence_name": evidence_file_name,
                    "feedback": feedback_text or "Rejected by reviewer during evidence verification.",
                    "observation": obs_text or "Control requirements not fully satisfied.",
                    "result": current_result,
                    "date": active_link.reviewed_at.strftime("%d %b %Y, %I:%M %p") if (active_link and active_link.reviewed_at) else "Recent",
                })

        total_controls = len(req_nodes)
        global_score_dict = self.assessment.get_global_score(req_assessments)
        maturity_score = global_score_dict.get("maturity_score")
        if maturity_score is not None and maturity_score >= 0:
            overall_compliance = round(float(maturity_score), 1)
        else:
            approved_count = status_counts["APPROVED"]
            overall_compliance = round((approved_count / total_controls * 100), 1) if total_controls > 0 else 100.0

        # Calculate domain percentages
        domain_list = []
        for d_name, d_data in domain_groups.items():
            d_total = d_data["total"]
            d_appr = d_data["approved"]
            d_pct = round((d_appr / d_total * 100), 1) if d_total > 0 else 0.0
            d_data["compliance_pct"] = d_pct
            domain_list.append(d_data)

        # 4. Current Evidence Register (is_active=True ONLY)
        evidence_register = []
        for link in active_links:
            req_ref = "General Control"
            if link.assessment_control and link.assessment_control.requirement_node:
                req_ref = link.assessment_control.requirement_node.ref_id or link.assessment_control.requirement_node.name

            evidence_register.append({
                "id": str(link.evidence.id),
                "name": link.evidence.name,
                "requirement": req_ref,
                "uploaded_by": link.control_evidence_mapping.mapped_by.email if (link.control_evidence_mapping and link.control_evidence_mapping.mapped_by) else "SPOC User",
                "uploaded_on": link.created_at.strftime("%d %b %Y, %I:%M %p"),
                "version": f"v{link.evidence_revision.version}" if link.evidence_revision else "v1.0",
                "review_status": link.review_status,
                "reviewer": link.reviewed_by.email if link.reviewed_by else "Unassigned",
                "reviewer_feedback": link.reviewer_feedback or "No feedback",
                "is_active": True,
            })

        # 5. Historical Evidence Register (is_active=False ONLY)
        historical_evidence_register = []
        for link in historical_links:
            req_ref = "General Control"
            if link.assessment_control and link.assessment_control.requirement_node:
                req_ref = link.assessment_control.requirement_node.ref_id or link.assessment_control.requirement_node.name

            historical_evidence_register.append({
                "id": str(link.evidence.id),
                "name": link.evidence.name,
                "requirement": req_ref,
                "uploaded_by": link.control_evidence_mapping.mapped_by.email if (link.control_evidence_mapping and link.control_evidence_mapping.mapped_by) else "SPOC User",
                "uploaded_on": link.created_at.strftime("%d %b %Y, %I:%M %p"),
                "version": f"v{link.evidence_revision.version}" if link.evidence_revision else "v1.0",
                "review_status": link.review_status,
                "reviewer": link.reviewed_by.email if link.reviewed_by else "Unassigned",
                "reviewer_feedback": link.reviewer_feedback or "Historical Rejection / Superseded",
                "is_active": False,
            })

        # 6. Assignments List
        assignments_list = []
        for ca in assignments_map.values():
            active_link = get_active_evidence_link(ca)
            ev_stat = active_link.review_status if active_link else "PENDING_EVIDENCE"
            assignments_list.append({
                "ref_id": ca.requirement_node.ref_id if ca.requirement_node else "Control",
                "spoc": ca.spoc_user.email if ca.spoc_user else "Unassigned",
                "reviewer": ca.reviewer_user.email if ca.reviewer_user else "Unassigned",
                "assigned_date": ca.created_at.strftime("%d %b %Y"),
                "due_date": ca.due_date.strftime("%d %b %Y") if ca.due_date else "Not set",
                "evidence_status": ev_stat,
            })

        # 7. Activity History
        activity_logs = []
        change_logs = AssignmentChangeLog.objects.filter(
            control_assignment__in=assignments_map.values()
        ).select_related("changed_by", "control_assignment").order_by("-created_at")[:50]

        for clog in change_logs:
            activity_logs.append({
                "timestamp": clog.created_at.strftime("%d %b %Y, %I:%M %p"),
                "user": clog.changed_by.email if clog.changed_by else "System",
                "event": f"Control Assignment {clog.field_changed} updated",
                "details": f"{clog.field_changed}: '{clog.previous_user or ''}' -> '{clog.new_user or ''}'",
            })

        if not activity_logs:
            activity_logs = [
                {
                    "timestamp": metadata["created_at"],
                    "user": metadata["author"],
                    "event": "Audit Checklist Initialized",
                    "details": f"Audit scope established for {metadata['framework_name']}.",
                }
            ]

        return {
            "metadata": metadata,
            "status_counts": status_counts,
            "historical_rejections_count": len(historical_evidence_register),
            "total_controls": total_controls,
            "overall_compliance": overall_compliance,
            "domains": domain_list,
            "controls": controls_list,
            "findings": findings_list,
            "evidence_register": evidence_register,
            "historical_evidence": historical_evidence_register,
            "assignments": assignments_list,
            "activity_logs": activity_logs,
            "report_type": report_type,
            "selected_sections": selected_sections,
        }


class AuditReportPdfRenderer:
    """
    Renders audit report data into a professional HTML template and compiles it into a downloadable PDF binary using WeasyPrint 68.1 and Matplotlib.
    """

    @staticmethod
    def generate_chart_base64(status_counts):
        """Generates a Matplotlib donut chart for compliance status distribution."""
        labels = ["Approved / Compliant", "Pending Review", "Pending Evidence", "Rejected", "Not Assigned", "Not Applicable"]
        counts = [
            status_counts.get("APPROVED", 0),
            status_counts.get("PENDING_REVIEW", 0),
            status_counts.get("PENDING_EVIDENCE", 0),
            status_counts.get("REJECTED", 0),
            status_counts.get("NOT_ASSIGNED", 0),
            status_counts.get("NOT_APPLICABLE", 0),
        ]
        colors = ["#10b981", "#f59e0b", "#d97706", "#f43f5e", "#8b5cf6", "#64748b"]

        filtered_labels = [l for l, c in zip(labels, counts) if c > 0]
        filtered_counts = [c for c in counts if c > 0]
        filtered_colors = [col for col, c in zip(colors, counts) if c > 0]

        if not filtered_counts:
            filtered_labels = ["No Data"]
            filtered_counts = [1]
            filtered_colors = ["#cbd5e1"]

        fig, ax = plt.subplots(figsize=(5, 3.5), subplot_kw=dict(aspect="equal"))
        wedges, texts, autotexts = ax.pie(
            filtered_counts,
            colors=filtered_colors,
            autopct="%1.1f%%" if sum(counts) > 0 else "",
            pctdistance=0.75,
            startangle=140,
            textprops=dict(color="#ffffff", weight="bold", size=8),
        )
        centre_circle = plt.Circle((0, 0), 0.55, fc="white")
        fig.gca().add_artist(centre_circle)
        ax.legend(wedges, filtered_labels, title="Status Breakdown", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1), fontsize=8)
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=200, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"

    def render_pdf(self, report_data):
        meta = report_data["metadata"]
        counts = report_data["status_counts"]
        chart_b64 = self.generate_chart_base64(counts)
        sections = set(report_data.get("selected_sections", []))
        report_type = report_data.get("report_type", "full")

        from core.models import CustomReportTemplate
        target_type = report_type if report_type in ["compliance", "intermediary_compliance"] else "compliance"
        custom_tmpl = CustomReportTemplate.objects.filter(report_type=target_type, is_active=True).first()

        if custom_tmpl:
            custom_title = custom_tmpl.title or "COMPREHENSIVE AUDIT DOSSIER & COMPLIANCE REPORT"
            custom_header = custom_tmpl.header_text or "CISO Assistant Audit Dossier"
            custom_footer = custom_tmpl.footer_text or "CONFIDENTIAL"
            custom_company = custom_tmpl.company_name or meta.get("organization", "Enterprise Compliance Organization")
            primary_color = custom_tmpl.primary_color or "#6366f1"
            custom_exec_text = custom_tmpl.custom_executive_summary_text or ""
            custom_concluding_text = custom_tmpl.custom_concluding_notes or ""
            custom_findings_t = custom_tmpl.custom_findings_title or "6. Reviewer Findings & Audit Observations"
            custom_evidence_t = custom_tmpl.custom_evidence_title or "5. Evidence Register (Active Submissions)"
            custom_activity_t = custom_tmpl.custom_activity_title or "7. Audit Trail & Chronological Log"

            if not custom_tmpl.show_executive_summary:
                sections.discard("executive_summary")
            if not custom_tmpl.show_findings:
                sections.discard("findings_observations")
            if not custom_tmpl.show_evidence_details:
                sections.discard("evidence_details")
            if not custom_tmpl.show_activity_history:
                sections.discard("activity_history")
        else:
            custom_title = "COMPREHENSIVE AUDIT DOSSIER & COMPLIANCE REPORT"
            custom_header = "CISO Assistant Audit Dossier"
            custom_footer = "CONFIDENTIAL"
            custom_company = meta.get("organization", "Enterprise Compliance Organization")
            primary_color = "#6366f1"
            custom_exec_text = ""
            custom_concluding_text = ""
            custom_findings_t = "6. Reviewer Findings & Audit Observations"
            custom_evidence_t = "5. Evidence Register (Active Submissions)"
            custom_activity_t = "7. Audit Trail & Chronological Log"

        from core.notification_service import _get_logo_base64
        logo_b64 = _get_logo_base64(theme="light")
        logo_html = (
            f'<img src="data:image/svg+xml;base64,{logo_b64}" style="max-height: 70px; max-width: 260px; margin-bottom: 20px; display: inline-block;" />'
            if logo_b64
            else f'<div class="cover-brand">{custom_company}</div>'
        )

        # HTML / CSS Template
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{meta['name']} - Audit Report</title>
<style>
  @page {{
    size: A4 portrait;
    margin: 18mm 15mm 20mm 15mm;
    @top-left {{
      content: "{custom_header}";
      font-size: 8pt;
      font-family: Helvetica, Arial, sans-serif;
      color: #64748b;
    }}
    @top-right {{
      content: "{meta['name']} | {meta['framework_name']}";
      font-size: 8pt;
      font-family: Helvetica, Arial, sans-serif;
      color: #64748b;
    }}
    @bottom-left {{
      content: "{custom_footer} | Generated: {meta['generated_at']}";
      font-size: 8pt;
      font-family: Helvetica, Arial, sans-serif;
      color: #64748b;
    }}
    @bottom-right {{
      content: "Page " counter(page) " of " counter(pages);
      font-size: 8pt;
      font-weight: bold;
      font-family: Helvetica, Arial, sans-serif;
      color: #0f172a;
    }}
  }}

  @page:first {{
    margin: 0;
    @top-left {{ content: none; }}
    @top-right {{ content: none; }}
    @bottom-left {{ content: none; }}
    @bottom-right {{ content: none; }}
  }}

  body {{
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    color: #1e293b;
    font-size: 9.5pt;
    line-height: 1.45;
  }}

  .cover-page {{
    height: 100vh;
    padding: 25mm 20mm 20mm 20mm;
    box-sizing: border-box;
    background: #ffffff;
    color: #1e293b;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    page-break-after: always;
  }}

  .cover-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 12px;
    border-bottom: 1px solid #e2e8f0;
    font-size: 8.5pt;
    color: #64748b;
    font-family: monospace;
  }}

  .cover-title-card {{
    margin-top: 25px;
    margin-bottom: 20px;
    padding: 22px 20px;
    border-radius: 10px;
    background-color: rgba(99, 102, 241, 0.06);
    border-left: 5px solid {primary_color};
  }}

  .cover-brand {{
    font-size: 9.5pt;
    font-weight: 800;
    letter-spacing: 2px;
    color: #64748b;
    text-transform: uppercase;
    margin-bottom: 6px;
  }}

  .cover-title {{
    font-size: 22pt;
    font-weight: 800;
    line-height: 1.2;
    color: {primary_color};
    margin-bottom: 6px;
  }}

  .cover-subtitle {{
    font-size: 11pt;
    color: #475569;
    font-weight: 500;
  }}

  .cover-badge {{
    display: inline-block;
    padding: 4px 10px;
    background: rgba(99, 102, 241, 0.1);
    border: 1px solid {primary_color};
    color: {primary_color};
    border-radius: 14px;
    font-size: 8.5pt;
    font-weight: bold;
    margin-top: 8px;
  }}

  .cover-exec-card {{
    margin-top: 15px;
    padding: 14px 18px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
  }}

  .cover-exec-title {{
    font-size: 8pt;
    text-transform: uppercase;
    font-weight: bold;
    color: #64748b;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
  }}

  .cover-exec-text {{
    font-size: 9pt;
    color: #334155;
    line-height: 1.45;
  }}

  .cover-score-card {{
    margin-top: 15px;
    padding: 14px 18px;
    background: #eef2ff;
    border: 1px solid #c7d2fe;
    border-radius: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}

  .cover-score-label {{
    font-weight: bold;
    color: #1e293b;
    font-size: 10pt;
  }}

  .cover-score-sub {{
    font-size: 8pt;
    color: #64748b;
    margin-top: 2px;
  }}

  .cover-score-badge {{
    background-color: {primary_color};
    color: #ffffff;
    padding: 6px 14px;
    border-radius: 6px;
    font-weight: bold;
    font-size: 10.5pt;
  }}

  .cover-meta-grid {{
    margin-top: 20px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    background: #f8fafc;
    padding: 15px;
    border-radius: 10px;
    border: 1px solid #e2e8f0;
  }}

  .cover-meta-item {{
    font-size: 9pt;
  }}

  .cover-meta-label {{
    color: #64748b;
    font-size: 7.5pt;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 600;
  }}

  .cover-meta-val {{
    color: #0f172a;
    font-weight: 600;
    margin-top: 2px;
  }}

  .cover-footer {{
    margin-top: auto;
    padding-top: 15px;
    border-top: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    font-size: 8.5pt;
    color: #64748b;
    font-family: monospace;
  }}

  .section-title {{
    font-size: 15pt;
    font-weight: 800;
    color: #0f172a;
    border-bottom: 2px solid {primary_color};
    padding-bottom: 5px;
    margin-top: 25px;
    margin-bottom: 15px;
    page-break-after: avoid;
  }}

  .grid-2 {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 15px;
  }}

  .card {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 12px 15px;
    margin-bottom: 12px;
  }}

  .metric-big {{
    font-size: 28pt;
    font-weight: 800;
    color: #10b981;
    line-height: 1;
  }}

  .metric-label {{
    font-size: 8.5pt;
    color: #64748b;
    text-transform: uppercase;
    font-weight: bold;
    margin-top: 4px;
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
    margin-bottom: 15px;
    font-size: 8.5pt;
  }}

  th {{
    background: #0f172a;
    color: #ffffff;
    text-align: left;
    padding: 7px 9px;
    font-weight: bold;
    font-size: 8pt;
    text-transform: uppercase;
  }}

  td {{
    padding: 6px 9px;
    border-bottom: 1px solid #e2e8f0;
    vertical-align: top;
  }}

  tr:nth-child(even) td {{
    background: #f8fafc;
  }}

  .badge {{
    display: inline-block;
    padding: 2px 7px;
    border-radius: 4px;
    font-size: 7.5pt;
    font-weight: bold;
    text-transform: uppercase;
  }}

  .badge-approved {{ background: #dcfce7; color: #15803d; border: 1px solid #86efac; }}
  .badge-pending-review {{ background: #fef3c7; color: #b45309; border: 1px solid #fde68a; }}
  .badge-pending-evidence {{ background: #ffedd5; color: #c2410c; border: 1px solid #fed7aa; }}
  .badge-rejected {{ background: #ffe4e6; color: #be123c; border: 1px solid #fecdd3; }}
  .badge-unassigned {{ background: #f3e8ff; color: #6b21a8; border: 1px solid #e9d5ff; }}

  .sign-grid {{
    margin-top: 40px;
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 20px;
    page-break-inside: avoid;
  }}

  .sign-box {{
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 15px;
    background: #ffffff;
  }}

  .sign-line {{
    margin-top: 35px;
    border-top: 1px solid #94a3b8;
    padding-top: 5px;
    font-size: 8pt;
    color: #64748b;
  }}
</style>
</head>
<body>

  <!-- COVER PAGE -->
  <div class="cover-page">
    <div>
      <div class="cover-header">
        <span>{custom_header}</span>
        <span style="font-weight: bold; color: {primary_color};">Page 1</span>
      </div>

      <div style="margin-top: 15px;">
        {logo_html}
      </div>

      <div class="cover-title-card" style="background-color: {primary_color}10; border-left: 5px solid {primary_color};">
        <div class="cover-brand">{custom_company}</div>
        <div class="cover-title" style="color: {primary_color};">{custom_title}</div>
        <div class="cover-subtitle">{meta['name']} &bull; {meta['framework_name']}</div>
        <span class="cover-badge" style="border-color: {primary_color}; color: {primary_color};">{meta['framework_name']}</span>
      </div>

      {f'<div class="cover-exec-card"><div class="cover-exec-title">Executive Overview</div><div class="cover-exec-text">{custom_exec_text}</div></div>' if custom_exec_text else ''}

      <div class="cover-score-card">
        <div>
          <div class="cover-score-label">Overall Compliance Score</div>
          <div class="cover-score-sub">Based on active control evaluation and evidence review</div>
        </div>
        <div class="cover-score-badge" style="background-color: {primary_color};">
          {report_data['overall_compliance']}% COMPLIANT
        </div>
      </div>

      <div class="cover-meta-grid">
        <div class="cover-meta-item">
          <div class="cover-meta-label">Audit Status</div>
          <div class="cover-meta-val">{meta['status']}</div>
        </div>
        <div class="cover-meta-item">
          <div class="cover-meta-label">Overall Compliance</div>
          <div class="cover-meta-val">{report_data['overall_compliance']}%</div>
        </div>
        <div class="cover-meta-item">
          <div class="cover-meta-label">Audit Scope</div>
          <div class="cover-meta-val">{meta['perimeter']}</div>
        </div>
        <div class="cover-meta-item">
          <div class="cover-meta-label">Report Date</div>
          <div class="cover-meta-val">{meta['generated_at']}</div>
        </div>
        <div class="cover-meta-item">
          <div class="cover-meta-label">Lead Author / SPOC</div>
          <div class="cover-meta-val">{meta['author']}</div>
        </div>
        <div class="cover-meta-item">
          <div class="cover-meta-label">Reviewer / Auditor</div>
          <div class="cover-meta-val">{meta['reviewer']}</div>
        </div>
      </div>
    </div>
    <div class="cover-footer">
      <div>{custom_footer}</div>
      <div>STRICTLY FOR AUDIT & COMPLIANCE REVIEW</div>
    </div>
  </div>
"""

        # SECTION 1: EXECUTIVE SUMMARY
        if "executive_summary" in sections or report_type == "executive":
            exec_note_html = f'<div class="card" style="background: #f0f4ff; border-left: 4px solid {primary_color}; margin-bottom: 15px;"><strong>Executive Note:</strong> {custom_exec_text}</div>' if custom_exec_text else ''
            html_content += f"""
  <div class="section-title">1. Executive Summary</div>
  {exec_note_html}
  <div class="grid-2">
    <div class="card" style="text-align: center;">
      <div class="metric-big">{report_data['overall_compliance']}%</div>
      <div class="metric-label">Overall Compliance Score</div>
    </div>
    <div class="card">
      <div style="font-size: 9pt; color: #475569;">
        <strong>Audit Summary:</strong> This dossier represents the official compliance assessment results for <strong>{meta['name']}</strong> under <strong>{meta['framework_name']}</strong>.
        Total assessable control requirements: <strong>{report_data['total_controls']}</strong>.
      </div>
    </div>
  </div>

  <div class="grid-2" style="margin-top: 15px;">
    <div>
      <table>
        <thead>
          <tr><th>Current Assessment Status</th><th style="text-align: right;">Count</th><th style="text-align: right;">% Share</th></tr>
        </thead>
        <tbody>
          <tr><td><span class="badge badge-approved">Approved / Compliant</span></td><td style="text-align: right;">{counts['APPROVED']}</td><td style="text-align: right;">{round((counts['APPROVED']/report_data['total_controls']*100), 1) if report_data['total_controls']>0 else 0}%</td></tr>
          <tr><td><span class="badge badge-pending-review">Pending Review</span></td><td style="text-align: right;">{counts['PENDING_REVIEW']}</td><td style="text-align: right;">{round((counts['PENDING_REVIEW']/report_data['total_controls']*100), 1) if report_data['total_controls']>0 else 0}%</td></tr>
          <tr><td><span class="badge badge-pending-evidence">Pending Evidence</span></td><td style="text-align: right;">{counts['PENDING_EVIDENCE']}</td><td style="text-align: right;">{round((counts['PENDING_EVIDENCE']/report_data['total_controls']*100), 1) if report_data['total_controls']>0 else 0}%</td></tr>
          <tr><td><span class="badge badge-rejected">Currently Rejected</span></td><td style="text-align: right;">{counts['REJECTED']}</td><td style="text-align: right;">{round((counts['REJECTED']/report_data['total_controls']*100), 1) if report_data['total_controls']>0 else 0}%</td></tr>
          <tr><td><span class="badge badge-unassigned">Not Assigned</span></td><td style="text-align: right;">{counts['NOT_ASSIGNED']}</td><td style="text-align: right;">{round((counts['NOT_ASSIGNED']/report_data['total_controls']*100), 1) if report_data['total_controls']>0 else 0}%</td></tr>
        </tbody>
      </table>
    </div>
    <div style="text-align: center;">
      <img src="{chart_b64}" style="max-width: 100%; height: auto;" />
    </div>
  </div>
"""

        # SECTION 2: AUDIT INFORMATION
        if "audit_info" in sections:
            html_content += f"""
  <div class="section-title">2. Audit Metadata & Governance</div>
  <table>
    <tr><th width="30%">Metadata Attribute</th><th>Value</th></tr>
    <tr><td>Audit Name</td><td><strong>{meta['name']}</strong></td></tr>
    <tr><td>Audit ID</td><td><code>{meta['id']}</code></td></tr>
    <tr><td>Framework</td><td>{meta['framework_name']} (v{meta['framework_version']})</td></tr>
    <tr><td>Audit Status</td><td>{meta['status']}</td></tr>
    <tr><td>Business Domain / Unit</td><td>{meta['domain']}</td></tr>
    <tr><td>Perimeter / Scope</td><td>{meta['perimeter']}</td></tr>
    <tr><td>Author / SPOC Lead</td><td>{meta['author']}</td></tr>
    <tr><td>Assigned Reviewer</td><td>{meta['reviewer']}</td></tr>
    <tr><td>Audit Period</td><td>{meta['start_date']} to {meta['audit_end_date']}</td></tr>
    <tr><td>Created Date</td><td>{meta['created_at']}</td></tr>
  </table>
"""

        # SECTION 3: DOMAIN ANALYSIS
        if "scope_framework" in sections or "compliance_overview" in sections:
            html_content += f"""
  <div class="section-title">3. Domain-Level Compliance Analysis</div>
  <table>
    <thead>
      <tr>
        <th>Domain Name</th>
        <th style="text-align: center;">Total Controls</th>
        <th style="text-align: center;">Approved</th>
        <th style="text-align: center;">Pending Review</th>
        <th style="text-align: center;">Pending Evidence</th>
        <th style="text-align: center;">Rejected</th>
        <th style="text-align: right;">Compliance %</th>
      </tr>
    </thead>
    <tbody>
"""
            for dom in report_data["domains"]:
                html_content += f"""
      <tr>
        <td><strong>{dom['domain_name']}</strong></td>
        <td style="text-align: center;">{dom['total']}</td>
        <td style="text-align: center; color: #10b981; font-weight: bold;">{dom['approved']}</td>
        <td style="text-align: center; color: #f59e0b;">{dom['pending_review']}</td>
        <td style="text-align: center; color: #d97706;">{dom['pending_evidence']}</td>
        <td style="text-align: center; color: #f43f5e;">{dom['rejected']}</td>
        <td style="text-align: right; font-weight: bold;">{dom['compliance_pct']}%</td>
      </tr>
"""
            html_content += """
    </tbody>
  </table>
"""

        # SECTION 4: FULL REQUIREMENT RESULTS REGISTER
        if "requirement_results" in sections and report_type != "executive":
            html_content += f"""
  <div class="section-title" style="page-break-before: always;">4. Complete Control & Requirement Register ({len(report_data['controls'])} Controls)</div>
  <table>
    <thead>
      <tr>
        <th width="10%">Ref ID</th>
        <th width="25%">Requirement Name</th>
        <th width="20%">Domain</th>
        <th width="15%">SPOC / Reviewer</th>
        <th width="15%">Active Status</th>
        <th width="15%">Latest Evidence</th>
      </tr>
    </thead>
    <tbody>
"""
            for c in report_data["controls"]:
                badge_cls = "badge-pending-evidence"
                if c["status"] == "APPROVED": badge_cls = "badge-approved"
                elif c["status"] == "PENDING_REVIEW": badge_cls = "badge-pending-review"
                elif c["status"] == "REJECTED": badge_cls = "badge-rejected"
                elif c["status"] == "NOT_ASSIGNED": badge_cls = "badge-unassigned"

                html_content += f"""
      <tr>
        <td><code>{c['ref_id']}</code></td>
        <td><strong>{c['name']}</strong></td>
        <td><span style="font-size: 7.5pt; color: #64748b;">{c['domain']}</span></td>
        <td><span style="font-size: 7.5pt;">{c['spoc']}<br/><i style="color: #64748b;">Rev: {c['reviewer']}</i></span></td>
        <td><span class="badge {badge_cls}">{c['status'].replace('_', ' ')}</span></td>
        <td><span style="font-size: 7.5pt;">{c['evidence_name']}</span></td>
      </tr>
"""
            html_content += """
    </tbody>
  </table>
"""

        # SECTION 5: EVIDENCE REGISTER (ACTIVE VS HISTORICAL)
        if "evidence_details" in sections:
            html_content += f"""
  <div class="section-title" style="page-break-before: always;">{custom_evidence_t}</div>
"""
            if not report_data["evidence_register"]:
                html_content += "<p style='font-style: italic; color: #64748b;'>No active evidence files have been uploaded for this audit yet.</p>"
            else:
                html_content += """
  <table>
    <thead>
      <tr>
        <th>Evidence Name</th>
        <th>Control Ref</th>
        <th>Uploaded By</th>
        <th>Uploaded On</th>
        <th>Version</th>
        <th>Current Status</th>
        <th>Reviewer Feedback</th>
      </tr>
    </thead>
    <tbody>
"""
                for ev in report_data["evidence_register"]:
                    b_cls = "badge-pending-review"
                    if ev["review_status"] == "APPROVED": b_cls = "badge-approved"
                    elif ev["review_status"] == "REJECTED": b_cls = "badge-rejected"

                    html_content += f"""
      <tr>
        <td><strong>{ev['name']}</strong></td>
        <td><code>{ev['requirement']}</code></td>
        <td>{ev['uploaded_by']}</td>
        <td>{ev['uploaded_on']}</td>
        <td>{ev['version']}</td>
        <td><span class="badge {b_cls}">{ev['review_status']}</span></td>
        <td><i>{ev['reviewer_feedback']}</i></td>
      </tr>
"""
                html_content += "</tbody></table>"

            # Historical evidence section
            html_content += "<h4 style='color: #475569; margin-top: 20px;'>Historical / Superseded Evidence Submissions</h4>"
            if not report_data["historical_evidence"]:
                html_content += "<p style='font-style: italic; color: #64748b;'>No historical re-submissions recorded.</p>"
            else:
                html_content += """
  <table>
    <thead>
      <tr>
        <th>Historical File Name</th>
        <th>Control Ref</th>
        <th>Uploaded By</th>
        <th>Uploaded On</th>
        <th>Version</th>
        <th>Historical Status</th>
        <th>Previous Feedback</th>
      </tr>
    </thead>
    <tbody>
"""
                for hev in report_data["historical_evidence"]:
                    html_content += f"""
      <tr>
        <td>{hev['name']}</td>
        <td><code>{hev['requirement']}</code></td>
        <td>{hev['uploaded_by']}</td>
        <td>{hev['uploaded_on']}</td>
        <td>{hev['version']}</td>
        <td><span class="badge badge-rejected">{hev['review_status']} (Superseded)</span></td>
        <td><i>{hev['reviewer_feedback']}</i></td>
      </tr>
"""
                html_content += "</tbody></table>"

        # SECTION 6: REVIEWER FINDINGS & OBSERVATIONS
        if "findings_observations" in sections:
            html_content += f"""
  <div class="section-title">{custom_findings_t}</div>
"""
            if not report_data["findings"]:
                html_content += "<div class='card' style='color: #15803d; background: #f0fdf4; border-color: #bbf7d0;'><strong>No Compliance Findings:</strong> All assessed controls are either approved or pending review. No active control rejections recorded.</div>"
            else:
                for idx, f_item in enumerate(report_data["findings"], 1):
                    html_content += f"""
  <div class="card" style="border-left: 4px solid #f43f5e;">
    <div style="font-weight: bold; color: #9f1239; font-size: 10pt;">Finding #{idx:03d} - Control {f_item['ref_id']}: {f_item['title']}</div>
    <div style="font-size: 8pt; color: #64748b; margin-top: 2px;">Domain: {f_item['domain']} | Reviewer: {f_item['reviewer']} | Date: {f_item['date']}</div>
    <div style="margin-top: 8px; font-size: 8.5pt;">
      <strong>Reviewer Rejection Notes:</strong> <i>"{f_item['feedback']}"</i>
    </div>
    <div style="margin-top: 4px; font-size: 8.5pt;">
      <strong>Audit Observation:</strong> {f_item['observation']}
    </div>
  </div>
"""

        # SECTION 7: AUDIT ACTIVITY LOG
        if "activity_history" in sections:
            html_content += f"""
  <div class="section-title">{custom_activity_t}</div>
  <table>
    <thead>
      <tr>
        <th width="20%">Timestamp</th>
        <th width="25%">Actor / User</th>
        <th width="25%">Audit Event</th>
        <th width="30%">Details</th>
      </tr>
    </thead>
    <tbody>
"""
            for act in report_data["activity_logs"]:
                html_content += f"""
      <tr>
        <td>{act['timestamp']}</td>
        <td>{act['user']}</td>
        <td><strong>{act['event']}</strong></td>
        <td>{act['details']}</td>
      </tr>
"""
            html_content += "</tbody></table>"

        # SECTION 8: AUDIT SIGN-OFF
        concluding_html = f'<p style="font-size: 8.5pt; color: #475569; margin-bottom: 12px;"><strong>Concluding Notes:</strong> {custom_concluding_text}</p>' if custom_concluding_text else ''
        html_content += f"""
  <div class="section-title" style="page-break-before: always;">8. Official Audit Sign-Off Dossier</div>
  {concluding_html}
  <p style="font-size: 8.5pt; color: #475569;">
    By signing below, the designated Lead Author, Reviewer, and CISO Officer confirm that the compliance data, evidence links, and control observations represented in this dossier accurately reflect the audit state for <strong>{meta['name']}</strong> as of <strong>{meta['generated_at']}</strong>.
  </p>

  <div class="sign-grid">
    <div class="sign-box">
      <div style="font-weight: bold; font-size: 9pt;">PREPARED BY</div>
      <div style="margin-top: 6px; font-size: 8.5pt;">Name: {meta['author']}</div>
      <div style="margin-top: 2px; font-size: 8.5pt;">Title: Lead SPOC / Author</div>
      <div class="sign-line">Signature & Date</div>
    </div>
    <div class="sign-box">
      <div style="font-weight: bold; font-size: 9pt;">REVIEWED BY</div>
      <div style="margin-top: 6px; font-size: 8.5pt;">Name: {meta['reviewer']}</div>
      <div style="margin-top: 2px; font-size: 8.5pt;">Title: Senior Compliance Reviewer</div>
      <div class="sign-line">Signature & Date</div>
    </div>
    <div class="sign-box">
      <div style="font-weight: bold; font-size: 9pt;">APPROVED BY</div>
      <div style="margin-top: 6px; font-size: 8.5pt;">Name: {meta['owner']}</div>
      <div style="margin-top: 2px; font-size: 8.5pt;">Title: Chief Information Security Officer (CISO)</div>
      <div class="sign-line">Signature & Date</div>
    </div>
  </div>
</body>
</html>
"""

        pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()
        return pdf_bytes
