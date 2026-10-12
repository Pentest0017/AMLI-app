#!/usr/bin/env bash
# wait for database to be ready
if [ ! -n "$DJANGO_SETTINGS_MODULE" ]; then
  export DJANGO_SETTINGS_MODULE=ciso_assistant.settings
fi
if [ ! -n "$DJANGO_SECRET_KEY" ]; then
  if [ ! -f db/django_secret_key ]; then
    openssl rand -hex 32 | install -m 600 /dev/stdin db/django_secret_key
    echo "generating initial Django secret key"
  fi
  export DJANGO_SECRET_KEY=$(<db/django_secret_key)
  echo "Django secret key read from file"
fi
while ! python manage.py showmigrations iam >/dev/null; do
  echo "database not ready; waiting"
  sleep 15
done
python manage.py migrate --settings="${DJANGO_SETTINGS_MODULE}"
python manage.py shell --settings="${DJANGO_SETTINGS_MODULE}" -c "
from core.startup import startup, ensure_admin_user
from iam.models import User
from allauth.account.models import EmailAddress

startup(sender=None)
ensure_admin_user()

import os

# Initial admin: password comes from the environment (never hardcoded).
# Only set when the account has no usable password yet, so later changes are kept.
email = os.environ.get('CISO_ASSISTANT_SUPERUSER_EMAIL')
password = os.environ.get('CISO_ASSISTANT_SUPERUSER_PASSWORD')
user = User.objects.filter(email__iexact=email).first() if email else None
if user and password and not user.has_usable_password():
    user.set_password(password)
    user.is_active = True
    user.keep_local_login = True
    user.save()
if user:
    email_obj, _ = EmailAddress.objects.get_or_create(user=user, email=user.email)
    email_obj.verified = True
    email_obj.primary = True
    email_obj.save()

from iam.models import UserGroup
admin_group = UserGroup.objects.filter(name='BI-UG-ADM').first()
if admin_group:
    for u in User.objects.filter(platform_role__in=['webadmin', 'superadmin']):
        if not u.user_groups.filter(id=admin_group.id).exists():
            u.user_groups.add(admin_group)
"

# Set default values for Gunicorn configuration
GUNICORN_WORKERS=${GUNICORN_WORKERS:-3}
GUNICORN_TIMEOUT=${GUNICORN_TIMEOUT:-100}
GUNICORN_KEEPALIVE=${GUNICORN_KEEPALIVE:-30}
GUNICORN_LIMIT_REQUEST_LINE=${GUNICORN_LIMIT_REQUEST_LINE:-5120}
GUNICORN_PORT=${PORT:-8000}

exec gunicorn --chdir ciso_assistant \
  --bind :$GUNICORN_PORT \
  --timeout $GUNICORN_TIMEOUT \
  --keep-alive $GUNICORN_KEEPALIVE \
  --workers=$GUNICORN_WORKERS \
  --limit-request-line=$GUNICORN_LIMIT_REQUEST_LINE \
  --env RUN_MAIN=true \
  ciso_assistant.wsgi:application
