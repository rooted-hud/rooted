const API_URL = "https://octagon-wham-gambling.ngrok-free.dev/chat";
const HEALTH_URL = API_URL.replace("/chat", "/health");
const NGROK_HEADERS = { 'ngrok-skip-browser-warning': 'true' };

const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const badge = document.querySelector('.badge');

// --- Server Status Check ---
async function checkServerStatus() {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 4000);
    try {
        const response = await fetch(HEALTH_URL, {
            method: 'GET',
            headers: NGROK_HEADERS,
            signal: controller.signal
        });
        setStatus(response.ok);
    } catch {
        setStatus(false);
    } finally {
        clearTimeout(timer);
    }
}

function setStatus(isOnline) {
    badge.textContent = isOnline ? 'online' : 'offline';
    badge.classList.toggle('badge-offline', !isOnline);
}

// Check on load, then every 30 seconds
checkServerStatus();
setInterval(checkServerStatus, 30000);


// --- Chat ---
function formatSourceUrl(url) {
    try {
        const parsed = new URL(url);
        return (parsed.hostname + parsed.pathname + parsed.search)
            .replace(/^www\./, '')
            .replace(/\/$/, '');
    } catch {
        return url; // if URL is malformed, show as-is
    }
}
function appendMessage(sender, text, sources = []) {
    const rowDiv = document.createElement('div');
    rowDiv.classList.add('message-row', sender === 'user' ? 'row-user' : 'row-bot');

    const senderDiv = document.createElement('div');
    senderDiv.classList.add('sender-col');
    senderDiv.textContent = sender === 'user' ? 'USER /' : 'BOT /';

    const contentDiv = document.createElement('div');
    contentDiv.classList.add('content-col');

    // Main answer text (always plain for user, markdown for bot)
    if (sender !== 'user') {
        contentDiv.innerHTML = marked.parse(text);
    } else {
        const p = document.createElement('p');
        p.textContent = text;
        contentDiv.appendChild(p);
    }

    // Numbered sources list
    if (sources.length > 0) {
        const sourceBlock = document.createElement('ol');
        sourceBlock.classList.add('source-list');
        sources.forEach(url => {
            const li = document.createElement('li');
            const a = document.createElement('a');
            a.href = url;
            a.target = '_blank';
            a.rel = 'noopener';
            a.textContent = formatSourceUrl(url) + ' ↗';
            li.appendChild(a);
            sourceBlock.appendChild(li);
        });
        contentDiv.appendChild(sourceBlock);
    }

    rowDiv.appendChild(senderDiv);
    rowDiv.appendChild(contentDiv);
    chatBox.appendChild(rowDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

async function handleSend() {
    const query = userInput.value.trim();
    if (!query) return;

    appendMessage('user', query, false);
    userInput.value = '';

    userInput.disabled = true;
    sendBtn.disabled = true;
    sendBtn.textContent = 'Thinking...';

    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...NGROK_HEADERS },
            body: JSON.stringify({ query })
        });

        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const data = await response.json();
        appendMessage('bot', data.answer, data.sources || []);
        console.log(data.chunks)

    } catch (error) {
        console.error('Error:', error);
        appendMessage('bot', 'Connection error. Our server is probably offline. Maybe try forking the [repository](https://github.com/rooted-hud/rooted) to try yourself!', false);
    } finally {
        userInput.disabled = false;
        sendBtn.disabled = false;
        sendBtn.textContent = 'Send /';
        userInput.focus();
    }
}

userInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') handleSend(); });
sendBtn.addEventListener('click', handleSend);

// --- Clear History on Load ---
const CLEAR_URL = API_URL.replace("/chat", "/clear_history");

async function clearHistoryOnLoad() {
    try {
        await fetch(CLEAR_URL, {
            method: 'POST',
            headers: NGROK_HEADERS
        });
        console.log("Session history cleared.");
    } catch (error) {
        console.error('Failed to clear history:', error);
    }
}

// Call it immediately
clearHistoryOnLoad();
