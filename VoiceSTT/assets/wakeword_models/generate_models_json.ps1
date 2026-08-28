$scriptPath = $PSScriptRoot
if ([string]::IsNullOrEmpty($scriptPath)) { $scriptPath = (Get-Location).Path }

$onnxModels = [ordered]@{}
$tfliteModels = [ordered]@{}
$ignoredModels = @("embedding_model", "melspectrogram", "silero_vad")

$aliasesMap = @{
    "hey_alfred"  = @("alfred")
    "hey_billy"   = @("billy")
    "hey_bro"     = @("bro")
    "hey_glados"  = @("glados")
    "hey_hermes"  = @("hermes")
    "hey_jarvis"  = @("jarvis")
    "hey_lucy"    = @("lucy")
    "hey_luna"    = @("luna")
    "hey_max"     = @("max")
    "hey_mira"    = @("mira")
    "hey_mycroft" = @("mycroft")
    "hey_nabu"    = @("nabu")
    "hey_nexus"   = @("nexus")
    "hey_nova"    = @("nova")
    "hey_oracle"  = @("oracle")
    "hey_rhasspy" = @("rhasspy")
    "hey_rocky"   = @("rocky")
    "hey_rona"    = @("rona")
}

$displayNamesMap = @{
    "hey_glados" = "Hey GLaDOS"
}

function Get-ModelKey {
    param([string]$FileName)
    $key = [System.IO.Path]::GetFileNameWithoutExtension($FileName)
    
    # Optional: Entfernt "wake_word_" am Anfang
    $key = $key -replace '^wake_word_', ''
    
    # Entfernt Versionsteile wie _v0.1, _v2
    $key = $key -replace '_v\d+(\.\d+)*$', ''
    
    # Entfernt Zeitstempel (falls noch vorhanden)
    $key = $key -replace '_\d{8}_\d{6}$', ''
    
    # Spezieller Fall fuer jarvis (jarvis_v2 -> hey_jarvis)
    if ($key -eq "jarvis") { $key = "hey_jarvis" }
    
    return $key.ToLowerInvariant()
}

function Get-ModelVersion {
    param([string]$FileName)
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($FileName)
    if ($baseName -match '_v(\d+(\.\d+)*)$') {
        $versionText = $Matches[1]
        if ($versionText -notmatch '\.') { $versionText += ".0" }
        return [version]$versionText
    }
    return [version]"0.0"
}

function Get-DisplayName {
    param([string]$Key)
    if ($displayNamesMap.ContainsKey($Key)) {
        return $displayNamesMap[$Key]
    }
    $parts = $Key -split '_'
    $capitalized = $parts | ForEach-Object {
        if ($_.Length -gt 0) {
            $_.Substring(0, 1).ToUpperInvariant() + $_.Substring(1).ToLowerInvariant()
        }
    }
    return ($capitalized -join ' ')
}

function Get-ArtifactSpec {
    param([string]$FileName)
    $filePath = Join-Path -Path $scriptPath -ChildPath $FileName
    $fileInfo = Get-Item -Path $filePath
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($filePath)
    try {
        $hashBytes = $hasher.ComputeHash($stream)
        $sha256 = ([System.BitConverter]::ToString($hashBytes) -replace '-', '').ToLowerInvariant()
    }
    finally {
        $stream.Close()
        $hasher.Dispose()
    }
    return [ordered]@{
        "file"   = $FileName
        "sha256" = $sha256
        "bytes"  = [long]$fileInfo.Length
    }
}

# ONNX-Dateien scannen (Pipeline-Modelle ignorieren, da sie statisch hinzugefuegt werden)
Get-ChildItem -Path $scriptPath -Filter "*.onnx" |
    Sort-Object @{ Expression = { Get-ModelKey $_.Name } }, @{ Expression = { Get-ModelVersion $_.Name } }, @{ Expression = { $_.Name.ToLowerInvariant() } } |
    Where-Object { $_.BaseName -notin $ignoredModels } |
    ForEach-Object {
        $key = Get-ModelKey $_.Name
        $onnxModels[$key] = $_.Name
    }

