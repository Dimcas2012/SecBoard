import logging
from django.utils import timezone
from .models import AutoStatusRule

logger = logging.getLogger(__name__)


def apply_auto_status_rules(alert):
    """
    Apply auto-status rules to a newly created FIM alert
    """
    try:
        # Get all active auto-status rules for this agent
        rules = AutoStatusRule.objects.filter(
            agent_name=alert.agent_name,
            is_active=True
        )
        
        for rule in rules:
            rule_applied = False
            
            # Check if alert matches the rule
            if rule.rule_type == 'file_name' and alert.file_name == rule.rule_value:
                rule_applied = True
            elif rule.rule_type == 'file_path' and alert.file_path == rule.rule_value:
                rule_applied = True
            elif rule.rule_type == 'file_hash_md5' and alert.file_hash_md5 == rule.rule_value:
                rule_applied = True
            elif rule.rule_type == 'file_hash_sha1' and alert.file_hash_sha1 == rule.rule_value:
                rule_applied = True
            elif rule.rule_type == 'file_hash_sha256' and alert.file_hash_sha256 == rule.rule_value:
                rule_applied = True
            
            if rule_applied:
                # Apply the rule
                alert.processing_status = rule.status
                alert.processed_at = timezone.now()
                alert.processed_by = rule.created_by  # Set the user who created the rule
                alert.processed = True
                if rule.risk_assessment:
                    alert.risk_assessment = rule.risk_assessment
                if rule.notes:
                    alert.investigation_notes = rule.notes
                alert.save()
                
                logger.info(f"Applied auto-status rule {rule.id} to alert {alert.alert_id}: {rule.status}")
                print(f"   🎯 Auto-status rule applied: {rule.get_rule_type_display()} → {rule.get_status_display()}")
                break  # Only apply the first matching rule
        
    except Exception as e:
        logger.error(f"Error applying auto-status rules: {str(e)}")
        print(f"   ⚠️ Error applying auto-status rules: {str(e)}")
