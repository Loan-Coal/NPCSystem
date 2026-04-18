Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Base = "http://127.0.0.1:8000"
$DoCleanup = $false

function Get-EnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Key,
        [string]$Default = ""
    )

    $line = Get-Content $Path | Where-Object { $_ -match "^\s*$Key\s*=" } | Select-Object -First 1
    if (-not $line) {
        if ($Default -ne "") { return $Default }
        throw "$Key not found in $Path"
    }

    $value = ($line -replace "^\s*$Key\s*=\s*", "").Trim().Trim('"').Trim("'")
    if ([string]::IsNullOrWhiteSpace($value)) {
        if ($Default -ne "") { return $Default }
        throw "$Key is empty in $Path"
    }

    return $value
}

function Get-EnvPath {
    $candidates = @(
        (Join-Path (Get-Location).Path ".env"),
        (Join-Path (Join-Path (Get-Location).Path "npc_engine") ".env")
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) { return $p }
    }
    throw ".env not found. Run this from npc_engine or repo root."
}

function ConvertFrom-JsonSafe {
    param([Parameter(Mandatory = $true)][string]$Text)

    $parameters = (Get-Command ConvertFrom-Json).Parameters
    if ($parameters.ContainsKey("Depth")) {
        return $Text | ConvertFrom-Json -Depth 100
    }
    return $Text | ConvertFrom-Json
}

function Invoke-WebRequestSafe {
    param(
        [Parameter(Mandatory = $true)][ValidateSet("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")][string]$Method,
        [Parameter(Mandatory = $true)][string]$Uri,
        [hashtable]$Headers,
        [string]$Body
    )

    $parameters = (Get-Command Invoke-WebRequest).Parameters
    $invokeArgs = @{
        Method = $Method
        Uri = $Uri
    }
    if ($null -ne $Headers) {
        $invokeArgs["Headers"] = $Headers
    }
    if (-not [string]::IsNullOrWhiteSpace($Body)) {
        $invokeArgs["Body"] = $Body
    }
    if ($parameters.ContainsKey("UseBasicParsing")) {
        $invokeArgs["UseBasicParsing"] = $true
    }

    return Invoke-WebRequest @invokeArgs
}

function New-ReadHeaders {
    return @{ "Authorization" = "Bearer $script:ApiKey" }
}

function New-WriteHeaders {
    param(
        [Parameter(Mandatory = $true)][string]$RequestId,
        [string]$IdempotencyKey = ([guid]::NewGuid().ToString()),
        [string]$RequestHash = ""
    )

    if ([string]::IsNullOrWhiteSpace($RequestHash)) {
        $RequestHash = "hash-$([guid]::NewGuid().ToString())"
    }

    return @{
        "Authorization" = "Bearer $script:ApiKey"
        "Content-Type" = "application/json"
        "X-Request-ID" = $RequestId
        "X-Idempotency-Key" = $IdempotencyKey
        "X-Idempotency-Request-Hash" = $RequestHash
    }
}

