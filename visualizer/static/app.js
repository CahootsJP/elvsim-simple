/**
 * Elevator Simulator - Frontend Application
 * Handles WebSocket communication and real-time visualization
 */

class ElevatorVisualizer {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.autoScroll = true;
        this.elevators = new Map(); // Store elevator state
        this.simulationTime = 0;
        
        this.initializeUI();
        this.connectWebSocket();
    }
    
    initializeUI() {
        // Status elements
        this.statusIndicator = document.getElementById('status-indicator');
        this.statusText = document.getElementById('status-text');
        this.simTimeElement = document.getElementById('sim-time');
        
        // Control buttons
        this.btnStart = document.getElementById('btn-start');
        this.btnPause = document.getElementById('btn-pause');
        this.btnReset = document.getElementById('btn-reset');
        this.btnClearLog = document.getElementById('btn-clear-log');
        this.chkAutoScroll = document.getElementById('chk-auto-scroll');
        
        // Containers
        this.elevatorContainer = document.getElementById('elevator-container');
        this.logContainer = document.getElementById('log-container');
        
        // Event listeners
        this.btnClearLog.addEventListener('click', () => this.clearLog());
        this.chkAutoScroll.addEventListener('change', (e) => {
            this.autoScroll = e.target.checked;
        });
        
        // Future: Add start/pause/reset functionality
        this.btnStart.addEventListener('click', () => this.sendCommand('start'));
        this.btnPause.addEventListener('click', () => this.sendCommand('pause'));
        this.btnReset.addEventListener('click', () => this.sendCommand('reset'));
    }
    
    connectWebSocket() {
        const wsUrl = 'ws://localhost:8765';
        this.addLog('system', `Connecting to ${wsUrl}...`);
        
        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                this.onConnected();
            };
            
            this.ws.onmessage = (event) => {
                this.onMessage(event.data);
            };
            
            this.ws.onerror = (error) => {
                this.onError(error);
            };
            
            this.ws.onclose = () => {
                this.onDisconnected();
            };
            
        } catch (error) {
            this.addLog('error', `Connection failed: ${error.message}`);
            this.updateConnectionStatus(false);
        }
    }
    
    onConnected() {
        this.isConnected = true;
        this.updateConnectionStatus(true);
        this.addLog('system', 'Connected to simulation server');
        
        // Send initial handshake
        this.sendCommand('hello');
    }
    
    onDisconnected() {
        this.isConnected = false;
        this.updateConnectionStatus(false);
        this.addLog('system', 'Disconnected from server');
        
        // Attempt reconnection after 3 seconds
        setTimeout(() => {
            if (!this.isConnected) {
                this.addLog('system', 'Attempting to reconnect...');
                this.connectWebSocket();
            }
        }, 3000);
    }
    
    onError(error) {
        this.addLog('error', `WebSocket error: ${error.message || 'Unknown error'}`);
    }
    
    onMessage(data) {
        try {
            const message = JSON.parse(data);
            this.handleMessage(message);
        } catch (error) {
            this.addLog('error', `Failed to parse message: ${error.message}`);
        }
    }
    
    handleMessage(message) {
        const { type, data } = message;
        
        switch (type) {
            case 'elevator_update':
                this.updateElevator(data);
                break;
                
            case 'event':
                this.handleEvent(data);
                break;
                
            case 'simulation_time':
                this.updateSimulationTime(data.time);
                break;
                
            case 'pong':
                // Heartbeat response
                break;
                
            default:
                console.log('Unknown message type:', type, data);
        }
    }
    
    updateElevator(data) {
        const { elevator_name, floor, state, passengers, capacity } = data;
        
        // Store elevator state
        this.elevators.set(elevator_name, data);
        
        // Update or create elevator UI
        let elevatorElement = document.getElementById(`elevator-${elevator_name}`);
        if (!elevatorElement) {
            elevatorElement = this.createElevatorElement(elevator_name);
            this.elevatorContainer.appendChild(elevatorElement);
        }
        
        // Update elevator display
        this.renderElevator(elevatorElement, data);
    }
    
    createElevatorElement(elevatorName) {
        const div = document.createElement('div');
        div.id = `elevator-${elevatorName}`;
        div.className = 'elevator-card';
        
        div.innerHTML = `
            <div class="elevator-header">
                <h3>${elevatorName}</h3>
                <span class="elevator-state"></span>
            </div>
            <div class="elevator-body">
                <div class="elevator-visual">
                    <div class="floor-labels"></div>
                    <div class="elevator-shaft">
                        <div class="elevator-car"></div>
                    </div>
                </div>
                <div class="elevator-info">
                    <div class="info-item">
                        <span class="label">Floor:</span>
                        <span class="value floor-value">-</span>
                    </div>
                    <div class="info-item">
                        <span class="label">State:</span>
                        <span class="value state-value">-</span>
                    </div>
                    <div class="info-item">
                        <span class="label">Passengers:</span>
                        <span class="value passengers-value">-</span>
                    </div>
                </div>
            </div>
        `;
        
        return div;
    }
    
    renderElevator(element, data) {
        const { floor, state, passengers, capacity, num_floors } = data;
        
        // Update state badge
        const stateBadge = element.querySelector('.elevator-state');
        stateBadge.textContent = state;
        stateBadge.className = `elevator-state state-${state.toLowerCase()}`;
        
        // Update info values
        element.querySelector('.floor-value').textContent = floor || '-';
        element.querySelector('.state-value').textContent = state || '-';
        element.querySelector('.passengers-value').textContent = 
            capacity ? `${passengers || 0}/${capacity}` : (passengers || 0);
        
        // Generate floor labels if not already present
        const floorLabelsContainer = element.querySelector('.floor-labels');
        if (num_floors && floorLabelsContainer.children.length === 0) {
            for (let f = 1; f <= num_floors; f++) {
                const label = document.createElement('div');
                label.className = 'floor-label';
                label.textContent = `${f}F`;
                floorLabelsContainer.appendChild(label);
            }
        }
        
        // Update elevator car position (visual representation)
        const elevatorCar = element.querySelector('.elevator-car');
        if (num_floors && floor) {
            // Calculate position from bottom (floor 1 = 0%, top floor = 100%)
            const positionPercent = ((floor - 1) / (num_floors - 1)) * 100;
            elevatorCar.style.bottom = `${positionPercent}%`;
        }
    }
    
    handleEvent(data) {
        const { event_type, elevator_name, floor, timestamp, details } = data;
        
        let message = `[${elevator_name}] ${event_type}`;
        if (floor) message += ` at floor ${floor}`;
        if (details) message += ` - ${details}`;
        
        this.addLog('event', message, timestamp);
    }
    
    updateSimulationTime(time) {
        this.simulationTime = time;
        this.simTimeElement.textContent = `${time.toFixed(2)}s`;
    }
    
    updateConnectionStatus(connected) {
        if (connected) {
            this.statusIndicator.className = 'status-indicator status-connected';
            this.statusText.textContent = 'Connected';
        } else {
            this.statusIndicator.className = 'status-indicator status-disconnected';
            this.statusText.textContent = 'Disconnected';
        }
    }
    
    addLog(type, message, timestamp = null) {
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry log-${type}`;
        
        const time = timestamp !== null ? timestamp.toFixed(2) : new Date().toLocaleTimeString();
        logEntry.innerHTML = `
            <span class="log-time">[${time}]</span>
            <span class="log-message">${this.escapeHtml(message)}</span>
        `;
        
        this.logContainer.appendChild(logEntry);
        
        // Auto-scroll to bottom
        if (this.autoScroll) {
            this.logContainer.scrollTop = this.logContainer.scrollHeight;
        }
        
        // Limit log entries to prevent memory issues
        const maxEntries = 500;
        while (this.logContainer.children.length > maxEntries) {
            this.logContainer.removeChild(this.logContainer.firstChild);
        }
    }
    
    clearLog() {
        this.logContainer.innerHTML = '';
        this.addLog('system', 'Log cleared');
    }
    
    sendCommand(command, data = {}) {
        if (!this.isConnected) {
            this.addLog('warning', 'Not connected to server');
            return;
        }
        
        const message = {
            type: command,
            data: data
        };
        
        this.ws.send(JSON.stringify(message));
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.elevatorViz = new ElevatorVisualizer();
});

