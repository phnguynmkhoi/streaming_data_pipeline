#!/bin/bash
# Creates/refreshes the hot+cold serving views in Trino (PLAN.md 4.3).
# Run after the first run_iceberg_merge.sh -- Trino validates each view's
# query at creation, so the Iceberg tables must already exist.
set -eu
cd "$(dirname "$0")/.."

docker exec -i trino trino < trino/views.sql
