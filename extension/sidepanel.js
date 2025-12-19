/**
 * RAGex Companion - Side Panel Controller
 * ========================================
 * Handles all side panel interactions, API communication, and UI updates.
 */

// ==================== Configuration ====================
const CONFIG = {
    API_BASE: 'http://127.0.0.1:8000/api/v1',
    MAX_PAGES: 3,
    REQUEST_TIMEOUT: 30000, // 30 seconds
    RETRY_ATTEMPTS: 2,
    ANIMATION_DURATION: 300
};

// ==================== State Management ====================
const STATE = {
    sessionHistory: [],
    currentUrl: '',
    isConnected: false,
    isProcessing: false,
    currentTab: null
};

// Typing animation state
let isTyping = false;

// ==================== DOM Elements Cache ====================
// Cache DOM elements for better performance
const DOM = {
    overlay: null,
    overlayText: null,
    overlaySubtext: null,
    statusBadge: null,
    urlDisplay: null,
    scanBtn: null,
    analysisCard: null,
    acType: null,
    acSummary: null,
    acTags: null,
    chatArea: null,
    userInput: null,
    sendBtn: null
};

/**
 * Convert summaries into bullet points for clearer scanning.
 * If a list already exists, return the original text.
 */
function formatSummaryAsBullets(text) {
    if (!text) return '';
    if (text.includes('<ul') || text.includes('<li')) return text;
    const cleaned = text.replace(/<<<FOLLOWUP>>>/g, '').replace(/\r?\n/g, ' ');
    const parts = cleaned
        .split(/[.!?]/)
        .map(p => p.trim())
        .filter(p => p.length > 0);
    if (parts.length === 0) return cleaned;
    const items = parts
        .map(p => `<li>${p.charAt(0).toUpperCase()}${p.slice(1)}</li>`)
        .join('');
    return `<ul style="padding-left:18px; margin: 0; line-height:1.5;">${items}</ul>`;
}

/**
 * Poll the backend until analysis for the given URL is ready.
 * Ensures we don't show "analysis complete" while indexing is still running.
 */
async function waitForAnalysisReady(url, maxWaitMs = 30000, intervalMs = 2000) {
    const start = Date.now();

    // Keep trying until backend reports non-empty analysis or we time out
    while (Date.now() - start < maxWaitMs) {
        const result = await apiRequest('/analyze', {
            body: JSON.stringify({ url })
        });

        if (result.success && result.data && result.data.type !== 'Empty') {
            return result.data;
        }

        // Still indexing / no content yet – wait a bit then retry
        await new Promise(resolve => setTimeout(resolve, intervalMs));
    }

    throw new Error('Indexing is taking longer than expected. Please try again in a moment.');
}

// ==================== Initialization ====================
/**
 * Initialize the extension when side panel loads
 */
async function initialize() {
    console.log('[RAGex] Initializing side panel...');
    
    // Cache DOM elements
    cacheDOMElements();
    
    // Setup event listeners
    setupEventListeners();
    
    // Get current tab information
    await getCurrentTab();
    
    // Check backend connection
    await checkBackendHealth();
    
    // Load session history from storage
    await loadSessionHistory();
    
    console.log('[RAGex] Initialization complete');
}

/**
 * Cache all DOM elements for better performance
 */
function cacheDOMElements() {
    DOM.overlay = document.getElementById('overlay');
    DOM.overlayText = document.getElementById('overlayText');
    DOM.overlaySubtext = document.getElementById('overlaySubtext');
    DOM.statusBadge = document.getElementById('statusBadge');
    DOM.urlDisplay = document.getElementById('urlDisplay');
    DOM.scanBtn = document.getElementById('scanBtn');
    DOM.analysisCard = document.getElementById('analysisCard');
    DOM.acType = document.getElementById('acType');
    DOM.acSummary = document.getElementById('acSummary');
    DOM.acTags = document.getElementById('acTags');
    DOM.chatArea = document.getElementById('chatArea');
    DOM.userInput = document.getElementById('userInput');
    DOM.sendBtn = document.getElementById('sendBtn');
}

/**
 * Setup all event listeners
 */
