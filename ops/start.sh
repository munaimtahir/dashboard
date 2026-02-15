#!/usr/bin/env bash
set -euo pipefail

PROJECT="dashboard"
LOG="/home/munaim/srv/ops/logs/dashboard_start_$(date +%Y%m%d_%H%M%S).log"

{
  echo "Starting project $PROJECT"
  docker compose -p "$PROJECT" up -d
  echo "Start completed"
} &> "$LOG"

echo "Log: $LOG"
