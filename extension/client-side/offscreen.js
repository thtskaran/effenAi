// Offscreen document script for handling audio capture

let mediaRecorder;
let audioContext;
let streamSource;
let mediaStream; // Keep track of the stream to stop tracks later
let audioChunks = [];
let currentRecordingId = null; // Store ID associated with this stream
let currentUserId = null; // Store user ID

chrome.runtime.onMessage.addListener(async (message) => {
    if (message.target !== 'offscreen') {
        return; // Ignore messages not specifically for us (optional safety)
    }

    switch (message.action) {
        case 'startOffscreenCapture':
            console.log("Offscreen: Received start command with streamId:", message.streamId);
            startCapture(message.streamId, message.userId); // Add userId
            break;
        case 'stopOffscreenCapture':
             console.log("Offscreen: Received stop command.");
            stopCapture();
            break;
        default:
            console.warn(`Offscreen: Unknown message action: ${message.action}`);
    }
});

async function startCapture(streamId, userId) {
     if (mediaRecorder && mediaRecorder.state === 'recording') {
         console.warn("Offscreen: Already recording.");
         return;
     }
     currentUserId = userId; // Store user for potential use
     console.log(`Offscreen: Starting capture for stream ${streamId}, user ${userId}`);

    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                mandatory: {
                    chromeMediaSource: 'tab',
                    chromeMediaSourceId: streamId
                }
            },
            video: false // No video capture needed
        });

        // --- Play audio locally ---
        audioContext = new AudioContext();
        streamSource = audioContext.createMediaStreamSource(mediaStream);
        streamSource.connect(audioContext.destination);
         console.log("Offscreen: Audio stream connected to local output.");
        // --- Recording setup ---
        const options = { mimeType: 'audio/webm;codecs=opus' }; // Good quality and compression
        mediaRecorder = new MediaRecorder(mediaStream, options);

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                // Convert blob to Base64 and send to background
                const reader = new FileReader();
                reader.onloadend = () => {
                    // Result contains the Base64 string (without the data: prefix)
                    const base64String = reader.result.split(',')[1];
                    chrome.runtime.sendMessage({ action: "audioChunk", chunk: base64String });
                     // console.log(`Offscreen: Sent audio chunk (Base64 size: ${base64String.length})`); // Verbose
                };
                reader.readAsDataURL(event.data);
            }
        };

        mediaRecorder.onstop = () => {
            console.log("Offscreen: MediaRecorder stopped.");
            cleanupStreams();
            // Notify background script that recording naturally stopped
            chrome.runtime.sendMessage({ action: "recordingStopped" });
             // Reset state
             mediaRecorder = null;
             currentRecordingId = null;
             currentUserId = null;
        };

        mediaRecorder.onerror = (event) => {
             console.error("Offscreen: MediaRecorder error:", event.error);
             cleanupStreams();
             chrome.runtime.sendMessage({ action: "recordingError", error: event.error.message || 'Unknown MediaRecorder error' });
        };

        // Start recording, collect chunks every few seconds (e.g., 5 seconds)
        mediaRecorder.start(5000);
        console.log("Offscreen: MediaRecorder started.");

    } catch (error) {
        console.error("Offscreen: Error starting getUserMedia/MediaRecorder:", error);
         chrome.runtime.sendMessage({ action: "recordingError", error: error.message || 'Failed to get user media' });
         cleanupStreams(); // Clean up if partially started
    }
}

function stopCapture() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop(); // This will trigger the onstop handler
         console.log("Offscreen: MediaRecorder stop requested.");
    } else {
        console.log("Offscreen: Stop requested but recorder not active.");
        cleanupStreams(); // Ensure cleanup even if not recording
    }
     // No need to close document here, background script handles it
}

function cleanupStreams() {
     console.log("Offscreen: Cleaning up streams and context.");
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        try { mediaRecorder.stop(); } catch (e) {}
    }
    if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
        mediaStream = null;
    }
    if (streamSource) {
        streamSource.disconnect();
        streamSource = null;
    }
    if (audioContext && audioContext.state !== 'closed') {
        audioContext.close();
        audioContext = null;
    }
     mediaRecorder = null; // Ensure reset
}

// Keep alive for Manifest V3 (basic heartbeat)
// Note: This is less critical for Offscreen Docs used with USER_MEDIA,
// as the media stream itself often keeps it alive, but good practice.
// (async () => {
//   setInterval(() => {
//     // console.log("Offscreen heartbeat"); // Very verbose
//   }, 20000); // Every 20 seconds
// })();