function Parse-BoolLike {
    param([string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return $false }
    return @("1", "true", "yes", "on") -contains $Text.Trim().ToLowerInvariant()
}

function Assert-True {
    param(
        [Parameter(Mandatory = $true)][bool]$Condition,
        [Parameter(Mandatory = $true)][string]$Message
    )
    if (-not $Condition) { throw "ASSERT FAILED: $Message" }
    Write-Host "[ASSERT OK] $Message" -ForegroundColor Green
}

function Read-ErrorResponseBody {
    param([Parameter(Mandatory = $true)]$Response)

    try {
        $contentProp = $Response.PSObject.Properties["Content"]
        if ($null -ne $contentProp -and $null -ne $Response.Content) {
            return $Response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        }
    } catch {}

    try {
        $streamMethod = $Response.PSObject.Methods["GetResponseStream"]
        if ($null -ne $streamMethod) {
            $stream = $Response.GetResponseStream()
            if ($null -ne $stream) {
                $reader = New-Object System.IO.StreamReader($stream)
                try {
                    return $reader.ReadToEnd()
                } finally {
                    $reader.Close()
                }
            }
        }
    } catch {}

    return ""
}

function Resolve-StatusCode {
    param([Parameter(Mandatory = $true)]$Response)

    try {
        $statusCode = $Response.StatusCode
        $valueProp = $statusCode.PSObject.Properties["value__"]
        if ($null -ne $valueProp) {
            return [int]$statusCode.value__
        }
        return [int]$statusCode
    } catch {
        return 0
    }
}

function Invoke-NpcApi {
    param(
        [Parameter(Mandatory = $true)][ValidateSet("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")][string]$Method,
        [Parameter(Mandatory = $true)][string]$Path,
        [hashtable]$Headers = $null,
        [object]$Body = $null,
        [int[]]$ExpectedStatus = @(200),
        [string]$Label = "",
        [switch]$AllowUnexpected
    )

    $uri = "$script:Base$Path"
    $jsonBody = $null
    if ($null -ne $Body) {
        if ($Body -is [string]) {
            $jsonBody = $Body
        } else {
            $jsonBody = $Body | ConvertTo-Json -Depth 50
        }
    }

    $status = 0
    $raw = ""
    $responseHeaders = $null

    try {
        $resp = Invoke-WebRequestSafe -Method $Method -Uri $uri -Headers $Headers -Body $jsonBody
        $status = [int]$resp.StatusCode
        $raw = [string]$resp.Content
        $responseHeaders = $resp.Headers
    } catch {
        if ($_.Exception -and $_.Exception.Response) {
            $status = Resolve-StatusCode -Response $_.Exception.Response
            $raw = Read-ErrorResponseBody -Response $_.Exception.Response
            if ([string]::IsNullOrWhiteSpace($raw)) {
                if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
                    $raw = $_.ErrorDetails.Message
                } else {
                    $raw = $_.Exception.Message
                }
            }
        } else {
            throw
        }
    }

    $parsed = $null
    if (-not [string]::IsNullOrWhiteSpace($raw)) {
        try {
            $parsed = ConvertFrom-JsonSafe -Text $raw
        } catch {
            $parsed = $raw
        }
    }

    $ok = $ExpectedStatus -contains $status
    $statusLabel = if ($ok) { "PASS" } else { "FAIL" }
    $prefix = if ([string]::IsNullOrWhiteSpace($Label)) { "$Method $Path" } else { $Label }

    if ($ok) {
        Write-Host "[$statusLabel] $prefix -> HTTP $status" -ForegroundColor Cyan
    } else {
        Write-Host "[$statusLabel] $prefix -> HTTP $status" -ForegroundColor Red
    }

    if ($null -ne $parsed) {
        if ($parsed -is [string]) {
            Write-Host $parsed
        } else {
            Write-Host ($parsed | ConvertTo-Json -Depth 20)
        }
    }

    if (-not $ok -and -not $AllowUnexpected) {
        throw "Unexpected status $status for $Method $Path (expected: $($ExpectedStatus -join ','))"
    }

    return [pscustomobject]@{
        StatusCode = $status
        Json = $parsed
        Raw = $raw
        Headers = $responseHeaders
        Uri = $uri
    }
}

$EnvPath = Get-EnvPath
$script:ApiKey = Get-EnvValue -Path $EnvPath -Key "API_KEY_SECRET"
$script:Base = $Base
$idempotencyEnforced = Parse-BoolLike (Get-EnvValue -Path $EnvPath -Key "IDEMPOTENCY_ENFORCE_HEADER" -Default "false")

$runId = Get-Date -Format "yyyyMMddHHmmss"
$playerId = "player_manual_$runId"
$npcId = "npc_manual_$runId"
$vendorId = "vendor_manual_$runId"
$locationA = "loc_manual_square_$runId"
$locationB = "loc_manual_docks_$runId"
$eventId = "event_manual_$runId"
$questId = "quest_manual_$runId"
$sessionId = "session_manual_$runId"
$sessionScope = "manual_session_$runId"

Write-Host "Using .env: $EnvPath"
Write-Host "IDEMPOTENCY_ENFORCE_HEADER=$idempotencyEnforced"

