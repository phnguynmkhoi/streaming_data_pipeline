#!/bin/bash

# Check if the user has provided an argument
if [ -z "$1" ]; then
    echo "Usage: $0 <arg>"
    echo "arg: schema name"
    exit 1
fi

# Get the first argument
ARG="$1"

# Build the JSON file path using the argument
JSON_FILE="pinot/${ARG}_table.json"

# Check if the JSON file exists
if [ ! -f "$JSON_FILE" ]; then
    echo "Error: JSON file '$JSON_FILE' not found!"
    exit 1
fi

# Execute the curl command
# curl -X POST \
#     -H "Content-Type: application/json" \
#     -d @"$JSON_FILE" \
#     http://localhost:9000/schemas

curl -X POST \
    -H "Content-Type: application/json" \
    -d @"$JSON_FILE" http://localhost:9000/tables
# Exit with the curl exit code
exit $?