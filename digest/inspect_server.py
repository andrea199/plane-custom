"""Read-only deployment preflight; never print credential values."""
import json
from django.db import connection
from plane.db.models import WorkspaceMember
from plane.license.utils.instance_value import get_email_configuration
from plane.db.models import APIToken

host, user, password, port, tls, ssl, sender = get_email_configuration()
print(json.dumps({"smtp": {"host": host, "port": port, "tls": tls,
    "ssl": ssl, "sender": sender, "username_configured": bool(user),
    "password_configured": bool(password)}}, default=str))
members = WorkspaceMember.objects.filter(workspace__slug="oniro").values(
    "member_id", "member__first_name", "member__last_name", "member__email", "role")
print(json.dumps({"members": list(members)}, default=str))
print(json.dumps({"api_tokens": list(APIToken.objects.filter(user_id="0d84b5c4-4dc1-4ab9-a981-ed5891f1d967", is_active=True).values("id", "label", "workspace_id", "expired_at"))}, default=str))
with connection.cursor() as cursor:
    for table in connection.introspection.table_names():
        if table.startswith("oniro_planning_"):
            cursor.execute('SELECT COUNT(*) FROM ' + connection.ops.quote_name(table))
            print(json.dumps({"planning_table": table, "count": cursor.fetchone()[0]}))
