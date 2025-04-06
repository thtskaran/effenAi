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
               
                const reader = new FileReader();
                reader.onloadend = () => {
                  
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
          
            chrome.runtime.sendMessage({ action: "recordingStopped" });
            
             mediaRecorder = null;
             currentRecordingId = null;
             currentUserId = null;
        };

        mediaRecorder.onerror = (event) => {
             console.error("Offscreen: MediaRecorder error:", event.error);
             cleanupStreams();
             chrome.runtime.sendMessage({ action: "recordingError", error: event.error.message || 'Unknown MediaRecorder error' });
        };

      
        mediaRecorder.start(5000);
        console.log("Offscreen: MediaRecorder started.");

    } catch (error) {
        console.error("Offscreen: Error starting getUserMedia/MediaRecorder:", error);
         chrome.runtime.sendMessage({ action: "recordingError", error: error.message || 'Failed to get user media' });
         cleanupStreams(); 
    }
}

function stopCapture() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop(); 
         console.log("Offscreen: MediaRecorder stop requested.");
    } else {
        console.log("Offscreen: Stop requested but recorder not active.");
        cleanupStreams();
    }
   
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
     mediaRecorder = null; 
}
