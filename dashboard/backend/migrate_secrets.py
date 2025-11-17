"""
Migrate secrets.yml to database.

Usage:
    python migrate_secrets.py --project cheapa

This will:
1. Read secrets.yml from projects/{project}/
2. Insert secrets into database
3. Insert aliases into database
4. Create backup: secrets.yml.backup
"""

import yaml
import argparse
from pathlib import Path
from sqlalchemy.orm import Session
from database import SessionLocal, init_db
from models import Secret, SecretAlias
import shutil


def parse_addon_secrets(addons_data):
    """
    Parse addon secrets from YAML structure.

    Example:
      postgres:
        primary:
          HOST: 10.1.0.3
          PORT: 5432

    Returns list of (key, value, source) tuples like:
      [('postgres.primary.HOST', '10.1.0.3', 'addon'), ...]
    """
    secrets = []

    for addon_type, instances in addons_data.items():
        if not isinstance(instances, dict):
            continue

        for instance_name, credentials in instances.items():
            if not isinstance(credentials, dict):
                continue

            for key, value in credentials.items():
                # Create dotted key: postgres.primary.HOST
                full_key = f"{addon_type}.{instance_name}.{key}"
                secrets.append((full_key, str(value), "addon"))

    return secrets


def migrate_project_secrets(project_name: str, db: Session, dry_run: bool = False):
    """Migrate secrets for a specific project."""

    # Get secrets.yml path
    superdeploy_root = Path(__file__).parent.parent.parent
    secrets_file = superdeploy_root / "projects" / project_name / "secrets.yml"

    if not secrets_file.exists():
        print(f"❌ No secrets.yml found for project: {project_name}")
        print(f"   Expected: {secrets_file}")
        return False

    print(f"\n📁 Reading: {secrets_file}")

    # Read secrets.yml
    with open(secrets_file, "r") as f:
        data = yaml.safe_load(f) or {}

    secrets_data = data.get("secrets", {})
    env_aliases_data = data.get("env_aliases", {})

    # Counters
    shared_count = 0
    app_count = 0
    addon_count = 0
    alias_count = 0

    # --- SHARED SECRETS ---
    shared_secrets = secrets_data.get("shared", {})
    print("\n🔐 Processing shared secrets...")

    for key, value in shared_secrets.items():
        if dry_run:
            print(f"   [DRY-RUN] Would insert: {key} (shared)")
        else:
            secret = Secret(
                project_name=project_name,
                app_name=None,  # NULL = shared
                key=key,
                value=str(value),
                environment="production",
                source="shared",
                editable=True,
            )
            db.merge(secret)  # merge instead of add (handles duplicates)
            shared_count += 1
            print(f"   ✓ {key}")

    # --- ADDON SECRETS ---
    addons_data = secrets_data.get("addons", {})
    print("\n🔌 Processing addon secrets...")

    addon_secrets = parse_addon_secrets(addons_data)
    for full_key, value, source in addon_secrets:
        if dry_run:
            print(f"   [DRY-RUN] Would insert: {full_key} (addon)")
        else:
            secret = Secret(
                project_name=project_name,
                app_name=None,  # Addons are shared
                key=full_key,
                value=value,
                environment="production",
                source="addon",
                editable=False,  # Addon secrets shouldn't be edited manually
            )
            db.merge(secret)
            addon_count += 1
            print(f"   ✓ {full_key}")

    # --- APP-SPECIFIC SECRETS ---
    apps_data = secrets_data.get("apps", {})
    print("\n📱 Processing app-specific secrets...")

    for app_name, app_secrets in apps_data.items():
        print(f"\n   App: {app_name}")
        if not isinstance(app_secrets, dict):
            continue

        for key, value in app_secrets.items():
            if dry_run:
                print(f"      [DRY-RUN] Would insert: {key}")
            else:
                secret = Secret(
                    project_name=project_name,
                    app_name=app_name,
                    key=key,
                    value=str(value),
                    environment="production",
                    source="app",
                    editable=True,
                )
                db.merge(secret)
                app_count += 1
                print(f"      ✓ {key}")

    # --- ENVIRONMENT ALIASES ---
    print("\n🔗 Processing environment aliases...")

    for app_name, aliases in env_aliases_data.items():
        print(f"\n   App: {app_name}")
        if not isinstance(aliases, dict):
            continue

        for alias_key, target_key in aliases.items():
            if dry_run:
                print(f"      [DRY-RUN] Would insert: {alias_key} → {target_key}")
            else:
                alias = SecretAlias(
                    project_name=project_name,
                    app_name=app_name,
                    alias_key=alias_key,
                    target_key=target_key,
                )
                db.merge(alias)
                alias_count += 1
                print(f"      ✓ {alias_key} → {target_key}")

    # Commit to database
    if not dry_run:
        db.commit()
        print("\n✅ Migration complete!")
    else:
        print("\n✅ Dry-run complete (no changes made)")

    # Summary
    print("\n📊 Summary:")
    print(f"   Shared secrets:  {shared_count}")
    print(f"   Addon secrets:   {addon_count}")
    print(f"   App secrets:     {app_count}")
    print(f"   Aliases:         {alias_count}")
    print(f"   Total:           {shared_count + addon_count + app_count + alias_count}")

    # Create backup
    if not dry_run:
        backup_path = secrets_file.with_suffix(".yml.backup")
        shutil.copy(secrets_file, backup_path)
        print(f"\n💾 Backup created: {backup_path}")
        print(
            "\n⚠️  Original secrets.yml NOT deleted (delete manually after verification)"
        )

    return True


def main():
    parser = argparse.ArgumentParser(description="Migrate secrets.yml to database")
    parser.add_argument("--project", required=True, help="Project name (e.g. cheapa)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes",
    )
    args = parser.parse_args()

    print(f"🚀 Starting migration for project: {args.project}")

    # Initialize database
    init_db()
    print("✓ Database initialized")

    # Get database session
    db = SessionLocal()

    try:
        success = migrate_project_secrets(args.project, db, dry_run=args.dry_run)

        if success:
            print("\n✨ Done!")
        else:
            print("\n❌ Migration failed")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
