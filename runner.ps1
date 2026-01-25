
Write-Host "Starting Queue Worker Runner..."

while ($true) {
    Write-Host "[Runner] Executing queue_worker.py..."
    
    # Run the worker script
    python queue_worker.py
    
    # Check exit code
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[Runner] ❌ CRASH: Worker stopped with exit code $LASTEXITCODE"
        Write-Host "[Runner] Timestamp: $(Get-Date)"
    } else {
        Write-Host "[Runner] Worker stopped with exit code 0."
    }
    
    Write-Host "[Runner] ⏳ Waiting 3 seconds before restart..."
    Start-Sleep -Seconds 3
    Write-Host "----------------------------------------"
}
