#!/bin/bash
set -e
cd "$(dirname "$0")"

cp .env.example .env
echo "Created .env from .env.example — fill in any values, then run ./run_api.sh or docker compose up"