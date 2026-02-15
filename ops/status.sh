#!/usr/bin/env bash
set -euo pipefail

PROJECT="dashboard"
docker ps --filter "label=com.docker.compose.project=$PROJECT"
