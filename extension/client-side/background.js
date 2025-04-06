const BACKEND_URL = "http://127.0.0.1:5000";
const MEETING_PATTERNS = ['meet.google.com', 'zoom.us/j/'];
const OFFSCREEN_DOCUMENT_PATH = 'offscreen.html';
const ACTIVITY_LOG_ALARM = 'dailyActivityLogAlarm';
const PERIODIC_SAVE_ALARM = 'periodicSaveAlarm';
const WORKING_HOUR_START = 9; 
const WORKING_HOUR_END = 17; 

let user = null;
let isLoggedIn = false;
let isRecording = false;
let recordingTabId = null;
let recordingTabUrl = null;
let recordingId = null;
let activeTabInfo = { tabId: null, url: null, domain: null, startTime: null };
let dailyActivityLog = {};

chrome.runtime.onInstalled.addListener(async () => {
    console.log("Extension Installed/Updated");
    await loadState();
    setupAlarms();
});

chrome.runtime.onStartup.addListener(async () => {
    console.log("Browser Started");
    await loadState();
    setupAlarms();
});

async function loadState() {
    try {
        const data = await chrome.storage.local.get(['user', 'isLoggedIn', 'dailyActivityLog']);
        if (data.isLoggedIn && data.user) {
            user = data.user;
            isLoggedIn = true;
            console.log("User loaded from storage:", user.email);
        } else {
            user = null;
            isLoggedIn = false;
        }
        dailyActivityLog = data.dailyActivityLog || {};
        console.log("Activity log loaded:", dailyActivityLog);
        isRecording = false;
        recordingTabId = null;
        recordingTabUrl = null;
        recordingId = null;

    } catch (error) {
        console.error("Error loading state:", error);
    }
}

function setupAlarms() {
    chrome.alarms.get(ACTIVITY_LOG_ALARM, (alarm) => {
        if (!alarm) {
            const now = new Date();
            const tomorrow = new Date(now);
            tomorrow.setDate(now.getDate() + 1);
            tomorrow.setHours(0, 0, 0, 0);
            const delayInMinutes = Math.max(1, (tomorrow.getTime() - now.getTime()) / 60000);

            chrome.alarms.create(ACTIVITY_LOG_ALARM, {
                when: Date.now() + delayInMinutes * 60000,
                periodInMinutes: 24 * 60
            });
            console.log(`Daily activity log alarm set for ${new Date(Date.now() + delayInMinutes * 60000).toLocaleString()}`);
        }
    });

    chrome.alarms.get(PERIODIC_SAVE_ALARM, (alarm) => {
        if(!alarm) {
            chrome.alarms.create(PERIODIC_SAVE_ALARM, { periodInMinutes: 15 });
            console.log("Periodic activity save alarm created.");
        }
    });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    switch (message.action) {
        case "login":
            handleLogin().then(() => sendResponse({ success: true })).catch(err => {
                console.error("Login error:", err);
                sendResponse({ success: false, error: err.message });
            });
            return true;
        case "logout":
            handleLogout().then(() => sendResponse({ success: true }));
            return true;
        case "getStatus":
            sendResponse({ loggedIn: isLoggedIn, user: user, isRecording: isRecording, recordingTabUrl: recordingTabUrl });
            break;
        case "startCapture":
            if (message.tabId) {
                handleStartCapture(message.tabId)
                    .then(() => sendResponse({ success: true }))
                    .catch(err => {
                        console.error("Start capture error:", err);
                        sendResponse({ success: false, error: err.message });
                    });
                return true;
            } else {
                sendResponse({ success: false, error: "Missing tabId" });
            }
            break;
        case "stopCapture":
            handleStopCapture()
                .then(() => sendResponse({ success: true }))
                .catch(err => {
                    console.error("Stop capture error:", err);
                    sendResponse({ success: false, error: err.message });
                });
            return true;
        case "audioChunk":
            if (isRecording && message.chunk) {
                sendAudioChunk(message.chunk);
            }
            break;
        case "recordingError":
            console.error("Error from offscreen recorder:", message.error);
            handleStopCapture("Error in offscreen document");
            break;
        case "recordingStopped":
            console.log("Offscreen document signaled recording stopped.");
            if (isRecording) {
                handleStopCapture("Stopped externally or finished");
            }
            break;
        default:
            console.warn("Unknown message action:", message.action);
            sendResponse({ success: false, error: "Unknown action" });
    }
    if (["login", "logout", "startCapture", "stopCapture"].includes(message.action)) {
        return true;
    }
});

