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
        this.waitingPassengers = {}; // Store waiting passengers data
        
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
        
        // Initialize placeholder elevators (Elevator_1 and Elevator_2)
        this.initializePlaceholderElevators();
    }
    
    initializePlaceholderElevators() {
        // Create Elevator Hall panel first (always on the left)
        let hallElement = document.getElementById('elevator-hall');
        if (!hallElement) {
            hallElement = this.createElevatorHallElement();
            this.elevatorContainer.appendChild(hallElement);
        }
        this.renderElevatorHall(hallElement, 10); // 10 floors by default
        
        // Create placeholder elevators to show from the start
        const placeholderElevators = ['Elevator_1', 'Elevator_2', 'Elevator_3'];
        
        placeholderElevators.forEach(elevatorName => {
            const placeholderData = {
                elevator_name: elevatorName,
                floor: 1,
                state: 'IDLE',
                passengers: 0,
                capacity: 50,
                num_floors: 10,
                car_calls: [],
                hall_calls_up: [],
                hall_calls_down: []
            };
            
            // Create elevator card
            let elevatorElement = document.getElementById(`elevator-${elevatorName}`);
            if (!elevatorElement) {
                elevatorElement = this.createElevatorElement(elevatorName);
                this.elevatorContainer.appendChild(elevatorElement);
            }
            
            // Render initial state
            this.renderElevator(elevatorElement, placeholderData);
            this.elevators.set(elevatorName, placeholderData);
        });
    }
    
    createElevatorHallElement() {
        const div = document.createElement('div');
        div.id = 'elevator-hall';
        div.className = 'elevator-card hall-card';
        
        div.innerHTML = `
            <div class="elevator-header hall-header">
                <h3>Elevator Hall</h3>
            </div>
            <div class="elevator-body">
                <div class="elevator-visual">
                    <div class="elevator-shaft-container">
                        <div class="floor-labels"></div>
                        <div class="elevator-shaft hall-shaft">
                            <!-- Waiting passengers will be positioned here -->
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        return div;
    }
    
    renderElevatorHall(element, numFloors) {
        const hallShaft = element.querySelector('.hall-shaft');
        const floorLabelsContainer = element.querySelector('.floor-labels');
        const shaftContainer = element.querySelector('.elevator-shaft-container');
        
        if (!hallShaft || !floorLabelsContainer || !numFloors) {
            return;
        }
        
        // Set height to match elevator shafts (exact same calculation)
        const carHeight = 30; // px (must match CSS .elevator-car height)
        const shaftHeight = carHeight * (numFloors + 1);
        hallShaft.style.height = `${shaftHeight}px`;
        floorLabelsContainer.style.height = `${shaftHeight}px`;
        if (shaftContainer) {
            shaftContainer.style.height = `${shaftHeight}px`;
        }
        
        // Generate floor labels if not already present (exact same as elevator panels)
        if (floorLabelsContainer.children.length === 0) {
            for (let f = 1; f <= numFloors; f++) {
                const label = document.createElement('div');
                label.className = 'floor-label';
                label.textContent = `${f}F`;
                
                // Position each label at the bottom of its floor
                const bottomPercent = ((f - 1) / numFloors) * 100;
                label.style.bottom = `${bottomPercent}%`;
                
                floorLabelsContainer.appendChild(label);
            }
        }
        
        // Render waiting passengers
        this.renderHallWaitingPassengers(hallShaft, numFloors);
    }
    
    renderHallWaitingPassengers(waitingArea, numFloors) {
        if (!waitingArea || !numFloors) {
            return;
        }
        
        // Clear existing waiting passenger displays
        waitingArea.innerHTML = '';
        
        console.log('[DEBUG] renderHallWaitingPassengers: waitingPassengers=', JSON.stringify(this.waitingPassengers));
        
        // Render waiting passengers for each floor
        for (let floor = 1; floor <= numFloors; floor++) {
            const floorKey = floor.toString();
            const waitingData = this.waitingPassengers[floorKey];
            
            console.log(`[DEBUG] Floor ${floor}: waitingData=`, JSON.stringify(waitingData));
            
            if (waitingData && (waitingData.UP > 0 || waitingData.DOWN > 0)) {
                const floorElement = document.createElement('div');
                floorElement.className = 'waiting-floor';
                
                // Calculate position at the CENTER of each floor (same as elevator panels)
                const floorHeight = 100 / numFloors;
                const bottomPercent = ((floor - 1) / numFloors) * 100 + (floorHeight / 2);
                floorElement.style.bottom = `${bottomPercent}%`;
                
                // Generate UP passengers display
                if (waitingData.UP > 0) {
                    const upElement = document.createElement('span');
                    upElement.className = 'waiting-up';
                    upElement.innerHTML = this.generateWaitingDisplay(waitingData.UP, '↑');
                    floorElement.appendChild(upElement);
                }
                
                // Generate DOWN passengers display
                if (waitingData.DOWN > 0) {
                    const downElement = document.createElement('span');
                    downElement.className = 'waiting-down';
                    downElement.innerHTML = this.generateWaitingDisplay(waitingData.DOWN, '↓');
                    floorElement.appendChild(downElement);
                }
                
                waitingArea.appendChild(floorElement);
            }
        }
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
                
            case 'waiting_passengers_update':
                this.updateWaitingPassengers(data);
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
                        <div class="elevator-shaft-container">
                            <div class="floor-labels"></div>
                            <div class="elevator-shaft">
                                <div class="elevator-car door-closed">
                                    <div class="door door-left"></div>
                                    <div class="door door-right"></div>
                                </div>
                            </div>
                            <div class="waiting-passengers"></div>
                        </div>
                        <div class="passenger-box">
                            <div class="passenger-squares"></div>
                            <div class="passenger-info">
                                <div class="passenger-count">0/50</div>
                                <div class="passenger-percent">0%</div>
                            </div>
                        </div>
                    </div>
            </div>
        `;
        
        return div;
    }
    
    renderElevator(element, data) {
        const { floor, state, passengers, capacity, num_floors, car_calls, hall_calls_up, hall_calls_down } = data;
        
        // Update state badge
        const stateBadge = element.querySelector('.elevator-state');
        stateBadge.textContent = state;
        stateBadge.className = `elevator-state state-${state.toLowerCase()}`;
        
        
        // Dynamically set shaft height based on number of floors
        const elevatorShaft = element.querySelector('.elevator-shaft');
        const floorLabelsContainer = element.querySelector('.floor-labels');
        const shaftContainer = element.querySelector('.elevator-shaft-container');
        const carHeight = 30; // px (must match CSS .elevator-car height)
        
        if (num_floors) {
            // Set shaft height: car height × (num_floors + 1) to ensure car is always visible
            const shaftHeight = carHeight * (num_floors + 1);
            elevatorShaft.style.height = `${shaftHeight}px`;
            floorLabelsContainer.style.height = `${shaftHeight}px`;
            if (shaftContainer) {
                shaftContainer.style.height = `${shaftHeight}px`;
            }
            
            // Set waiting passengers area height
            const waitingArea = element.querySelector('.waiting-passengers');
            if (waitingArea) {
                waitingArea.style.height = `${shaftHeight}px`;
            }
        }
        
        // Generate floor labels if not already present
        if (num_floors && floorLabelsContainer.children.length === 0) {
            for (let f = 1; f <= num_floors; f++) {
                const label = document.createElement('div');
                label.className = 'floor-label';
                label.textContent = `${f}F`;
                
                // Position each label at the bottom of its floor
                const bottomPercent = ((f - 1) / num_floors) * 100;
                label.style.bottom = `${bottomPercent}%`;
                
                floorLabelsContainer.appendChild(label);
            }
        }
        
        // Update elevator car position (visual representation)
        const elevatorCar = element.querySelector('.elevator-car');
        if (num_floors && floor) {
            // Calculate position from bottom (floor 1 = 0%, floor 10 = 90%)
            // Use num_floors (not num_floors - 1) to utilize full 10 slots
            const positionPercent = ((floor - 1) / num_floors) * 100;
            elevatorCar.style.bottom = `${positionPercent}%`;
        }
        
        // Render car call indicators (◎ purple, small)
        this.renderCarCalls(elevatorShaft, car_calls || [], num_floors);
        
        // Render hall call indicators (△ UP green, ▽ DOWN orange)
        this.renderHallCalls(elevatorShaft, hall_calls_up || [], hall_calls_down || [], num_floors);
        
        // Render passenger box
        this.renderPassengerBox(element, passengers, capacity);
        
        // Render waiting passengers
        this.renderWaitingPassengers(element, num_floors);
    }
    
    renderCarCalls(shaftElement, carCalls, numFloors) {
        // Remove existing car call indicators
        const existing = shaftElement.querySelectorAll('.car-call-indicator');
        existing.forEach(el => el.remove());
        
        // Add car call indicators for each floor
        if (!numFloors || !carCalls || carCalls.length === 0) return;
        
        carCalls.forEach(targetFloor => {
            const indicator = document.createElement('div');
            indicator.className = 'car-call-indicator';
            indicator.textContent = '●';
            indicator.title = `Car call to floor ${targetFloor}`;
            
            // Position indicator at the CENTER of the target floor
            const floorHeight = 100 / numFloors; // Height of each floor slot (%)
            const bottomPercent = ((targetFloor - 1) / numFloors) * 100 + (floorHeight / 2);
            indicator.style.bottom = `${bottomPercent}%`;
            
            shaftElement.appendChild(indicator);
        });
    }
    
    renderHallCalls(shaftElement, hallCallsUp, hallCallsDown, numFloors) {
        // Remove existing hall call indicators
        const existing = shaftElement.querySelectorAll('.hall-call-indicator');
        existing.forEach(el => el.remove());
        
        // Add hall call indicators for each floor
        if (!numFloors) return;
        
        const floorHeight = 100 / numFloors; // Height of each floor slot (%)
        
        // Render UP hall calls (▲ green filled)
        hallCallsUp.forEach(targetFloor => {
            const indicator = document.createElement('div');
            indicator.className = 'hall-call-indicator hall-call-up';
            indicator.textContent = '▲';
            indicator.title = `Hall call UP at floor ${targetFloor}`;
            
            // Position indicator at the target floor
            let bottomPercent = ((targetFloor - 1) / numFloors) * 100 + (floorHeight / 2);
            
            // If both UP and DOWN exist at same floor, offset UP upward
            if (hallCallsDown.includes(targetFloor)) {
                bottomPercent += floorHeight * 0.15; // Offset up by 15% of floor height
            }
            
            indicator.style.bottom = `${bottomPercent}%`;
            shaftElement.appendChild(indicator);
        });
        
        // Render DOWN hall calls (▼ orange filled)
        hallCallsDown.forEach(targetFloor => {
            const indicator = document.createElement('div');
            indicator.className = 'hall-call-indicator hall-call-down';
            indicator.textContent = '▼';
            indicator.title = `Hall call DOWN at floor ${targetFloor}`;
            
            // Position indicator at the target floor
            let bottomPercent = ((targetFloor - 1) / numFloors) * 100 + (floorHeight / 2);
            
            // If both UP and DOWN exist at same floor, offset DOWN downward
            if (hallCallsUp.includes(targetFloor)) {
                bottomPercent -= floorHeight * 0.15; // Offset down by 15% of floor height
            }
            
            indicator.style.bottom = `${bottomPercent}%`;
            shaftElement.appendChild(indicator);
        });
    }
    
    renderPassengerBox(elevatorElement, passengers, capacity) {
        const passengerBox = elevatorElement.querySelector('.passenger-box');
        const squaresContainer = elevatorElement.querySelector('.passenger-squares');
        const countElement = elevatorElement.querySelector('.passenger-count');
        const percentElement = elevatorElement.querySelector('.passenger-percent');
        
        if (!passengerBox || !squaresContainer || !countElement || !percentElement) {
            return;
        }
        
        // Calculate occupancy
        const occupancyRate = capacity > 0 ? passengers / capacity : 0;
        const percentage = Math.round(occupancyRate * 100);
        
        // Update text displays
        countElement.textContent = `${passengers}/${capacity}`;
        percentElement.textContent = `${percentage}%`;
        
        // Determine color based on occupancy
        let boxClass = 'passenger-box';
        if (occupancyRate <= 0.3) {
            boxClass += ' occupancy-low';
        } else if (occupancyRate <= 0.7) {
            boxClass += ' occupancy-medium';
        } else {
            boxClass += ' occupancy-high';
        }
        passengerBox.className = boxClass;
        
        // Clear existing squares
        squaresContainer.innerHTML = '';
        
        // Add passenger squares (■) with spacing
        if (passengers > 0) {
            const maxSquaresToShow = 5;
            const squaresToShow = Math.min(passengers, maxSquaresToShow);
            
            // Create squares
            for (let i = 0; i < squaresToShow; i++) {
                const square = document.createElement('span');
                square.className = 'passenger-square';
                square.textContent = '■';
                squaresContainer.appendChild(square);
            }
            
            // Add "+X" text if more passengers than squares shown
            if (passengers > maxSquaresToShow) {
                const extraCount = passengers - maxSquaresToShow;
                const extraText = document.createElement('span');
                extraText.className = 'passenger-extra';
                extraText.textContent = `+${extraCount}`;
                squaresContainer.appendChild(extraText);
            }
        }
    }
    
    updateWaitingPassengers(waitingData) {
        console.log('[DEBUG] updateWaitingPassengers called with data:', JSON.stringify(waitingData));
        this.waitingPassengers = waitingData;
        
        // Update Elevator Hall panel
        const hallElement = document.getElementById('elevator-hall');
        if (hallElement) {
            const hallShaft = hallElement.querySelector('.hall-shaft');
            if (hallShaft) {
                // Get number of floors from any elevator (they should all be the same)
                const firstElevator = this.elevators.values().next().value;
                const numFloors = firstElevator ? firstElevator.num_floors : 10;
                console.log('[DEBUG] Rendering hall waiting passengers, numFloors:', numFloors);
                this.renderHallWaitingPassengers(hallShaft, numFloors);
            }
        }
        
        // Clear waiting areas from all elevator displays
        this.elevators.forEach((elevatorData, elevatorName) => {
            const elevatorElement = document.getElementById(`elevator-${elevatorName}`);
            if (elevatorElement) {
                const numFloors = elevatorData.num_floors;
                this.renderWaitingPassengers(elevatorElement, numFloors);
            }
        });
    }
    
    renderWaitingPassengers(elevatorElement, numFloors) {
        // Waiting passengers are now shown in the Elevator Hall panel
        // Clear the waiting area in elevator panels
        const waitingArea = elevatorElement.querySelector('.waiting-passengers');
        if (waitingArea) {
            waitingArea.innerHTML = '';
        }
    }
    
    generateWaitingDisplay(count, direction) {
        // Simple numeric display: 👤 ×5 ↑
        let display = '';
        
        // Passenger icon
        display += '<span class="waiting-passenger-icon">👤</span>';
        
        // Count with × symbol
        display += `<span class="waiting-count">×${count}</span>`;
        
        // Direction arrow
        display += `<span class="waiting-direction-icon">${direction}</span>`;
        
        // Debug log
        console.log(`Waiting display: count=${count}, direction=${direction}, display="👤 ×${count} ${direction}"`);
        
        return display;
    }
    
    handleEvent(data) {
        const { event_type, elevator_name, floor, timestamp, details } = data;
        
        let message = `[${elevator_name}] ${event_type}`;
        if (floor) message += ` at floor ${floor}`;
        if (details) message += ` - ${details}`;
        
        this.addLog('event', message, timestamp);
        
        // Handle door events for animation
        if (elevator_name) {
            const elevatorElement = document.getElementById(`elevator-${elevator_name}`);
            if (elevatorElement) {
                const elevatorCar = elevatorElement.querySelector('.elevator-car');
                if (elevatorCar) {
                    switch (event_type) {
                        case 'DOOR_OPENING_START':
                            elevatorCar.classList.add('door-opening');
                            elevatorCar.classList.remove('door-closed', 'door-closing');
                            break;
                            
                        case 'DOOR_OPENING_COMPLETE':
                            elevatorCar.classList.add('door-open');
                            elevatorCar.classList.remove('door-opening', 'door-closed');
                            break;
                            
                        case 'DOOR_CLOSING_START':
                            elevatorCar.classList.add('door-closing');
                            elevatorCar.classList.remove('door-open', 'door-opening');
                            break;
                            
                        case 'DOOR_CLOSING_COMPLETE':
                            elevatorCar.classList.add('door-closed');
                            elevatorCar.classList.remove('door-closing', 'door-open');
                            break;
                    }
                }
            }
        }
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

