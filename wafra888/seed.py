#!/usr/bin/env python3
"""يزرع الحسابات الاثنا عشر بكلمة سر ابتدائية موحّدة (من DEFAULT_PASSWORD أو "0000")
وإجبار تغييرها أول دخول. آمن تشغّله أكتر من مرة — ما بيلمس حساب موجود أصلاً.

الاستخدام:
    python3 seed.py
"""
from wafra888 import create_app, repo
from wafra888.security import hash_password, slugify
from wafra888.seed_data import SEED_ACCOUNTS


def main():
    app = create_app()
    with app.app_context():
        default_password = app.config["DEFAULT_PASSWORD"]
        created, skipped = 0, 0
        for acc in SEED_ACCOUNTS:
            slug = slugify(acc["name"])
            existing = repo.get_account_by_slug(slug)
            if existing:
                skipped += 1
                continue
            repo.create_account(slug, acc["name"], acc["role"], hash_password(default_password))
            created += 1
            print(f"  + انزرع: {acc['name']} ({acc['role']})")
        print(f"\nتم. حسابات جديدة: {created} — موجودة مسبقاً وما انلمست: {skipped}")
        print(f'كلمة السر الابتدائية للكل: "{default_password}" (لازم تنغيّر أول دخول)')


if __name__ == "__main__":
    main()
