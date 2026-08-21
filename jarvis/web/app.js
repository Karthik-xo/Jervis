/**
 * JARVIS AI OS v2.0 — Movie-Style HUD Engine
 *
 * Provides real-time WebSocket telemetry, interactive HUD visualizations,
 * canvas audio waveform renderer (Ambient, Listening, Speaking),
 * Speech-to-Text & Text-to-Speech engine (English & Tamil support),
 * global search engine, task management, sidebar navigation, and notification drawer.
 */

(() => {
    "use strict";

    // ── Configuration ──────────────────────────────────────────────────────
    const WS_URL = `ws://${location.host}/ws`;
    const API_BASE = `${location.protocol}//${location.host}`;
    const RECONNECT_DELAY = 2000;
    const STATUS_POLL_MS = 5000;

    // ── DOM Cache ──────────────────────────────────────────────────────────
    const $id = (id) => document.getElementById(id);
    const $query = (sel) => document.querySelector(sel);
    const $queryAll = (sel) => document.querySelectorAll(sel);

    const els = {
        // Clock & Date
        clockTime: $id("clock-time"),
        heroDate: $id("hero-date"),

        // Voice & Status Badges
        arcCenterText: $id("arc-center-text"),
        voiceStatePill: $id("voice-state-pill"),
        sttLangSelect: $id("stt-lang-select"),

        // System Telemetry Rings
        ringCpuCircle: $id("ring-cpu-circle"),
        ringCpuText: $id("ring-cpu-text"),
        ringMemCircle: $id("ring-mem-circle"),
        ringMemText: $id("ring-mem-text"),
        ringStorageCircle: $id("ring-storage-circle"),
        ringStorageText: $id("ring-storage-text"),
        ringNetCircle: $id("ring-net-circle"),
        ringNetText: $id("ring-net-text"),

        // Metrics
        healthPct: $id("health-pct"),
        agentsCountPill: $id("agents-count-pill"),
        memTotalVal: $id("mem-total-val"),
        memRelVal: $id("mem-rel-val"),
        memCtxVal: $id("mem-ctx-val"),
        anaCmdsNum: $id("ana-cmds-num"),
        anaAutoNum: $id("ana-auto-num"),
        anaSuccNum: $id("ana-succ-num"),
        anaTimeNum: $id("ana-time-num"),

        // Chat Assistant
        chatMessages: $id("chat-messages"),
        assistantInput: $id("assistant-input"),
        btnAssistantMic: $id("btn-assistant-mic"),
        btnAssistantSend: $id("btn-assistant-send"),
        btnClearChat: $id("btn-clear-chat"),
        aiThinkingIndicator: $id("ai-thinking-indicator"),

        // Voice Console
        waveformCanvas: $id("waveform-canvas"),
        btnMicToggle: $id("btn-mic-toggle"),
        voiceHistoryList: $id("voice-history-list"),

        // Tasks
        tasksPendingBadge: $id("tasks-pending-badge"),
        taskTextInput: $id("task-text-input"),
        taskDueInput: $id("task-due-input"),
        btnAddTask: $id("btn-add-task"),
        taskItemsContainer: $id("task-items-container"),

        // Search & Overlays
        globalSearch: $id("global-search"),
        searchResultsDropdown: $id("search-results-dropdown"),
        searchResultsList: $id("search-results-list"),
        sidebar: $id("sidebar"),
        sidebarToggle: $id("sidebar-toggle"),
        mobileHamburger: $id("mobile-hamburger"),
        btnNotifications: $id("btn-notifications"),
        btnCloseNotif: $id("btn-close-notif"),
        notificationsDrawer: $id("notifications-drawer"),
    };

    // ── State ──────────────────────────────────────────────────────────────
    let ws = null;
    let currentTaskFilter = "pending";
    let isRecording = false;
    let animFrameReq = null;
    let waveformPhase = 0;
    let currentVoiceMode = "STANDBY"; // STANDBY, LISTENING, SPEAKING, PROCESSING
    let searchDebounce = null;
    let selectedSearchIndex = -1;
    let speechRecognition = null;

    // ── Helper Utilities ───────────────────────────────────────────────────
    function escHtml(str) {
        const d = document.createElement("div");
        d.textContent = str || "";
        return d.innerHTML;
    }

    function updateClock() {
        const now = new Date();
        const timeStr = now.toLocaleTimeString("en-US", { hour12: true });
        if (els.clockTime) els.clockTime.textContent = timeStr;

        const dateOptions = { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' };
        if (els.heroDate) els.heroDate.textContent = now.toLocaleDateString("en-US", dateOptions);
    }

    // ── System Ring Telemetry Updater ─────────────────────────────────────
    function setRingProgress(circleEl, textEl, pct) {
        if (!circleEl || !textEl) return;
        const val = Math.min(100, Math.max(0, Number(pct) || 0));
        const strokeDashoffset = 251 - (251 * val / 100);
        circleEl.style.strokeDashoffset = strokeDashoffset;
        textEl.textContent = `${val}%`;
    }

    // ── Voice State Management & Waveform Visualizer ──────────────────────
    function updateVoiceState(state) {
        const st = (state || "STANDBY").toUpperCase();
        currentVoiceMode = st;

        if (els.arcCenterText) els.arcCenterText.textContent = st;
        if (els.voiceStatePill) {
            els.voiceStatePill.textContent = st;
            els.voiceStatePill.className = `pill-badge state-${st.toLowerCase()}`;
        }

        // Toggle microphone button highlight
        if (els.btnMicToggle) {
            els.btnMicToggle.classList.toggle("recording", st === "LISTENING");
        }
        if (els.btnAssistantMic) {
            els.btnAssistantMic.classList.toggle("recording", st === "LISTENING");
        }
    }

    // ── Continuous Holographic Waveform Animation Engine ───────────────────
    function renderWaveformFrame() {
        if (!els.waveformCanvas) return;
        const canvas = els.waveformCanvas;
        const ctx = canvas.getContext("2d");
        const width = canvas.width;
        const height = canvas.height;
        const cy = height / 2;

        ctx.clearRect(0, 0, width, height);

        if (currentVoiceMode === "LISTENING") {
            // Energetic multi-frequency wave (Cyan & Gold)
            ctx.beginPath();
            ctx.lineWidth = 2.5;
            ctx.strokeStyle = "#00F0FF";
            ctx.shadowBlur = 10;
            ctx.shadowColor = "#00F0FF";

            ctx.moveTo(0, cy);
            for (let x = 0; x < width; x++) {
                const angle1 = (x * 0.04) + waveformPhase;
                const angle2 = (x * 0.08) - (waveformPhase * 1.5);
                const amp = Math.sin(x * 0.015) * 22 + Math.cos(x * 0.03) * 10;
                const y = cy + (Math.sin(angle1) + Math.cos(angle2)) * amp * 0.6;
                ctx.lineTo(x, y);
            }
            ctx.stroke();

            // Secondary wave layer
            ctx.beginPath();
            ctx.lineWidth = 1.5;
            ctx.strokeStyle = "rgba(251, 191, 36, 0.7)";
            ctx.shadowBlur = 6;
            ctx.shadowColor = "#FBBF24";

            ctx.moveTo(0, cy);
            for (let x = 0; x < width; x++) {
                const angle = (x * 0.06) - waveformPhase * 0.8;
                const y = cy + Math.sin(angle) * 12;
                ctx.lineTo(x, y);
            }
            ctx.stroke();
            waveformPhase += 0.18;

        } else if (currentVoiceMode === "SPEAKING") {
            // High-frequency speech wave (Teal & Blue)
            ctx.beginPath();
            ctx.lineWidth = 2.5;
            ctx.strokeStyle = "#00FFC8";
            ctx.shadowBlur = 12;
            ctx.shadowColor = "#00FFC8";

            ctx.moveTo(0, cy);
            for (let x = 0; x < width; x++) {
                const angle = (x * 0.07) + waveformPhase * 1.2;
                const amp = Math.sin(x * 0.02) * 18 + 5;
                const y = cy + Math.sin(angle) * amp;
                ctx.lineTo(x, y);
            }
            ctx.stroke();
            waveformPhase += 0.22;

        } else {
            // STANDBY Mode: Smooth ambient holographic sine wave
            ctx.beginPath();
            ctx.lineWidth = 1.5;
            ctx.strokeStyle = "rgba(0, 240, 255, 0.5)";
            ctx.shadowBlur = 4;
            ctx.shadowColor = "rgba(0, 240, 255, 0.4)";

            ctx.moveTo(0, cy);
            for (let x = 0; x < width; x++) {
                const angle = (x * 0.03) + waveformPhase;
                const y = cy + Math.sin(angle) * 6;
                ctx.lineTo(x, y);
            }
            ctx.stroke();
            waveformPhase += 0.05;
        }

        animFrameReq = requestAnimationFrame(renderWaveformFrame);
    }

    // ── Speech-to-Text & Microphone System ────────────────────────────────
    function initSpeechRecognition() {
        const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRec) {
            console.warn("Web Speech API not supported in this browser.");
            return null;
        }

        const rec = new SpeechRec();
        rec.continuous = false;
        rec.interimResults = true;

        rec.onstart = () => {
            isRecording = true;
            updateVoiceState("LISTENING");
        };

        rec.onresult = (event) => {
            let finalTranscript = "";
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += transcript;
                }
            }
            if (finalTranscript.trim()) {
                if (els.assistantInput) els.assistantInput.value = finalTranscript;
                sendCommand(finalTranscript);
            }
        };

        rec.onerror = (e) => {
            console.warn("Speech recognition error:", e.error);
            isRecording = false;
            updateVoiceState("STANDBY");
        };

        rec.onend = () => {
            isRecording = false;
            if (currentVoiceMode === "LISTENING") {
                updateVoiceState("STANDBY");
            }
        };

        return rec;
    }

    function toggleMicrophone() {
        if (!speechRecognition) {
            speechRecognition = initSpeechRecognition();
        }

        if (isRecording && speechRecognition) {
            speechRecognition.stop();
            isRecording = false;
            updateVoiceState("STANDBY");
            return;
        }

        if (speechRecognition) {
            // Resolve language code from selector
            const selectedLang = els.sttLangSelect ? els.sttLangSelect.value : "en";
            if (selectedLang === "ta") {
                speechRecognition.lang = "ta-IN";
            } else if (selectedLang === "en") {
                speechRecognition.lang = "en-US";
            } else {
                speechRecognition.lang = navigator.language || "en-US";
            }

            try {
                speechRecognition.start();
            } catch (e) {
                console.warn("Speech rec start error:", e);
            }
        } else {
            // Fallback if browser Speech API unavailable
            updateVoiceState("LISTENING");
            setTimeout(() => {
                updateVoiceState("STANDBY");
                appendChatMessage("assistant", "Voice engine ready. Web Speech API or microphone permission required for browser listening.");
            }, 3000);
        }
    }

    // ── Text-to-Speech Output Engine ──────────────────────────────────────
    function speakText(text) {
        if (!window.speechSynthesis) return;

        window.speechSynthesis.cancel(); // Stop ongoing speech
        const utterance = new SpeechSynthesisUtterance(text);

        const selectedLang = els.sttLangSelect ? els.sttLangSelect.value : "en";
        if (selectedLang === "ta" || /[\u0B80-\u0BFF]/.test(text)) {
            utterance.lang = "ta-IN";
        } else {
            utterance.lang = "en-US";
        }

        utterance.rate = 1.0;
        utterance.pitch = 1.0;

        utterance.onstart = () => updateVoiceState("SPEAKING");
        utterance.onend = () => updateVoiceState("STANDBY");
        utterance.onerror = () => updateVoiceState("STANDBY");

        window.speechSynthesis.speak(utterance);
    }

    // ── Chat Assistant Messages ───────────────────────────────────────────
    function appendChatMessage(role, text) {
        if (!els.chatMessages) return;

        const div = document.createElement("div");
        div.className = `message ${role === "user" ? "user-msg" : "assistant-msg"}`;
        const avatarStr = role === "user" ? "U" : "J";
        const senderStr = role === "user" ? "YOU" : "JARVIS AI";

        div.innerHTML = `
            <div class="msg-avatar">${avatarStr}</div>
            <div class="msg-content">
                <span class="msg-sender">${senderStr}</span>
                <p>${escHtml(text)}</p>
            </div>
        `;

        els.chatMessages.appendChild(div);
        els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
    }

    async function sendCommand(cmdText) {
        const text = (cmdText || els.assistantInput?.value || "").trim();
        if (!text) return;

        if (els.assistantInput) els.assistantInput.value = "";
        appendChatMessage("user", text);

        if (els.aiThinkingIndicator) els.aiThinkingIndicator.classList.remove("hidden");
        updateVoiceState("PROCESSING");

        try {
            const resp = await fetch(`${API_BASE}/api/command`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ command: text }),
            });
            const data = await resp.json();
            const reply = data.reply || "Action processed successfully, sir.";
            appendChatMessage("assistant", reply);
            addVoiceHistoryEntry(text);
            speakText(reply);
            fetchTasks();

            if (reply.includes("Navigating to")) {
                const navMatch = reply.match(/Navigating to ([^,]+)/i);
                if (navMatch) {
                    const targetName = navMatch[1].trim().toLowerCase();
                    const tabMap = {
                        "dashboard": "dashboard",
                        "settings": "settings",
                        "ai assistant": "assistant",
                        "voice console": "voice",
                        "ai agents": "agents",
                        "memory system": "memory",
                        "analytics": "analytics",
                        "automations": "automations",
                        "security": "security"
                    };
                    if (tabMap[targetName]) navigateToTab(tabMap[targetName]);
                }
            }
        } catch (e) {
            appendChatMessage("assistant", "Error processing command. Server unavailable.");
            updateVoiceState("STANDBY");
        } finally {
            if (els.aiThinkingIndicator) els.aiThinkingIndicator.classList.add("hidden");
        }
    }

    function addVoiceHistoryEntry(text) {
        if (!els.voiceHistoryList) return;
        const now = new Date();
        const timeStr = now.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });

        const div = document.createElement("div");
        div.className = "voice-hist-item";
        div.innerHTML = `
            <span class="hist-time">${timeStr}</span>
            <span class="hist-text">${escHtml(text)}</span>
        `;
        els.voiceHistoryList.prepend(div);

        while (els.voiceHistoryList.children.length > 20) {
            els.voiceHistoryList.removeChild(els.voiceHistoryList.lastChild);
        }
    }

    // ── Global Search System ──────────────────────────────────────────────
    async function performGlobalSearch(query) {
        const q = (query || "").trim();
        if (!q) {
            if (els.searchResultsDropdown) els.searchResultsDropdown.classList.add("hidden");
            return;
        }

        try {
            const resp = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(q)}`);
            const data = await resp.json();
            renderSearchResults(data.results || []);
        } catch (e) {
            console.warn("Search error:", e);
        }
    }

    function renderSearchResults(results) {
        if (!els.searchResultsDropdown || !els.searchResultsList) return;
        els.searchResultsList.innerHTML = "";
        selectedSearchIndex = -1;

        if (results.length === 0) {
            els.searchResultsList.innerHTML = `<div style="font-size:0.75rem;color:var(--text-muted);padding:8px;">No matching results found in JARVIS memory.</div>`;
            els.searchResultsDropdown.classList.remove("hidden");
            return;
        }

        results.forEach((item, idx) => {
            const div = document.createElement("div");
            div.className = "search-item";
            div.dataset.index = idx;
            div.dataset.action = item.action;

            div.innerHTML = `
                <div class="search-item-left">
                    <span class="search-item-title">${escHtml(item.title)}</span>
                    <span class="search-item-sub">${escHtml(item.subtitle)}</span>
                </div>
                <span class="search-item-type">${escHtml(item.type)}</span>
            `;

            div.addEventListener("click", () => {
                executeSearchAction(item.action, item.title);
                els.searchResultsDropdown.classList.add("hidden");
                if (els.globalSearch) els.globalSearch.value = "";
            });

            els.searchResultsList.appendChild(div);
        });

        els.searchResultsDropdown.classList.remove("hidden");
    }

    function executeSearchAction(actionStr, title) {
        if (!actionStr) return;
        const [type, payload] = actionStr.split(":");

        if (type === "cmd") {
            sendCommand(payload);
        } else if (type === "nav") {
            navigateToTab(payload);
        } else if (type === "task") {
            navigateToTab("dashboard");
            const taskEl = document.querySelector(`.btn-toggle-task[data-id="${payload}"]`);
            if (taskEl) taskEl.scrollIntoView({ behavior: "smooth" });
        } else if (type === "chat") {
            navigateToTab("assistant");
            if (els.assistantInput) els.assistantInput.value = payload;
        } else {
            sendCommand(`Inspect ${title}`);
        }
    }

    // ── Navigation & Section Focus ────────────────────────────────────────
    const TAB_TO_ID_MAP = {
        "dashboard": "hero-banner",
        "command-center": "panel-command-center",
        "assistant": "panel-assistant",
        "voice": "panel-voice",
        "agents": "panel-agents",
        "memory": "panel-memory",
        "automations": "panel-automations",
        "kb": "panel-kb",
        "documents": "panel-documents",
        "analytics": "panel-analytics",
        "security": "panel-security",
        "settings": "panel-settings"
    };

    let isNavigating = false;
    let navTimeout = null;

    function navigateToTab(tabName) {
        if (!tabName) return;

        isNavigating = true;
        if (navTimeout) clearTimeout(navTimeout);

        // 1. Highlight selected sidebar navigation item
        $queryAll(".nav-item").forEach(b => {
            if (b.dataset.tab === tabName) {
                b.classList.add("active");
            } else {
                b.classList.remove("active");
            }
        });

        // 2. Automatically close mobile sidebar drawer if open
        if (els.sidebar) {
            els.sidebar.classList.remove("mobile-open");
        }

        // 3. Resolve target DOM element
        const targetId = TAB_TO_ID_MAP[tabName] || `panel-${tabName}`;
        const targetPanel = $id(targetId) || document.querySelector(`.${targetId}`);

        if (targetPanel) {
            targetPanel.scrollIntoView({ behavior: "smooth", block: "start" });
            targetPanel.style.borderColor = "var(--cyan)";
            targetPanel.style.boxShadow = "0 0 25px rgba(0, 240, 255, 0.5)";
            setTimeout(() => {
                targetPanel.style.borderColor = "";
                targetPanel.style.boxShadow = "";
            }, 1800);
        }

        navTimeout = setTimeout(() => {
            isNavigating = false;
        }, 1200);
    }

    function initScrollSpy() {
        const mainArea = $id("main-area");
        if (!mainArea) return;

        let scrollDebounce = null;
        mainArea.addEventListener("scroll", () => {
            if (isNavigating) return;
            if (scrollDebounce) return;
            scrollDebounce = setTimeout(() => {
                scrollDebounce = null;
                if (isNavigating) return;

                const scrollPos = mainArea.scrollTop;
                let activeTab = "dashboard";

                const entries = Object.entries(TAB_TO_ID_MAP).map(([tab, id]) => ({
                    tab,
                    el: $id(id)
                })).filter(item => item.el !== null);

                for (const item of entries) {
                    const top = item.el.offsetTop - mainArea.offsetTop;
                    if (scrollPos >= top - 140) {
                        activeTab = item.tab;
                    }
                }

                $queryAll(".nav-item").forEach(btn => {
                    btn.classList.toggle("active", btn.dataset.tab === activeTab);
                });
            }, 80);
        }, { passive: true });
    }

    // ── Task Management ───────────────────────────────────────────────────
    async function fetchTasks() {
        try {
            const resp = await fetch(`${API_BASE}/api/tasks?include_done=true`);
            const data = await resp.json();
            renderTasks(data.tasks || []);
        } catch (e) {
            console.warn("Task fetch error:", e);
        }
    }

    function renderTasks(tasks) {
        if (!els.taskItemsContainer) return;
        els.taskItemsContainer.innerHTML = "";

        const filtered = tasks.filter(t => {
            if (currentTaskFilter === "pending") return !t.done;
            if (currentTaskFilter === "completed") return t.done;
            return true;
        });

        const pendingCount = tasks.filter(t => !t.done).length;
        if (els.tasksPendingBadge) els.tasksPendingBadge.textContent = `${pendingCount} PENDING`;

        if (filtered.length === 0) {
            els.taskItemsContainer.innerHTML = `<p class="placeholder-text">No ${currentTaskFilter} tasks. JARVIS standing by.</p>`;
            return;
        }

        filtered.forEach(t => {
            const div = document.createElement("div");
            div.className = `task-item ${t.done ? "task-done" : ""}`;
            const dueStr = t.due_relative ? `<span class="task-due-badge">${escHtml(t.due_relative)}</span>` : "";

            div.innerHTML = `
                <button class="task-checkbox-btn btn-toggle-task" data-id="${t.id}" data-done="${t.done}" title="${t.done ? 'Mark pending' : 'Mark completed'}">
                    ${t.done ? '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>' : ''}
                </button>
                <div class="task-details">
                    <span class="task-title">${escHtml(t.text)}</span>
                    ${dueStr}
                </div>
                <div class="task-actions">
                    <button class="task-delete-btn btn-delete-task" data-id="${t.id}" title="Delete task">
                        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                </div>
            `;
            els.taskItemsContainer.appendChild(div);
        });

        els.taskItemsContainer.querySelectorAll(".btn-toggle-task").forEach(btn => {
            btn.addEventListener("click", async () => {
                const tid = Number(btn.dataset.id);
                await fetch(`${API_BASE}/api/tasks/complete`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ task_id: tid }),
                });
                fetchTasks();
            });
        });

        els.taskItemsContainer.querySelectorAll(".btn-delete-task").forEach(btn => {
            btn.addEventListener("click", async () => {
                const tid = Number(btn.dataset.id);
                await fetch(`${API_BASE}/api/tasks/delete`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ task_id: tid }),
                });
                fetchTasks();
            });
        });
    }


    async function addTask() {
        const text = (els.taskTextInput?.value || "").trim();
        if (!text) return;
        const dueMins = els.taskDueInput?.value ? Number(els.taskDueInput.value) : null;

        try {
            await fetch(`${API_BASE}/api/tasks`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text, due_minutes: dueMins }),
            });
            if (els.taskTextInput) els.taskTextInput.value = "";
            if (els.taskDueInput) els.taskDueInput.value = "";
            fetchTasks();
        } catch (e) {
            console.warn("Add task error:", e);
        }
    }

    // ── Telemetry Status Fetching ──────────────────────────────────────────
    async function fetchStatus() {
        try {
            const resp = await fetch(`${API_BASE}/api/status`);
            const d = await resp.json();

            setRingProgress(els.ringCpuCircle, els.ringCpuText, d.cpu_percent ?? 23);
            setRingProgress(els.ringMemCircle, els.ringMemText, d.memory_percent ?? 45);
            setRingProgress(els.ringStorageCircle, els.ringStorageText, d.storage_percent ?? 70);
            setRingProgress(els.ringNetCircle, els.ringNetText, d.network_percent ?? 82);

            if (els.memTotalVal) els.memTotalVal.textContent = (d.total_memories ?? 12458).toLocaleString();
            if (els.anaCmdsNum) els.anaCmdsNum.textContent = (d.total_commands ?? 1248).toLocaleString();

            if (d.voice_state && !isRecording) updateVoiceState(d.voice_state);
        } catch (e) {
            console.warn("Status fetch error:", e);
        }
    }

    // ── WebSocket Client ───────────────────────────────────────────────────
    function connectWS() {
        try {
            ws = new WebSocket(WS_URL);
        } catch (e) {
            console.warn("WebSocket fallback.");
            return;
        }

        ws.onopen = () => {
            console.log("WebSocket connected.");
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                const { event: evName, data } = msg;

                if (evName === "voice_state" && !isRecording) {
                    updateVoiceState(data.state);
                } else if (evName === "transcript") {
                    appendChatMessage("user", data.text);
                    addVoiceHistoryEntry(data.text);
                } else if (evName === "reply") {
                    appendChatMessage("assistant", data.reply);
                    speakText(data.reply);
                } else if (evName === "ui_navigate") {
                    if (data && data.tab) navigateToTab(data.tab);
                } else if (evName === "task_update") {
                    fetchTasks();
                }
            } catch (e) {
                console.warn("WS parse error:", e);
            }
        };

        ws.onclose = () => {
            setTimeout(connectWS, RECONNECT_DELAY);
        };
    }

    // ── Event Listener Binding ─────────────────────────────────────────────
    function initEvents() {
        // Sidebar Navigation
        $queryAll(".nav-item").forEach(btn => {
            btn.addEventListener("click", () => {
                navigateToTab(btn.dataset.tab);
            });
        });

        // Sidebar Collapse Toggle
        if (els.sidebarToggle) {
            els.sidebarToggle.addEventListener("click", () => {
                if (els.sidebar) els.sidebar.classList.toggle("collapsed");
            });
        }

        // Mobile Hamburger Drawer
        if (els.mobileHamburger) {
            els.mobileHamburger.addEventListener("click", () => {
                if (els.sidebar) els.sidebar.classList.toggle("mobile-open");
            });
        }

        // Notifications Modal Toggle
        if (els.btnNotifications) {
            els.btnNotifications.addEventListener("click", () => {
                if (els.notificationsDrawer) els.notificationsDrawer.classList.toggle("hidden");
            });
        }
        if (els.btnCloseNotif) {
            els.btnCloseNotif.addEventListener("click", () => {
                if (els.notificationsDrawer) els.notificationsDrawer.classList.add("hidden");
            });
        }

        // Global Search Input
        if (els.globalSearch) {
            els.globalSearch.addEventListener("input", () => {
                clearTimeout(searchDebounce);
                searchDebounce = setTimeout(() => {
                    performGlobalSearch(els.globalSearch.value);
                }, 200);
            });

            els.globalSearch.addEventListener("keydown", (e) => {
                const items = els.searchResultsList ? els.searchResultsList.querySelectorAll(".search-item") : [];

                if (e.key === "ArrowDown") {
                    e.preventDefault();
                    if (items.length > 0) {
                        selectedSearchIndex = Math.min(items.length - 1, selectedSearchIndex + 1);
                        items.forEach((it, idx) => it.classList.toggle("active-item", idx === selectedSearchIndex));
                    }
                } else if (e.key === "ArrowUp") {
                    e.preventDefault();
                    if (items.length > 0) {
                        selectedSearchIndex = Math.max(0, selectedSearchIndex - 1);
                        items.forEach((it, idx) => it.classList.toggle("active-item", idx === selectedSearchIndex));
                    }
                } else if (e.key === "Enter") {
                    if (selectedSearchIndex >= 0 && items[selectedSearchIndex]) {
                        items[selectedSearchIndex].click();
                    } else {
                        sendCommand(els.globalSearch.value);
                        els.globalSearch.value = "";
                        if (els.searchResultsDropdown) els.searchResultsDropdown.classList.add("hidden");
                    }
                } else if (e.key === "Escape") {
                    if (els.searchResultsDropdown) els.searchResultsDropdown.classList.add("hidden");
                }
            });
        }

        // Close search dropdown on click outside
        document.addEventListener("click", (e) => {
            if (els.globalSearch && !els.globalSearch.contains(e.target) && els.searchResultsDropdown && !els.searchResultsDropdown.contains(e.target)) {
                els.searchResultsDropdown.classList.add("hidden");
            }
        });

        // Chat & Assistant Send
        if (els.btnAssistantSend) els.btnAssistantSend.addEventListener("click", () => sendCommand());
        if (els.assistantInput) {
            els.assistantInput.addEventListener("keydown", (e) => {
                if (e.key === "Enter") sendCommand();
            });
        }

        // Microphone Buttons (Voice Console & Chat bar)
        if (els.btnMicToggle) els.btnMicToggle.addEventListener("click", toggleMicrophone);
        if (els.btnAssistantMic) els.btnAssistantMic.addEventListener("click", toggleMicrophone);

        // Global Shortcut Ctrl + K
        document.addEventListener("keydown", (e) => {
            if (e.ctrlKey && e.key.toLowerCase() === "k") {
                e.preventDefault();
                if (els.globalSearch) {
                    els.globalSearch.focus();
                    els.globalSearch.select();
                }
            }
        });

        // Tasks
        if (els.btnAddTask) els.btnAddTask.addEventListener("click", addTask);

        $queryAll(".task-tab").forEach(tabBtn => {
            tabBtn.addEventListener("click", () => {
                $queryAll(".task-tab").forEach(t => t.classList.remove("active"));
                tabBtn.classList.add("active");
                currentTaskFilter = tabBtn.dataset.filter;
                fetchTasks();
            });
        });

        // Prompt Chips
        $queryAll(".chip-btn").forEach(chip => {
            chip.addEventListener("click", () => {
                sendCommand(chip.dataset.prompt);
            });
        });

        // Clear Chat
        if (els.btnClearChat) {
            els.btnClearChat.addEventListener("click", () => {
                if (els.chatMessages) {
                    els.chatMessages.innerHTML = `
                        <div class="message assistant-msg">
                            <div class="msg-avatar">J</div>
                            <div class="msg-content">
                                <span class="msg-sender">JARVIS AI</span>
                                <p>Chat thread cleared, Sir. Standing by.</p>
                            </div>
                        </div>
                    `;
                }
            });
        }
    }

    // ── Initialization ─────────────────────────────────────────────────────
    updateClock();
    initEvents();
    initScrollSpy();

    connectWS();
    fetchStatus();
    fetchTasks();

    // Start continuous audio visualizer animation loop
    renderWaveformFrame();

    setInterval(updateClock, 1000);
    setInterval(fetchStatus, STATUS_POLL_MS);
})();
