<#
.SYNOPSIS
    OpenCrew setup for Windows (experimental, source install — no service).

.DESCRIPTION
    Bootstraps the Kiro Crew gateway on the opencode (kas) backend on Windows:
    clones/reuses the checkout, creates an in-checkout .venv (the stock
    Windows convention), restores the frontend bundle from the official wheel,
    writes %USERPROFILE%\.kiro\crew.env with the KAS node pins, merges the
    kirocrew agents + MCP servers into opencode.json, writes the agent prompt
    files, links the skills directory, and sets config.json for the kas
    backend (with the Windows sandbox opt-in).

    Idempotent. Windows has no kirocrew service manager: run the gateway
    manually (see the output) or via Task Scheduler.

.PARAMETER Check
    Verify-only: report state, change nothing.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File setup.ps1
    powershell -ExecutionPolicy Bypass -File setup.ps1 -Check
#>
param(
    [switch]$Check
)

$ErrorActionPreference = "Stop"
$RepoUrl   = "https://github.com/hamin2006/OpenCrew.git"
$WheelVer  = "0.3.0"
$Checkout  = Join-Path $HOME "KiroCrew"
$KiHome    = Join-Path $HOME ".kiro"
$CrewHome  = Join-Path $KiHome "crew"
$EnvFile   = Join-Path $KiHome "crew.env"
$OcConfig  = Join-Path $HOME ".config\opencode"
$OcJson    = Join-Path $OcConfig "opencode.json"
$OcAgentDir= Join-Path $OcConfig "agent"
$SkillsDir = Join-Path $CrewHome "skills"
$OcSkills  = Join-Path $OcConfig "skills"
$DefaultModel = if ($env:OPENCREW_MODEL) { $env:OPENCREW_MODEL } else { "deepseek/deepseek-v4-flash" }
$model = $DefaultModel

function Say($m) { Write-Host "== $m" -ForegroundColor Cyan }
function Ok($m)  { Write-Host "  [OK] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "  [!] $m" -ForegroundColor Yellow }
function Fail($m){ Write-Host "  [X] $m" -ForegroundColor Red }
function Set-Utf8NoBom($Path, $Content) {
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $enc)
}

# ── Preflight ─────────────────────────────────────────────────────────────
Say "Preflight"
$OpenCodeBin = ""
$c = Get-Command opencode -ErrorAction SilentlyContinue
if ($c) { $OpenCodeBin = $c.Source }
if (-not $OpenCodeBin) {
    foreach ($cand in @(
        (Join-Path $HOME ".opencode\bin\opencode.exe"),
        (Join-Path $HOME ".opencode\bin\opencode"),
        (Join-Path $HOME "AppData\Local\opencode\opencode.exe")
    )) {
        if (Test-Path $cand) { $OpenCodeBin = $cand; break }
    }
}
if (-not $OpenCodeBin) {
    Fail "opencode not found. Install it first:  https://opencode.ai/install"
    exit 1
}
Ok "opencode: $OpenCodeBin"

