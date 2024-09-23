#!/bin/bash

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Print installed packages for debugging
pip list

echo "Build completed successfully!"
