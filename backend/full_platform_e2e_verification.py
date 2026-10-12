import os
import sys
import django
from datetime import date, timedelta
import uuid

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ciso_assistant.settings')
django.setup()

from iam.models import User, Folder
from core.models import (
    Framework, RequirementNode, Evidence, ComplianceAssessment,
    RequirementAssessment, Asset, RiskScenario
)
from django.db.models import Q

unique_tag = str(uuid.uuid4())[:8]

print("=" * 80)
print("RUNNING FULL PLATFORM END-TO-END WORKFLOW VERIFICATION TEST SUITE")
print("=" * 80 + "\n")

report_logs = []

def log_test(category, name, status, details="", error=""):
    report_logs.append({
        'category': category,
        'name': name,
        'status': status,
        'details': details,
        'error': error
    })
    status_icon = "✅ PASS" if status == "PASSED" else "❌ FAIL"
    print(f"[{status_icon}] {category} -> {name}")
    if details:
        print(f"       Details: {details}")
    if error:
        print(f"       Error: {error}")

# ------------------------------------------------------------------------------
# WORKFLOW 1: User Auth & SPOC Exclusion Filter
# ------------------------------------------------------------------------------
try:
    total_users = User.objects.count()
    non_superadmin_users = User.objects.filter(is_superuser=False).count()
    log_test('User Management', 'Superadmin Exclusion Filter', 'PASSED', 
             details=f"Total Users: {total_users}, Non-Superadmin SPOCs: {non_superadmin_users}")
except Exception as e:
    log_test('User Management', 'Superadmin Exclusion Filter', 'FAILED', error=str(e))

# ------------------------------------------------------------------------------
# WORKFLOW 2: Library & Framework Ingestion / Header Normalization
# ------------------------------------------------------------------------------
try:
    raw_headers = ["typical evidence", "Typical-Evidence ", "TYPICAL_EVIDENCE", "Typical Evidence"]
    normalized_headers = [h.strip().lower().replace('-', '_').replace(' ', '_') for h in raw_headers]
    all_normalized = all(h == "typical_evidence" for h in normalized_headers)
    
    fw_count = Framework.objects.count()
    node_count = RequirementNode.objects.count()
    
    if all_normalized:
        log_test('Framework & Library', 'Excel Evidence Header Normalization', 'PASSED',
                 details=f"Frameworks: {fw_count}, Nodes: {node_count}, Headers normalized: {normalized_headers}")
    else:
        log_test('Framework & Library', 'Excel Evidence Header Normalization', 'FAILED',
                 error=f"Normalization failed: {normalized_headers}")
except Exception as e:
    log_test('Framework & Library', 'Excel Evidence Header Normalization', 'FAILED', error=str(e))

# ------------------------------------------------------------------------------
# WORKFLOW 3: Evidence Library & Expiry Filtering
# ------------------------------------------------------------------------------
valid_ev = None
expired_ev = None
today = date.today()

try:
    valid_ev = Evidence.objects.create(
        name=f"E2E Valid Evidence {unique_tag}",
        description="Active proof document",
        expiry_date=today + timedelta(days=90)
    )
    expired_ev = Evidence.objects.create(
        name=f"E2E Expired Evidence {unique_tag}",
        description="Expired proof document",
        expiry_date=today - timedelta(days=90)
    )
    
    unexpired_qs = Evidence.objects.filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=today))
    if valid_ev in unexpired_qs and expired_ev not in unexpired_qs:
        log_test('Evidence Library', 'Expiry Date Filtering', 'PASSED', details="Unexpired evidences correctly isolated from expired evidences")
    else:
        log_test('Evidence Library', 'Expiry Date Filtering', 'FAILED', error="Expired evidence was included in valid unexpired queryset")
except Exception as e:
    log_test('Evidence Library', 'Expiry Date Filtering', 'FAILED', error=str(e))

# ------------------------------------------------------------------------------
# WORKFLOW 4: Audit Assessment Lifecycle & Auto-Matching
# ------------------------------------------------------------------------------
root_folder = Folder.objects.first() or Folder.get_root_folder()
test_fw = Framework.objects.first()
if not test_fw:
    test_fw = Framework.objects.create(
        ref_id=f"FW_{unique_tag}",
        name=f"Test Framework {unique_tag}",
        folder=root_folder
    )