Invoke-NpcApi -Method GET -Path "/health" -ExpectedStatus @(200) -Label "health"
Invoke-NpcApi -Method GET -Path "/v1/protected" -Headers (New-ReadHeaders) -ExpectedStatus @(200) -Label "protected"

$meta = @{ request_id = "req-meta-$runId"; actor_id = "manual_tester"; reason = "manual_e2e" }

Invoke-NpcApi -Method POST -Path "/v1/graph/locations" -Headers (New-WriteHeaders -RequestId "req-loc-a") -ExpectedStatus @(200) -Body @{ id = $locationA; name = "Manual Square"; region = "manual"; location_tag = "square"; descriptor = "manual location a" }
Invoke-NpcApi -Method POST -Path "/v1/graph/locations" -Headers (New-WriteHeaders -RequestId "req-loc-b") -ExpectedStatus @(200) -Body @{ id = $locationB; name = "Manual Docks"; region = "manual"; location_tag = "docks"; descriptor = "manual location b" }

Invoke-NpcApi -Method POST -Path "/v1/graph/characters" -Headers (New-WriteHeaders -RequestId "req-char-player") -ExpectedStatus @(200) -Body @{ id = $playerId; name = "Manual Player"; archetype = "adventurer"; faction = "manual"; biography = "player"; current_location_id = $locationA; is_player = $true; is_active = $true; gossipy = 40; credulity = 60; honesty = 55; current_mood = "neutral" }
Invoke-NpcApi -Method POST -Path "/v1/graph/characters" -Headers (New-WriteHeaders -RequestId "req-char-npc") -ExpectedStatus @(200) -Body @{ id = $npcId; name = "Manual NPC"; archetype = "guard"; faction = "manual"; biography = "npc"; current_location_id = $locationA; is_player = $false; is_active = $true; gossipy = 70; credulity = 45; honesty = 65; current_mood = "neutral" }
Invoke-NpcApi -Method POST -Path "/v1/graph/characters" -Headers (New-WriteHeaders -RequestId "req-char-vendor") -ExpectedStatus @(200) -Body @{ id = $vendorId; name = "Manual Vendor"; archetype = "merchant"; faction = "manual"; biography = "vendor"; current_location_id = $locationA; is_player = $false; is_active = $true; gossipy = 50; credulity = 50; honesty = 70; current_mood = "neutral" }

Invoke-NpcApi -Method POST -Path "/v1/graph/edges/located_at" -Headers (New-WriteHeaders -RequestId "req-loc-player") -ExpectedStatus @(200) -Body @{ character_id = $playerId; location_id = $locationA; is_permanent_resident = $false; meta = $meta }
Invoke-NpcApi -Method POST -Path "/v1/graph/edges/located_at" -Headers (New-WriteHeaders -RequestId "req-loc-npc") -ExpectedStatus @(200) -Body @{ character_id = $npcId; location_id = $locationA; is_permanent_resident = $true; meta = $meta }
Invoke-NpcApi -Method POST -Path "/v1/graph/edges/relates_to" -Headers (New-WriteHeaders -RequestId "req-rel") -ExpectedStatus @(200) -Body @{ src_id = $npcId; dst_id = $playerId; trust = 60; fear = 30; affection = 55; meta = $meta }

Invoke-NpcApi -Method POST -Path "/v1/graph/events" -Headers (New-WriteHeaders -RequestId "req-event") -ExpectedStatus @(200) -Body @{
    id = $eventId
    summary = "Manual event"
    severity = 50
    location_id = $locationA
    occurred_at = (Get-Date).ToUniversalTime().ToString("o")
    tick_id = 9001
    participants = @($npcId)
    event_type = "crime"
    is_public = $true
    producer = "manual_test"
    origin_engine = "manual"
    schema_version = "v1.4"
    provenance = @{ request_id = "req-event"; actor_id = "manual_tester"; reason = "manual"; idempotency_key = "manual-$runId"; idempotency_request_hash = "hash-manual-$runId" }
}

