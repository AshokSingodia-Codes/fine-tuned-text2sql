#!/usr/bin/env bash
set -e

echo "Downloading Spider dataset..."
mkdir -p data/raw
python -m src.t2s.data.download
