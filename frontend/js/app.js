// Global Application State
let state = {
    meetings: [],
    selectedMeeting: null,
    recordingType: null, // 'browser' or 'server'
    recordingDuration: 0,
    timerInterval: null,
    statusPollInterval: null,
    mediaRecorder: null,
    audioChunks: [],
    settings: {
        has_key: false,
        recording_device_id: null,
        company_name: ""
    }
};

// DOM Elements
const elements = {
    meetingsContainer: document.getElementById('meetings-container'),
    searchInput: document.getElementById('search-input'),
    newMeetingBtn: document.getElementById('new-meeting-btn'),
    settingsBtn: document.getElementById('settings-btn'),
    
    // Views
    welcomeView: document.getElementById('welcome-view'),
    meetingView: document.getElementById('meeting-view'),
    
    // Meeting View Details
    meetingTitle: document.getElementById('meeting-title'),
    meetingDate: document.getElementById('meeting-date'),
    meetingDuration: document.getElementById('meeting-duration'),
    meetingStatusBadge: document.getElementById('meeting-status-badge'),
    downloadPdfBtn: document.getElementById('download-pdf-btn'),
    deleteMeetingBtn: document.getElementById('delete-meeting-btn'),
    
    // Tabs
    tabButtons: document.querySelectorAll('.tab-btn'),
    tabPanes: document.querySelectorAll('.tab-pane'),
    
    // Insights Tab
    insightDecisionsCount: document.getElementById('insight-decisions-count'),
    insightActionsCount: document.getElementById('insight-actions-count'),
    insightMeetingDuration: document.getElementById('insight-meeting-duration'),
    insightOverviewContent: document.getElementById('insight-overview-content'),
    
    // Minutes Tab
    momOverview: document.getElementById('mom-overview'),
    momKeyPoints: document.getElementById('mom-key-points'),
    momDecisions: document.getElementById('mom-decisions'),
    momActionItems: document.getElementById('mom-action-items'),
    
    // Transcript Tab
    momTranscript: document.getElementById('mom-transcript'),
    viewAudioContainer: document.getElementById('view-audio-container'),
    viewAudioPlayer: document.getElementById('view-audio-player'),
    
    // Overlays
    recordingOverlay: document.getElementById('recording-overlay'),
    recordingStatusTitle: document.getElementById('recording-status-title'),
    recordingTypeSubtitle: document.getElementById('recording-type-subtitle'),
    recordingTimerVal: document.getElementById('recording-timer-val'),
    stopRecordBtn: document.getElementById('stop-record-btn'),
    cancelRecordBtn: document.getElementById('cancel-record-btn'),
    processingOverlay: document.getElementById('processing-overlay'),
    
    // Modals
    settingsModal: document.getElementById('settings-modal'),
    settingsForm: document.getElementById('settings-form'),
    settingsApiKey: document.getElementById('settings-api-key'),
    settingsDeviceId: document.getElementById('settings-device-id'),
    settingsCompany: document.getElementById('settings-company'),
    settingsOllamaModel: document.getElementById('settings-ollama-model'),
    sounddeviceSettingGroup: document.getElementById('sounddevice-setting-group'),
    
    uploadModal: document.getElementById('upload-modal'),
    uploadForm: document.getElementById('upload-form'),
    uploadTitle: document.getElementById('upload-title'),
    uploadFile: document.getElementById('upload-file'),
    
    // Welcomes page action buttons
    cardBrowserRecordBtn: document.querySelector('.start-browser-record-btn'),
    cardServerRecordBtn: document.querySelector('.start-server-record-btn'),
    cardUploadBtn: document.querySelector('.trigger-upload-btn'),
    closeModalBtns: document.querySelectorAll('.close-modal-btn')
};

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', () => {
    initApp();
    setupEventListeners();
});

function initApp() {
    fetchMeetings();
    fetchSettings();
    
    // Check if recording is already active on the server
    checkServerRecordingStatus();
}

