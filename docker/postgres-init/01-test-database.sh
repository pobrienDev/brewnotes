#!/bin/bash
# Runs once when the data volume is first created. Adds the separate test database.
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
    CREATE DATABASE brewnotes_test OWNER brewnotes;
SQL
