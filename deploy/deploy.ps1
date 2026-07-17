# =============================================================================
# YuanMo ZhuLu - Windows Deploy Script (PowerShell 5.1 Compatible)
# Usage: .\deploy\deploy.ps1 [-Server <IP>] [-User <user>] [-Port <port>] [-SkipBuild]
# =============================================================================
param(
    [string]$Server = "",
    [string]$User = "root",
    [int]$Port = 22,
    [switch]$SkipBuild = $false
)

$ErrorActionPreference = "Stop"
$ProjectDir = (Get-Item (Split-Path -Parent $MyInvocation.MyCommand.Path)).Parent.FullName
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$PackageName = "yuanmo-deploy-${Timestamp}.tar.gz"
$PackagePath = Join-Path $env:TEMP $PackageName
$ServerDeployPath = "/opt/yuanmo"

Write-Host ""
Write-Host "  YuanMo ZhuLu 3.0 - Windows Deploy Packager"
Write-Host "  ===========================================" -ForegroundColor Blue
Write-Host ""

# ------------------------------------------------------------
# Step 1: Build frontend
# ------------------------------------------------------------
if (-not $SkipBuild) {
    Write-Host "[1/4] Building frontend..." -ForegroundColor Green
    Push-Location (Join-Path $ProjectDir "frontend")
    try {
        $npmResult = npm run build 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] Frontend build failed!" -ForegroundColor Red
            Write-Host $npmResult
            exit 1
        }
        Write-Host "  OK: frontend/dist/" -ForegroundColor Green
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "[1/4] Skip build (--SkipBuild)" -ForegroundColor Yellow
    $distIndex = Join-Path $ProjectDir "frontend\dist\index.html"
    if (-not (Test-Path $distIndex)) {
        Write-Host "[ERROR] frontend/dist/index.html not found! Remove --SkipBuild" -ForegroundColor Red
        exit 1
    }
}

# ------------------------------------------------------------
# Step 2: Package files
# ------------------------------------------------------------
Write-Host "[2/4] Packaging..." -ForegroundColor Green

$PackDir = Join-Path $env:TEMP "yuanmo-pack-${Timestamp}"
New-Item -ItemType Directory -Force -Path $PackDir | Out-Null

$filesToCopy = @(
    @{Src="server";                    Dst="server"},
    @{Src="server.py";                 Dst="server.py"},
    @{Src="requirements.txt";          Dst="requirements.txt"},
    @{Src="frontend\dist";             Dst="frontend\dist"},
    @{Src="deploy\Dockerfile";         Dst="deploy\Dockerfile"},
    @{Src="deploy\docker-compose.yml"; Dst="deploy\docker-compose.yml"},
    @{Src="deploy\nginx\default.conf"; Dst="deploy\nginx\default.conf"},
    @{Src="deploy\update-server.sh";   Dst="deploy\update-server.sh"},
    @{Src="deploy\.env";               Dst="deploy\.env"}
)

foreach ($item in $filesToCopy) {
    $src = Join-Path $ProjectDir $item.Src
    $dst = Join-Path $PackDir $item.Dst
    $dstDir = Split-Path -Parent $dst
    if (-not (Test-Path $dstDir)) {
        New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
    }
    if (Test-Path $src) {
        Copy-Item -Recurse -Force -Path $src -Destination $dst
        Write-Host "  + $($item.Src)" -ForegroundColor DarkGray
    }
    else {
        Write-Host "  WARN: not found - $($item.Src)" -ForegroundColor Yellow
    }
}

# Create DEPLOY_README.txt
$readmePath = Join-Path $PackDir "DEPLOY_README.txt"
$readmeContent = @"
==============================================
YuanMo ZhuLu 3.0 - Deploy Package ($Timestamp)
==============================================

Server-side steps (Ubuntu 22.04 LTS):

1. Upload package:
   scp $PackageName root@<SERVER_IP>:$ServerDeployPath/

2. SSH into server:
   ssh root@<SERVER_IP>

3. Extract and deploy:
   cd $ServerDeployPath
   tar -xzf $PackageName
   chmod +x deploy/update-server.sh
   bash deploy/update-server.sh

4. Verify:
   curl https://qiankuntokenyun.cn/api/health

Note: update-server.sh preserves existing nginx config by default.
  To force nginx update: bash deploy/update-server.sh --force-nginx

