#!/bin/bash

set -e 

echo -e "\nCopying over the .env.example into an .env file - fill in the values after.\n"
cp .env.example .env

uv sync --dev

echo -e "The .venv file set up, activate by running \`source .venv/bin/activate\`\n"

echo "project setup complete!"
