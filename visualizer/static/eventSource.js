/**
 * Event Source Abstraction Layer
 * Provides unified interface for different data sources:
 * - FileEventSource: Replay from JSONL file
 * - LiveFileEventSource: Live streaming from JSONL file
 * - WebSocketEventSource: Real-time WebSocket (legacy support)
 */

class EventSource {
    constructor() {
        this.listeners = [];
    }

    subscribe(callback) {
        this.listeners.push(callback);
    }

    notify(event) {
        for (const listener of this.listeners) {
            listener(event);
        }
    }

    async start() {
        throw new Error('start() must be implemented by subclass');
    }

    stop() {
        throw new Error('stop() must be implemented by subclass');
    }
}


/**
 * FileEventSource: Replay mode
 * Loads complete JSONL file and plays back with controls
 */
class FileEventSource extends EventSource {
    constructor(apiBaseUrl = 'http://localhost:5000') {
        super();
        this.apiBaseUrl = apiBaseUrl;
        this.events = [];
        this.metadata = null;
        this.currentIndex = 0;
        this.isPlaying = false;
        this.playbackSpeed = 1.0;
        this.timer = null;
        this.startTime = null;
        this.pausedTime = 0;
    }

    async loadFile(filename) {
        console.log(`[FileEventSource] Loading file: ${filename}`);
        
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/logs/${filename}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const allEvents = await response.json();
            
            // Separate metadata from events
            this.metadata = allEvents.find(e => e.type === 'metadata');
            this.events = allEvents.filter(e => e.type !== 'metadata');
            
            console.log(`[FileEventSource] Loaded ${this.events.length} events`);
            console.log(`[FileEventSource] Metadata:`, this.metadata);
            
            // Notify metadata
            if (this.metadata) {
                this.notify(this.metadata);
            }
            
            return {
                eventCount: this.events.length,
                metadata: this.metadata
            };
        } catch (error) {
            console.error('[FileEventSource] Error loading file:', error);
            throw error;
        }
    }

    async start() {
        console.log('[FileEventSource] Starting playback');
        this.isPlaying = true;
        this.startTime = Date.now() - this.pausedTime;
        this.playEvents();
    }

    stop() {
        console.log('[FileEventSource] Stopping playback');
        this.isPlaying = false;
        if (this.timer) {
            clearTimeout(this.timer);
            this.timer = null;
        }
    }

    pause() {
        console.log('[FileEventSource] Pausing playback');
        this.pausedTime = Date.now() - this.startTime;
        this.stop();
    }

    resume() {
        console.log('[FileEventSource] Resuming playback');
        this.start();
    }

    seekTo(time) {
        console.log(`[FileEventSource] Seeking to time: ${time}`);
        
        const wasPlaying = this.isPlaying;
        
        // Stop current playback
        this.stop();
        
        // STEP 1: Clear all state (notify subscribers to clear all state)
        this.notify({ type: 'clear_state' });
        
        // STEP 2: Replay all events from 0 to target time
        console.log(`[FileEventSource] Replaying events from 0 to ${time}s...`);
        let replayedCount = 0;
        
        for (let i = 0; i < this.events.length; i++) {
            if (this.events[i].time <= time) {
                this.notify(this.events[i]);
                this.currentIndex = i;
                replayedCount++;
            } else {
                break;
            }
        }
        
        console.log(`[FileEventSource] Replayed ${replayedCount} events`);
        
        // STEP 3: Set new playback position
        this.currentIndex++; // Move to next event after target time
        this.pausedTime = time * 1000;
        
        // STEP 4: Resume playback if it was playing
        if (wasPlaying) {
            this.start();
        }
    }

    setPlaybackSpeed(speed) {
        console.log(`[FileEventSource] Setting playback speed: ${speed}x`);
        this.playbackSpeed = speed;
        
        // Restart if currently playing
        if (this.isPlaying) {
            const wasPlaying = this.isPlaying;
            this.stop();
            if (wasPlaying) {
                this.start();
            }
        }
    }

    playEvents() {
        if (!this.isPlaying || this.currentIndex >= this.events.length) {
            if (this.currentIndex >= this.events.length) {
                console.log('[FileEventSource] Playback complete');
                this.notify({ type: 'playback_complete' });
            }
            return;
        }

        const event = this.events[this.currentIndex];
        const nextEvent = this.events[this.currentIndex + 1];

        // Notify this event
        this.notify(event);
        this.currentIndex++;

        // Schedule next event
        if (nextEvent) {
            const delay = ((nextEvent.time - event.time) * 1000) / this.playbackSpeed;
            this.timer = setTimeout(() => this.playEvents(), delay);
        } else {
            // Last event
            console.log('[FileEventSource] Playback complete');
            this.isPlaying = false;
            this.notify({ type: 'playback_complete' });
        }
    }

    getCurrentTime() {
        if (this.currentIndex === 0) return 0;
        if (this.currentIndex >= this.events.length) {
            return this.events[this.events.length - 1].time;
        }
        return this.events[this.currentIndex - 1].time;
    }

    getDuration() {
        if (this.events.length === 0) return 0;
        return this.events[this.events.length - 1].time;
    }
}


