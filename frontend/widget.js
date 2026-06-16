/**
 * ARIA Widget — floating chat for Varshith's portfolio.
 *
 * Embed with one line:
 *   <script src="https://your-deploy.hf.space/widget.js" data-api="https://your-deploy.hf.space"></script>
 *
 * Or inline during local dev:
 *   <script>window.ARIA_API_BASE = 'http://localhost:8000';</script>
 *   <script src="./widget.js"></script>
 */
(function () {
  'use strict';

  // Resolve API base: attribute on the script tag > global > same origin
  const scriptEl = document.currentScript;
  const API_BASE =
    (scriptEl && scriptEl.getAttribute('data-api')) ||
    window.ARIA_API_BASE ||
    '';

  const MARKED_CDN =
    'https://cdnjs.cloudflare.com/ajax/libs/marked/9.1.6/marked.min.js';

  // -------------------------------------------------------------------------
  // Styles
  // -------------------------------------------------------------------------
  const CSS = `
    #aria-fab {
      position: fixed;
      bottom: 28px;
      right: 28px;
      z-index: 99998;
      width: 56px;
      height: 56px;
      border-radius: 50%;
      background: linear-gradient(135deg, #f59e0b, #b45309);
      border: none;
      cursor: pointer;
      box-shadow: 0 4px 24px rgba(245,158,11,0.35);
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: 'Inter', system-ui, sans-serif;
      font-weight: 700;
      font-size: 18px;
      color: #000;
      transition: transform 0.2s, box-shadow 0.2s;
    }
    #aria-fab:hover {
      transform: scale(1.07);
      box-shadow: 0 6px 32px rgba(245,158,11,0.5);
    }
    #aria-fab .aria-close-icon { display: none; }
    #aria-fab.open .aria-a-icon { display: none; }
    #aria-fab.open .aria-close-icon { display: block; }

    #aria-panel {
      position: fixed;
      bottom: 100px;
      right: 28px;
      z-index: 99997;
      width: 380px;
      max-height: 560px;
      background: #0a0a0a;
      border: 1px solid #252525;
      border-radius: 16px;
      display: none;
      flex-direction: column;
      overflow: hidden;
      box-shadow: 0 24px 64px rgba(0,0,0,0.6);
      font-family: 'Inter', system-ui, sans-serif;
      transform-origin: bottom right;
      animation: aria-open 0.2s ease;
    }
    #aria-panel.visible { display: flex; }
    @keyframes aria-open {
      from { opacity: 0; transform: scale(0.92) translateY(8px); }
      to   { opacity: 1; transform: scale(1) translateY(0); }
    }

    /* Panel header */
    #aria-header {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 14px 16px;
      border-bottom: 1px solid #1e1e1e;
      background: #111;
      flex-shrink: 0;
    }
    .aria-av {
      width: 32px; height: 32px;
      border-radius: 50%;
      background: linear-gradient(135deg, #f59e0b, #b45309);
      display: flex; align-items: center; justify-content: center;
      font-weight: 700; font-size: 13px; color: #000; flex-shrink: 0;
    }
    .aria-title { font-size: 14px; font-weight: 600; color: #e5e7eb; }
    .aria-sub { font-size: 11px; color: #6b7280; }
    .aria-dot {
      width: 6px; height: 6px; border-radius: 50%;
      background: #22c55e; margin-left: auto;
      animation: aria-pulse 2s infinite;
    }
    @keyframes aria-pulse {
      0%,100% { opacity: 1; } 50% { opacity: 0.3; }
    }

    /* Messages */
    #aria-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 14px;
      scroll-behavior: smooth;
    }
    #aria-messages::-webkit-scrollbar { width: 3px; }
    #aria-messages::-webkit-scrollbar-thumb { background: #252525; border-radius: 4px; }

    /* Suggestions */
    #aria-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      padding: 0 12px 10px;
    }
    .aria-chip {
      padding: 5px 12px;
      border: 1px solid #252525;
      border-radius: 100px;
      font-size: 11px;
      color: #6b7280;
      background: #111;
      cursor: pointer;
      transition: all 0.15s;
      font-family: inherit;
    }
    .aria-chip:hover { border-color: #f59e0b; color: #f59e0b; }

    /* Bubbles */
    .aria-msg { display: flex; flex-direction: column; }
    .aria-msg.user { align-self: flex-end; align-items: flex-end; }
    .aria-msg.bot  { align-self: flex-start; align-items: flex-start; }
    .aria-bubble {
      padding: 10px 14px;
      border-radius: 12px;
      font-size: 13px;
      line-height: 1.6;
      max-width: 280px;
    }
    .aria-msg.user .aria-bubble {
      background: #1c1c1c;
      border: 1px solid #252525;
      color: #e5e7eb;
    }
    .aria-msg.bot .aria-bubble {
      background: #111;
      border: 1px solid #252525;
      color: #e5e7eb;
    }
    .aria-bubble p { margin: 0 0 8px; }
    .aria-bubble p:last-child { margin: 0; }
    .aria-bubble strong { color: #fff; }
    .aria-bubble ul, .aria-bubble ol { padding-left: 16px; margin: 0 0 8px; }
    .aria-bubble li { margin-bottom: 3px; }
    .aria-bubble a { color: #f59e0b; text-decoration: none; }
    .aria-bubble a:hover { text-decoration: underline; }
    .aria-bubble code {
      background: #1a1a1a; padding: 1px 5px;
      border-radius: 3px; font-size: 12px;
    }

    /* Typing dots */
    .aria-typing {
      display: flex; align-items: center; gap: 4px;
      padding: 10px 14px;
      background: #111; border: 1px solid #252525;
      border-radius: 12px;
    }
    .aria-typing span {
      width: 5px; height: 5px; border-radius: 50%;
      background: #6b7280; animation: aria-bounce 1.2s infinite;
    }
    .aria-typing span:nth-child(2) { animation-delay: 0.2s; }
    .aria-typing span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes aria-bounce {
      0%,80%,100% { transform: translateY(0); }
      40% { transform: translateY(-5px); }
    }

    /* Input */
    #aria-input-row {
      display: flex;
      gap: 8px;
      padding: 10px 12px;
      border-top: 1px solid #1e1e1e;
      background: #111;
      align-items: flex-end;
      flex-shrink: 0;
    }
    #aria-input {
      flex: 1;
      background: #0a0a0a;
      border: 1px solid #252525;
      border-radius: 8px;
      color: #e5e7eb;
      font-size: 13px;
      padding: 9px 12px;
      resize: none;
      outline: none;
      min-height: 38px;
      max-height: 90px;
      line-height: 1.5;
      font-family: inherit;
      transition: border-color 0.15s;
    }
    #aria-input:focus { border-color: #f59e0b; }
    #aria-input::placeholder { color: #4b5563; }
    #aria-send {
      width: 38px; height: 38px;
      background: #f59e0b; border: none; border-radius: 8px;
      cursor: pointer; display: flex; align-items: center; justify-content: center;
      transition: all 0.15s; flex-shrink: 0;
    }
    #aria-send:hover { background: #d97706; }
    #aria-send:disabled { background: #252525; cursor: not-allowed; }
    #aria-send svg { width: 15px; height: 15px; }
    #aria-mic {
      width: 38px; height: 38px;
      background: transparent;
      border: 1px solid #252525;
      border-radius: 8px; cursor: pointer;
      display: none; align-items: center; justify-content: center;
      color: #6b7280; transition: all 0.15s; flex-shrink: 0;
    }
    #aria-mic.visible { display: flex; }
    #aria-mic:hover { border-color: #f59e0b; color: #f59e0b; }
    #aria-mic.recording { border-color: #ef4444; color: #ef4444; animation: aria-mic-pulse 1s infinite; }
    #aria-mic svg { width: 15px; height: 15px; }
    @keyframes aria-mic-pulse {
      0%,100% { box-shadow: 0 0 0 0 rgba(239,68,68,0.4); }
      50% { box-shadow: 0 0 0 5px rgba(239,68,68,0); }
    }

    /* Empty state */
    #aria-empty {
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      gap: 8px; text-align: center; flex: 1; padding: 24px 16px;
    }
    #aria-empty .aria-em-av {
      width: 44px; height: 44px; border-radius: 50%;
      background: linear-gradient(135deg, #f59e0b, #b45309);
      display: flex; align-items: center; justify-content: center;
      font-weight: 700; font-size: 16px; color: #000; margin-bottom: 6px;
    }
    #aria-empty h3 { font-size: 15px; font-weight: 600; color: #e5e7eb; }
    #aria-empty p { font-size: 12px; color: #6b7280; }

    @media (max-width: 440px) {
      #aria-panel { right: 12px; left: 12px; width: auto; bottom: 88px; }
      #aria-fab { right: 16px; bottom: 20px; }
    }
  `;

  // -------------------------------------------------------------------------
  // DOM
  // -------------------------------------------------------------------------
  function inject() {
    const style = document.createElement('style');
    style.textContent = CSS;
    document.head.appendChild(style);

    // FAB
    const fab = document.createElement('button');
    fab.id = 'aria-fab';
    fab.setAttribute('aria-label', 'Chat with ARIA');
    fab.innerHTML = `
      <span class="aria-a-icon">A</span>
      <span class="aria-close-icon">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </span>`;
    document.body.appendChild(fab);

    // Panel
    const panel = document.createElement('div');
    panel.id = 'aria-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', 'ARIA chat');
    panel.innerHTML = `
      <div id="aria-header">
        <div class="aria-av">A</div>
        <div>
          <div class="aria-title">ARIA</div>
          <div class="aria-sub">Ask about Varshith</div>
        </div>
        <div class="aria-dot"></div>
      </div>
      <div id="aria-empty">
        <div class="aria-em-av">A</div>
        <h3>Hi, I'm ARIA</h3>
        <p>Ask me anything about Varshith — projects, skills, or background.</p>
      </div>
      <div id="aria-messages" style="display:none"></div>
      <div id="aria-chips"></div>
      <div id="aria-input-row">
        <textarea id="aria-input" placeholder="Ask about Varshith..." rows="1"></textarea>
        <button id="aria-mic" title="Voice input">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            <line x1="12" y1="19" x2="12" y2="23"/>
            <line x1="8" y1="23" x2="16" y2="23"/>
          </svg>
        </button>
        <button id="aria-send" title="Send">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>`;
    document.body.appendChild(panel);

    return { fab, panel };
  }

  // -------------------------------------------------------------------------
  // Logic
  // -------------------------------------------------------------------------
  function init() {
    const { fab, panel } = inject();
    const messagesEl = panel.querySelector('#aria-messages');
    const inputEl = panel.querySelector('#aria-input');
    const sendBtn = panel.querySelector('#aria-send');
    const chipsEl = panel.querySelector('#aria-chips');
    const emptyEl = panel.querySelector('#aria-empty');

    let history = [];
    let isStreaming = false;
    let isOpen = false;

    // Toggle panel
    fab.addEventListener('click', () => {
      isOpen = !isOpen;
      fab.classList.toggle('open', isOpen);
      panel.classList.toggle('visible', isOpen);
      if (isOpen) {
        // Re-animate
        panel.style.animation = 'none';
        panel.offsetHeight; // reflow
        panel.style.animation = '';
        inputEl.focus();
      }
    });

    // Close on Escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && isOpen) fab.click();
    });

    // Auto-resize textarea
    inputEl.addEventListener('input', () => {
      inputEl.style.height = 'auto';
      inputEl.style.height = Math.min(inputEl.scrollHeight, 90) + 'px';
    });

    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
    sendBtn.addEventListener('click', sendMessage);

    // Helpers
    function showMessages() {
      emptyEl.style.display = 'none';
      messagesEl.style.display = 'flex';
    }

    function scrollToBottom() {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function escapeHtml(str) {
      return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }

    function appendUser(text) {
      showMessages();
      const div = document.createElement('div');
      div.className = 'aria-msg user';
      div.innerHTML = `<div class="aria-bubble">${escapeHtml(text)}</div>`;
      messagesEl.appendChild(div);
      scrollToBottom();
    }

    function appendBot() {
      const div = document.createElement('div');
      div.className = 'aria-msg bot';
      div.innerHTML = `
        <div class="aria-bubble">
          <div class="aria-typing"><span></span><span></span><span></span></div>
          <div class="aria-content" style="display:none"></div>
        </div>`;
      messagesEl.appendChild(div);
      scrollToBottom();
      return div;
    }

    // Suggested chips
    async function loadChips() {
      try {
        const res = await fetch(`${API_BASE}/api/suggested`);
        const data = await res.json();
        chipsEl.innerHTML = '';
        data.questions.forEach(q => {
          const btn = document.createElement('button');
          btn.className = 'aria-chip';
          btn.textContent = q;
          btn.addEventListener('click', () => {
            inputEl.value = q;
            sendMessage();
          });
          chipsEl.appendChild(btn);
        });
      } catch {}
    }

    function getSessionId() {
      let sid = sessionStorage.getItem('aria_sid');
      if (!sid) { sid = Math.random().toString(36).slice(2); sessionStorage.setItem('aria_sid', sid); }
      return sid;
    }

    // Ensure marked is available
    function ensureMarked(cb) {
      if (window.marked) return cb();
      const s = document.createElement('script');
      s.src = MARKED_CDN;
      s.onload = cb;
      document.head.appendChild(s);
    }

    async function sendMessage() {
      const query = inputEl.value.trim();
      if (!query || isStreaming) return;

      isStreaming = true;
      sendBtn.disabled = true;
      inputEl.value = '';
      inputEl.style.height = 'auto';
      chipsEl.innerHTML = '';

      appendUser(query);
      const botEl = appendBot();
      const typingEl = botEl.querySelector('.aria-typing');
      const contentEl = botEl.querySelector('.aria-content');

      let accumulated = '';

      try {
        const res = await fetch(`${API_BASE}/api/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query, history, session_id: getSessionId() }),
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const raw = line.slice(6).trim();
            if (raw === '[DONE]') break;
            try {
              const parsed = JSON.parse(raw);
              if (parsed.token) {
                if (!accumulated) {
                  typingEl.style.display = 'none';
                  contentEl.style.display = 'block';
                }
                accumulated += parsed.token;
                ensureMarked(() => {
                  contentEl.innerHTML = window.marked.parse(accumulated);
                });
                scrollToBottom();
              }
              if (parsed.error) {
                typingEl.style.display = 'none';
                contentEl.style.display = 'block';
                contentEl.innerHTML = `<em style="color:#ef4444">${escapeHtml(parsed.error)}</em>`;
              }
            } catch {}
          }
        }
      } catch {
        typingEl.style.display = 'none';
        contentEl.style.display = 'block';
        contentEl.innerHTML = `<em style="color:#ef4444">Something went wrong. Please try again.</em>`;
      }

      if (accumulated) {
        history.push({ role: 'user', content: query });
        history.push({ role: 'assistant', content: accumulated });
        if (history.length > 20) history = history.slice(-20);
      }

      isStreaming = false;
      sendBtn.disabled = false;
    }

    // Voice-to-text (Web Speech API — Chrome/Edge/Safari only)
    const micBtn = panel.querySelector('#aria-mic');
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRec) {
      micBtn.classList.add('visible');
      const rec = new SpeechRec();
      rec.lang = 'en-US';
      rec.interimResults = false;
      rec.maxAlternatives = 1;
      let listening = false;

      micBtn.addEventListener('click', () => {
        if (listening) { rec.stop(); return; }
        rec.start();
      });

      rec.onstart = () => {
        listening = true;
        micBtn.classList.add('recording');
        inputEl.placeholder = 'Listening…';
      };

      rec.onresult = (e) => {
        const t = e.results[0][0].transcript;
        inputEl.value = t;
        inputEl.style.height = 'auto';
        inputEl.style.height = Math.min(inputEl.scrollHeight, 90) + 'px';
        setTimeout(() => { if (inputEl.value === t) sendMessage(); }, 600);
      };

      rec.onend = () => {
        listening = false;
        micBtn.classList.remove('recording');
        inputEl.placeholder = 'Ask about Varshith…';
      };

      rec.onerror = () => {
        listening = false;
        micBtn.classList.remove('recording');
      };
    }

    // Init
    loadChips();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
