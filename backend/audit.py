import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def record_audit(db: Any, admin_email: str, ip: str, action: str, document_id: str, details: Optional[Dict[str, Any]] = None) -> None:
    if not admin_email or not action or not document_id:
        return
    entry = {
        'id': str(uuid.uuid4()),
        'admin_email': admin_email,
        'ip_address': ip,
        'action': action,
        'document_id': document_id,
        'details': details or {},
        'timestamp': now_iso(),
    }
    await db.audit_logs.insert_one(entry)
