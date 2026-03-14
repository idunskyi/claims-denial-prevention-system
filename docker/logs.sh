#!/bin/bash

source ./.env

# Get list of services
SERVICES=$(docker compose -p "$PROJECT_NAME" config --services | sort)

# Convert services to an array
SERVICE_ARRAY=($SERVICES)

# Add 'All' option to the array
SERVICE_ARRAY=("All" "${SERVICE_ARRAY[@]}")

# Display the list of services
echo "Select the service(s) you want to tail logs from:"
for i in "${!SERVICE_ARRAY[@]}"; do
  printf "%3d) %s\n" $((i+1)) "${SERVICE_ARRAY[i]}"
done

echo "Enter the numbers corresponding to the services (e.g., 1 2 3), or 'All' to monitor all logs:"

# Read user input
read -ra INPUT

# Check if 'All' is selected
if [[ " ${INPUT[@]} " =~ " 1 " || " ${INPUT[@]} " =~ " All " ]]; then
  docker compose -p "$PROJECT_NAME" logs -f --timestamps
else
  # Map selected numbers to service names
  SELECTED_SERVICES=()
  for index in "${INPUT[@]}"; do
    SELECTED_SERVICES+=("${SERVICE_ARRAY[$((index-1))]}")
  done
  docker compose -p "$PROJECT_NAME" logs -f --timestamps "${SELECTED_SERVICES[@]}"
fi