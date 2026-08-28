$scriptPath = $PSScriptRoot
if ([string]::IsNullOrEmpty($scriptPath)) { $scriptPath = (Get-Location).Path }

$onnxModels = [ordered]@{}
$tfliteModels = [ordered]@{}
$ignoredModels = @("embedding_model", "melspectrogram", "silero_vad")

# Hilfsfunktion, um den Key aus dem Dateinamen zu generieren
function Get-ModelKey {
    param([string]$FileName)
    $key = [System.IO.Path]::GetFileNameWithoutExtension($FileName)
    
    # Optional: Entfernt "wake_word_" am Anfang
    $key = $key -replace '^wake_word_', ''
    
    # Entfernt Versionsteile wie _v0.1, _v2
    $key = $key -replace '_v\d+(\.\d+)*$', ''
    
    # Entfernt Zeitstempel (falls noch vorhanden)
    $key = $key -replace '_\d{8}_\d{6}$', ''
    
    # Spezieller Fall für jarvis aus dem Beispiel (jarvis_v2 -> hey_jarvis)
    if ($key -eq "jarvis") { $key = "hey_jarvis" }
    
    return $key
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

# ONNX-Dateien scannen (Pipeline-Modelle ignorieren, da sie statisch hinzugefügt werden)
Get-ChildItem -Path $scriptPath -Filter "*.onnx" | Sort-Object @{ Expression = { Get-ModelKey $_.Name } }, @{ Expression = { Get-ModelVersion $_.Name } }, @{ Expression = { $_.Name.ToLowerInvariant() } } | Where-Object { $_.BaseName -notin $ignoredModels } | ForEach-Object {
    $key = Get-ModelKey $_.Name
    $onnxModels[$key] = $_.Name
}

# TFLite-Dateien scannen (Pipeline-Modelle ignorieren)
Get-ChildItem -Path $scriptPath -Filter "*.tflite" | Sort-Object @{ Expression = { Get-ModelKey $_.Name } }, @{ Expression = { Get-ModelVersion $_.Name } }, @{ Expression = { $_.Name.ToLowerInvariant() } } | Where-Object { $_.BaseName -notin $ignoredModels } | ForEach-Object {
    $key = Get-ModelKey $_.Name
    $tfliteModels[$key] = $_.Name
}

# Default Model ermitteln
$defaultModel = "alexa"
if (-not $onnxModels.Contains($defaultModel) -and $onnxModels.Count -gt 0) {
    # Falls alexa nicht existiert, nimm das erste gefundene Modell
    $defaultModel = ($onnxModels.Keys | Select-Object -First 1)
}

# JSON Struktur aufbauen
$jsonData = [ordered]@{
    "openwakeword_models" = [ordered]@{
        "path" = "."
        "default_model" = $defaultModel
        "pipeline_models" = [ordered]@{
            "embedding_model_onnx"   = "embedding_model.onnx"
            "melspectrogram_onnx"    = "melspectrogram.onnx"
            "embedding_model_tflite" = "embedding_model.tflite"
            "melspectrogram_tflite"  = "melspectrogram.tflite"
        }
        "onnx_models" = $onnxModels
        "tflite_models" = $tfliteModels
    }
}

# Als JSON formatieren
$jsonOutput = $jsonData | ConvertTo-Json -Depth 5

# JSON Datei im selben Ordner speichern
$outputPath = Join-Path -Path $scriptPath -ChildPath "models.json"
$utf8WithoutBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($outputPath, $jsonOutput, $utf8WithoutBom)

Write-Host "Die Datei 'models.json' wurde erfolgreich in $scriptPath erstellt."
