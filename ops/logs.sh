#!/usr/bin/env bash
set -euo pipefail

PROJECT="dashboard"
docker compose -p "$PROJECT" logs --tail=200
