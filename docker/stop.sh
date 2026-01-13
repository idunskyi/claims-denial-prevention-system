#!/bin/bash

source ./.env

docker compose -p "$PROJECT_NAME" down --timeout 0