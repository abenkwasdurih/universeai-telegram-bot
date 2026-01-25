#!/bin/bash

echo "Starting Queue Worker Runner..."

while true; do
    echo "[Runner] Executing queue_worker.py..."
    
    # Run the worker script
    python queue_worker.py
    
    # Capture the exit code
    EXIT_CODE=$?
    
    # Check if it crashed (non-zero exit code)
    if [ $EXIT_CODE -ne 0 ]; then
        echo "[Runner] ❌ CRASH: Worker stopped with exit code $EXIT_CODE"
        echo "[Runner] Timestamp: $(date)"
    else
        echo "[Runner] Worker stopped with exit code 0."
    fi
    
    echo "[Runner] ⏳ Waiting 3 seconds before restart..."
    sleep 3
    echo "----------------------------------------"
done