if ($Check) {
    if (Test-Path (Join-Path $Checkout ".git")) { Ok "checkout: $Checkout" } else { Fail "checkout missing: $Checkout" }
    if (Test-Path (Join-Path $Checkout ".venv\Scripts\python.exe")) { Ok ".venv present" } else { Fail ".venv missing" }
    if (Test-Path (Join-Path $Checkout "src\kiro_crew\static\dist\index.html")) { Ok "frontend dist present" } else { Fail "frontend dist missing" }
    if (Test-Path $EnvFile) {
        $envText = Get-Content $EnvFile -Raw
        if ($envText -match "KIROCREW_KAS_NODE=") { Ok "env file: KAS_NODE set" } else { Fail "env file: KAS_NODE missing" }
    } else { Fail "env file missing: $EnvFile" }
    if (Test-Path $OcJson) {
        $cfg = Get-Content $OcJson -Raw | ConvertFrom-Json
        $hasAgents = $true
        foreach ($a in @("kirocrew","kirocrew-lite","kirocrew-research","kirocrew-heartbeat","kirocrew-knowledge")) {
            if (-not ($cfg.agent.PSObject.Properties.Name -contains $a)) { $hasAgents = $false }
        }
        $hasMcp = ($cfg.mcp.PSObject.Properties.Name -contains "kirocrew-core") -and ($cfg.mcp.PSObject.Properties.Name -contains "kirocrew-cron")
        if ($hasAgents -and $hasMcp) { Ok "opencode.json: agents + MCPs present" } else { Fail "opencode.json incomplete" }
    } else { Fail "opencode.json missing" }
    foreach ($n in @("kirocrew-research","kirocrew-heartbeat","kirocrew-knowledge")) {
        if (Test-Path (Join-Path $OcAgentDir "$n.md")) { Ok "agent md: $n" } else { Fail "agent md missing: $n" }
    }
    $link = Get-Item $OcSkills -ErrorAction SilentlyContinue
    if ($link -and $link.LinkType -eq "Junction" -and $link.Target -eq $SkillsDir) { Ok "skills junction" } else { Fail "skills junction missing" }
    Say "Done. Run with no flags to apply what is missing."
    exit 0
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Fail "git not found"; exit 1 }

# ── 1. Checkout ───────────────────────────────────────────────────────────
if ((Test-Path $Checkout) -and -not (Test-Path (Join-Path $Checkout ".git"))) {
    Fail "checkout path $Checkout exists but is not a git repository"
    Write-Host "       Move it aside or set \$Checkout elsewhere."
    exit 1
}
if (-not (Test-Path (Join-Path $Checkout ".git"))) {
    Say "Cloning OpenCrew"
    git clone $RepoUrl $Checkout | Out-Null
    if (-not (Test-Path (Join-Path $Checkout ".git"))) { Fail "clone failed"; exit 1 }
    git -C $Checkout remote add upstream https://github.com/kirodotdev/KiroCrew.git 2>$null
}
Ok "checkout: $Checkout"

# ── 2. Python + in-checkout .venv ─────────────────────────────────────────
Say "Python venv"
$Py = ""
foreach ($cand in @("py -3.12", "py -3", "python")) {
    $parts = $cand -split " "
    $exe = Get-Command $parts[0] -ErrorAction SilentlyContinue
    if ($exe) { $Py = $cand; break }
}
if (-not $Py) { Fail "Python 3.10+ not found. Install from python.org and re-run."; exit 1 }
if (-not (Test-Path (Join-Path $Checkout ".venv\Scripts\python.exe"))) {
    Push-Location $Checkout
    Invoke-Expression "$Py -m venv .venv"
    Pop-Location
}
$VenvPy = Join-Path $Checkout ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) { Fail "venv creation failed — install Python 3.10+ (python.org) and re-run"; exit 1 }
Ok "venv: $VenvPy"

# Prefer the most recently used model from opencode's session store over the
# hardcoded fallback — a fresh config starts on the model actually used last.
if (-not $env:OPENCREW_MODEL) {
    $ResolveMru = @'
import json, glob, os, sqlite3, sys

def db_mru(db_path):
    try:
        con = sqlite3.connect("file:" + db_path + "?mode=ro", uri=True, timeout=2)
        row = con.execute(
            "SELECT model FROM session WHERE model IS NOT NULL AND model != '' "
            "ORDER BY time_updated DESC LIMIT 1"
        ).fetchone()
        con.close()
        if row:
            m = json.loads(row[0])
            pid, mid = m.get("providerID"), m.get("id")
            if pid and mid:
                print(pid + "/" + mid)
                return True
    except Exception:
        pass
    return False

base = os.path.expanduser("~/.local/share/opencode")
for db in ("opencode.db", "opencode-local.db"):
    if os.path.exists(os.path.join(base, db)) and db_mru(os.path.join(base, db)):
        sys.exit(0)
best, best_ts = None, 0
for f in glob.glob(os.path.join(base, "project/*/storage/session/info/*.json")):
    try:
        st = os.path.getmtime(f)
        d = json.load(open(f))
        mid = d.get("modelID")
        if mid and st > best_ts:
            best, best_ts = mid, st
    except Exception:
        continue
if best:
    print(best)
sys.exit(0)
'@
    $mru = ($ResolveMru | & $VenvPy -) 2>$null | Out-String
    $mru = $mru.Trim()
    if ($mru) { $DefaultModel = $mru; Ok "model: most recently used -> $mru" }
}