Rollback: backup created at /opt/yuanmo-backup-*

==============================================
"@
[System.IO.File]::WriteAllText($readmePath, $readmeContent, [System.Text.UTF8Encoding]::new($false))

# Package
Push-Location $PackDir
try {
    tar -czf $PackagePath *
    $packageSize = [math]::Round((Get-Item $PackagePath).Length / 1MB, 2)
    Write-Host "  OK: $PackagePath (${packageSize} MB)" -ForegroundColor Green
}
finally {
    Pop-Location
}

Remove-Item -Recurse -Force $PackDir

# ------------------------------------------------------------
# Step 3-4: Upload and remote deploy
# ------------------------------------------------------------
if ($Server) {
    Write-Host "[3/4] Uploading to server $Server ..." -ForegroundColor Green
    
    $sshConn = "${User}@${Server}"
    Write-Host "  Checking SSH connection..."
    
    $sshTestOK = $false
    try {
        $testCmd = "ssh -p ${Port} -o ConnectTimeout=5 -o BatchMode=yes ${sshConn} 'echo OK' 2>&1"
        $sshResult = Invoke-Expression $testCmd
        if ($LASTEXITCODE -eq 0) {
            $sshTestOK = $true
        }
    } catch { }

    if (-not $sshTestOK) {
        Write-Host "  WARN: SSH keyless login not available (may need password)" -ForegroundColor Yellow
        Write-Host "  Manual commands:" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  scp -P ${Port} ${PackagePath} ${sshConn}:${ServerDeployPath}/" -ForegroundColor Cyan
        Write-Host "  ssh -p ${Port} ${sshConn}" -ForegroundColor Cyan
        Write-Host "  cd ${ServerDeployPath} && tar -xzf ${PackageName} && bash deploy/update-server.sh" -ForegroundColor Cyan
        Write-Host ""
        exit 0
    }

    # Create remote dir
    Invoke-Expression "ssh -p ${Port} ${sshConn} 'mkdir -p ${ServerDeployPath}'" 2>&1 | Out-Null

    # Upload
    Write-Host "  Uploading package..."
    Invoke-Expression "scp -P ${Port} ${PackagePath} ${sshConn}:${ServerDeployPath}/"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Upload failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "  OK: upload complete" -ForegroundColor Green

    # Remote deploy
    Write-Host "[4/4] Remote deploy..." -ForegroundColor Green
    $remoteCmd = "cd ${ServerDeployPath} && tar -xzf ${PackageName} && chmod +x deploy/update-server.sh && bash deploy/update-server.sh"
    Invoke-Expression "ssh -p ${Port} ${sshConn} '${remoteCmd}'"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  WARN: remote update may have issues, check server logs" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "  =========================================" -ForegroundColor Blue
    Write-Host "  Done! Visit: https://qiankuntokenyun.cn" -ForegroundColor Green
    Write-Host "  =========================================" -ForegroundColor Blue
    Write-Host ""
}
else {
    Write-Host "[3/4] No server specified, skip upload" -ForegroundColor Yellow
    Write-Host "[4/4] Package ready:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  =========================================" -ForegroundColor Blue
    Write-Host "  Package: $PackageName (${packageSize} MB)" -ForegroundColor Green
    Write-Host "  =========================================" -ForegroundColor Blue
    Write-Host ""
    Write-Host "  Next steps (manual):" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  1. Upload to Alibaba Cloud server:" -ForegroundColor White
    Write-Host "     scp ${PackagePath} root@<SERVER_IP>:${ServerDeployPath}/" -ForegroundColor White
    Write-Host ""
    Write-Host "  2. SSH into server:" -ForegroundColor White
    Write-Host "     ssh root@<SERVER_IP>" -ForegroundColor White
    Write-Host ""
    Write-Host "  3. Extract and deploy:" -ForegroundColor White
    Write-Host "     cd ${ServerDeployPath}" -ForegroundColor White
    Write-Host "     tar -xzf ${PackageName}" -ForegroundColor White
    Write-Host "     bash deploy/update-server.sh" -ForegroundColor White
    Write-Host ""
    Write-Host "  4. Verify:" -ForegroundColor White
    Write-Host "     curl https://qiankuntokenyun.cn/api/health" -ForegroundColor White
    Write-Host ""
}

Write-Host "  Package kept at: $PackagePath" -ForegroundColor DarkGray
Write-Host ""
