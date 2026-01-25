$ImageName = Read-Host -Prompt "Masukkan Nama Image Docker (contoh: username/universeai-bot)"
if ([string]::IsNullOrWhiteSpace($ImageName)) {
    Write-Host "Nama Image wajib diisi." -ForegroundColor Red
    exit 1
}

$Tag = Read-Host -Prompt "Masukkan Tag (default: latest)"
if ([string]::IsNullOrWhiteSpace($Tag)) {
    $Tag = "latest"
}

$FullImage = "$ImageName`:$Tag"

Write-Host "Sedang Build Image Docker: $FullImage..." -ForegroundColor Cyan
docker build -t $FullImage .

if ($LASTEXITCODE -eq 0) {
    Write-Host "Build Berhasil!" -ForegroundColor Green
    
    $Push = Read-Host -Prompt "Apakah Anda ingin push ke registry? (y/n)"
    if ($Push -eq "y") {
        Write-Host "Sedang melakukan Push ke registry..." -ForegroundColor Cyan
        docker push $FullImage
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Push Berhasil!" -ForegroundColor Green
        }
        else {
            Write-Host "Push Gagal. Pastikan Anda sudah login (docker login)." -ForegroundColor Red
        }
    }
}
else {
    Write-Host "Build Gagal." -ForegroundColor Red
}
