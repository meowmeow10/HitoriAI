// Hitori AI Chat Application
class HitoriChat {
    constructor() {
        this.messagesContainer = document.getElementById('messages');
        this.messageInput = document.getElementById('message-input');
        this.sendBtn = document.getElementById('send-btn');
        this.voiceBtn = document.getElementById('voice-btn');
        this.statsBtn = document.getElementById('stats-btn');
        this.trainBtn = document.getElementById('train-btn');
        this.clearBtn = document.getElementById('clear-btn');
        this.loadingOverlay = document.getElementById('loading-overlay');
        this.voiceStatus = document.getElementById('voice-status');
        this.voiceStatusText = document.getElementById('voice-status-text');
        
        this.isListening = false;
        this.isSpeaking = false;
        this.recognition = null;
        this.synthesis = window.speechSynthesis;
        
        this.initializeEventListeners();
        this.initializeSpeechRecognition();
        this.checkBrowserSupport();
    }
    
    initializeEventListeners() {
        // Send message on button click
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        
        // Send message on Enter key press
        this.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Voice input button
        this.voiceBtn.addEventListener('click', () => this.toggleVoiceInput());
        
        // Stats button
        this.statsBtn.addEventListener('click', () => this.showStats());
        
        // Train button
        this.trainBtn.addEventListener('click', () => this.trainFromWeb());
        
        // Clear chat button
        this.clearBtn.addEventListener('click', () => this.clearChat());
        
        // Stop speech when clicking anywhere while speaking
        document.addEventListener('click', (e) => {
            if (this.isSpeaking && !e.target.closest('.message')) {
                this.stopSpeech();
            }
        });
    }
    
    initializeSpeechRecognition() {
        if ('webkitSpeechRecognition' in window) {
            this.recognition = new webkitSpeechRecognition();
        } else if ('SpeechRecognition' in window) {
            this.recognition = new SpeechRecognition();
        }
        
        if (this.recognition) {
            this.recognition.continuous = false;
            this.recognition.interimResults = false;
            this.recognition.lang = 'en-US';
            
            this.recognition.onstart = () => {
                this.isListening = true;
                this.voiceBtn.classList.add('voice-listening');
                this.voiceStatus.style.display = 'block';
                this.voiceStatusText.textContent = 'Listening...';
            };
            
            this.recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                this.messageInput.value = transcript;
                this.voiceStatusText.textContent = 'Got it! Click send or speak again.';
                setTimeout(() => {
                    this.voiceStatus.style.display = 'none';
                }, 2000);
            };
            
            this.recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                this.stopVoiceInput();
                this.showError(`Voice recognition error: ${event.error}`);
            };
            