Invoke-NpcApi -Method POST -Path "/v1/graph/edges/knows_about" -Headers (New-WriteHeaders -RequestId "req-knows") -ExpectedStatus @(200) -Body @{ character_id = $npcId; event_id = $eventId; knowledge_state = "knows"; learned_at_tick = 9001; meta = $meta }
Invoke-NpcApi -Method POST -Path "/v1/graph/edges/participated_in" -Headers (New-WriteHeaders -RequestId "req-part") -ExpectedStatus @(200) -Body @{ character_id = $npcId; event_id = $eventId; role = "witness"; meta = $meta }

$state = Invoke-NpcApi -Method GET -Path "/v1/npc/$npcId/state?include_relations=true&include_events=true" -Headers (New-ReadHeaders) -ExpectedStatus @(200)
Assert-True -Condition ($null -ne $state.Json.character) -Message "NPC state contains character"

$d1 = Invoke-NpcApi -Method POST -Path "/v1/dialogue" -Headers (New-WriteHeaders -RequestId "req-dialogue-1") -ExpectedStatus @(200) -Body @{ player_id = $playerId; npc_id = $npcId; player_message = "What happened at the square?"; location_id = $locationA; session_id = $sessionId }
Assert-True -Condition ($d1.Json.session_id -eq $sessionId) -Message "Dialogue returns same session id"

Invoke-NpcApi -Method PATCH -Path "/v1/graph/world_state" -Headers (New-WriteHeaders -RequestId "req-world") -ExpectedStatus @(200) -Body @{ weather = "storm"; active_conditions = @("manual_test"); faction_standings = @{ manual = 10 }; meta = $meta }

$qOffer = Invoke-NpcApi -Method POST -Path "/v1/quest/offer" -Headers (New-WriteHeaders -RequestId "req-quest-offer") -ExpectedStatus @(200) -Body @{ quest_id = $questId; player_id = $playerId; title = "Collect Tokens"; objectives = @(@{ objective_id = "obj_tokens"; target_count = 2 }); item_rewards = @(@{ item_id = "dock_token"; quantity = 1 }); currency_reward = @{ amount = 25 } }
Assert-True -Condition ($qOffer.Json.status -eq "ok") -Message "Quest offer accepted"

Invoke-NpcApi -Method POST -Path "/v1/quest/accept" -Headers (New-WriteHeaders -RequestId "req-quest-accept") -ExpectedStatus @(200) -Body @{ quest_id = $questId; player_id = $playerId }
Invoke-NpcApi -Method POST -Path "/v1/quest/objective" -Headers (New-WriteHeaders -RequestId "req-quest-obj-1") -ExpectedStatus @(200) -Body @{ quest_id = $questId; player_id = $playerId; objective_id = "obj_tokens"; progress_delta = 1 }
Invoke-NpcApi -Method POST -Path "/v1/quest/objective" -Headers (New-WriteHeaders -RequestId "req-quest-obj-2") -ExpectedStatus @(200) -Body @{ quest_id = $questId; player_id = $playerId; objective_id = "obj_tokens"; progress_delta = 1 }
Invoke-NpcApi -Method POST -Path "/v1/quest/evaluate" -Headers (New-WriteHeaders -RequestId "req-quest-eval") -ExpectedStatus @(200) -Body @{ quest_id = $questId; player_id = $playerId }
Invoke-NpcApi -Method POST -Path "/v1/quest/reward" -Headers (New-WriteHeaders -RequestId "req-quest-reward") -ExpectedStatus @(200) -Body @{ quest_id = $questId; player_id = $playerId }

$buyIdem = [guid]::NewGuid().ToString()
$buyBody = @{ player_id = $playerId; npc_id = $npcId; action_type = "buy_item"; intensity = 20; counterparty_id = $vendorId; currency_amount = 10; currency_reason = "manual_buy_test"; session_scope = $sessionScope }
$buy1 = Invoke-NpcApi -Method POST -Path "/v1/action" -Headers (New-WriteHeaders -RequestId "req-buy-1" -IdempotencyKey $buyIdem -RequestHash "hash-buy-$runId") -ExpectedStatus @(200) -Body $buyBody
$buy2 = Invoke-NpcApi -Method POST -Path "/v1/action" -Headers (New-WriteHeaders -RequestId "req-buy-2" -IdempotencyKey $buyIdem -RequestHash "hash-buy-$runId") -ExpectedStatus @(200) -Body $buyBody
Assert-True -Condition ($buy1.Json.currency_transfer.source_balance -eq $buy2.Json.currency_transfer.source_balance) -Message "Repeated idempotency key does not double debit"