async function handleLogin() {
    if (isLoggedIn) {
        console.log("Already logged in.");
        return;
    }
    console.log("Starting Google OAuth flow...");
    try {
        const redirectUrl = chrome.identity.getRedirectURL();
        console.log("Using redirect URL:", redirectUrl);
        const clientId = chrome.runtime.getManifest().oauth2.client_id;
        const scopes = chrome.runtime.getManifest().oauth2.scopes.join(' ');
        const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?` +
            `client_id=${clientId}&` +
            `response_type=code&` +
            `redirect_uri=${encodeURIComponent(redirectUrl)}&` +
            `scope=${encodeURIComponent(scopes)}&` +
            `access_type=offline&` +
            `prompt=consent`;

        const resultUrl = await chrome.identity.launchWebAuthFlow({
            url: authUrl,
            interactive: true
        });

        if (chrome.runtime.lastError || !resultUrl) {
            throw new Error(chrome.runtime.lastError ? chrome.runtime.lastError.message : "OAuth flow failed or was cancelled.");
        }

        console.log("OAuth flow successful, got result URL:", resultUrl);
        const url = new URL(resultUrl);
        const code = url.searchParams.get('code');

        if (!code) {
            throw new Error("Authorization code not found in redirect URL.");
        }

        console.log("Exchanging code for tokens via backend...");
        const response = await fetch(`${BACKEND_URL}/auth/google/callback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: code, redirectUri: redirectUrl })
        });

        if (!response.ok) {
            const errorData = await response.text();
            throw new Error(`Backend token exchange failed: ${response.status} ${errorData}`);
        }

        const backendResponse = await response.json();

        if (backendResponse.success && backendResponse.user) {
            console.log("Backend login successful:", backendResponse.user);
            user = backendResponse.user;
            isLoggedIn = true;
            await chrome.storage.local.set({ user, isLoggedIn });
            await notifyPopupStatus();
        } else {
            throw new Error("Backend did not confirm successful login or return user data.");
        }

    } catch (error) {
        console.error("OAuth Error:", error);
        isLoggedIn = false;
        user = null;
        await chrome.storage.local.remove(['user', 'isLoggedIn']);
        await notifyPopupStatus();
        throw error;
    }
}

async function handleLogout() {
    console.log("Logging out...");
    if (isRecording) {
        await handleStopCapture("Logging out");
    }

    isLoggedIn = false;
    user = null;
    await chrome.storage.local.remove(['user', 'isLoggedIn']);
    await notifyPopupStatus();
    console.log("Logged out locally.");
}

async function hasOffscreenDocument(path) {
  const offscreenUrl = chrome.runtime.getURL(path);
  const matchedClients = await clients.matchAll();
  for (const client of matchedClients) {
    if (client.url === offscreenUrl) {
      return true;
    }
  }
  return false;
}

async function handleStartCapture(tabId) {
    if (!isLoggedIn) throw new Error("Please login first.");
    if (isRecording) throw new Error("Already recording another meeting.");

    try {
        const tab = await chrome.tabs.get(tabId);
        if (!tab || !MEETING_PATTERNS.some(p => tab.url.includes(p))) {
            throw new Error("Target tab is not a recognized meeting URL or doesn't exist.");
        }

        console.log(`Starting capture for tab ${tabId}: ${tab.url}`);

        const hasDoc = await hasOffscreenDocument(OFFSCREEN_DOCUMENT_PATH);
        if (hasDoc) {
            console.warn("Offscreen document already exists, closing existing one.");
            await chrome.offscreen.closeDocument();
        }

        const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tabId });

        await chrome.offscreen.createDocument({
            url: OFFSCREEN_DOCUMENT_PATH,
            reasons: [chrome.offscreen.Reason.USER_MEDIA],
            justification: 'Recording audio from meeting tab for transcription',
        });
        console.log("Offscreen document created.");

        chrome.runtime.sendMessage({
            action: "startOffscreenCapture",
            target: "offscreen",
            streamId: streamId,
            userId: user?.email
        });
        console.log("Sent streamId to offscreen document.");

        isRecording = true;
        recordingTabId = tabId;
        recordingTabUrl = tab.url;
        recordingId = `rec_${user?.email || 'unknown'}_${Date.now()}`;
        console.log("Recording started, state updated. Recording ID:", recordingId);

        chrome.action.setBadgeText({ text: 'REC', tabId: recordingTabId });
        chrome.action.setBadgeBackgroundColor({ color: '#FF0000', tabId: recordingTabId });

        await notifyPopupStatus();

    } catch (error) {
        console.error("Failed to start capture:", error);
        await handleStopCapture(`Failed to start: ${error.message}`);
        throw error;
    }
}

