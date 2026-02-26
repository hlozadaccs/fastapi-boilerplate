#!/bin/bash
# Script to initialize test database

set -e

echo "Initializing test database..."

# Set test database environment
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5433
export POSTGRES_DB=fastapi_db_test

# Run migrations
poetry run alembic upgrade head

echo "✓ Test database initialized successfully"
