// --- UPDATE THIS TO YOUR NGROK/VPS URL ---
// e.g., "https://1a2b-3c4d.ngrok.app/chat"
const API_URL = "http://127.0.0.1:8000/chat"; 

const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');

function appendMessage(sender, text, isMarkdown = false) {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('message', sender === 'user' ? 'user-message' : 'bot-message');
    
    const contentDiv = document.createElement('div');
    contentDiv.classList.add('message-content');
    
    if (isMarkdown) {
        // Parse the markdown into HTML using the marked library
        contentDiv.innerHTML = marked.parse(text);
    } else {
        contentDiv.textContent = text;
    }
    
    msgDiv.appendChild(contentDiv);
    chatBox.appendChild(msgDiv);
    
    // Auto-scroll to the bottom
    chatBox.scrollTop = chatBox.scrollHeight;
}

async function handleSend() {
    const query = userInput.value.trim();
    if (!query) return;

    // 1. Show user message and clear input
    appendMessage('user', query, false);
    userInput.value = '';
    
    // 2. Disable input while waiting
    userInput.disabled = true;
    sendBtn.disabled = true;
    sendBtn.textContent = "Thinking...";

    try {
        // 3. Send to your Python backend
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query: query })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        
        // 4. Show bot response (True flag enables Markdown parsing)
        appendMessage('bot', data.answer, true);

    } catch (error) {
        console.error('Error:', error);
        appendMessage('bot', '⚠️ Connection error. Make sure your Python backend and tunnel are running.', false);
    } finally {
        // 5. Re-enable inputs
        userInput.disabled = false;
        sendBtn.disabled = false;
        sendBtn.textContent = "Send";
        userInput.focus();
    }
}

// Allow pressing 'Enter' to send
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        handleSend();
    }
});

// Click event for the send button
sendBtn.addEventListener('click', handleSend);