async function handleStopCapture(reason = "User requested") {
    if (!isRecording && !await hasOffscreenDocument(OFFSCREEN_DOCUMENT_PATH)) {
        console.log("Stop capture called but not recording or offscreen doc missing.");
        return;
    }
    console.log(`Stopping capture. Reason: ${reason}`);

    try {
        chrome.runtime.sendMessage({ action: "stopOffscreenCapture", target: "offscreen" });
    } catch (error) {
        console.warn("Could not send stop message to offscreen (might be closing already):", error);
    }

    try {
        if (await hasOffscreenDocument(OFFSCREEN_DOCUMENT_PATH)) {
            await chrome.offscreen.closeDocument();
            console.log("Offscreen document closed.");
        }
    } catch(error) {
        console.error("Error closing offscreen document:", error);
    }

    if (recordingTabId) {
        try {
            await chrome.action.setBadgeText({ text: '', tabId: recordingTabId });
        } catch(e) { }
    }

    isRecording = false;
    recordingTabId = null;
    recordingTabUrl = null;
    const endedRecordingId = recordingId;
    recordingId = null;

    if (user && endedRecordingId) {
        try {
            await fetch(`${BACKEND_URL}/audio/stream/end`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ userId: user.email, recordingId: endedRecordingId, reason: reason })
            });
            console.log("Sent end-of-stream notification to backend for:", endedRecordingId);
        } catch (error) {
            console.error("Failed to send end-of-stream notification:", error);
        }
    }

    await notifyPopupStatus();
    console.log("Recording stopped, state reset.");
}

