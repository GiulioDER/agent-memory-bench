#!/bin/sh
set -e

echo "==> validating order intake"
python validate.py

echo "==> nightly billing"
python bill.py