// --- EVENT LISTENERS ---
function setupEventListeners() {
    // Search
    elements.searchInput.addEventListener('input', filterMeetings);
    
    // Navigation & Modals
    elements.newMeetingBtn.addEventListener('click', showWelcomeView);
    elements.settingsBtn.addEventListener('click', openSettingsModal);
    elements.cardUploadBtn.addEventListener('click', openUploadModal);
    
    elements.closeModalBtns.forEach(btn => {
        btn.addEventListener('click', closeAllModals);
    });
    
    // Settings Form Submit
    elements.settingsForm.addEventListener('submit', handleSettingsSubmit);
    
    // Upload Form Submit
    elements.uploadForm.addEventListener('submit', handleUploadSubmit);
    
    // Browser Recording Triggers
    elements.cardBrowserRecordBtn.addEventListener('click', startBrowserRecording);
    
    // Server Recording Triggers
    elements.cardServerRecordBtn.addEventListener('click', startServerRecording);
    
    // Recording Actions Overlay
    elements.stopRecordBtn.addEventListener('click', stopRecording);
    elements.cancelRecordBtn.addEventListener('click', cancelRecording);
    
    // Meeting View Actions
    elements.downloadPdfBtn.addEventListener('click', downloadMeetingPdf);
    elements.deleteMeetingBtn.addEventListener('click', deleteMeeting);
    
    // Title Edit
    elements.meetingTitle.addEventListener('blur', handleTitleRename);
    elements.meetingTitle.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            elements.meetingTitle.blur();
        }
    });

    // Tab Navigation
    elements.tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.getAttribute('data-tab');
            switchTab(tabId);
        });
    });
}

// --- API ACTIONS ---

async function fetchMeetings() {
    try {
        const response = await fetch('/api/meetings');
        state.meetings = await response.json();
        renderMeetingList();
        
        // If we have a selected meeting, poll for status updates
        if (state.selectedMeeting) {
            const updated = state.meetings.find(m => m.id === state.selectedMeeting.id);
            if (updated && updated.status !== state.selectedMeeting.status) {
                // Status changed, reload selected details
                selectMeeting(updated.id);
            }
        }
    } catch (err) {
        console.error('Error fetching meetings:', err);
    }
}

async function fetchSettings() {
    try {
        const response = await fetch('/api/settings');
        const data = await response.json();
        
        state.settings = data.settings;
        
        // Populate inputs
        elements.settingsApiKey.value = data.settings.gemini_api_key || "";
        elements.settingsCompany.value = data.settings.company_name || "";
        elements.settingsOllamaModel.value = data.settings.ollama_model || "tinyllama";
        
        // Handle input device selector
        const deviceSelect = elements.settingsDeviceId;
        deviceSelect.innerHTML = '<option value="">-- No Microphone / Offline Mode --</option>';
        
        if (data.sounddevice_available && data.audio_devices.length > 0) {
            elements.sounddeviceSettingGroup.style.display = 'block';
            data.audio_devices.forEach(device => {
                const opt = document.createElement('option');
                opt.value = device.id;
                opt.textContent = `${device.name} (Ch: ${device.max_input_channels})`;
                if (device.id === data.settings.recording_device_id) {
                    opt.selected = true;
                }
                deviceSelect.appendChild(opt);
            });
            // Show Server Recording card
            document.getElementById('card-server-record').style.opacity = '1';
            document.getElementById('card-server-record').style.pointerEvents = 'auto';
        } else {
            // Disable server recording if not available
            elements.sounddeviceSettingGroup.style.display = 'none';
            const serverCard = document.getElementById('card-server-record');
            serverCard.style.opacity = '0.5';
            serverCard.style.pointerEvents = 'none';
            serverCard.querySelector('p').textContent = "Server recording is disabled. Python sounddevice is not available.";
        }
    } catch (err) {
        console.error('Error fetching settings:', err);
    }
}

async function handleSettingsSubmit(e) {
    e.preventDefault();
    
    const api_key = elements.settingsApiKey.value.trim();
    const device_id = elements.settingsDeviceId.value ? parseInt(elements.settingsDeviceId.value) : null;
    const company = elements.settingsCompany.value.trim();
    const ollama_model = elements.settingsOllamaModel.value.trim() || "tinyllama";
    
    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                gemini_api_key: api_key,
                recording_device_id: device_id,
                company_name: company,
                ollama_model: ollama_model
            })
        });
        
        const res = await response.json();
        if (res.status === 'success') {
            closeAllModals();
            fetchSettings(); // Refresh
            alert("Settings updated successfully!");
        } else {
            alert("Error saving settings.");
        }
    } catch (err) {
        console.error('Settings update error:', err);
        alert("Failed to connect to the server.");
    }
}

