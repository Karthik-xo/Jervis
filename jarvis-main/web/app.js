/**
 * JARVIS Cyberpunk HUD Dashboard — Main Logic & Web Speech Integration
 */

let currentFilter = 'pending';
let isProcessing = false;
let recognition = null;
let isListeningWeb = false;

document.addEventListener('DOMContentLoaded', () => {
    initClock();
    fetchStatus();
    fetchTasks();
    fetchLogs();
    initCanvasAnimation();

    // Setup Event Listeners
    document.getElementById('command-form').addEventListener('submit', handleCommandSubmit);
    document.getElementById('task-form').addEventListener('submit', handleTaskSubmit);

    // Auto Refresh Intervals
    setInterval(fetchStatus, 5000);
    setInterval(fetchTasks, 4000);
    setInterval(fetchLogs, 3000);
});

/* Live Clock & Date */
function initClock() {
    const clockEl = document.getElementById('live-clock');
    const dateEl = document.getElementById('live-date');

    function update() {
        const now = new Date();
        clockEl.textContent = now.toTimeString().split(' ')[0];
        dateEl.textContent = now.toISOString().split('T')[0];
    }
    update();
    setInterval(update, 1000);
}

/* System Status Fetcher */
async function fetchStatus() {
    try {
        const res = await fetch('/api/status');
        if (!res.ok) return;
        const data = await res.json();

        document.getElementById('val-os').textContent = data.system || 'Windows';
        document.getElementById('val-mic').textContent = data.mic_spec || 'Default Mic';
        document.getElementById('val-brain').textContent = data.model || 'Claude 3.5 Sonnet';
        document.getElementById('val-tts').textContent = data.elevenlabs_configured ? 'ElevenLabs + SAPI5' : 'Native SAPI5 Fallback';
        document.getElementById('ai-model-badge').textContent = (data.model || 'CLAUDE-3.5-SONNET').toUpperCase();
    } catch (e) {
        console.warn('Status fetch failed:', e);
    }
}

/* Task Management */
async function fetchTasks() {
    try {
        const res = await fetch('/api/tasks?include_done=true');
        if (!res.ok) return;
        const data = await res.json();
        renderTasks(data.tasks || []);
    } catch (e) {
        console.warn('Tasks fetch failed:', e);
    }
}

function renderTasks(tasks) {
    const container = document.getElementById('task-list-container');
    const pendingBadge = document.getElementById('pending-count-badge');
    
    const pendingTasks = tasks.filter(t => !t.done);
    pendingBadge.textContent = `${pendingTasks.length} PENDING`;

    let filtered = tasks;
    if (currentFilter === 'pending') filtered = tasks.filter(t => !t.done);
    else if (currentFilter === 'completed') filtered = tasks.filter(t => t.done);

    if (filtered.length === 0) {
        container.innerHTML = `<div class="empty-state">No ${currentFilter} tasks. JARVIS standby.</div>`;
        return;
    }

    container.innerHTML = filtered.map(t => `
        <div class="task-item ${t.done ? 'done' : ''}">
            <div class="task-info">
                <input type="checkbox" class="task-check" ${t.done ? 'checked' : ''} onchange="toggleTask(${t.id}, this.checked)">
                <span class="task-text">#${t.id} ${escapeHtml(t.text)}</span>
                ${t.due_relative ? `<span class="task-due">⏳ ${t.due_relative}</span>` : ''}
            </div>
            <button class="btn-del" onclick="deleteTask(${t.id})" title="Delete Task">✕</button>
        </div>
    `).join('');
}

function setTaskFilter(filter) {
    currentFilter = filter;
    document.querySelectorAll('.task-tabs .tab').forEach(t => t.classList.remove('active'));
    document.getElementById(`tab-${filter}`).classList.add('active');
    fetchTasks();
}

async function handleTaskSubmit(e) {
    e.preventDefault();
    const textInput = document.getElementById('task-text-input');
    const dueInput = document.getElementById('task-due-input');

    const text = textInput.value.trim();
    if (!text) return;

    const due_minutes = dueInput.value ? parseFloat(dueInput.value) : null;

    try {
        const res = await fetch('/api/tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, due_minutes })
        });
        if (res.ok) {
            textInput.value = '';
            dueInput.value = '';
            fetchTasks();
        }
    } catch (err) {
        alert('Could not create task');
    }
}

async function toggleTask(taskId, isDone) {
    if (!isDone) return;
    try {
        await fetch('/api/tasks/complete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_id: taskId })
        });
        fetchTasks();
    } catch (e) {
        console.error('Task complete error:', e);
    }
}

async function deleteTask(taskId) {
    try {
        await fetch('/api/tasks/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_id: taskId })
        });
        fetchTasks();
    } catch (e) {
        console.error('Task delete error:', e);
    }
}