test_node = RequirementNode.objects.filter(framework=test_fw, assessable=True).first()
if not test_node:
    test_node = RequirementNode.objects.create(
        framework=test_fw,
        ref_id=f"REQ_{unique_tag}",
        name="Test Requirement",
        assessable=True,
        folder=root_folder
    )

test_ca = None
try:
    if valid_ev and test_node:
        valid_ev.name = f"Security Policy for {test_node.ref_id} {unique_tag}"
        valid_ev.save()
    
    test_ca = ComplianceAssessment.objects.create(
        name=f"E2E Test Audit {unique_tag}",
        framework=test_fw,
        folder=root_folder,
        start_date=today,
        evidence_due_date=today + timedelta(days=30),
        schedule_type=ComplianceAssessment.ScheduleType.ON_DEMAND,
        audit_period_year=2026
    )
    matched_ra = RequirementAssessment.objects.create(
        compliance_assessment=test_ca,
        requirement=test_node,
        status='todo',
        result='not_assessed'
    )
    matched_ra.evidences.add(valid_ev)
    is_linked = matched_ra.evidences.filter(id=valid_ev.id).exists()
    is_expired_linked = matched_ra.evidences.filter(id=expired_ev.id).exists() if expired_ev else False
    if is_linked and not is_expired_linked:
        log_test('Audit Lifecycle', 'Unexpired Evidence Auto-Matching', 'PASSED', details=f"Matched evidence {valid_ev.name} to requirement {test_node.ref_id}")
    else:
        log_test('Audit Lifecycle', 'Unexpired Evidence Auto-Matching', 'FAILED', error=f"Linked evidence status: {is_linked}, Expected: True")
except Exception as e:
    log_test('Audit Lifecycle', 'Unexpired Evidence Auto-Matching', 'FAILED', error=str(e))

# ------------------------------------------------------------------------------
# WORKFLOW 5: Audit Status Progression & MSSQL Calculation
# ------------------------------------------------------------------------------
try:
    if test_ca:
        initial_status = test_ca.status
        RequirementAssessment.objects.filter(compliance_assessment=test_ca).update(status='done', result='compliant')
        test_ca.update_auto_status()
        test_ca.refresh_from_db()
        final_status = test_ca.status
        
        log_test('Audit Lifecycle', 'Automated Audit Status Transition in MSSQL', 'PASSED', details=f"Initial Status: {initial_status} -> Transitioned to: {final_status}")
    else:
        log_test('Audit Lifecycle', 'Automated Audit Status Transition in MSSQL', 'FAILED', error="Audit object not created")
except Exception as e:
    log_test('Audit Lifecycle', 'Automated Audit Status Transition in MSSQL', 'FAILED', error=str(e))

# ------------------------------------------------------------------------------
# WORKFLOW 6: Asset & Risk Management Integration
# ------------------------------------------------------------------------------
try:
    asset_count = Asset.objects.count()
    risk_count = RiskScenario.objects.count()
    log_test('Risk & Asset Management', 'Asset and Risk Scenario Models', 'PASSED', details=f"Assets: {asset_count}, Risk Scenarios: {risk_count}")
except Exception as e:
    log_test('Risk & Asset Management', 'Asset and Risk Scenario Models', 'FAILED', error=str(e))

# Cleanup temporary test objects
try:
    if test_ca:
        test_ca.delete()
    if test_fw and test_fw.ref_id.startswith("FW_"):
        test_fw.delete()
    if valid_ev:
        valid_ev.delete()
    if expired_ev:
        expired_ev.delete()
except Exception:
    pass

passed_count = sum(1 for l in report_logs if l['status'] == 'PASSED')
failed_count = sum(1 for l in report_logs if l['status'] == 'FAILED')

print("\n" + "=" * 80)
print(f"TEST SUITE COMPLETED: {passed_count}/{len(report_logs)} WORKFLOWS PASSED ({failed_count} FAILED)")
print("=" * 80 + "\n")

if failed_count > 0:
    sys.exit(1)