# TFLite-Dateien scannen (Pipeline-Modelle ignorieren)
Get-ChildItem -Path $scriptPath -Filter "*.tflite" |
    Sort-Object @{ Expression = { Get-ModelKey $_.Name } }, @{ Expression = { Get-ModelVersion $_.Name } }, @{ Expression = { $_.Name.ToLowerInvariant() } } |
    Where-Object { $_.BaseName -notin $ignoredModels } |
    ForEach-Object {
        $key = Get-ModelKey $_.Name
        $tfliteModels[$key] = $_.Name
    }

# Default Model ermitteln
$defaultModel = "alexa"
if (-not $onnxModels.Contains($defaultModel) -and $onnxModels.Count -gt 0) {
    $defaultModel = ($onnxModels.Keys | Select-Object -First 1)
}

# Catalog-Revision ermitteln (aus existierender models.json beibehalten falls vorhanden)
$existingManifestPath = Join-Path -Path $scriptPath -ChildPath "models.json"
$catalogRevision = 2
if (Test-Path $existingManifestPath) {
    try {
        $existingJson = Get-Content -Path $existingManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($existingJson.catalogRevision) {
            $catalogRevision = [int]$existingJson.catalogRevision
        }
    }
    catch {}
}

# Pipeline-Sektion aufbauen
$pipeline = [ordered]@{
    "onnx" = [ordered]@{
        "melspectrogram" = Get-ArtifactSpec "melspectrogram.onnx"
        "embedding"      = Get-ArtifactSpec "embedding_model.onnx"
    }
    "tflite" = [ordered]@{
        "melspectrogram" = Get-ArtifactSpec "melspectrogram.tflite"
        "embedding"      = Get-ArtifactSpec "embedding_model.tflite"
    }
}

# Wake-Words aufbauen
$allKeys = ($onnxModels.Keys + $tfliteModels.Keys) | Select-Object -Unique | Sort-Object
$wakeWords = @()
foreach ($key in $allKeys) {
    $artifacts = [ordered]@{}
    if ($onnxModels.Contains($key)) {
        $artifacts["onnx"] = Get-ArtifactSpec $onnxModels[$key]
    }
    if ($tfliteModels.Contains($key)) {
        $artifacts["tflite"] = Get-ArtifactSpec $tfliteModels[$key]
    }

    $aliases = @()
    if ($aliasesMap.ContainsKey($key)) {
        $aliases = $aliasesMap[$key]
    }

    $wakeWords += [ordered]@{
        "id"              = $key
        "displayName"     = Get-DisplayName $key
        "aliases"         = $aliases
        "artifactVersion" = "1"
        "artifacts"       = $artifacts
    }
}

# Legacy Mirror fuer den v1-Pfad
$legacyModels = [ordered]@{
    "path"            = "."
    "default_model"   = $defaultModel
    "pipeline_models" = [ordered]@{
        "melspectrogram_onnx"    = "melspectrogram.onnx"
        "embedding_model_onnx"   = "embedding_model.onnx"
        "melspectrogram_tflite"  = "melspectrogram.tflite"
        "embedding_model_tflite" = "embedding_model.tflite"
    }
    "onnx_models"     = $onnxModels
    "tflite_models"   = $tfliteModels
}

# JSON-Struktur aufbauen
$jsonData = [ordered]@{
    "manifestVersion"     = 2
    "catalogRevision"     = $catalogRevision
    "generatedBy"         = "tools/sync_wakeword_assets.py"
    "description"         = "Kanonische Wake-Word-Catalog-Authority des v2-Pfades. Der Abschnitt 'openwakeword_models' ist nur ein Legacyspiegel fuer den v1-Pfad bis AP-SRV-070."
    "pipeline"            = $pipeline
    "wakeWords"           = $wakeWords
    "openwakeword_models" = $legacyModels
}

# Als JSON formatieren
$jsonOutput = $jsonData | ConvertTo-Json -Depth 10

# JSON-Datei im selben Ordner speichern
$outputPath = Join-Path -Path $scriptPath -ChildPath "models.json"
$utf8WithoutBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($outputPath, ($jsonOutput + "`n"), $utf8WithoutBom)

Write-Host "Die Datei 'models.json' wurde erfolgreich in $scriptPath erstellt."
