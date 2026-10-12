param(
    [string]$FrontendMarker = "reportTemplates",
    [string]$BackendMarker = "AssignmentBatch",
    [string]$TargetUrl = "https://localhost:8443"
)

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  CISO ASSISTANT DEPLOYMENT DIAGNOSTIC VERIFIER  " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# Step 1: Docker Containers Status
Write-Host "`n[1/6] Checking Docker Container Status..." -ForegroundColor Yellow
try {
    $psOutput = docker compose ps --format json | ConvertFrom-Json
    foreach ($c in $psOutput) {
        $statusColor = if ($c.State -eq "running") { "Green" } else { "Red" }
        Write-Host "  - Container '$($c.Name)' ($($c.Service)): $($c.State)" -ForegroundColor $statusColor
    }
} catch {
    Write-Host "  ! Error querying docker compose ps: $_" -ForegroundColor Red
}

# Step 2: Check Frontend Container Source
Write-Host "`n[2/6] Checking Frontend Container Build Output..." -ForegroundColor Yellow
$feMatches = docker compose exec frontend grep -rn "$FrontendMarker" /app/build 2>$null
if ($feMatches) {
    Write-Host "  [PASS] Frontend container has the updated marker!" -ForegroundColor Green
    $sampleStr = [string]$feMatches[0]
    Write-Host "  Sample match: $($sampleStr.Substring(0, [Math]::Min(120, $sampleStr.Length)))" -ForegroundColor Gray
} else {
    Write-Host "  [FAIL] Frontend container missing marker '$FrontendMarker'" -ForegroundColor Red
}

# Step 3: Check Backend Container Source
Write-Host "`n[3/6] Checking Backend Container Code..." -ForegroundColor Yellow
$beMatches = docker compose exec backend grep -rn "$BackendMarker" /code/core 2>$null
if ($beMatches) {
    Write-Host "  [PASS] Backend container has the updated symbol!" -ForegroundColor Green
    Write-Host "         Sample match: $($beMatches[0].Substring(0, [Math]::Min(120, $beMatches[0].Length)))" -ForegroundColor Gray
} else {
    Write-Host "  [FAIL] Backend container missing symbol '$BackendMarker'" -ForegroundColor Red
}

# Step 4: Fetch Route & Extract Dynamic JS Chunks
Write-Host "`n[4/6] Fetching App Shell from Caddy ($TargetUrl)..." -ForegroundColor Yellow
try {
    $curlHtml = curl.exe -k -s -L "$TargetUrl/"
    if ($curlHtml) {
        Write-Host "  [PASS] Successfully reached Caddy over HTTPS." -ForegroundColor Green
        
        # Extract JS chunk links from HTML
        $jsMatches = [regex]::Matches($curlHtml, '_app/immutable/[^"]+\.js') | Select-Object -ExpandProperty Value -Unique
        Write-Host "  Discovered $($jsMatches.Count) core JS bundle chunks in app shell:" -ForegroundColor Gray
        foreach ($js in $jsMatches) {
            Write-Host "   -> $js" -ForegroundColor DarkGray
        }
    } else {
        Write-Host "  [FAIL] Caddy returned empty response." -ForegroundColor Red
    }
} catch {
    Write-Host "  [FAIL] Failed to connect to Caddy at $($TargetUrl): $_" -ForegroundColor Red
}

# Step 5: Test Key Route & Dynamic Node Fetching
Write-Host "`n[5/6] Testing Dynamic Chunk Retrieval via Caddy..." -ForegroundColor Yellow
$targetChunkMatch = docker exec frontend grep -rn "$FrontendMarker" /app/build/client/_app/immutable/nodes/ 2>$null
if ($targetChunkMatch) {
    # Extract filename from grep output
    $filePath = ($targetChunkMatch -split ":")[0]
    $relativeUrl = $filePath.Replace("/app/build/client/", "")
    Write-Host "  Located target node chunk in container: $relativeUrl" -ForegroundColor Gray
    
    # Curl through Caddy
    $chunkCurl = curl.exe -k -s "$TargetUrl/$relativeUrl"
    if ($chunkCurl -match [regex]::Escape($FrontendMarker)) {
        Write-Host "  [PASS] Caddy served the exact NEW chunk through HTTPS!" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] Caddy served chunk but marker missing!" -ForegroundColor Red
    }
} else {
    Write-Host "  [WARN] Could not find client node chunk containing marker '$FrontendMarker'" -ForegroundColor Yellow
}

# Step 6: Backend API Endpoint Execution Test
Write-Host "`n[6/6] Testing Live Backend API Endpoint Execution..." -ForegroundColor Yellow
try {
    $apiResponse = curl.exe -k -s "$TargetUrl/api/health/"
    if ($apiResponse -match "ok" -or $apiResponse -match "status") {
        Write-Host "  [PASS] Live Backend API is healthy & executing ($apiResponse)" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] Health endpoint returned: $apiResponse" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  [FAIL] Backend API endpoint unreachable: $_" -ForegroundColor Red
}

Write-Host "`n==================================================" -ForegroundColor Cyan
Write-Host "DIAGNOSTIC SUMMARY:" -ForegroundColor Cyan
Write-Host "If Steps 1-6 PASS, the Docker -> frontend/backend -> Caddy -> HTTPS delivery pipeline is verified." -ForegroundColor White
Write-Host "Any remaining stale UI issue is downstream of Caddy, unless the browser is requesting a different URL/asset than the diagnostic tested." -ForegroundColor White
Write-Host "==================================================" -ForegroundColor Cyan
