from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0183_alter_escalationlog_compliance_assessment'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='assessmentcontrolsnapshot',
            index=models.Index(fields=['compliance_assessment', 'spoc_user'], name='core_assess_complia_8a7f06_idx'),
        ),
        migrations.AddIndex(
            model_name='assessmentcontrolsnapshot',
            index=models.Index(fields=['compliance_assessment', 'framework'], name='core_assess_complia_c4d7b0_idx'),
        ),
        migrations.AddIndex(
            model_name='assessmentcontrolsnapshot',
            index=models.Index(fields=['compliance_assessment', 'snapshot_version'], name='core_assess_complia_451892_idx'),
        ),
        migrations.AddIndex(
            model_name='assessmentreviewlevel',
            index=models.Index(fields=['reviewer_user', 'level'], name='core_assess_reviewe_58e5b0_idx'),
        ),
        migrations.AddIndex(
            model_name='assignmentchangelog',
            index=models.Index(fields=['control_assignment', 'action_type'], name='core_assign_control_e515c4_idx'),
        ),
        migrations.AddIndex(
            model_name='assignmentchangelog',
            index=models.Index(fields=['changed_by', '-created_at'], name='core_assign_changed_a5a1ae_idx'),
        ),
        migrations.AddIndex(
            model_name='assignmentchangelog',
            index=models.Index(fields=['bulk_operation_id'], name='core_assign_bulk_op_9b790b_idx'),
        ),
        migrations.AddIndex(
            model_name='auditcompletion',
            index=models.Index(fields=['compliance_assessment', 'completion_number'], name='core_auditc_complia_a8283a_idx'),
        ),
        migrations.AddIndex(
            model_name='auditcompletion',
            index=models.Index(fields=['closed_at'], name='core_auditc_closed__31a35e_idx'),
        ),
        migrations.AddIndex(
            model_name='auditevidencelink',
            index=models.Index(fields=['assessment_control', 'review_status'], name='core_audite_assessm_5c7c45_idx'),
        ),
        migrations.AddIndex(
            model_name='auditevidencelink',
            index=models.Index(fields=['reviewed_by', 'review_status'], name='core_audite_reviewe_a816a0_idx'),
        ),
        migrations.AddIndex(
            model_name='auditevidencelink',
            index=models.Index(fields=['evidence', 'review_level'], name='core_audite_evidenc_fcb9ab_idx'),
        ),
        migrations.AddIndex(
            model_name='auditevidencelink',
            index=models.Index(fields=['expiry_warning', 'review_status'], name='core_audite_expiry__7ce6d0_idx'),
        ),
        migrations.AddIndex(
            model_name='auditevidencelink',
            index=models.Index(fields=['evidence_revision', 'review_status'], name='core_audite_evidenc_59ef12_idx'),
        ),
        migrations.AddIndex(
            model_name='auditreopenlog',
            index=models.Index(fields=['compliance_assessment', '-reopened_at'], name='core_auditr_complia_545ef1_idx'),
        ),
        migrations.AddIndex(
            model_name='controlassignment',
            index=models.Index(fields=['framework', 'spoc_user'], name='core_contro_framewo_f65dcf_idx'),
        ),
        migrations.AddIndex(
            model_name='controlassignment',
            index=models.Index(fields=['framework', 'reviewer_user'], name='core_contro_framewo_2bcda8_idx'),
        ),
        migrations.AddIndex(
            model_name='controlassignment',
            index=models.Index(fields=['spoc_user', 'is_active'], name='core_contro_spoc_us_a9ffe8_idx'),
        ),
        migrations.AddIndex(
            model_name='controlassignment',
            index=models.Index(fields=['reviewer_user', 'is_active'], name='core_contro_reviewe_2b73d2_idx'),
        ),
        migrations.AddIndex(
            model_name='controlevidencemapping',
            index=models.Index(fields=['control_assignment', 'is_active'], name='core_contro_control_a3288f_idx'),
        ),
        migrations.AddIndex(
            model_name='escalationlog',
            index=models.Index(fields=['compliance_assessment', 'escalation_date'], name='core_escala_complia_221a6d_idx'),
        ),
        migrations.AddIndex(
            model_name='evidencerequirementsnapshot',
            index=models.Index(fields=['assessment_control', 'is_mandatory'], name='core_eviden_assessm_f70cf8_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['user', 'is_read', '-created_at'], name='core_notifi_user_id_f286cd_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['user', 'notification_type', 'is_read'], name='core_notifi_user_id_b2d286_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['created_at'], name='core_notifi_created_d0c445_idx'),
        ),
    ]
