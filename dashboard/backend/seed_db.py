"""
Seed database from filesystem.

Reads config.yml and secrets.yml and populates DB.
Run this once to migrate from filesystem to database.
"""

from pathlib import Path
import yaml
from database import SessionLocal
from models import Project, Environment, App, Addon, Secret


def seed_database():
    """Seed database with projects, apps, addons from filesystem."""
    db = SessionLocal()

    try:
        project_root = Path(__file__).parent.parent.parent
        projects_dir = project_root / "projects"

        if not projects_dir.exists():
            print("❌ No projects directory found")
            return

        seeded_projects = 0
        seeded_apps = 0
        seeded_addons = 0
        seeded_secrets = 0

        for project_dir in sorted(projects_dir.iterdir()):
            if not project_dir.is_dir() or project_dir.name.startswith("."):
                continue

            config_file = project_dir / "config.yml"
            if not config_file.exists():
                continue

            project_name = project_dir.name
            print(f"\n📦 Processing {project_name}...")

            # Read config.yml
            with open(config_file, "r") as f:
                config = yaml.safe_load(f)

            # Check if project already exists
            existing = db.query(Project).filter(Project.name == project_name).first()

            if not existing:
                # Create project
                cloud_config = config.get("cloud", {})
                new_project = Project(
                    name=project_name,
                    cloud_provider=cloud_config.get("provider", "gcp"),
                    cloud_region=cloud_config.get("region", "us-central1"),
                    cloud_zone=cloud_config.get("zone", "us-central1-a"),
                )
                db.add(new_project)
                db.flush()

                # Create default environments
                for env_name in ["production", "staging", "review"]:
                    env = Environment(name=env_name, project_id=new_project.id)
                    db.add(env)

                db.commit()
                seeded_projects += 1
                print("  ✅ Project created")
                project = new_project
            else:
                print("  ⏭️  Project exists")
                project = existing

            # Seed Apps from config.yml
            apps_config = config.get("apps", {})
            github_config = config.get("github", {})
            github_org = github_config.get("organization", "cheapaio")

            for app_name, app_config in apps_config.items():
                # Check if app exists
                existing_app = (
                    db.query(App)
                    .filter(App.project_id == project.id, App.name == app_name)
                    .first()
                )

                if not existing_app:
                    new_app = App(
                        project_id=project.id,
                        name=app_name,
                        type=app_config.get("type", "web"),
                        vm=app_config.get("vm"),
                        domain=app_config.get("domain"),
                        port=app_config.get("port"),
                        dockerfile_path=app_config.get("dockerfile"),
                        processes=app_config.get("processes"),
                        repo=app_config.get("repo", app_name),
                        owner=app_config.get("owner", github_org),
                    )
                    db.add(new_app)
                    seeded_apps += 1
                    print(f"    ✅ App: {app_name}")

            # Seed Addons from config.yml
            addons_config = config.get("addons", {})
            for category, category_addons in addons_config.items():
                if not isinstance(category_addons, dict):
                    continue

                for addon_name, addon_config in category_addons.items():
                    if not isinstance(addon_config, dict):
                        continue

                    # Check if addon exists
                    existing_addon = (
                        db.query(Addon)
                        .filter(
                            Addon.project_id == project.id, Addon.name == addon_name
                        )
                        .first()
                    )

                    if not existing_addon:
                        addon_type = addon_config.get("type")
                        plan = addon_config.get("plan", "standard")

                        # Find attachments
                        attachments = []
                        for app_name, app_config in apps_config.items():
                            app_addons = app_config.get("addons", [])
                            for attachment in app_addons:
                                addon_ref = (
                                    attachment
                                    if isinstance(attachment, str)
                                    else attachment.get("addon")
                                )
                                if addon_ref == f"{category}.{addon_name}":
                                    as_prefix = (
                                        attachment.get("as")
                                        if isinstance(attachment, dict)
                                        else None
                                    )
                                    attachments.append(
                                        {"app_name": app_name, "as_prefix": as_prefix}
                                    )

                        new_addon = Addon(
                            project_id=project.id,
                            name=addon_name,
                            type=addon_type,
                            category=category,
                            plan=plan,
                            status="running",
                            attachments=attachments,
                        )
                        db.add(new_addon)
                        seeded_addons += 1
                        print(f"    ✅ Addon: {addon_name} ({addon_type})")

            # Flush to DB so addons are available for credentials seeding
            db.flush()

            # Seed Secrets from secrets.yml
            secrets_file = project_dir / "secrets.yml"
            if secrets_file.exists():
                with open(secrets_file, "r") as f:
                    secrets_data = yaml.safe_load(f)

                # Get production environment
                production_env = (
                    db.query(Environment)
                    .filter(
                        Environment.project_id == project.id,
                        Environment.name == "production",
                    )
                    .first()
                )

                if production_env and secrets_data:
                    # Extract secrets root
                    secrets_root = secrets_data.get("secrets", {})

                    # 1. Seed addon credentials to Addon.credentials field
                    addon_secrets = secrets_root.get("addons", {})
                    for addon_type, type_addons in addon_secrets.items():
                        for addon_name, credentials in type_addons.items():
                            addon = (
                                db.query(Addon)
                                .filter(
                                    Addon.project_id == project.id,
                                    Addon.type == addon_type,
                                    Addon.name == addon_name,
                                )
                                .first()
                            )
                            if addon:
                                addon.credentials = credentials
                                print(
                                    f"      ✅ Addon credentials: {addon_type}/{addon_name}"
                                )

                    # 2. Seed app secrets to Secret table
                    # Shared secrets
                    shared_secrets = secrets_root.get("shared", {})
                    for key, value in shared_secrets.items():
                        existing = (
                            db.query(Secret)
                            .filter(
                                Secret.environment_id == production_env.id,
                                Secret.app == "shared",
                                Secret.key == key,
                            )
                            .first()
                        )
                        if not existing:
                            new_secret = Secret(
                                environment_id=production_env.id,
                                app="shared",
                                key=key,
                                value=str(value),
                            )
                            db.add(new_secret)
                            seeded_secrets += 1
                            print(f"      ✅ Secret: shared:{key}")

                    # App-specific secrets
                    app_secrets_data = secrets_root.get("apps", {})
                    for app_key, app_secrets in app_secrets_data.items():
                        for key, value in app_secrets.items():
                            existing = (
                                db.query(Secret)
                                .filter(
                                    Secret.environment_id == production_env.id,
                                    Secret.app == app_key,
                                    Secret.key == key,
                                )
                                .first()
                            )
                            if not existing:
                                new_secret = Secret(
                                    environment_id=production_env.id,
                                    app=app_key,
                                    key=key,
                                    value=str(value),
                                )
                                db.add(new_secret)
                                seeded_secrets += 1
                                print(f"      ✅ Secret: {app_key}:{key}")

            db.commit()

        print("\n🎉 Seed Complete!")
        print(f"  Projects: {seeded_projects}")
        print(f"  Apps: {seeded_apps}")
        print(f"  Addons: {seeded_addons}")
        print(f"  Secrets: {seeded_secrets}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    print("🌱 Seeding database from config.yml...\n")
    seed_database()