$eventsResp = Invoke-NpcApi -Method GET -Path "/v1/graph/events?limit=500&offset=0" -Headers (New-ReadHeaders) -ExpectedStatus @(200)
$questEvents = @($eventsResp.Json.data | Where-Object { $_.id -like "${questId}:*" })
Write-Host "Quest events found: $($questEvents.Count)"
$questEvents | Select-Object id, event_type, summary, producer, origin_engine, schema_version | Format-Table -AutoSize

$reindex = Invoke-NpcApi -Method POST -Path "/v1/graph/admin/reindex" -Headers (New-WriteHeaders -RequestId "req-reindex") -ExpectedStatus @(202) -Body @{ npc_ids = @($npcId, $vendorId) }
$jobId = $reindex.Json.data.job_id

if (-not [string]::IsNullOrWhiteSpace($jobId)) {
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 300
        $job = Invoke-NpcApi -Method GET -Path "/v1/graph/admin/reindex/$jobId" -Headers (New-ReadHeaders) -ExpectedStatus @(200)
        $status = $job.Json.data.status
        if ($status -in @("completed", "failed")) {
            Write-Host "Reindex job finished with status=$status"
            break
        }
    }
}

if ($DoCleanup) {
    Invoke-NpcApi -Method DELETE -Path "/v1/graph/edges/participated_in/$npcId/$eventId" -Headers (New-WriteHeaders -RequestId "req-del-part") -ExpectedStatus @(200)
    Invoke-NpcApi -Method DELETE -Path "/v1/graph/edges/knows_about/$npcId/$eventId" -Headers (New-WriteHeaders -RequestId "req-del-knows") -ExpectedStatus @(200)
    Invoke-NpcApi -Method DELETE -Path "/v1/graph/edges/relates_to/$npcId/$playerId" -Headers (New-WriteHeaders -RequestId "req-del-rel") -ExpectedStatus @(200)

    $eventsAll = Invoke-NpcApi -Method GET -Path "/v1/graph/events?limit=1000&offset=0" -Headers (New-ReadHeaders) -ExpectedStatus @(200)
    $questEventsToDelete = @($eventsAll.Json.data | Where-Object { $_.id -like "${questId}:*" })
    foreach ($qe in $questEventsToDelete) {
        Invoke-NpcApi -Method DELETE -Path "/v1/graph/admin/events/$($qe.id)" -Headers (New-WriteHeaders -RequestId "req-del-$([guid]::NewGuid().ToString())") -ExpectedStatus @(200)
    }

    Invoke-NpcApi -Method DELETE -Path "/v1/graph/admin/events/$eventId" -Headers (New-WriteHeaders -RequestId "req-del-event") -ExpectedStatus @(200, 404)
    Invoke-NpcApi -Method DELETE -Path "/v1/graph/admin/characters/$npcId" -Headers (New-WriteHeaders -RequestId "req-del-npc") -ExpectedStatus @(200, 404)
    Invoke-NpcApi -Method DELETE -Path "/v1/graph/admin/characters/$vendorId" -Headers (New-WriteHeaders -RequestId "req-del-vendor") -ExpectedStatus @(200, 404)
    Invoke-NpcApi -Method DELETE -Path "/v1/graph/admin/characters/$playerId" -Headers (New-WriteHeaders -RequestId "req-del-player") -ExpectedStatus @(200, 404)
    Invoke-NpcApi -Method DELETE -Path "/v1/graph/admin/locations/$locationA" -Headers (New-WriteHeaders -RequestId "req-del-loc-a") -ExpectedStatus @(200, 404)
    Invoke-NpcApi -Method DELETE -Path "/v1/graph/admin/locations/$locationB" -Headers (New-WriteHeaders -RequestId "req-del-loc-b") -ExpectedStatus @(200, 404)
}

Write-Host "Manual system test run completed."
Write-Host "QuestId=$questId PlayerId=$playerId NpcId=$npcId VendorId=$vendorId EventId=$eventId"