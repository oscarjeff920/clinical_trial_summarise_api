#!/bin/bash

set -e

uv sync

uv run python -m app.api.local_api_run