async function selectMeeting(meetingId) {
    try {
        const response = await fetch(`/api/meetings/${meetingId}`);
        if (!response.ok) return;
        
        const meeting = await response.json();
        state.selectedMeeting = meeting;
        
        // Highlight in sidebar
        document.querySelectorAll('.meeting-item').forEach(el => {
            el.classList.remove('active');
            if (parseInt(el.getAttribute('data-id')) === meetingId) {
                el.classList.add('active');
            }
        });
        
        renderMeetingDetails(meeting);
        
        // Handle background polling if still processing
        if (meeting.status === 'processing') {
            startStatusPolling(meetingId);
        } else {
            stopStatusPolling();
        }
    } catch (err) {
        console.error('Error fetching meeting detail:', err);
    }
}

async function handleUploadSubmit(e) {
    e.preventDefault();
    
    const title = elements.uploadTitle.value.trim();
    const file = elements.uploadFile.files[0];
    
    if (!title || !file) return;
    
    closeAllModals();
    showProcessingOverlay();
    
    const formData = new FormData();
    formData.append('title', title);
    formData.append('file', file);
    
    try {
        const response = await fetch('/api/meetings/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        if (data.status === 'success') {
            // Refresh meetings and select the newly created one
            await fetchMeetings();
            selectMeeting(data.meeting_id);
        } else {
            alert(`Error uploading: ${data.message}`);
        }
    } catch (err) {
        console.error('Upload failed:', err);
        alert("Failed to upload file to backend.");
    } finally {
        hideProcessingOverlay();
    }
}