# ── 3. Editable install ───────────────────────────────────────────────────
Say "Editable install"
& $VenvPy -m pip install -e $Checkout --quiet
$module = & $VenvPy -c "import kiro_crew; print(kiro_crew.__file__)"
if ($module -like "$Checkout*") { Ok "kiro_crew resolves from the checkout" } else { Fail "editable install not effective: $module"; exit 1 }

# ── 4. Frontend bundle (from the official wheel) ──────────────────────────
if (Test-Path (Join-Path $Checkout "src\kiro_crew\static\dist\index.html")) {
    Ok "frontend dist already present"
} else {
    Say "Restoring frontend dist from the official wheel"
    $sums = Invoke-WebRequest -UseBasicParsing "https://download.crew.kiro.dev/cli/stable/$WheelVer/SHA256SUMS" | Select-Object -ExpandProperty Content
    $sha = ($sums -split "`n" | Where-Object { $_ -match "kirocrew-$WheelVer-py3-none-any.whl" } | ForEach-Object { ($_ -split " ")[0] }).Trim()
    if (-not $sha) { Fail "could not resolve wheel SHA256 from SHA256SUMS"; exit 1 }
    $wheel = Join-Path $env:TEMP "kirocrew-$WheelVer.whl"
    Invoke-WebRequest -UseBasicParsing -OutFile $wheel "https://download.crew.kiro.dev/cli/stable/$WheelVer/kirocrew-$WheelVer-py3-none-any.whl#sha256=$sha"
    $extract = Join-Path $env:TEMP "kc-wheel-x"
    if (Test-Path $extract) { Remove-Item -Recurse -Force $extract }
    New-Item -ItemType Directory -Path $extract | Out-Null
    $tarOk = $false
    if (Get-Command tar -ErrorAction SilentlyContinue) {
        tar -xf $wheel -C $extract "kiro_crew/static" 2>$null
        $tarOk = Test-Path (Join-Path $extract "kiro_crew\static")
    }
    if (-not $tarOk) {
        # Fallback: extract the whole wheel with the venv python (a .whl is a zip).
        & $VenvPy -c "import zipfile; zipfile.ZipFile(r'$wheel').extractall(r'$extract')"
    }
    $dst = Join-Path $Checkout "src\kiro_crew\static"
    if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
    Copy-Item -Recurse (Join-Path $extract "kiro_crew\static") $dst
    Ok "frontend dist restored"
}

# ── 5. Env file (no service on Windows; runtime reads ~/.kiro/crew.env) ───
Say "Env file ($EnvFile)"
New-Item -ItemType Directory -Path $KiHome -Force | Out-Null
$vars = [ordered]@{
    "KIROCREW_KAS_NODE"      = $OpenCodeBin
    "KIROCREW_KAS_SCRIPT"    = "true.exe"
    "KIROCREW_PROJECT_DIR"   = $Checkout
}
$existing = @{}
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match "^([^=]+)=(.*)$") { $existing[$matches[1]] = $matches[2] }
    }
}
foreach ($k in $vars.Keys) { if (-not $existing.ContainsKey($k)) { $existing[$k] = $vars[$k] } }
$existing.GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Key)=$($_.Value)" } | Set-Content -Path $EnvFile -Encoding ASCII
Ok "env file has KAS_NODE / KAS_SCRIPT / PROJECT_DIR"

