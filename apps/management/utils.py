from apps.management.models import AuditLog, Branch


def log_audit(action, entity_type, entity_id="", message="", user=None, branch_code=""):
    branch = None
    if branch_code:
        branch = Branch.objects.filter(code=branch_code).first()

    AuditLog.objects.create(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id or ""),
        message=message or "",
        user=user if user and user.is_authenticated else None,
        branch=branch,
    )