async function handleTitleRename() {
    if (!state.selectedMeeting) return;
    
    const newTitle = elements.meetingTitle.textContent.trim();
    if (!newTitle || newTitle === state.selectedMeeting.title) {
        elements.meetingTitle.textContent = state.selectedMeeting.title;
        return;
    }
    
    try {
        const response = await fetch(`/api/meetings/${state.selectedMeeting.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: newTitle })
        });
        const res = await response.json();
        if (res.status === 'success') {
            state.selectedMeeting.title = newTitle;
            fetchMeetings(); // Refresh sidebar list
        } else {
            elements.meetingTitle.textContent = state.selectedMeeting.title;
            alert("Error renaming meeting.");
        }
    } catch (err) {
        console.error('Rename error:', err);
        elements.meetingTitle.textContent = state.selectedMeeting.title;
    }
}

async function deleteMeeting() {
    if (!state.selectedMeeting) return;
    if (!confirm(`Are you sure you want to delete the meeting "${state.selectedMeeting.title}"?`)) return;
    
    const id = state.selectedMeeting.id;
    try {
        const response = await fetch(`/api/meetings/${id}`, {
            method: 'DELETE'
        });
        const res = await response.json();
        if (res.status === 'success') {
            state.selectedMeeting = null;
            showWelcomeView();
            fetchMeetings();
        }
    } catch (err) {
        console.error('Failed to delete meeting:', err);
    }
}

function downloadMeetingPdf() {
    if (!state.selectedMeeting) return;
    const id = state.selectedMeeting.id;
    window.open(`/api/meetings/${id}/pdf`, '_blank');
}

// --- RECORDING ACTIONS ---

// 1. Client-Side Browser Recording
let audioCtx = null;
let scriptProcessor = null;
let micSource = null;
let samples = [];

async function startBrowserRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        // Setup AudioContext (fallback to webkitAudioContext)
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        micSource = audioCtx.createMediaStreamSource(stream);
        
        // 4096 buffer size, 1 input channel, 1 output channel
        scriptProcessor = audioCtx.createScriptProcessor(4096, 1, 1);
        
        samples = [];
        scriptProcessor.onaudioprocess = (e) => {
            const input = e.inputBuffer.getChannelData(0);
            for (let i = 0; i < input.length; i++) {
                samples.push(input[i]);
            }
        };
        
        micSource.connect(scriptProcessor);
        scriptProcessor.connect(audioCtx.destination);
        
        state.recordingType = 'browser';
        showRecordingOverlay("Browser Microphone");
        startTimer();
        
        // Keep stream reference to stop it later
        state.stream = stream;
        
    } catch (err) {
        console.error("Microphone access denied:", err);
        alert("Microphone permission required for browser recording: " + err.message);
    }
}

// 2. Server-Side Physical Microphone Recording
async function startServerRecording() {
    try {
        const response = await fetch('/api/meetings/record/start', {
            method: 'POST'
        });
        const res = await response.json();
        
        if (res.status === 'success') {
            state.recordingType = 'server';
            showRecordingOverlay("Server Hardware Microphone");
            startTimer();
        } else {
            alert(res.message);
        }
    } catch (err) {
        console.error("Server recording trigger failed:", err);
        alert("Failed to start hardware recording.");
    }
}

async function checkServerRecordingStatus() {
    try {
        const response = await fetch('/api/meetings/record/status');
        const data = await response.json();
        
        if (data.is_recording) {
            state.recordingType = 'server';
            state.recordingDuration = data.duration;
            showRecordingOverlay("Server Hardware Microphone");
            startTimer(true); // resume
        }
    } catch (err) {
        console.error("Error checking server status:", err);
    }
}

// 3. General Recording Stop / Cancel
async function stopRecording() {
    stopTimer();
    hideRecordingOverlay();
    
    if (state.recordingType === 'browser') {
        if (scriptProcessor) {
            scriptProcessor.disconnect();
            scriptProcessor.onaudioprocess = null;
        }
        if (micSource) {
            micSource.disconnect();
        }
        if (audioCtx) {
            audioCtx.close();
        }
        if (state.stream) {
            state.stream.getTracks().forEach(track => track.stop());
        }
        
        showProcessingOverlay();
        
        // Run downsampling and encoding
        setTimeout(async () => {
            try {
                const inputSampleRate = audioCtx ? audioCtx.sampleRate : 44100;
                const outputSampleRate = 16000;
                
                const downsampled = downsampleBuffer(samples, inputSampleRate, outputSampleRate);
                const wavBlob = encodeWAV(downsampled, outputSampleRate);
                
                const title = `Browser Record - ${new Date().toLocaleDateString()} ${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`;
                
                const formData = new FormData();
                formData.append('title', title);
                formData.append('file', wavBlob, 'record.wav');
                
                const response = await fetch('/api/meetings/upload', {
                    method: 'POST',
                    body: formData
                });
                const res = await response.json();
                if (res.status === 'success') {
                    await fetchMeetings();
                    selectMeeting(res.meeting_id);
                } else {
                    alert(`Upload failed: ${res.message}`);
                }
            } catch (err) {
                console.error("Failed to process and upload browser recording:", err);
                alert("Could not process browser recording.");
            } finally {
                hideProcessingOverlay();
            }
        }, 100);
    } else if (state.recordingType === 'server') {
        showProcessingOverlay();
        const title = `Host Record - ${new Date().toLocaleDateString()} ${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`;
        
        try {
            const response = await fetch(`/api/meetings/record/stop?title=${encodeURIComponent(title)}`, {
                method: 'POST'
            });
            const res = await response.json();
            if (res.status === 'success') {
                await fetchMeetings();
                selectMeeting(res.meeting_id);
            } else {
                alert(`Error stopping server recorder: ${res.message}`);
            }
        } catch (err) {
            console.error("Failed to stop server recording:", err);
            alert("Connection error while stopping server recording.");
        } finally {
            hideProcessingOverlay();
        }
    }
    
    state.recordingType = null;
}

function cancelRecording() {
    if (!confirm("Are you sure you want to cancel the current recording? Audio will not be saved.")) return;
    
    stopTimer();
    hideRecordingOverlay();
    
    if (state.recordingType === 'browser') {
        if (scriptProcessor) {
            scriptProcessor.disconnect();
            scriptProcessor.onaudioprocess = null;
        }
        if (micSource) {
            micSource.disconnect();
        }
        if (audioCtx) {
            audioCtx.close();
        }
        if (state.stream) {
            state.stream.getTracks().forEach(track => track.stop());
        }
    } else if (state.recordingType === 'server') {
        fetch(`/api/meetings/record/stop?title=Cancelled`).then(r => r.json()).then(res => {
            if (res.meeting_id) {
                fetch(`/api/meetings/${res.meeting_id}`, { method: 'DELETE' });
            }
        });
    }
    
    state.recordingType = null;
}

// --- POLLING UTILITIES ---
function startStatusPolling(meetingId) {
    stopStatusPolling(); // Clear existing
    state.statusPollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/meetings/${meetingId}`);
            if (!response.ok) return;
            const meeting = await response.json();
            
            if (meeting.status !== 'processing') {
                stopStatusPolling();
                fetchMeetings(); // update list
                selectMeeting(meetingId); // refresh details
            }
        } catch (err) {
            console.error("Polling error:", err);
        }
    }, 3000);
}

