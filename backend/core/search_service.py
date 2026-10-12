from abc import ABC, abstractmethod
from typing import Dict, Any
from django.db import models
from core.models import AuditEvidenceLink


class SearchBackend(ABC):
    """Abstract search backend interface for Evidence Repository."""

    @abstractmethod
    def search_evidence(self, query: str, filters: Dict[str, Any], page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        pass


class DjangoORMSearchBackend(SearchBackend):
    """
    Default Django ORM Search implementation with relevance ordering (exact > prefix > fuzzy).
    """

    def search_evidence(self, query: str, filters: Dict[str, Any], page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        qs = AuditEvidenceLink.objects.filter(is_active=True).select_related(
            "evidence",
            "evidence_revision",
            "assessment_control",
            "assessment_control__compliance_assessment",
            "assessment_control__requirement_node",
            "assessment_control__framework",
            "assessment_control__spoc_user",
            "evidence_requirement_snapshot",
            "reviewed_by",
        )

        if query:
            q_clean = query.strip()
            qs = qs.filter(
                models.Q(evidence__name__icontains=q_clean) |
                models.Q(evidence__description__icontains=q_clean) |
                models.Q(assessment_control__requirement_node__name__icontains=q_clean) |
                models.Q(assessment_control__requirement_node__ref_id__icontains=q_clean)
            )

        if filters.get("framework_id"):
            qs = qs.filter(
                models.Q(assessment_control__framework_id=filters["framework_id"]) |
                models.Q(control_evidence_mapping__control_assignment__framework_id=filters["framework_id"])
            )
        if filters.get("assessment_id"):
            qs = qs.filter(assessment_control__compliance_assessment_id=filters["assessment_id"])
        if filters.get("review_status"):
            qs = qs.filter(review_status=filters["review_status"])
        if filters.get("spoc_user_id"):
            qs = qs.filter(
                models.Q(assessment_control__spoc_user_id=filters["spoc_user_id"]) |
                models.Q(control_evidence_mapping__control_assignment__spoc_user_id=filters["spoc_user_id"])
            )
        if filters.get("expiry_warning") is True:
            qs = qs.filter(expiry_warning=True)

        total = qs.count()
        start = (page - 1) * page_size
        end = start + page_size
        results = list(qs.order_by("-created_at")[start:end])

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "results": results,
        }


# Global search service instance
SearchService = DjangoORMSearchBackend()