            this.recognition.onend = () => {
                this.stopVoiceInput();
            };
        }
    }
    
    checkBrowserSupport() {
        if (!this.recognition) {
            this.voiceBtn.style.display = 'none';
            console.warn('Speech recognition not supported in this browser');
        }
        
        if (!this.synthesis) {
            console.warn('Speech synthesis not supported in this browser');
        }
    }
    
    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message) return;
        
        // Clear input and disable send button
        this.messageInput.value = '';
        this.sendBtn.disabled = true;
        
        // Add user message to chat
        this.addMessage(message, 'user');
        
        // Show loading
        this.showLoading(true);
        
        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Add AI response to chat
                this.addMessage(data.response, 'assistant');
                
                // Speak the response if synthesis is available
                this.speakMessage(data.response);
            } else {
                this.showError(data.error || 'An error occurred');
            }
        } catch (error) {
            console.error('Error sending message:', error);
            this.showError('Failed to send message. Please check your connection.');
        } finally {
            this.showLoading(false);
            this.sendBtn.disabled = false;
            this.messageInput.focus();
        }
    }
    
    addMessage(content, sender, isHtml = false) {
        // Remove welcome message if it exists
        const welcomeMessage = this.messagesContainer.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.remove();
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const senderName = sender === 'user' ? 'You' : 'Hitori';
        
        messageDiv.innerHTML = `
            <div class="message-bubble">
                ${isHtml ? content : this.formatMessage(content)}
            </div>
            <div class="message-info">
                ${senderName} • ${timestamp}
            </div>
        `;
        
        // Add speaking indicator for assistant messages (but not for stats)
        if (sender === 'assistant' && !isHtml) {
            const speakingIndicator = document.createElement('div');
            speakingIndicator.className = 'speaking-indicator';
            speakingIndicator.innerHTML = '<i class="fas fa-volume-up"></i> Speaking...';
            speakingIndicator.style.display = 'none';
            messageDiv.appendChild(speakingIndicator);
        }
        
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    formatMessage(content) {
        // Basic text formatting - convert newlines to <br> and handle basic markdown-like formatting
        return content
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>');
    }
    
    speakMessage(text) {
        if (!this.synthesis) return;
        
        // Stop any ongoing speech
        this.synthesis.cancel();
        
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 0.9;
        utterance.pitch = 1;
        utterance.volume = 0.8;
        
        // Find a suitable voice (prefer female voices for Hitori)
        const voices = this.synthesis.getVoices();
        const preferredVoice = voices.find(voice => 
            voice.lang.startsWith('en') && 
            (voice.name.includes('Female') || voice.name.includes('Samantha') || voice.name.includes('Karen'))
        ) || voices.find(voice => voice.lang.startsWith('en'));
        
        if (preferredVoice) {
            utterance.voice = preferredVoice;
        }
        
        utterance.onstart = () => {
            this.isSpeaking = true;
            const lastMessage = this.messagesContainer.lastElementChild;
            if (lastMessage && lastMessage.classList.contains('assistant')) {
                const indicator = lastMessage.querySelector('.speaking-indicator');
                if (indicator) {
                    indicator.style.display = 'block';
                }
            }
        };
        
        utterance.onend = () => {
            this.isSpeaking = false;
            const lastMessage = this.messagesContainer.lastElementChild;
            if (lastMessage && lastMessage.classList.contains('assistant')) {
                const indicator = lastMessage.querySelector('.speaking-indicator');
                if (indicator) {
                    indicator.style.display = 'none';
                }
            }
        };
        
        utterance.onerror = (event) => {
            console.error('Speech synthesis error:', event.error);
            this.isSpeaking = false;
        };
        
        this.synthesis.speak(utterance);
    }
    
    stopSpeech() {
        if (this.synthesis) {
            this.synthesis.cancel();
            this.isSpeaking = false;
        }
    }
    
    toggleVoiceInput() {
        if (!this.recognition) {
            this.showError('Voice recognition is not supported in your browser');
            return;
        }
        
        if (this.isListening) {
            this.recognition.stop();
        } else {
            this.recognition.start();
        }
    }
    
    stopVoiceInput() {
        this.isListening = false;
        this.voiceBtn.classList.remove('voice-listening');
        this.voiceStatus.style.display = 'none';
    }
    
    async clearChat() {
        if (confirm('Are you sure you want to clear the chat history?')) {
            try {
                const response = await fetch('/clear', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                });
                
                const data = await response.json();
                
                if (data.success) {
                    this.messagesContainer.innerHTML = `
                        <div class="welcome-message text-center text-muted py-5">
                            <i class="fas fa-robot fa-3x mb-3 text-info"></i>
                            <h5>Hello! I'm Hitori, your AI assistant.</h5>
                            <p>You can type a message or use the microphone button to talk to me.</p>
                            <p>If you want me to learn, press the Download button!
                        </div>
                    `;
                } else {
                    this.showError(data.error || 'Failed to clear chat');
                }
            } catch (error) {
                console.error('Error clearing chat:', error);
                this.showError('Failed to clear chat. Please try again.');
            }
        }
    }
    
    showLoading(show) {
        this.loadingOverlay.style.display = show ? 'flex' : 'none';
    }
    
    showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.innerHTML = `
            <i class="fas fa-exclamation-triangle me-2"></i>
            ${message}
        `;
        
        this.messagesContainer.appendChild(errorDiv);
        this.scrollToBottom();
        
        // Remove error after 5 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.remove();
            }
        }, 5000);
    }
    
    async showStats() {
        try {
            const response = await fetch('/stats');
            const stats = await response.json();
            
            const statsMessage = `
                <div class="stats-info">
                    <h6><i class="fas fa-brain me-2"></i>Hitori's Learning Progress</h6>
                    <ul class="list-unstyled mb-0">
                        <li><strong>Total Conversations:</strong> ${stats.total_interactions}</li>
                        <li><strong>Topics Learned:</strong> ${stats.topics_learned}</li>
                        <li><strong>Response Patterns:</strong> ${stats.patterns_learned}</li>
                        ${stats.database_knowledge !== undefined ? `<li><strong>Database Knowledge:</strong> ${stats.database_knowledge} items</li>` : ''}
                        ${stats.database_conversations !== undefined ? `<li><strong>Database Conversations:</strong> ${stats.database_conversations}</li>` : ''}
                        ${stats.web_scraping_enabled ? '<li><strong>Web Learning:</strong> ✓ Enabled</li>' : ''}
                        <li><strong>Last Updated:</strong> ${new Date(stats.last_updated).toLocaleString()}</li>
                    </ul>
                </div>
            `;
            
            this.addMessage(statsMessage, 'assistant', true);
        } catch (error) {
            console.error('Error fetching stats:', error);
            this.showError('Could not load AI statistics');
        }
    }
    
    async trainFromWeb() {
        try {
            // Show confirmation dialog
            const topics = prompt('Enter topics to learn about (comma-separated), or leave empty for general knowledge:', 
                'artificial intelligence, technology, science');
            
            if (topics === null) return; // User cancelled
            
            const topicsArray = topics ? topics.split(',').map(t => t.trim()).filter(t => t) : [];
            
            // Show loading
            this.showLoading(true);
            this.trainBtn.disabled = true;
            this.trainBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            
            const response = await fetch('/train', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    topics: topicsArray,
                    max_sources: 5
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                const trainingMessage = `
                    <div class="training-result">
                        <h6><i class="fas fa-download me-2 text-success"></i>Web Training Complete!</h6>
                        <ul class="list-unstyled mb-0">
                            <li><strong>Sources Scraped:</strong> ${result.sources_scraped}</li>
                            <li><strong>Knowledge Added:</strong> ${result.knowledge_items_added} items</li>
                            <li><strong>Topics Learned:</strong> ${result.topics_learned}</li>
                            ${result.errors && result.errors.length > 0 ? `<li class="text-warning"><strong>Errors:</strong> ${result.errors.length}</li>` : ''}
                        </ul>
                        <small class="text-muted">I'm now smarter and can answer more questions!</small>
                    </div>
                `;
                
                this.addMessage(trainingMessage, 'assistant', true);
            } else {
                this.showError(result.error || 'Training failed');
            }
        } catch (error) {
            console.error('Error training:', error);
            this.showError('Failed to start training. Please try again.');
        } finally {
            this.showLoading(false);
            this.trainBtn.disabled = false;
            this.trainBtn.innerHTML = '<i class="fas fa-download"></i>';
        }
    }
    
    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }
}

// Initialize the chat application when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new HitoriChat();
});

// Handle page visibility changes to manage speech synthesis
document.addEventListener('visibilitychange', () => {
    if (document.hidden && window.speechSynthesis) {
        window.speechSynthesis.cancel();
    }
});