# ── 6. opencode.json (agents + MCP servers) ───────────────────────────────
Say "opencode config ($OcJson)"
New-Item -ItemType Directory -Path $OcConfig -Force | Out-Null
if (-not (Test-Path $OcJson)) {
    Set-Utf8NoBom $OcJson ("{\"$schema\":\"https://opencode.ai/config.json\",\"model\":\"$DefaultModel\",\"permission\":\"allow\"}")
}
$cfg = $null
try { $cfg = Get-Content $OcJson -Raw | ConvertFrom-Json } catch { }
if (-not $cfg) {
    Warn "opencode.json could not be parsed (comments or trailing commas are allowed by opencode but not by PowerShell's JSON parser)."
    Warn "Backing it up as opencode.json.bak and SKIPPING the agents/MCP merge — merge manually per docs/opencode-backend/README.md."
    Copy-Item $OcJson ($OcJson + ".bak") -Force
} else {
if (-not $cfg.agent) { $cfg | Add-Member -NotePropertyName agent -NotePropertyValue ([pscustomobject]@{}) }
if (-not $cfg.mcp)   { $cfg | Add-Member -NotePropertyName mcp -NotePropertyValue ([pscustomobject]@{}) }
# kirocrew agents carry NO model pin: they inherit the config's top-level
# model, so changing the default updates every agent at once.
$agents = [ordered]@{
    "kirocrew"            = [pscustomobject]@{ description = "Kiro Crew persistent assistant agent"; mode = "primary" }
    "kirocrew-lite"       = [pscustomobject]@{ description = "Kiro Crew lite assistant agent"; mode = "primary" }
    "kirocrew-research"   = [pscustomobject]@{ description = "Autonomous research worker — runs one research cycle per turn in a Research Lab campaign loop."; mode = "primary" }
    "kirocrew-heartbeat"  = [pscustomobject]@{ description = "Unattended polling worker — runs one HeartbeatService task per cycle with a read-only toolset."; mode = "primary" }
    "kirocrew-knowledge"  = [pscustomobject]@{ description = "Dedicated agent for knowledge extraction, categorization, and summarization."; mode = "primary" }
}
$kiroBin = Join-Path $Checkout ".venv\Scripts\kirocrew.exe"
$mcp = [ordered]@{
    "kirocrew-core" = [pscustomobject]@{ type = "local"; command = @($kiroBin, "mcp-core") }
    "kirocrew-cron" = [pscustomobject]@{ type = "local"; command = @($kiroBin, "mcp-cron") }
}
foreach ($k in $agents.Keys) {
    $exists = $cfg.agent.PSObject.Properties.Name -contains $k
    if (-not $exists) { $cfg.agent | Add-Member -NotePropertyName $k -NotePropertyValue $agents[$k] }
    $entry = $cfg.agent.PSObject.Properties[$k]
    if ($entry) { $entry.Value.PSObject.Properties.Remove("model") }
}
foreach ($k in $mcp.Keys) {
    $exists = $cfg.mcp.PSObject.Properties.Name -contains $k
    if (-not $exists) { $cfg.mcp | Add-Member -NotePropertyName $k -NotePropertyValue $mcp[$k] }
}
$cfg | ConvertTo-Json -Depth 12 | Set-Utf8NoBom $OcJson
Ok "opencode.json updated"
}

