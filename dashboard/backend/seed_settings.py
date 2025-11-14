"""Seed settings table with GitHub token."""

from database import SessionLocal, init_db
from models import Setting

# GitHub token (manually set for now)
GITHUB_TOKEN = "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"


def seed_settings():
    """Seed settings table with initial values."""
    init_db()
    db = SessionLocal()

    try:
        # Check if github_token already exists
        existing = db.query(Setting).filter(Setting.key == "github_token").first()

        if existing:
            print(f"✓ GitHub token already exists: {existing.value[:20]}...")
            # Update if needed
            if existing.value != GITHUB_TOKEN:
                existing.value = GITHUB_TOKEN
                db.commit()
                print("🔄 GitHub token updated")
        else:
            # Create new setting
            new_setting = Setting(key="github_token", value=GITHUB_TOKEN, encrypted=0)
            db.add(new_setting)
            db.commit()
            print(f"✅ GitHub token seeded: {GITHUB_TOKEN[:20]}...")

        print("\n✓ Settings seeded successfully!")

    except Exception as e:
        print(f"❌ Error seeding settings: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_settings()
