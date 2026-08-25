// Minimal browser client for the VoiceSTT realtime WebSocket contract.
//
// It speaks the current protocol:
//   * connects to /ws/transcribe (the server has no WebSocket route on "/"),
//   * sends {"type":"start"} before any audio, because the server rejects
//     audio packets while the stream is stopped,
//   * consumes the realtime and final messages (the old sentence message type
//     no longer exists),
//   * sends pcm_s16le audio packets with the metadata the server validates.
//
// This example deliberately stays a *legacy style* client: it does not send
// the activation trigger query parameters, so the server keeps the session in
// the legacy activation mode and decides on its own when to record. That makes
// it the compatibility reference for "an old client still works".

const SERVER_ORIGIN = (() => {
    const override = new URLSearchParams(window.location.search).get("server");
    if (override) {
        return override;
    }
    if (window.location.protocol.startsWith("http")) {
        const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
        return `${scheme}//${window.location.hostname}:9001`;
    }
    return "ws://localhost:9001";
})();

const TRANSCRIBE_URL = `${SERVER_ORIGIN}/ws/transcribe`;

let socket = null;
let displayDiv = document.getElementById("textDisplay");
let server_available = false;
let mic_available = false;
let stream_started = false;
let fullSentences = [];

const serverCheckInterval = 5000; // Check every 5 seconds

function handleServerMessage(event) {
    let data;
    try {
        data = JSON.parse(event.data);
    } catch (error) {
        return; // binary or malformed frames are not expected here
    }

    switch (data.type) {
        case "hello":
            // The session exists. `sessionCapabilities.activationTriggers`
            // tells a modern client whether it may send trigger commands; this
            // example intentionally does not use them.
            break;
        case "ready":
            startStream();
            break;
        case "realtime":
            displayRealtimeText(data.displayText || data.text || "", displayDiv);
            break;
        case "final":
            if (data.text) {
                fullSentences.push(data.text);
            }
            displayRealtimeText("", displayDiv);
            break;
        case "error":
            console.error("server error", data.where, data.message);
            break;
        default:
            break;
    }
}

function startStream() {
    if (stream_started || !socket || socket.readyState !== WebSocket.OPEN) {
        return;
    }
    socket.send(JSON.stringify({ type: "start" }));
    stream_started = true;
    start_msg();
}

function connectToServer() {
    socket = new WebSocket(TRANSCRIBE_URL);

    socket.onopen = function () {
        server_available = true;
        stream_started = false;
        start_msg();
    };

    socket.onmessage = handleServerMessage;

    socket.onclose = function () {
        server_available = false;
        stream_started = false;
        start_msg();
    };

    socket.onerror = function (event) {
        console.error("websocket error", event);
    };
}

function displayRealtimeText(realtimeText, displayDiv) {
    let displayedText =
        fullSentences
            .map((sentence, index) => {
                let span = document.createElement("span");
                span.textContent = sentence + " ";
                span.className = index % 2 === 0 ? "yellow" : "cyan";
                return span.outerHTML;
            })
            .join("") + realtimeText;

    displayDiv.innerHTML = displayedText;
}

function start_msg() {
    if (!mic_available) {
        displayRealtimeText("🎤  please allow microphone access  🎤", displayDiv);
    } else if (!server_available) {
        displayRealtimeText("🖥️  please start server  🖥️", displayDiv);
    } else {
        displayRealtimeText("👄  start speaking  👄", displayDiv);
    }
}

// Check server availability periodically
setInterval(() => {
    if (!server_available) {
        connectToServer();
    }
}, serverCheckInterval);

connectToServer();
start_msg();

// Request access to the microphone
navigator.mediaDevices
    .getUserMedia({ audio: true })
    .then((stream) => {
        let audioContext = new AudioContext();
        let source = audioContext.createMediaStreamSource(stream);
        let processor = audioContext.createScriptProcessor(256, 1, 1);

        source.connect(processor);
        processor.connect(audioContext.destination);
        mic_available = true;
        start_msg();

        processor.onaudioprocess = function (e) {
            if (!socket || socket.readyState !== WebSocket.OPEN || !stream_started) {
                return;
            }

            let inputData = e.inputBuffer.getChannelData(0);
            let outputData = new Int16Array(inputData.length);

            // Convert to 16-bit PCM
            for (let i = 0; i < inputData.length; i++) {
                outputData[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768));
            }

            // The server validates these fields, so all of them are sent.
            let metadata = JSON.stringify({
                sampleRate: audioContext.sampleRate,
                channels: 1,
                format: "pcm_s16le",
                frames: outputData.length,
            });
            let metadataBytes = new TextEncoder().encode(metadata);
            let metadataLength = new ArrayBuffer(4);
            let metadataLengthView = new DataView(metadataLength);
            metadataLengthView.setInt32(0, metadataBytes.byteLength, true); // little-endian
            let combinedData = new Blob([metadataLength, metadataBytes, outputData.buffer]);
            socket.send(combinedData);
        };
    })
    .catch((e) => console.error(e));