function stopStatusPolling() {
    if (state.statusPollInterval) {
        clearInterval(state.statusPollInterval);
        state.statusPollInterval = null;
    }
}

// --- TIMER UTILITIES ---
function startTimer(resume = false) {
    if (!resume) {
        state.recordingDuration = 0;
    }
    elements.recordingTimerVal.textContent = formatTime(state.recordingDuration);
    
    state.timerInterval = setInterval(() => {
        state.recordingDuration++;
        elements.recordingTimerVal.textContent = formatTime(state.recordingDuration);
        
        // If server recording, we also sync with real status occasionally
        if (state.recordingType === 'server' && state.recordingDuration % 5 === 0) {
            fetch('/api/meetings/record/status')
                .then(r => r.json())
                .then(data => {
                    if (data.is_recording) {
                        state.recordingDuration = data.duration;
                    }
                });
        }
    }, 1000);
}

function stopTimer() {
    if (state.timerInterval) {
        clearInterval(state.timerInterval);
        state.timerInterval = null;
    }
}

function formatTime(totalSeconds) {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

// --- UI RENDERING & TOGGLES ---

function showWelcomeView() {
    elements.meetingView.classList.remove('active');
    elements.welcomeView.classList.add('active');
    state.selectedMeeting = null;
    
    // Remove active state from list items
    document.querySelectorAll('.meeting-item').forEach(el => el.classList.remove('active'));
}

function showMeetingView() {
    elements.welcomeView.classList.remove('active');
    elements.meetingView.classList.add('active');
}

function switchTab(tabId) {
    elements.tabButtons.forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-tab') === tabId);
    });
    elements.tabPanes.forEach(pane => {
        pane.classList.toggle('active', pane.getAttribute('id') === tabId);
    });
}

function openSettingsModal() {
    fetchSettings(); // Refresh before opening
    elements.settingsModal.classList.add('active');
}

function openUploadModal() {
    elements.uploadTitle.value = "";
    elements.uploadFile.value = null;
    elements.uploadModal.classList.add('active');
}

function closeAllModals() {
    elements.settingsModal.classList.remove('active');
    elements.uploadModal.classList.remove('active');
}

function showRecordingOverlay(typeText) {
    elements.recordingTypeSubtitle.textContent = `via ${typeText}`;
    elements.recordingOverlay.classList.add('active');
}

function hideRecordingOverlay() {
    elements.recordingOverlay.classList.remove('active');
}

function showProcessingOverlay() {
    elements.processingOverlay.classList.add('active');
}

function hideProcessingOverlay() {
    elements.processingOverlay.classList.remove('active');
}

