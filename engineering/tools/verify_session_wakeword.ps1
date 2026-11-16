[CmdletBinding()]
param(
    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$BaseUrl = "http://localhost:8010",

    [Parameter()]
    [ValidateRange(1, 120)]
    [int]$TimeoutSeconds = 15,

    [Parameter()]
    [switch]$HttpOnly
)

$ErrorActionPreference = "Stop"

function Assert-Condition {
    param(
        [Parameter(Mandatory)]
        [bool]$Condition,

        [Parameter(Mandatory)]
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Receive-WebSocketJson {
    param(
        [Parameter(Mandatory)]
        [System.Net.WebSockets.ClientWebSocket]$Socket,

        [Parameter(Mandatory)]
        [System.Threading.CancellationToken]$CancellationToken
    )

    $buffer = [byte[]]::new(65536)
    $builder = [System.Text.StringBuilder]::new()

    do {
        $segment = [ArraySegment[byte]]::new($buffer)
        $result = $Socket.ReceiveAsync(
            $segment,
            $CancellationToken
        ).GetAwaiter().GetResult()

        if ($result.MessageType -eq [System.Net.WebSockets.WebSocketMessageType]::Close) {
            throw "Der Server hat den WebSocket vor dem hello-Handshake geschlossen."
        }
        if ($result.MessageType -ne [System.Net.WebSockets.WebSocketMessageType]::Text) {
            continue
        }

        $text = [System.Text.Encoding]::UTF8.GetString(
            $buffer,
            0,
            $result.Count
        )
        [void]$builder.Append($text)
    } while (-not $result.EndOfMessage)

    return $builder.ToString() | ConvertFrom-Json
}

$normalizedBaseUrl = $BaseUrl.TrimEnd("/")
$openApi = Invoke-RestMethod `
    -Uri "$normalizedBaseUrl/openapi.json" `
    -TimeoutSec $TimeoutSeconds
$config = Invoke-RestMethod `
    -Uri "$normalizedBaseUrl/api/config" `
    -TimeoutSec $TimeoutSeconds

$queryParameters = @(
    $config.sessionCapabilities.wakeWord.queryParameters
)
$backends = @($config.sessionCapabilities.wakeWord.backends)

# AP-SRV-070: the product version now comes from one automatic version
# authority (VoiceSTT/_version.py) and changes on every release, so this
# check only validates the published shape, not a specific frozen literal.
Assert-Condition `
    -Condition ($openApi.info.version -match '^\d+\.\d+\.\d+') `
    -Message "FastAPI-Version ist keine gueltige SemVer-Version: $($openApi.info.version)"
Assert-Condition `
    -Condition ($config.sessionCapabilities.version -ge 1) `
    -Message "Der Server veröffentlicht keinen versionierten Session-Contract."
Assert-Condition `
    -Condition ($queryParameters -contains "wakeWordEnabled") `
    -Message "wakeWordEnabled fehlt im veröffentlichten Session-Contract."
Assert-Condition `
    -Condition ($queryParameters -contains "wakeWords") `
    -Message "wakeWords fehlt im veröffentlichten Session-Contract."
Assert-Condition `
    -Condition ($backends -contains "openwakeword") `
    -Message "OpenWakeWord fehlt im veröffentlichten Session-Contract."

$httpResult = [ordered]@{
    BaseUrl = $normalizedBaseUrl
    ApiVersion = $openApi.info.version
    SessionContractVersion = $config.sessionCapabilities.version
    WakeWordSessionContract = $true
    OpenWakeWordAdvertised = $true
}

if ($HttpOnly) {
    [pscustomobject]$httpResult
    return
}

$baseUri = [Uri]$normalizedBaseUrl
$webSocketScheme = if ($baseUri.Scheme -eq "https") { "wss" } else { "ws" }
$authority = $baseUri.Authority
$basePath = $baseUri.AbsolutePath.TrimEnd("/")
$webSocketUri = [Uri](
    "${webSocketScheme}://${authority}${basePath}" +
    "/ws/transcribe?wakeWordEnabled=false&wakeWords=proof_should_be_ignored"
)

$socket = [System.Net.WebSockets.ClientWebSocket]::new()
$timeout = [System.Threading.CancellationTokenSource]::new(
    [TimeSpan]::FromSeconds($TimeoutSeconds)
)

try {
    [void]$socket.ConnectAsync(
        $webSocketUri,
        $timeout.Token
    ).GetAwaiter().GetResult()

    $hello = Receive-WebSocketJson `
        -Socket $socket `
        -CancellationToken $timeout.Token

    Assert-Condition `
        -Condition ($hello.type -eq "hello") `
        -Message "Erste WebSocket-Nachricht ist kein hello: $($hello.type)"
    Assert-Condition `
        -Condition ($hello.sessionConfig.version -ge 1) `
        -Message "hello enthält keinen versionierten sessionConfig-Contract."
    Assert-Condition `
        -Condition ($hello.sessionConfig.requestedWakeWordEnabled -eq $false) `
        -Message "Der angeforderte Deaktivierungsmodus wurde nicht bestätigt."
    Assert-Condition `
        -Condition ($hello.sessionConfig.effectiveWakeWordEnabled -eq $false) `
        -Message "Wake Word ist in der Prüfsession unerwartet aktiv."
    Assert-Condition `
        -Condition (@($hello.sessionConfig.ignoredFields) -contains "wakeWords") `
        -Message "Das bei deaktiviertem Wake Word wirkungslose Feld wurde nicht bestätigt."
    Assert-Condition `
        -Condition (
            @($hello.sessionCapabilities.wakeWord.queryParameters) -contains
            "wakeWordEnabled"
        ) `
        -Message "hello veröffentlicht den neuen Session-Contract nicht."

    $httpResult["WebSocketHandshake"] = "passed"
    $httpResult["SessionId"] = $hello.sessionId
    $httpResult["RequestedWakeWordEnabled"] = (
        $hello.sessionConfig.requestedWakeWordEnabled
    )
    $httpResult["EffectiveWakeWordEnabled"] = (
        $hello.sessionConfig.effectiveWakeWordEnabled
    )
    $httpResult["IgnoredFields"] = (
        @($hello.sessionConfig.ignoredFields) -join ", "
    )

    [pscustomobject]$httpResult
}
finally {
    if ($socket.State -eq [System.Net.WebSockets.WebSocketState]::Open) {
        [void]$socket.CloseAsync(
            [System.Net.WebSockets.WebSocketCloseStatus]::NormalClosure,
            "verification complete",
            [System.Threading.CancellationToken]::None
        ).GetAwaiter().GetResult()
    }
    $timeout.Dispose()
    $socket.Dispose()
}
