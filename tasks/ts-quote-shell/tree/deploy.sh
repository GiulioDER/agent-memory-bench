#!/usr/bin/env bash
set -euo pipefail

TARGET=$1

mkdir -p $TARGET/app
cp app/main.py $TARGET/app/
echo "deployed app to $TARGET"
