const loginButton = document.getElementById('loginButton');
const logoutButton = document.getElementById('logoutButton');
const recordButton = document.getElementById('recordButton');
const loginSection = document.getElementById('loginSection');
const mainSection = document.getElementById('mainSection');
const userInfoDiv = document.getElementById('userInfo');
const userAvatar = document.getElementById('userAvatar');
const userEmail = document.getElementById('userEmail');
const statusDiv = document.getElementById('status');


document.addEventListener('DOMContentLoaded', async () => {
    try {
        const { loggedIn, user, isRecording, recordingTabUrl } = await chrome.runtime.sendMessage({ action: "getStatus" });
        updateUI(loggedIn, user, isRecording, recordingTabUrl);
    } catch (error) {
        console.error("Error getting status from background:", error);
        statusDiv.textContent = "Error loading status.";
       
        updateUI(false);
    }
});

loginButton.addEventListener('click', () => {
    statusDiv.textContent = "Initiating Google Login...";
    chrome.runtime.sendMessage({ action: "login" });
   
    window.close(); 
});

logoutButton.addEventListener('click', async () => {
    await chrome.runtime.sendMessage({ action: "logout" });
    updateUI(false);
    statusDiv.textContent = "Logged out.";
});

recordButton.addEventListener('click', async () => {
    const { isRecording } = await chrome.runtime.sendMessage({ action: "getStatus" });

    if (isRecording) {
        // Stop recording
        statusDiv.textContent = "Stopping recording...";
        recordButton.disabled = true;
        try {
            await chrome.runtime.sendMessage({ action: "stopCapture" });
            statusDiv.textContent = "Recording stopped.";
            recordButton.textContent = "Start Meeting Recording";
            recordButton.disabled = false;
        } catch (error) {
            console.error("Error stopping capture:", error);
            statusDiv.textContent = `Error stopping: ${error.message}`;
            recordButton.disabled = false; // Re-enable if failed
        }
    } else {
        // Start recording
        statusDiv.textContent = "Checking active tab...";
        try {
            const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
            if (activeTab && (activeTab.url.includes('meet.google.com') || activeTab.url.includes('zoom.us/j/'))) {
                statusDiv.textContent = "Starting recording...";
                recordButton.disabled = true;
                await chrome.runtime.sendMessage({ action: "startCapture", tabId: activeTab.id });
                statusDiv.textContent = `Recording meeting on: ${new URL(activeTab.url).hostname}`;
                recordButton.textContent = "Stop Recording";
                recordButton.disabled = false;
                 window.close(); // Close popup after starting
            } else {
                statusDiv.textContent = "Not on a Meet or Zoom tab.";
            }
        } catch (error) {
            console.error("Error starting capture:", error);
            statusDiv.textContent = `Error starting: ${error.message}`;
            recordButton.disabled = false;
        }
    }
});

// Listen for updates from the background script (optional, good for live updates if popup stays open)
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === "updatePopupStatus") {
         const { loggedIn, user, isRecording, recordingTabUrl } = message.status;
         updateUI(loggedIn, user, isRecording, recordingTabUrl);
    }
});


function updateUI(loggedIn, user = null, isRecording = false, recordingTabUrl = null) {
    if (loggedIn && user) {
        loginSection.classList.add('hidden');
        mainSection.classList.remove('hidden');
        userInfoDiv.style.display = 'flex';
        userAvatar.src = user.avatarUrl || 'icons/icon48.png'; // Default icon if no avatar
        userEmail.textContent = user.email;

        if (isRecording) {
            recordButton.textContent = "Stop Recording";
            statusDiv.textContent = `Recording meeting on: ${recordingTabUrl ? new URL(recordingTabUrl).hostname : 'Unknown'}`;
        } else {
            recordButton.textContent = "Start Meeting Recording";
            statusDiv.textContent = "Idle. Start recording in Meet/Zoom tab.";
        }
         recordButton.disabled = false; // Ensure enabled after update
    } else {
        loginSection.classList.remove('hidden');
        mainSection.classList.add('hidden');
        userInfoDiv.style.display = 'none';
        statusDiv.textContent = "Please log in.";
    }
}