async function sendAudioChunk(base64Chunk) {
    if (!isLoggedIn || !user || !isRecording || !recordingId) {
        console.warn("Cannot send audio chunk, invalid state.");
        return;
    }
    try {
        const response = await fetch(`${BACKEND_URL}/audio/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                userId: user.email,
                recordingId: recordingId,
                chunk: base64Chunk
            })
        });
        if (!response.ok) {
            console.error(`Backend audio chunk error: ${response.status} ${await response.text()}`);
        }
    } catch (error) {
        console.error("Network error sending audio chunk:", error);
    }
}

function isWorkingHours() {
    const now = new Date();
    const currentHour = now.getHours();
    return currentHour >= WORKING_HOUR_START && currentHour < WORKING_HOUR_END;
}

function getDomain(url) {
    if (!url || !url.startsWith('http')) {
        return null;
    }
    try {
        return new URL(url).hostname;
    } catch (e) {
        return null;
    }
}

async function updateActivity(previousTabInfo, endTime) {
    if (!isLoggedIn || !isWorkingHours() || !previousTabInfo || !previousTabInfo.domain || !previousTabInfo.startTime) {
        return;
    }

    const durationSeconds = Math.round((endTime - previousTabInfo.startTime) / 1000);
    if (durationSeconds > 1) {
        const domain = previousTabInfo.domain;
        dailyActivityLog[domain] = (dailyActivityLog[domain] || 0) + durationSeconds;
    }
}

chrome.tabs.onActivated.addListener(async (activeInfo) => {
    const previousTabInfo = { ...activeTabInfo };
    const endTime = Date.now();
    await updateActivity(previousTabInfo, endTime);

    try {
        const tab = await chrome.tabs.get(activeInfo.tabId);
        activeTabInfo = {
            tabId: activeInfo.tabId,
            url: tab.url,
            domain: getDomain(tab.url),
            startTime: endTime
        };
    } catch (e) {
        activeTabInfo = { tabId: null, url: null, domain: null, startTime: null };
    }
});

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
    if (tabId === activeTabInfo.tabId && changeInfo.url && activeTabInfo.url !== changeInfo.url) {
        const previousTabInfo = { ...activeTabInfo };
        const endTime = Date.now();
        await updateActivity(previousTabInfo, endTime);

        activeTabInfo.url = changeInfo.url;
        activeTabInfo.domain = getDomain(changeInfo.url);
        activeTabInfo.startTime = endTime;
    }
    if (isRecording && tabId === recordingTabId && changeInfo.url) {
        recordingTabUrl = changeInfo.url;
        await notifyPopupStatus();
        if (!MEETING_PATTERNS.some(p => recordingTabUrl.includes(p))) {
            console.warn("Recorded tab navigated away from meeting URL. Stopping recording.");
            await handleStopCapture("Tab navigated away");
        }
    }
});

chrome.windows.onFocusChanged.addListener(async (windowId) => {
    const previousTabInfo = { ...activeTabInfo };
    const endTime = Date.now();
    await updateActivity(previousTabInfo, endTime);

    if (windowId === chrome.windows.WINDOW_ID_NONE) {
        activeTabInfo = { tabId: null, url: null, domain: null, startTime: null };
    } else {
        try {
            const [tab] = await chrome.tabs.query({ active: true, windowId: windowId });
            if (tab) {
                activeTabInfo = {
                    tabId: tab.id,
                    url: tab.url,
                    domain: getDomain(tab.url),
                    startTime: endTime
                };
            } else {
                activeTabInfo = { tabId: null, url: null, domain: null, startTime: null };
            }
        } catch (e) {
            activeTabInfo = { tabId: null, url: null, domain: null, startTime: null };
        }
    }
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
    if (alarm.name === ACTIVITY_LOG_ALARM) {
        console.log("Daily activity log alarm triggered.");
        const previousTabInfo = { ...activeTabInfo };
        const endTime = Date.now();
        await updateActivity(previousTabInfo, endTime);

        await sendActivityLog();

        dailyActivityLog = {};
        await chrome.storage.local.set({ dailyActivityLog });

        if (activeTabInfo.tabId){
            activeTabInfo.startTime = endTime;
        }
        console.log("Daily activity log sent and reset.");

    } else if (alarm.name === PERIODIC_SAVE_ALARM) {
        const previousTabInfo = { ...activeTabInfo };
        const endTime = Date.now();
        await updateActivity(previousTabInfo, endTime);

        await chrome.storage.local.set({ dailyActivityLog });

        if (activeTabInfo.tabId){
            activeTabInfo.startTime = endTime;
        }
    }
});

async function sendActivityLog() {
    if (!isLoggedIn || !user || Object.keys(dailyActivityLog).length === 0) {
        console.log("Not logged in or no activity to send.");
        return;
    }

    const logToSend = [];
    for (const domain in dailyActivityLog) {
        logToSend.push({ domain: domain, durationSeconds: dailyActivityLog[domain] });
    }

    const today = new Date().toISOString().split('T')[0];
    console.log(`Sending activity log for ${today} (${logToSend.length} domains)`);

    try {
        const response = await fetch(`${BACKEND_URL}/activity/log`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                userId: user.email,
                date: today,
                activity: logToSend
            })
        });
        if (!response.ok) {
            console.error(`Backend activity log error: ${response.status} ${await response.text()}`);
        } else {
            console.log("Activity log sent successfully.");
        }
    } catch (error) {
        console.error("Network error sending activity log:", error);
    }
}

async function notifyPopupStatus() {
    try {
        await chrome.runtime.sendMessage({
            action: "updatePopupStatus",
            status: {
                loggedIn: isLoggedIn,
                user: user,
                isRecording: isRecording,
                recordingTabUrl: recordingTabUrl
            }
        });
    } catch(e) {
        if (!e.message.includes("Receiving end does not exist")) {
            console.warn("Error sending status update to popup:", e);
        }
    }
}