# ── 7. Agent prompts ──────────────────────────────────────────────────────
Say "Agent prompts ($OcAgentDir)"
New-Item -ItemType Directory -Path $OcAgentDir -Force | Out-Null
$fallbacks = @{
    "kirocrew-research"  = "Autonomous research worker — runs one research cycle per turn."
    "kirocrew-heartbeat" = "Unattended polling worker — runs one HeartbeatService task per cycle."
    "kirocrew-knowledge" = "Dedicated agent for knowledge extraction, categorization, and summarization."
}
$kiroAgentsDir = Join-Path $KiHome "agents"
foreach ($name in $fallbacks.Keys) {
    $out = Join-Path $OcAgentDir "$name.md"
    if (Test-Path $out) {
        $mdText = Get-Content $out -Raw
        if ($mdText -match "(?m)^model: .*$") {
            $mdText = $mdText -replace "(?m)^model: .*$`n?", ""
            Set-Utf8NoBom $out $mdText
            Ok "+ $name.md (model line removed)"
        }
        continue
    }
    $prompt = $fallbacks[$name]
    $desc = $fallbacks[$name]
    $src = Join-Path $kiroAgentsDir "$name.json"
    if (Test-Path $src) {
        $data = Get-Content $src -Raw | ConvertFrom-Json
        if ($data.prompt) { $prompt = $data.prompt }
        if ($data.description) { $desc = $data.description }
    }
    $md = "---`ndescription: $desc`nmode: primary`n---`n`n$prompt`n"
    Set-Utf8NoBom $out $md
    Ok "+ $name.md"
}

# ── 8. Skills junction ────────────────────────────────────────────────────
Say "Skills junction"
New-Item -ItemType Directory -Path $SkillsDir -Force | Out-Null
$link = Get-Item $OcSkills -ErrorAction SilentlyContinue
if ($link -and $link.LinkType -eq "Junction" -and $link.Target -eq $SkillsDir) {
    Ok "skills junction already correct"
} elseif (Test-Path $OcSkills) {
    Rename-Item $OcSkills ($OcSkills + ".premerge")
    New-Item -ItemType Junction -Path $OcSkills -Target $SkillsDir | Out-Null
    Warn "pre-existing skills dir moved to skills.premerge"
} else {
    New-Item -ItemType Junction -Path $OcSkills -Target $SkillsDir | Out-Null
}
Ok "skills junction -> $SkillsDir"

# ── 9. Crew config (kas backend + Windows sandbox opt-in) ─────────────────
Say "Crew config ($CrewHome\config.json)"
New-Item -ItemType Directory -Path $CrewHome -Force | Out-Null
$config = Join-Path $CrewHome "config.json"
if (-not (Test-Path $config)) {
    Set-Utf8NoBom $config '{"agent":{"acp_backend":"kas"}}'
}
$cc = $null
try { $cc = Get-Content $config -Raw | ConvertFrom-Json } catch { }
if (-not $cc) {
    Warn "config.json could not be parsed — backing it up and SKIPPING. Set agent.acp_backend=kas and agent.sandbox_allow_unsandboxed_exec=true manually."
    Copy-Item $config ($config + ".bak") -Force
} else {
if (-not $cc.agent) { $cc | Add-Member -NotePropertyName agent -NotePropertyValue ([pscustomobject]@{}) }
$cc.agent | Add-Member -NotePropertyName acp_backend -NotePropertyValue "kas" -Force
$cc.agent | Add-Member -NotePropertyName sandbox_allow_unsandboxed_exec -NotePropertyValue $true -Force
$cc | ConvertTo-Json -Depth 8 | Set-Utf8NoBom $config
}
Warn "Windows has no OS sandbox for the agent: sandbox_allow_unsandboxed_exec is set (stock fail-closed would refuse to run otherwise). This is the documented tradeoff — review it."

# ── 10. Run instructions ──────────────────────────────────────────────────
Say "Run"
Write-Host ""
Write-Host "  Windows has no kirocrew service manager — start the gateway with:"
Write-Host "      cd $Checkout"
Write-Host "      .\.venv\Scripts\python.exe -m kiro_crew gateway"
Write-Host ""
Write-Host "  Optional Task Scheduler (logon-triggered, like launchd):"
Write-Host '      schtasks /Create /TN "OpenCrew" /SC ONLOGON /RL LIMITED /TR "powershell -NoProfile -WindowStyle Hidden -Command \"cd C:\path\to\KiroCrew; .\.venv\Scripts\python.exe -m kiro_crew gateway\""'
Write-Host ""
Write-Host "  Dashboard: http://localhost:5476   (kirocrew token for the URL)"
Say "Done"