function filterMeetings() {
    const query = elements.searchInput.value.toLowerCase();
    const items = elements.meetingsContainer.querySelectorAll('.meeting-item');
    
    items.forEach(item => {
        const title = item.querySelector('.meeting-item-title').textContent.toLowerCase();
        if (title.includes(query)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}

function renderMeetingList() {
    const container = elements.meetingsContainer;
    container.innerHTML = '';
    
    if (state.meetings.length === 0) {
        container.innerHTML = '<div class="list-placeholder">No meetings found.</div>';
        return;
    }
    
    state.meetings.forEach(meeting => {
        const item = document.createElement('div');
        item.classList.add('meeting-item');
        item.setAttribute('data-id', meeting.id);
        if (state.selectedMeeting && state.selectedMeeting.id === meeting.id) {
            item.classList.add('active');
        }
        
        // Date Formatter
        let displayDate = meeting.date;
        try {
            const d = new Date(meeting.date);
            displayDate = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
        } catch(e) {}
        
        // Duration Formatter
        const durMin = Math.floor(meeting.duration / 60);
        const durSec = meeting.duration % 60;
        const displayDur = durMin > 0 ? `${durMin}m ${durSec}s` : `${durSec}s`;
        
        // Status indicator class
        let statusClass = 'completed';
        if (meeting.status === 'processing') statusClass = 'processing';
        if (meeting.status === 'failed') statusClass = 'failed';
        
        item.innerHTML = `
            <div class="meeting-item-title">${meeting.title}</div>
            <div class="meeting-item-meta">
                <span>${displayDate}</span>
                <span class="badge ${statusClass}">${meeting.status}</span>
            </div>
        `;
        
        item.addEventListener('click', () => {
            selectMeeting(meeting.id);
        });
        
        container.appendChild(item);
    });
}

function renderMeetingDetails(meeting) {
    showMeetingView();
    switchTab('tab-insights'); // Reset tab to insights
    
    // Set headers
    elements.meetingTitle.textContent = meeting.title;
    
    try {
        const d = new Date(meeting.date);
        elements.meetingDate.textContent = d.toLocaleDateString(undefined, { dateStyle: 'long' });
    } catch(e) {
        elements.meetingDate.textContent = meeting.date;
    }
    
    const min = Math.floor(meeting.duration / 60);
    const sec = meeting.duration % 60;
    elements.meetingDuration.textContent = min > 0 ? `${min} min ${sec} sec` : `${sec} sec`;
    
    // Status Badge
    elements.meetingStatusBadge.className = `badge ${meeting.status}`;
    elements.meetingStatusBadge.textContent = meeting.status.toUpperCase();
    
    // PDF Button state
    elements.downloadPdfBtn.disabled = meeting.status !== 'completed';
    elements.downloadPdfBtn.style.opacity = meeting.status === 'completed' ? '1' : '0.5';
    
    // Audio Player setup
    if (meeting.audio_path) {
        elements.viewAudioContainer.style.display = 'block';
        elements.viewAudioPlayer.src = `/api/meetings/${meeting.id}/audio`;
    } else {
        elements.viewAudioContainer.style.display = 'none';
        elements.viewAudioPlayer.src = '';
    }
    
    // Render content based on status
    if (meeting.status === 'processing') {
        renderProcessingDetails();
    } else if (meeting.status === 'failed') {
        renderFailedDetails(meeting);
    } else {
        renderCompletedDetails(meeting);
    }
}

function renderProcessingDetails() {
    // Insights Tab
    elements.insightDecisionsCount.textContent = '-';
    elements.insightActionsCount.textContent = '-';
    elements.insightMeetingDuration.textContent = 'Processing...';
    elements.insightOverviewContent.innerHTML = '<em>This meeting is currently being processed by AI. Transcription and summary will appear automatically once done.</em>';
    
    // Minutes Tab
    elements.momOverview.innerHTML = '<em>Processing...</em>';
    elements.momKeyPoints.innerHTML = '<li>Processing...</li>';
    elements.momDecisions.innerHTML = '<li>Processing...</li>';
    elements.momActionItems.innerHTML = '<tr><td colspan="3" class="text-center">Processing...</td></tr>';
    
    // Transcript Tab
    elements.momTranscript.innerHTML = '<em>Transcribing audio in background, please wait...</em>';
}

function renderFailedDetails(meeting) {
    const summary = meeting.summary || {};
    
    elements.insightDecisionsCount.textContent = '0';
    elements.insightActionsCount.textContent = '0';
    elements.insightMeetingDuration.textContent = 'Failed';
    elements.insightOverviewContent.textContent = summary.overview || 'AI Processing failed for this meeting.';
    
    elements.momOverview.textContent = summary.overview || 'Processing failed.';
    elements.momKeyPoints.innerHTML = (summary.key_points || []).map(p => `<li>${p}</li>`).join('') || '<li>Error processing points.</li>';
    elements.momDecisions.innerHTML = (summary.decisions || []).map(d => `<li>${d}</li>`).join('') || '<li>Error processing decisions.</li>';
    elements.momActionItems.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Failed to generate action items. See backend log.</td></tr>';
    
    elements.momTranscript.innerHTML = `<span style="color:var(--danger)">Error: ${meeting.transcript || 'AI process crash.'}</span>`;
}

function renderCompletedDetails(meeting) {
    const summary = meeting.summary || { overview: '', key_points: [], decisions: [], action_items: [] };
    
    // Insights Tab
    elements.insightDecisionsCount.textContent = (summary.decisions || []).length;
    elements.insightActionsCount.textContent = (summary.action_items || []).length;
    
    const min = Math.floor(meeting.duration / 60);
    elements.insightMeetingDuration.textContent = `${min} min`;
    elements.insightOverviewContent.textContent = summary.overview || 'No overview generated.';
    
    // Minutes Tab
    elements.momOverview.textContent = summary.overview || 'No overview generated.';
    
    // Key Points
    if (summary.key_points && summary.key_points.length > 0) {
        elements.momKeyPoints.innerHTML = summary.key_points.map(pt => `<li>${pt}</li>`).join('');
    } else {
        elements.momKeyPoints.innerHTML = '<li>No key points recorded.</li>';
    }
    
    // Decisions
    if (summary.decisions && summary.decisions.length > 0) {
        elements.momDecisions.innerHTML = summary.decisions.map(dec => `<li>${dec}</li>`).join('');
    } else {
        elements.momDecisions.innerHTML = '<li>No decisions recorded.</li>';
    }
    
    // Action Items
    if (summary.action_items && summary.action_items.length > 0) {
        elements.momActionItems.innerHTML = summary.action_items.map(item => `
            <tr>
                <td><strong>${item.task || 'Task'}</strong></td>
                <td>${item.assignee || 'Unassigned'}</td>
                <td>${item.deadline || 'N/A'}</td>
            </tr>
        `).join('');
    } else {
        elements.momActionItems.innerHTML = '<tr><td colspan="3" class="text-center">No action items assigned.</td></tr>';
    }
    
    // Transcript Tab
    if (meeting.transcript) {
        // Format transcript with line breaks & bold speaker tags
        const formattedTranscript = meeting.transcript.split('\n')
            .filter(para => para.trim().length > 0)
            .map(para => {
                if (para.includes(':') && !para.startsWith('http')) {
                    const parts = para.split(':');
                    const speaker = parts[0];
                    const content = parts.slice(1).join(':');
                    return `<p><strong>${speaker}:</strong>${content}</p>`;
                }
                return `<p>${para}</p>`;
            })
            .join('');
        elements.momTranscript.innerHTML = formattedTranscript;
    } else {
        elements.momTranscript.innerHTML = '<em>No transcript available.</em>';
    }
}

// WAV Recording Helpers
function writeUTFBytes(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
    }
}

function encodeWAV(samples, sampleRate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);
    
    writeUTFBytes(view, 0, 'RIFF');
    view.setUint32(4, 36 + samples.length * 2, true);
    writeUTFBytes(view, 8, 'WAVE');
    writeUTFBytes(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); // PCM format
    view.setUint16(22, 1, true); // Mono channel
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true); // Byte rate
    view.setUint16(32, 2, true); // Block align
    view.setUint16(34, 16, true); // Bits per sample
    writeUTFBytes(view, 36, 'data');
    view.setUint32(40, samples.length * 2, true);
    
    let offset = 44;
    for (let i = 0; i < samples.length; i++, offset += 2) {
        let s = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
    
    return new Blob([view], { type: 'audio/wav' });
}

function downsampleBuffer(buffer, inputSampleRate, outputSampleRate) {
    if (inputSampleRate === outputSampleRate) {
        return buffer;
    }
    const sampleRateRatio = inputSampleRate / outputSampleRate;
    const newLength = Math.round(buffer.length / sampleRateRatio);
    const result = new Float32Array(newLength);
    let offsetResult = 0;
    let offsetBuffer = 0;
    while (offsetResult < result.length) {
        const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
        let accum = 0, count = 0;
        for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
            accum += buffer[i];
            count++;
        }
        result[offsetResult] = count > 0 ? accum / count : 0;
        offsetResult++;
        offsetBuffer = nextOffsetBuffer;
    }
    return result;
}