function setupEventListeners() {
    // Scan button click
    DOM.scanBtn.addEventListener('click', handleScanClick);
    
    // Send button click
    DOM.sendBtn.addEventListener('click', handleSendClick);
    
    // Input field enter key
    DOM.userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendClick();
        }
    });
    
    // Input field focus/blur for better UX
    DOM.userInput.addEventListener('focus', () => {
        DOM.userInput.parentElement.style.transform = 'scale(1.01)';
    });
    
    DOM.userInput.addEventListener('blur', () => {
        DOM.userInput.parentElement.style.transform = 'scale(1)';
    });
    
    // Scroll listener for sticky analysis card effect
    DOM.chatArea.addEventListener('scroll', handleScroll);
    
    // Tab change listener (when user switches tabs and comes back)
    document.addEventListener('visibilitychange', handleVisibilityChange);
    
    console.log('[RAGex] Event listeners attached');
}

// ==================== Tab Management ====================
/**
 * Get current active tab information
 */
async function getCurrentTab() {
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        
        if (tab && tab.url) {
            STATE.currentTab = tab;
            
            // Check if URL is accessible
            if (tab.url.startsWith('http://') || tab.url.startsWith('https://')) {
                const newUrl = tab.url;
                
                // Check if URL changed (for re-scan)
                if (STATE.currentUrl && STATE.currentUrl !== newUrl && STATE.isConnected) {
                    console.log('[RAGex] URL changed, need to re-scan');
                    DOM.scanBtn.textContent = 'Connect';
                    DOM.scanBtn.classList.add('glow-button');
                    STATE.isConnected = false;
                    updateStatus('ready', 'Ready');
                    
                    // Clear analysis card
                    DOM.analysisCard.classList.remove('visible');
                }
                
                STATE.currentUrl = newUrl;
                const hostname = new URL(newUrl).hostname;
                DOM.urlDisplay.textContent = hostname;
                DOM.urlDisplay.classList.add('active');
                DOM.scanBtn.disabled = false;
                
                console.log('[RAGex] Current tab:', hostname);
            } else {
                // Restricted page (chrome://, about:, etc.)
                DOM.urlDisplay.textContent = 'Restricted Page';
                DOM.scanBtn.disabled = true;
                DOM.scanBtn.title = 'Cannot analyze this type of page';
                
                console.warn('[RAGex] Restricted page detected');
            }
        } else {
            DOM.urlDisplay.textContent = 'No Active Tab';
            DOM.scanBtn.disabled = true;
            
            console.warn('[RAGex] No active tab found');
        }
        
    } catch (error) {
        console.error('[RAGex] Error getting current tab:', error);
        showError('Failed to access current tab');
    }
}

/**
 * Handle visibility change (when user switches back to tab)
 */
async function handleVisibilityChange() {
    if (!document.hidden) {
        console.log('[RAGex] Tab became visible, checking for URL changes');
        await getCurrentTab();
    }
}

/**
 * Handle scroll event for sticky analysis card
 */
function handleScroll() {
    const scrollTop = DOM.chatArea.scrollTop;
    
    // Add shadow to analysis card when scrolled
    if (scrollTop > 10 && DOM.analysisCard.classList.contains('visible')) {
        DOM.analysisCard.classList.add('scrolled');
    } else {
        DOM.analysisCard.classList.remove('scrolled');
    }
}

// ==================== Backend Communication ====================
/**
 * Check if backend is reachable
 */
async function checkBackendHealth() {
    try {
        const response = await fetchWithTimeout(`${CONFIG.API_BASE.replace('/api/v1', '')}/`, {
            method: 'GET'
        }, 5000);
        
        if (response.ok) {
            updateStatus('ready', 'Ready');
            console.log('[RAGex] Backend is healthy');
            return true;
        } else {
            updateStatus('error', 'Backend Error');
            console.error('[RAGex] Backend returned error:', response.status);
            return false;
        }
        
    } catch (error) {
        updateStatus('error', 'Backend Offline');
        console.error('[RAGex] Backend health check failed:', error);
        
        // Don't show error message immediately - only when user tries to interact
        console.warn('[RAGex] Backend is offline. Will show error when user tries to use the extension.');
        
        return false;
    }
}

/**
 * Fetch with timeout wrapper
 */
async function fetchWithTimeout(url, options = {}, timeout = CONFIG.REQUEST_TIMEOUT) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    
    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal
        });
        clearTimeout(timeoutId);
        return response;
    } catch (error) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
            throw new Error('Request timeout');
        }
        throw error;
    }
}

