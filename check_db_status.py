#!/usr/bin/env python3
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

engine = create_engine("postgresql://localhost/superdeploy")
Session = sessionmaker(bind=engine)
db = Session()

print("=== PROJECTS ===")
result = db.execute(text("SELECT name, apps_config IS NOT NULL as has_apps FROM projects WHERE name='cheapa'"))
for row in result:
    print(f"  {row.name}: apps_config={row.has_apps}")

print("\n=== SECRETS (count by source) ===")
result = db.execute(text("SELECT source, COUNT(*) FROM secrets WHERE project_name='cheapa' GROUP BY source"))
for row in result:
    print(f"  {row.source}: {row.count}")

print("\n=== ALIASES (count by app) ===")
result = db.execute(text("SELECT app_name, COUNT(*) FROM secret_aliases WHERE project_name='cheapa' GROUP BY app_name"))
for row in result:
    print(f"  {row.app_name}: {row.count}")

print("\n=== VMS ===")
result = db.execute(text("SELECT name, role FROM vms WHERE project_id=(SELECT id FROM projects WHERE name='cheapa')"))
count = 0
for row in result:
    print(f"  {row.name} ({row.role})")
    count += 1
if count == 0:
    print("  (empty)")

db.close()

