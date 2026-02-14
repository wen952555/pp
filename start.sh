#!/bin/bash
echo "Starting PikPak Bot..."
echo "Press Ctrl+C to stop."

# Loop to restart bot if it crashes
while true; do
    python bot.py
    echo "Bot stopped. Restarting in 3 seconds..."
    sleep 3
done