/* Command Handling */
async function handleCommandSubmit(e) {
    e.preventDefault();
    const input = document.getElementById('command-input');
    const cmd = input.value.trim();
    if (!cmd) return;

    input.value = '';
    executeCommand(cmd);
}

function executeQuick(cmdText) {
    executeCommand(cmdText);
}

async function executeCommand(commandText) {
    const transcriptEl = document.getElementById('live-transcript');
    const arcCore = document.getElementById('arc-core-node');
    const arcState = document.getElementById('arc-state-text');

    transcriptEl.textContent = `Processing: "${commandText}"...`;
    arcCore.classList.add('active');
    arcState.textContent = 'THINKING';
    isProcessing = true;

    try {
        const res = await fetch('/api/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: commandText })
        });

        if (res.ok) {
            const data = await res.json();
            transcriptEl.textContent = `JARVIS: "${data.reply}"`;
            arcState.textContent = 'SPEAKING';
        } else {
            transcriptEl.textContent = 'Error processing command.';
            arcState.textContent = 'ERROR';
        }
    } catch (err) {
        transcriptEl.textContent = 'Could not communicate with JARVIS server.';
        arcState.textContent = 'OFFLINE';
    } finally {
        setTimeout(() => {
            arcCore.classList.remove('active');
            arcState.textContent = 'STANDBY';
            isProcessing = false;
        }, 3000);
        fetchTasks();
        fetchLogs();
    }
}

/* Browser Microphone Speech Recognition API */
function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        console.warn('Web Speech Recognition API not supported in this browser.');
        return null;
    }

    const rec = new SpeechRecognition();
    rec.continuous = false;
    rec.interimResults = true;
    rec.lang = 'en-US';

    rec.onstart = () => {
        isListeningWeb = true;
        isProcessing = true;
        const voiceBtnText = document.getElementById('voice-btn-text');
        if (voiceBtnText) voiceBtnText.textContent = 'LISTENING...';
        document.getElementById('arc-core-node').classList.add('active');
        document.getElementById('arc-state-text').textContent = 'LISTENING';
    };

    rec.onresult = (event) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            transcript += event.results[i][0].transcript;
        }
        document.getElementById('command-input').value = transcript;
        document.getElementById('live-transcript').textContent = `Voice Input: "${transcript}"`;

        if (event.results[0].isFinal) {
            rec.stop();
            executeCommand(transcript);
        }
    };

    rec.onerror = (event) => {
        console.warn('Speech recognition error:', event.error);
        resetVoiceBtn();
    };

    rec.onend = () => {
        resetVoiceBtn();
    };

    return rec;
}

function resetVoiceBtn() {
    isListeningWeb = false;
    isProcessing = false;
    const voiceBtnText = document.getElementById('voice-btn-text');
    if (voiceBtnText) voiceBtnText.textContent = 'TALK';
    document.getElementById('arc-core-node').classList.remove('active');
    document.getElementById('arc-state-text').textContent = 'STANDBY';
}

function toggleVoiceInput() {
    if (!recognition) {
        recognition = initSpeechRecognition();
    }

    if (!recognition) {
        alert('Web Speech Recognition is not supported by your browser. Please use Google Chrome, Brave, or MS Edge.');
        return;
    }

    if (isListeningWeb) {
        recognition.stop();
    } else {
        try {
            recognition.start();
        } catch (e) {
            console.warn('Speech recognition start exception:', e);
        }
    }
}

/* Log Console Stream */
async function fetchLogs() {
    try {
        const res = await fetch('/api/logs');
        if (!res.ok) return;
        const data = await res.json();
        renderLogs(data.logs || []);
    } catch (e) {
        console.warn('Logs fetch failed:', e);
    }
}

function renderLogs(logs) {
    const box = document.getElementById('log-stream-box');
    if (!logs || logs.length === 0) return;

    box.innerHTML = logs.map(l => `
        <div class="log-line">
            <span class="log-time">${l.timestamp}</span>
            <span class="log-tag info">${l.level}</span>
            ${escapeHtml(l.message)}
        </div>
    `).join('');
    box.scrollTop = box.scrollHeight;
}

function refreshLogs() {
    fetchLogs();
}

/* Audio Waveform Canvas Animation */
function initCanvasAnimation() {
    const canvas = document.getElementById('waveform-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    let step = 0;
    function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        ctx.beginPath();
        ctx.lineWidth = 2;
        ctx.strokeStyle = isProcessing ? '#00f3ff' : 'rgba(0, 243, 255, 0.2)';

        const width = canvas.width;
        const height = canvas.height;
        const mid = height / 2;

        for (let x = 0; x < width; x += 4) {
            const amplitude = isProcessing ? 18 : 4;
            const freq = isProcessing ? 0.05 : 0.02;
            const y = mid + Math.sin(x * freq + step) * amplitude;
            if (x === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();

        step += isProcessing ? 0.15 : 0.04;
        requestAnimationFrame(draw);
    }
    draw();
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
