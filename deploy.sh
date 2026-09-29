#!/bin/bash
# deploy.sh snippet - Safely build database configuration profile layers

echo "Building production database connection configurations..."

# Create a clean database.ini replacing local targets with environment targets
cat << EOF > database.ini
[postgresql]
host=${DB_HOST}
database=${DB_NAME}
user=${DB_USER}
password=${DB_PASSWORD}
port=${DB_PORT:-5440}
EOF

echo "database.ini file populated dynamically. Executing migration tasks..."
# python ingest_catalog.py
