#!/bin/bash

# Usage check
if [ -z "$1" ]; then
  echo "Usage: $0 <PI_HOST>"
  exit 1
fi

# Variables
PI_USER=juara
PI_HOST=$1
REMOTE_PATH=/home/pi/juara-field-sensors
LOCAL_PATH=./

# Sync code to Pi
rsync -avz --exclude-from='.rsync-exclude' "$LOCAL_PATH" "$PI_USER@$PI_HOST:$REMOTE_PATH"

# Run the code on the Pi over SSH
ssh "$PI_USER@$PI_HOST" "cd $REMOTE_PATH"