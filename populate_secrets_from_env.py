#!/usr/bin/env python3
"""
Read .env files from all apps and populate database with secrets and aliases.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from pathlib import Path
import secrets
import string

engine = create_engine("postgresql://localhost/superdeploy")
Session = sessionmaker(bind=engine)
db = Session()

PROJECT_NAME = "cheapa"

# App .env file paths
APP_ENV_FILES = {
    "api": "/Users/cfkarakulak/Desktop/cheapa.io/code/api/.env",
    "services": "/Users/cfkarakulak/Desktop/cheapa.io/code/services/.env",
    "storefront": "/Users/cfkarakulak/Desktop/cheapa.io/storefront/.env",
}


def generate_password(length=32):
    """Generate secure random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def read_env_file(path):
    """Read .env file and return dict"""
    env_vars = {}
    if not Path(path).exists():
        print(f"  ⚠️  File not found: {path}")
        return env_vars

    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()

    return env_vars


print("=" * 80)
print("POPULATING SECRETS FROM .ENV FILES")
print("=" * 80)

# 1. READ ALL .ENV FILES
print("\n📁 Step 1: Reading .env files...")
app_secrets = {}
for app_name, env_path in APP_ENV_FILES.items():
    print(f"  Reading {app_name}...")
    app_secrets[app_name] = read_env_file(env_path)
    print(f"    ✓ Found {len(app_secrets[app_name])} variables")

# 2. GENERATE ADDON SECRETS
print("\n🔐 Step 2: Generating addon secrets...")
ADDON_SECRETS = {
    "postgres.postgres.HOST": "10.1.0.3",
    "postgres.postgres.PORT": "5432",
    "postgres.postgres.USER": "cheapa_user",
    "postgres.postgres.PASSWORD": generate_password(),
    "postgres.postgres.DATABASE": "cheapa_db",
    "rabbitmq.rabbitmq.HOST": "10.1.0.3",
    "rabbitmq.rabbitmq.PORT": "5672",
    "rabbitmq.rabbitmq.USER": "cheapa_user",
    "rabbitmq.rabbitmq.PASSWORD": generate_password(),
    "rabbitmq.rabbitmq.MANAGEMENT_PORT": "15672",
}
print(f"  ✓ Generated {len(ADDON_SECRETS)} addon secrets")

# 3. INSERT ADDON SECRETS
print("\n💾 Step 3: Inserting addon secrets to database...")
for key, value in ADDON_SECRETS.items():
    db.execute(
        text("""
        INSERT INTO secrets (project_name, key, value, source, environment, editable, created_at)
        VALUES (:project, :key, :value, 'addon', 'production', false, :now)
    """),
        {"project": PROJECT_NAME, "key": key, "value": value, "now": datetime.utcnow()},
    )
print(f"  ✓ Inserted {len(ADDON_SECRETS)} addon secrets")
db.commit()

# 4. INSERT SHARED SECRETS
print("\n💾 Step 4: Inserting shared secrets...")
SHARED_SECRETS = {
    "DOCKER_ORG": "c100394",
    "DOCKER_USERNAME": "c100394",
    "DOCKER_TOKEN": "dckr_pat_66Qh3Hf-qh7rTKH22eBAUOTi41I",
    "REPOSITORY_TOKEN": "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",
}
for key, value in SHARED_SECRETS.items():
    db.execute(
        text("""
        INSERT INTO secrets (project_name, key, value, source, environment, editable, created_at)
        VALUES (:project, :key, :value, 'shared', 'production', true, :now)
    """),
        {"project": PROJECT_NAME, "key": key, "value": value, "now": datetime.utcnow()},
    )
print(f"  ✓ Inserted {len(SHARED_SECRETS)} shared secrets")
db.commit()

# 5. INSERT APP SECRETS
print("\n💾 Step 5: Inserting app-specific secrets...")
total_app_secrets = 0
for app_name, env_vars in app_secrets.items():
    for key, value in env_vars.items():
        # Skip empty values
        if not value:
            continue
        db.execute(
            text("""
            INSERT INTO secrets (project_name, app_name, key, value, source, environment, editable, created_at)
            VALUES (:project, :app, :key, :value, 'app', 'production', true, :now)
        """),
            {
                "project": PROJECT_NAME,
                "app": app_name,
                "key": key,
                "value": value,
                "now": datetime.utcnow(),
            },
        )
        total_app_secrets += 1
print(f"  ✓ Inserted {total_app_secrets} app-specific secrets")
db.commit()

# 6. CREATE ALIASES
print("\n🔀 Step 6: Creating aliases...")
ALIASES = [
    ("DB_HOST", "postgres.postgres.HOST"),
    ("DB_PORT", "postgres.postgres.PORT"),
    ("DB_USERNAME", "postgres.postgres.USER"),
    ("DB_PASSWORD", "postgres.postgres.PASSWORD"),
    ("DB_DATABASE", "postgres.postgres.DATABASE"),
    ("RABBIT_HOST", "rabbitmq.rabbitmq.HOST"),
    ("RABBIT_PORT", "rabbitmq.rabbitmq.PORT"),
    ("RABBIT_USERNAME", "rabbitmq.rabbitmq.USER"),
    ("RABBIT_PASSWORD", "rabbitmq.rabbitmq.PASSWORD"),
]

total_aliases = 0
for app_name in ["api", "services", "storefront"]:
    for alias_key, target_key in ALIASES:
        db.execute(
            text("""
            INSERT INTO secret_aliases (project_name, app_name, alias_key, target_key, created_at, updated_at)
            VALUES (:project, :app, :alias_key, :target_key, :now, :now)
        """),
            {
                "project": PROJECT_NAME,
                "app": app_name,
                "alias_key": alias_key,
                "target_key": target_key,
                "now": datetime.utcnow(),
            },
        )
        total_aliases += 1
print(f"  ✓ Created {total_aliases} aliases")
db.commit()

# 7. SUMMARY
print("\n" + "=" * 80)
print("✅ DATABASE POPULATION COMPLETE!")
print("=" * 80)
print(f"  Addon secrets:  {len(ADDON_SECRETS)}")
print(f"  Shared secrets: {len(SHARED_SECRETS)}")
print(f"  App secrets:    {total_app_secrets}")
print(f"  Aliases:        {total_aliases}")
print(
    f"  TOTAL:          {len(ADDON_SECRETS) + len(SHARED_SECRETS) + total_app_secrets + total_aliases}"
)
print("=" * 80)

db.close()