/**
 * LiveFileEventSource: Live mode
 * Polls JSONL file for new events (for simulation live viewing)
 */
class LiveFileEventSource extends EventSource {
    constructor(filename, apiBaseUrl = 'http://localhost:5000') {
        super();
        this.filename = filename;
        this.apiBaseUrl = apiBaseUrl;
        this.lastLine = 0;
        this.isRunning = false;
        this.pollInterval = 100; // 100ms polling
        this.timer = null;
    }

    async start() {
        console.log(`[LiveFileEventSource] Starting live streaming: ${this.filename}`);
        this.isRunning = true;
        this.lastLine = 0; // Start from beginning
        this.poll();
    }

    stop() {
        console.log('[LiveFileEventSource] Stopping live streaming');
        this.isRunning = false;
        if (this.timer) {
            clearTimeout(this.timer);
            this.timer = null;
        }
    }

    async poll() {
        if (!this.isRunning) return;

        try {
            const response = await fetch(
                `${this.apiBaseUrl}/api/logs/stream?file=${this.filename}&from=${this.lastLine}`
            );
            
            if (response.ok) {
                const data = await response.json();
                const newEvents = data.events;

                for (const event of newEvents) {
                    this.notify(event);
                    
                    // Update lastLine from event metadata
                    if (event._line_number !== undefined) {
                        this.lastLine = event._line_number + 1;
                    }
                }

                if (newEvents.length > 0) {
                    console.log(`[LiveFileEventSource] Received ${newEvents.length} new events`);
                }
            }
        } catch (error) {
            console.error('[LiveFileEventSource] Polling error:', error);
        }

        // Schedule next poll
        this.timer = setTimeout(() => this.poll(), this.pollInterval);
    }
}


/**
 * WebSocketEventSource: Legacy WebSocket support
 * For backward compatibility with existing WebSocket-based system
 */
class WebSocketEventSource extends EventSource {
    constructor(wsUrl = 'ws://localhost:8765') {
        super();
        this.wsUrl = wsUrl;
        this.ws = null;
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
        this.currentReconnectDelay = this.reconnectDelay;
    }

    async start() {
        console.log(`[WebSocketEventSource] Connecting to ${this.wsUrl}`);
        this.connect();
    }

    connect() {
        this.ws = new WebSocket(this.wsUrl);

        this.ws.onopen = () => {
            console.log('[WebSocketEventSource] Connected');
            this.currentReconnectDelay = this.reconnectDelay;
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.notify(data);
            } catch (error) {
                console.error('[WebSocketEventSource] Parse error:', error);
            }
        };

        this.ws.onerror = (error) => {
            console.error('[WebSocketEventSource] WebSocket error:', error);
        };

        this.ws.onclose = () => {
            console.log('[WebSocketEventSource] Connection closed');
            // Auto-reconnect
            setTimeout(() => {
                if (this.ws) {
                    console.log('[WebSocketEventSource] Reconnecting...');
                    this.connect();
                    this.currentReconnectDelay = Math.min(
                        this.currentReconnectDelay * 2,
                        this.maxReconnectDelay
                    );
                }
            }, this.currentReconnectDelay);
        };
    }

    stop() {
        console.log('[WebSocketEventSource] Stopping');
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}

