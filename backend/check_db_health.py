#!/usr/bin/env python
"""
Quick database health check script.
Run: python check_db_health.py
"""
import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
django.setup()

from django.db import connection
from django.core.cache import cache

def check_database():
    print("=" * 60)
    print("DATABASE HEALTH CHECK")
    print("=" * 60)
    
    # Check database connection
    print("\n1. Database Connection:", end=" ")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result and result[0] == 1:
                print("✅ OK")
            else:
                print("❌ FAILED")
                return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False
    
    # Check User table
    print("2. User Table:", end=" ")
    try:
        from apps.users.models import User
        user_count = User.objects.count()
        print(f"✅ OK ({user_count} users)")
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False
    
    # Check Redis
    print("3. Redis Connection:", end=" ")
    try:
        cache.set("test_health", "ok", 10)
        result = cache.get("test_health")
        if result == "ok":
            print("✅ OK")
        else:
            print("❌ FAILED")
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ ALL CHECKS PASSED")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = check_database()
    sys.exit(0 if success else 1)
