#!/usr/bin/env bash
set -euo pipefail

PROJECT="dashboard"
APPDIR="/home/munaim/srv/apps/dashboard"
LOG="/home/munaim/srv/ops/logs/dashboard_deploy_$(date +%Y%m%d_%H%M%S).log"

{
  echo "Deploying $PROJECT"
  cd "$APPDIR"

  if [ -d ".git" ]; then
    echo "Pulling latest code"
    git fetch --all
    git reset --hard origin/$(git rev-parse --abbrev-ref HEAD)
  else
    echo "No git repo found. Skipping pull."
  fi

  echo "Rebuilding containers"
  docker compose -p "$PROJECT" build --pull

  echo "Bringing up containers"
  docker compose -p "$PROJECT" up -d

  echo "Deploy finished"



} &> "$LOG"

echo "Log: $LOG"
