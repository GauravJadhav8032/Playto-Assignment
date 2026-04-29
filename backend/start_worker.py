#!/usr/bin/env python
"""
Worker startup script — runs before qcluster to validate
DB connectivity and print a clear error if something is wrong.
"""
import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

try:
    django.setup()
except Exception as e:
    print(f"[FATAL] Django setup failed: {e}", file=sys.stderr)
    sys.exit(1)

try:
    from django.db import connection
    connection.ensure_connection()
    print("[OK] Database connection established.")
except Exception as e:
    print(f"[FATAL] Cannot connect to database: {e}", file=sys.stderr)
    sys.exit(1)

try:
    from django_q.cluster import Cluster
    print("[OK] django-q imported successfully.")
except Exception as e:
    print(f"[FATAL] django-q import failed: {e}", file=sys.stderr)
    sys.exit(1)

print("[OK] All checks passed. Starting qcluster...")
os.execvp("python", ["python", "manage.py", "qcluster"])