/**
 * Make API request with retry logic
 */
async function apiRequest(endpoint, options = {}, retries = CONFIG.RETRY_ATTEMPTS) {
    const url = `${CONFIG.API_BASE}${endpoint}`;
    
    for (let attempt = 0; attempt <= retries; attempt++) {
        try {
            console.log(`[RAGex] API Request (attempt ${attempt + 1}/${retries + 1}): ${endpoint}`);
            
            const response = await fetchWithTimeout(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log('[RAGex] API Response received');
            return { success: true, data };
            
        } catch (error) {
            console.error(`[RAGex] API Request failed (attempt ${attempt + 1}):`, error);
            
            // If last attempt, return error
            if (attempt === retries) {
                return { 
                    success: false, 
                    error: error.message || 'Request failed' 
                };
            }
            
            // Wait before retry (exponential backoff)
            await new Promise(resolve => setTimeout(resolve, 1000 * (attempt + 1)));
        }
    }
}

// ==================== Main Features ====================
/**
 * Handle scan/connect button click
 */
async function handleScanClick() {
    if (STATE.isProcessing || !STATE.currentUrl) return;
    
    console.log('[RAGex] Starting scan automation');
    STATE.isProcessing = true;
    
    // Re-fetch current URL from active tab
    await getCurrentTab();
    
    // Clear chat area if this is a re-scan
    if (STATE.isConnected) {
        DOM.chatArea.innerHTML = '';
    }
    
    // Reset session history on each scan to prevent context bleed between pages
    STATE.sessionHistory = [];
    await saveSessionHistory();
    
    // Update UI
    setOverlay(true, 'Connecting to page...', 'Reading content');
    DOM.scanBtn.disabled = true;
    DOM.scanBtn.classList.remove('glow-button');
    updateStatus('processing', 'Indexing...');
    
    try {
        // STEP 1: Index the URL
        console.log('[RAGex] Step 1: Indexing URL');
        setOverlay(true, 'Indexing Content...', `Crawling up to ${CONFIG.MAX_PAGES} pages`);
        
        const indexResult = await apiRequest('/index', {
            body: JSON.stringify({
                url: STATE.currentUrl,
                max_pages: CONFIG.MAX_PAGES
            })
        });
        
        if (!indexResult.success) {
            throw new Error(indexResult.error || 'Indexing failed');
        }
        
        console.log('[RAGex] Indexing request accepted');
        
        // STEP 2: Poll backend until indexing for this URL is actually ready
        console.log('[RAGex] Step 2: Waiting for backend to finish indexing');
        setOverlay(true, 'Processing...', 'Building knowledge graph');

        const analysis = await waitForAnalysisReady(STATE.currentUrl);
        
        // Graceful fade out
        setOverlay(true, 'Complete!', 'Ready to chat');
        await new Promise(resolve => setTimeout(resolve, 800));
        
        // Fade out overlay gradually
        DOM.overlay.classList.add('fade-out');
        await new Promise(resolve => setTimeout(resolve, 600));
        DOM.overlay.classList.remove('active', 'fade-out');
        
        // Render analysis card
        renderAnalysisCard(analysis);
        
        // STEP 5: Update state and UI
        STATE.isConnected = true;
        updateStatus('connected', 'Connected');
        
        // Enable chat
        DOM.userInput.disabled = false;
        DOM.sendBtn.disabled = false;
        DOM.scanBtn.textContent = 'Re-Scan';
        DOM.scanBtn.disabled = false;
        
        // Add success message with suggestions
        addMessage(
            `<i class="fas fa-check-circle" style="color: var(--green); margin-right: 8px;"></i> <strong>Analysis complete!</strong><br>I've indexed <strong>${new URL(STATE.currentUrl).hostname}</strong>. You can now ask me anything about it.`,
            'bot',
            { 
                suggestions: [
                    'Summarize this page',
                    'What are the main topics?',
                    'What is this page about?'
                ]
            }
        );
        
        // Save to storage
        await saveSessionHistory();
        
        console.log('[RAGex] Scan automation complete');
        
    } catch (error) {
        console.error('[RAGex] Scan automation failed:', error);
        
        // Fade out overlay on error too
        DOM.overlay.classList.add('fade-out');
        await new Promise(resolve => setTimeout(resolve, 600));
        DOM.overlay.classList.remove('active', 'fade-out');
        
        updateStatus('error', 'Connection Failed');
        
        addMessage(
            `<i class="fas fa-exclamation-circle" style="color: var(--red); margin-right: 8px;"></i> <strong>Error:</strong> ${error.message}<br>Please check if the RAG backend is running at <code>localhost:8000</code>`,
            'bot',
            { isError: true }
        );
        
        DOM.scanBtn.disabled = false;
        
    } finally {
        STATE.isProcessing = false;
    }
}

/**
 * Handle send button click or enter key
 */
async function handleSendClick() {
    const question = DOM.userInput.value.trim();
    
    if (!question || STATE.isProcessing || !STATE.isConnected) return;
    
    console.log('[RAGex] User query:', question);
    STATE.isProcessing = true;
    
    // Add user message
    addMessage(question, 'user');
    
    // Clear input
    DOM.userInput.value = '';
    DOM.userInput.disabled = true;
    DOM.sendBtn.disabled = true;
    
    // Add loading indicator
    const loaderId = addLoadingMessage();
    
    try {
        const startTime = Date.now();
        
        // Make API request, including the current URL so summaries stay page-specific
        const result = await apiRequest('/query', {
            body: JSON.stringify({
                question: question,
                history: STATE.sessionHistory,
                url: STATE.currentUrl
            })
        });
        
        const latency = ((Date.now() - startTime) / 1000).toFixed(2);
        
        // Remove loader
        removeMessage(loaderId);
        
        if (!result.success) {
            throw new Error(result.error || 'Query failed');
        }
        
        const data = result.data;
        
        // Update session history
        STATE.sessionHistory.push({ role: 'user', content: question });
        STATE.sessionHistory.push({ role: 'assistant', content: data.answer });
        
        // Add bot response
        addMessage(
            data.answer,
            'bot',
            {
                sources: data.sources,
                confidence: data.confidence || data.confidence_score,
                latency: latency,
                refusal: data.refusal,
                isSummary: /summary|summarize/i.test(question)
            }
        );
        
        // Save to storage
        await saveSessionHistory();
        
        console.log('[RAGex] Query completed successfully');
        
    } catch (error) {
        console.error('[RAGex] Query failed:', error);
        
        removeMessage(loaderId);
        
        addMessage(
            `<i class="fas fa-exclamation-circle" style="color: var(--red); margin-right: 8px;"></i> <strong>Error:</strong> ${error.message}`,
            'bot',
            { isError: true }
        );
        
    } finally {
        STATE.isProcessing = false;
        DOM.userInput.disabled = false;
        DOM.sendBtn.disabled = false;
        DOM.userInput.focus();
    }
}

// ==================== UI Helpers ====================
/**
 * Update status badge
 */
function updateStatus(type, text) {
    DOM.statusBadge.className = 'status-badge';
    
    switch (type) {
        case 'connected':
            DOM.statusBadge.classList.add('active');
            break;
        case 'error':
            DOM.statusBadge.classList.add('error');
            break;
        // 'ready' and 'processing' use default style
    }
    
    DOM.statusBadge.textContent = text;
}

/**
 * Show/hide overlay with gradual blue fade
 */
function setOverlay(show, text = 'Processing...', subtext = '') {
    if (show) {
        DOM.overlayText.textContent = text;
        DOM.overlaySubtext.textContent = subtext;
        DOM.overlay.classList.remove('fade-out');
        DOM.overlay.classList.add('active');
    } else {
        // Gradual fade out
        DOM.overlay.classList.add('fade-out');
        setTimeout(() => {
            DOM.overlay.classList.remove('active', 'fade-out');
        }, 600);
    }
}

/**
 * Parse analysis response from LLM
 */
function parseAnalysisResponse(response) {
    try {
        // Remove markdown code blocks if present
        let jsonStr = response.replace(/```json/g, '').replace(/```/g, '').trim();
        
        // Parse JSON
        const analysis = JSON.parse(jsonStr);
        
        return {
            type: analysis.type || 'Web Content',
            summary: analysis.summary || 'No summary available',
            topics: Array.isArray(analysis.topics) ? analysis.topics : []
        };
        
    } catch (error) {
        console.warn('[RAGex] Failed to parse analysis JSON:', error);
        
        // Fallback: use raw text
        return {
            type: 'Web Content',
            summary: response.substring(0, 200),
            topics: []
        };
    }
}

/**
 * Render analysis card
 */
function renderAnalysisCard(analysis) {
    DOM.acType.textContent = analysis.type;
    DOM.acSummary.innerHTML = formatSummaryAsBullets(analysis.summary);
    
    // Clear and populate tags
    DOM.acTags.innerHTML = '';
    analysis.topics.forEach(topic => {
        const tag = document.createElement('span');
        tag.className = 'ac-tag';
        tag.textContent = `#${topic}`;
        DOM.acTags.appendChild(tag);
    });
    
    // Show card with animation
    DOM.analysisCard.classList.add('visible');
}

/**
 * Add message to chat
 */
function addMessage(text, role, meta = null) {
    const row = document.createElement('div');
    row.className = `msg-row ${role}`;
    
    // Create bubble container
    const bubble = document.createElement('div');
    bubble.className = `msg ${role} ${meta?.refusal ? 'refusal' : ''}`;
    
    row.appendChild(bubble);
    DOM.chatArea.appendChild(row);

    // Render Logic
    if (role === 'user') {
        // Instant render for user messages - use marked if available
        try {
            if (typeof marked !== 'undefined' && marked.parse) {
                bubble.innerHTML = marked.parse(text);
            } else {
                bubble.textContent = text;
            }
        } catch (e) {
            console.warn('[RAGex] Marked parse error, using plain text:', e);
            bubble.textContent = text;
        }
        scrollToBottom();
    } else {
        // BOT: Typing Effect with Marked.js
        let formattedText = text;
        if (meta?.isSummary) {
            formattedText = formatSummaryAsBullets(formattedText);
        }
        
        // Only use marked for non-HTML content
        try {
            if (typeof marked !== 'undefined' && marked.parse && !text.includes('<') && !meta?.isError) {
                formattedText = marked.parse(text);
            }
        } catch (e) {
            console.warn('[RAGex] Marked parse error for bot message:', e);
        }
        
        // Prepare meta HTML for later
        let metaHtml = '';
        if (meta && !meta.isError) {
            let sourceLinks = 'Internal';
            if (meta.sources?.length > 0) {
                sourceLinks = meta.sources.map(s => {
                    try {
                        return `<a href="${s}" target="_blank" class="source-link">${new URL(s).pathname}</a>`;
                    } catch {
                        return `<span class="source-link">${s}</span>`;
                    }
                }).join(', ');
            }
            
            let metaContent = '';
            if (meta.latency) {
                metaContent += `<span class="meta-tag"><i class="fas fa-clock"></i> ${meta.latency}s</span>`;
            }
            if (meta.confidence !== undefined) {
                const confScore = typeof meta.confidence === 'number' ? 
                    Math.round(meta.confidence * 100) : 
                    (meta.confidence === 'high' ? 90 : meta.confidence === 'medium' ? 70 : 50);
                metaContent += `<span class="meta-tag"><i class="fas fa-bolt"></i> ${confScore}%</span>`;
            }
            if (sourceLinks !== 'Internal') {
                metaContent += `<span class="meta-tag"><i class="fas fa-link"></i> ${sourceLinks}</span>`;
            }
            
            if (metaContent) {
                metaHtml = `<div class="msg-meta" style="opacity:0; transition: opacity 0.8s ease;">${metaContent}</div>`;
            }
        }

        // For error messages, skip typing animation and render immediately
        if (meta?.isError) {
            bubble.innerHTML = formattedText;
            if (metaHtml) {
                bubble.innerHTML += metaHtml;
                setTimeout(() => {
                    const footer = bubble.querySelector('.msg-meta');
                    if (footer) footer.style.opacity = '1';
                }, 100);
            }
            scrollToBottom();
            return;
        }

        // Start typing animation for regular bot messages
        isTyping = true;
        bubble.innerHTML = '<span class="cursor" style="display:inline-block; width:2px; height:1em; background:var(--accent); margin-left:4px; animation:blink 0.7s infinite;"></span>';
        
        // Split text into words for typing effect
        const words = formattedText.split(" ");
        let currentHTML = "";
        let i = 0;
        
        const typeInterval = setInterval(() => {
            if (i < words.length) {
                currentHTML += (i > 0 ? " " : "") + words[i];
                bubble.innerHTML = currentHTML + '<span class="cursor" style="display:inline-block; width:2px; height:1em; background:var(--accent); margin-left:4px; animation:blink 0.7s infinite;"></span>';
                scrollToBottom();
                i++;
            } else {
                // Typing complete
                clearInterval(typeInterval);
                isTyping = false;
                
                // Remove cursor and add final content
                bubble.innerHTML = currentHTML;
                
                // Append meta information with fade in
                if (metaHtml) {
                    bubble.innerHTML += metaHtml;
                    setTimeout(() => {
                        const footer = bubble.querySelector('.msg-meta');
                        if (footer) footer.style.opacity = '1';
                    }, 100);
                }
                
                // Add suggestions below message with fade in
                if (meta?.suggestions?.length > 0) {
                    // Create a separate row for suggestions
                    const suggestionsRow = document.createElement('div');
                    suggestionsRow.className = 'msg-row bot';
                    suggestionsRow.style.opacity = '0';
                    suggestionsRow.style.transition = 'opacity 0.6s ease';
                    
                    const suggestionsContainer = document.createElement('div');
                    suggestionsContainer.className = 'suggestions';
                    
                    meta.suggestions.forEach(s => {
                        const chip = document.createElement('button');
                        chip.className = 'suggestion-chip';
                        chip.textContent = s;
                        chip.addEventListener('click', () => {
                            DOM.userInput.value = s;
                            DOM.userInput.focus();
                            handleSendClick();
                        });
                        suggestionsContainer.appendChild(chip);
                    });
                    
                    suggestionsRow.appendChild(suggestionsContainer);
                    DOM.chatArea.appendChild(suggestionsRow);
                    
                    // Fade in suggestions
                    setTimeout(() => {
                        suggestionsRow.style.opacity = '1';
                        scrollToBottom();
                    }, 150);
                }
                
                scrollToBottom();
            }
        }, 35); // Speed: 35ms per word
    }
}

/**
 * Add loading message
 */
function addLoadingMessage() {
    const id = `loader-${Date.now()}`;
    const row = document.createElement('div');
    row.id = id;
    row.className = 'msg-row bot';
    row.innerHTML = `
        <div class="msg bot" style="display: flex; align-items: center; gap: 12px; background: transparent; border: none; padding: 0;">
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
            <span style="font-size: 0.85rem; color: var(--text-sub); font-style: italic;">Processing your question...</span>
        </div>`;
    
    DOM.chatArea.appendChild(row);
    scrollToBottom();
    
    return id;
}

/**
 * Remove message by ID
 */
function removeMessage(id) {
    const element = document.getElementById(id);
    if (element) {
        element.remove();
    }
}

/**
 * Scroll chat to bottom
 */
function scrollToBottom() {
    DOM.chatArea.scrollTo({
        top: DOM.chatArea.scrollHeight,
        behavior: 'smooth'
    });
}

/**
 * Show error message
 */
function showError(message) {
    addMessage(`<i class="fas fa-exclamation-circle" style="color: var(--red); margin-right: 8px;"></i> <strong>Error:</strong> ${message}`, 'bot', { isError: true });
}

// ==================== Storage Management ====================
/**
 * Load session history from Chrome storage
 */
async function loadSessionHistory() {
    try {
        const result = await chrome.storage.local.get([
            'ragex_extension_sessionHistory',
            'sessionHistory' // legacy key fallback
        ]);
        const stored = result.ragex_extension_sessionHistory ?? result.sessionHistory;
        if (stored) {
            STATE.sessionHistory = stored;
            console.log('[RAGex] Loaded session history:', STATE.sessionHistory.length, 'messages');
        }
    } catch (error) {
        console.error('[RAGex] Failed to load session history:', error);
    }
}

/**
 * Save session history to Chrome storage
 */
async function saveSessionHistory() {
    try {
        await chrome.storage.local.set({
            ragex_extension_sessionHistory: STATE.sessionHistory,
            ragex_extension_lastActivity: Date.now()
        });
        console.log('[RAGex] Saved session history');
    } catch (error) {
        console.error('[RAGex] Failed to save session history:', error);
    }
}

// ==================== Entry Point ====================
// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
} else {
    initialize();
}