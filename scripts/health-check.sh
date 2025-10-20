#!/bin/bash
# Health Check Script - Verify all services

set -e

echo "🔍 SuperDeploy Health Check"
echo "═══════════════════════════════════════"

FAILED=0

# API
echo -n "API: "
if curl -sf http://localhost:8000/healthz > /dev/null; then
  echo "✅ HEALTHY"
else
  echo "❌ FAILED"
  FAILED=1
fi

# Dashboard
echo -n "Dashboard: "
if curl -sf http://localhost/ > /dev/null; then
  echo "✅ HEALTHY"
else
  echo "❌ FAILED"
  FAILED=1
fi

# Forgejo
echo -n "Forgejo: "
if curl -sf http://localhost:3001/api/v1/healthz > /dev/null; then
  echo "✅ HEALTHY"
else
  echo "❌ FAILED"
  FAILED=1
fi

# PostgreSQL
echo -n "PostgreSQL: "
if docker exec superdeploy-postgres pg_isready -U superdeploy > /dev/null 2>&1; then
  echo "✅ HEALTHY"
else
  echo "❌ FAILED"
  FAILED=1
fi

# RabbitMQ
echo -n "RabbitMQ: "
if docker exec superdeploy-rabbitmq rabbitmq-diagnostics ping > /dev/null 2>&1; then
  echo "✅ HEALTHY"
else
  echo "❌ FAILED"
  FAILED=1
fi

echo "═══════════════════════════════════════"
if [ $FAILED -eq 0 ]; then
  echo "✅ ALL SERVICES HEALTHY"
  exit 0
else
  echo "❌ SOME SERVICES FAILED"
  exit 1
fi

