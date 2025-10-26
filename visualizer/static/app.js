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
        
        // Mode management
        this.currentMode = 'live'; // 'live' or 'replay'
        this.fileEventSource = null;
        this.isPlaying = false;
        this.playbackSpeed = 1.0;
        this.API_BASE_URL = 'http://localhost:5000';
        
        // Replay state tracking
        this.replayState = {
            hallCalls: {},  // {elevatorName: {up: Set(), down: Set()}}
            carCalls: {}    // {elevatorName: Set()}
        };
        
        this.initializeUI();
        this.initializeModeSelector();
        this.initializePlaybackControls();
        this.initializeDarkMode();
        
        // Start in live mode
        this.switchToLiveMode();
    }
    
    initializeUI() {
        // Status elements
        this.statusIndicator = document.getElementById('status-indicator');
        this.statusText = document.getElementById('status-text');
        this.simTimeElement = document.getElementById('sim-time');
        
        // Control buttons
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
    
    
    clearAllState() {
        console.log('[App] Clearing all state');
        
        // Clear elevator state
        this.elevators.clear();
        
        // Clear replay state
        this.replayState = {
            hallCalls: {},
            carCalls: {}
        };
        
        // Clear waiting passengers
        this.waitingPassengers = {};
        
        // Clear DOM: elevator container
        this.elevatorContainer.innerHTML = '';
        
        // Recreate Elevator Hall panel
        this.createElevatorHallPanel();
        
        console.log('[App] All state cleared');
    }
    
    createElevatorHallPanel() {
        // Use existing method to maintain consistency
        let hallElement = document.getElementById('elevator-hall');
        if (!hallElement) {
            hallElement = this.createElevatorHallElement();
            this.elevatorContainer.appendChild(hallElement);
        }
        this.renderElevatorHall(hallElement, 10); // 10 floors by default
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
                
            case 'calls_update':
                // Update only hall calls and car calls, not elevator position
                this.updateCallsOnly(data);
                break;
                
            case 'pong':
                // Heartbeat response
                break;
                
            default:
                console.log('Unknown message type:', type, data);
        }
    }
    
    updateCallsOnly(data) {
        const { elevator_name, car_calls, hall_calls_up, hall_calls_down } = data;
        
        // Get existing elevator element
        let elevatorElement = document.getElementById(`elevator-${elevator_name}`);
        if (!elevatorElement) {
            // Elevator doesn't exist yet, skip update
            return;
        }
        
        const shaftElement = elevatorElement.querySelector('.elevator-shaft');
        if (!shaftElement) return;
        
        // Remove old call indicators
        shaftElement.querySelectorAll('.car-call-indicator, .hall-call-indicator').forEach(el => el.remove());
        
        // Render car calls
        this.renderCarCalls(shaftElement, car_calls || [], data.num_floors || 10);
        
        // Render hall calls
        this.renderHallCalls(shaftElement, hall_calls_up || [], hall_calls_down || [], data.num_floors || 10);
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
    
    updateConnectionStatus(status, text) {
        // Status can be: 'polling', 'playing', 'paused', 'completed', 'error', 'disconnected'
        // For backward compatibility, also accept boolean (true/false)
        if (typeof status === 'boolean') {
            status = status ? 'polling' : 'disconnected';
            text = status === 'polling' ? 'Polling' : 'Disconnected';
        }
        
        // Update indicator class
        const classMap = {
            'polling': 'status-connected',      // 🟢 Green
            'playing': 'status-connected',      // 🟢 Green
            'paused': 'status-paused',          // 🟡 Yellow
            'completed': 'status-completed',    // ⚪ Gray
            'error': 'status-error',            // 🔴 Red
            'disconnected': 'status-disconnected' // 🔴 Red
        };
        
        this.statusIndicator.className = `status-indicator ${classMap[status] || 'status-disconnected'}`;
        this.statusText.textContent = text || status;
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
    
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // ==========================================
    // Mode Selector & Playback Controls
    // ==========================================
    
    initializeModeSelector() {
        const modeLiveBtn = document.getElementById('mode-live');
        const modeReplayBtn = document.getElementById('mode-replay');
        const fileSelector = document.getElementById('file-selector');
        const logFileSelect = document.getElementById('log-file-select');
        const btnLoadFile = document.getElementById('btn-load-file');
        
        // Mode button handlers
        modeLiveBtn.addEventListener('click', () => this.selectMode('live'));
        modeReplayBtn.addEventListener('click', () => this.selectMode('replay'));
        
        // Load button handler
        btnLoadFile.addEventListener('click', () => {
            const filename = logFileSelect.value;
            if (filename) {
                this.loadReplayFile(filename);
            }
        });
        
        // Load available log files
        this.loadAvailableFiles();
    }
    
    initializePlaybackControls() {
        const btnPlayPause = document.getElementById('btn-play-pause');
        const btnRestart = document.getElementById('btn-restart');
        const speedSelect = document.getElementById('speed-select');
        const timelineSlider = document.getElementById('timeline-slider');
        
        if (btnPlayPause) {
            btnPlayPause.addEventListener('click', () => this.togglePlayPause());
        }
        
        if (btnRestart) {
            btnRestart.addEventListener('click', () => this.restart());
        }
        
        if (speedSelect) {
            speedSelect.addEventListener('change', (e) => {
                this.playbackSpeed = parseFloat(e.target.value);
                if (this.fileEventSource) {
                    this.fileEventSource.setPlaybackSpeed(this.playbackSpeed);
                }
            });
        }
        
        if (timelineSlider) {
            timelineSlider.addEventListener('input', (e) => {
                if (this.fileEventSource) {
                    const percentage = parseFloat(e.target.value);
                    const duration = this.fileEventSource.getDuration();
                    const targetTime = (percentage / 100) * duration;
                    this.fileEventSource.seekTo(targetTime);
                }
            });
        }
        
        // Start time updater
        setInterval(() => this.updatePlaybackDisplay(), 100);
    }
    
    initializeDarkMode() {
        const darkModeToggle = document.getElementById('dark-mode-toggle');
        const iconLight = darkModeToggle.querySelector('.icon-light');
        const iconDark = darkModeToggle.querySelector('.icon-dark');
        
        // Load saved preference
        const savedDarkMode = localStorage.getItem('darkMode') === 'true';
        if (savedDarkMode) {
            document.body.classList.add('dark-mode');
            iconLight.style.display = 'none';
            iconDark.style.display = 'block';
        }
        
        // Toggle handler
        darkModeToggle.addEventListener('click', () => {
            const isDarkMode = document.body.classList.toggle('dark-mode');
            
            // Update icon
            if (isDarkMode) {
                iconLight.style.display = 'none';
                iconDark.style.display = 'block';
            } else {
                iconLight.style.display = 'block';
                iconDark.style.display = 'none';
            }
            
            // Save preference
            localStorage.setItem('darkMode', isDarkMode);
        });
    }
    
    selectMode(mode) {
        const modeLiveBtn = document.getElementById('mode-live');
        const modeReplayBtn = document.getElementById('mode-replay');
        const fileSelector = document.getElementById('file-selector');
        
        // Update button states
        if (mode === 'live') {
            modeLiveBtn.classList.add('active');
            modeReplayBtn.classList.remove('active');
            fileSelector.style.display = 'none';
            this.switchToLiveMode();
        } else {
            modeLiveBtn.classList.remove('active');
            modeReplayBtn.classList.add('active');
            fileSelector.style.display = 'flex';
        }
    }
    
    switchToLiveMode() {
        console.log('[App] Switching to Live mode');
        
        // Stop replay if active
        if (this.fileEventSource) {
            this.fileEventSource.stop();
            this.fileEventSource = null;
        }
        
        // Disconnect WebSocket if connected
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        
        // Show/hide panels
        document.getElementById('playback-controls').style.display = 'none';
        
        // Clear visualization
        this.clearVisualization();
        
        // Start live file polling (using LiveFileEventSource)
        this.startLiveFilePolling();
        
        this.currentMode = 'live';
    }
    
    startLiveFilePolling() {
        console.log('[App] Starting live file polling...');
        
        // Create LiveFileEventSource
        this.fileEventSource = new LiveFileEventSource(
            this.API_BASE_URL, 
            'simulation_log.jsonl', 
            100 // Poll every 100ms
        );
        
        // Subscribe to events
        this.fileEventSource.subscribe((event) => {
            // Check for errors
            if (event.type === 'error') {
                this.updateConnectionStatus('error', 'Error');
                this.addLog('error', `Polling error: ${event.message || 'Unknown error'}`);
            } else {
                // Normal event processing
                this.updateConnectionStatus('polling', 'Polling');
                this.handleReplayEvent(event);
            }
        });
        
        // Start polling
        this.fileEventSource.start();
        
        this.addLog('system', 'Live mode: polling simulation_log.jsonl');
        this.updateConnectionStatus('polling', 'Polling');
    }
    
    async switchToReplayMode(filename) {
        console.log('[App] Switching to Replay mode:', filename);
        
        // Disconnect WebSocket
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        
        // Show/hide panels
        document.getElementById('playback-controls').style.display = 'block';
        
        // Clear visualization
        this.clearVisualization();
        
        this.currentMode = 'replay';
    }
    
    async loadAvailableFiles() {
        try {
            const response = await fetch(`${this.API_BASE_URL}/api/logs/list`);
            const files = await response.json();
            
            const select = document.getElementById('log-file-select');
            if (!select) return;
            
            // Clear existing options except first
            select.innerHTML = '<option value="">-- Select Log File --</option>';
            
            // Add file options
            files.forEach(file => {
                const option = document.createElement('option');
                option.value = file.name;
                const size = this.formatSize(file.size);
                option.textContent = `${file.name} (${size})`;
                select.appendChild(option);
            });
            
            console.log(`[App] Loaded ${files.length} log files`);
        } catch (error) {
            console.error('[App] Error loading files:', error);
        }
    }
    
    async loadReplayFile(filename) {
        try {
            await this.switchToReplayMode(filename);
            
            // Create file event source
            this.fileEventSource = new FileEventSource(this.API_BASE_URL);
            
            // Subscribe to events
            this.fileEventSource.subscribe((event) => this.handleReplayEvent(event));
            
            // Load file
            const info = await this.fileEventSource.loadFile(filename);
            this.addLog('system', `Loaded ${info.eventCount} events from ${filename}`);
            
            // Auto-play
            this.fileEventSource.start();
            this.isPlaying = true;
            this.updatePlayPauseButton();
            this.updateConnectionStatus('playing', 'Playing');
            
        } catch (error) {
            console.error('[App] Error loading replay file:', error);
            this.addLog('error', `Failed to load ${filename}: ${error.message}`);
            this.updateConnectionStatus('error', 'Error');
        }
    }
    
    handleReplayEvent(event) {
        // Convert FileEventSource events to the format expected by handleMessage
        if (event.type === 'metadata') {
            // Handle metadata
            console.log('[Replay] Metadata:', event.data);
            return;
        }
        
        if (event.type === 'clear_state') {
            // Clear all visualization state
            console.log('[Replay] Clearing all state for seek operation');
            this.clearAllState();
            return;
        }
        
        if (event.type === 'playback_complete') {
            this.addLog('system', 'Playback complete');
            this.isPlaying = false;
            this.updatePlayPauseButton();
            this.updateConnectionStatus('completed', 'Completed');
            return;
        }
        
        // Convert JSONL event format to WebSocket message format
        const message = this.convertJSONLToMessage(event);
        if (message) {
            this.handleMessage(message);
        }
    }
    
    convertJSONLToMessage(event) {
        // Convert JSONL event format to WebSocket message format
        switch (event.type) {
            case 'elevator_status':
                return {
                    type: 'elevator_update',
                    data: {
                        elevator_name: event.data.elevator,
                        floor: event.data.floor,
                        state: event.data.state,
                        passengers: event.data.passengers,
                        capacity: event.data.capacity,
                        num_floors: 10, // Default
                        car_calls: this.getCarCallsForElevator(event.data.elevator),
                        hall_calls_up: this.getHallCallsUp(event.data.elevator),
                        hall_calls_down: this.getHallCallsDown(event.data.elevator)
                    }
                };
            
            case 'hall_call_registered':
                // Store hall call for later display
                return null; // Will be displayed via elevator_status
            
            case 'hall_call_assignment':
                // Track hall call assignment
                const elevator = event.data.elevator;
                const floor = event.data.floor;
                const direction = event.data.direction;
                
                if (!this.replayState) {
                    this.replayState = {
                        hallCalls: {},
                        carCalls: {}
                    };
                }
                
                if (!this.replayState.hallCalls[elevator]) {
                    this.replayState.hallCalls[elevator] = {
                        up: new Set(),
                        down: new Set()
                    };
                }
                
                if (direction === 'UP') {
                    this.replayState.hallCalls[elevator].up.add(floor);
                } else {
                    this.replayState.hallCalls[elevator].down.add(floor);
                }
                
                // Immediately trigger calls update (without changing elevator position)
                return {
                    type: 'calls_update',
                    data: {
                        elevator_name: elevator,
                        num_floors: 10,
                        car_calls: this.getCarCallsForElevator(elevator),
                        hall_calls_up: this.getHallCallsUp(elevator),
                        hall_calls_down: this.getHallCallsDown(elevator)
                    }
                };
            
            case 'hall_call_off':
                // Remove hall call
                const offElevator = event.data.elevator;
                const offFloor = event.data.floor;
                const offDirection = event.data.direction;
                
                if (this.replayState && this.replayState.hallCalls[offElevator]) {
                    if (offDirection === 'UP') {
                        this.replayState.hallCalls[offElevator].up.delete(offFloor);
                    } else {
                        this.replayState.hallCalls[offElevator].down.delete(offFloor);
                    }
                }
                
                // Immediately trigger calls update to hide hall call
                return {
                    type: 'calls_update',
                    data: {
                        elevator_name: offElevator,
                        num_floors: 10,
                        car_calls: this.getCarCallsForElevator(offElevator),
                        hall_calls_up: this.getHallCallsUp(offElevator),
                        hall_calls_down: this.getHallCallsDown(offElevator)
                    }
                };
            
            case 'car_call_registered':
                // Track car call
                const carElevator = event.data.elevator;
                const carFloor = event.data.floor;
                
                if (!this.replayState) {
                    this.replayState = {
                        hallCalls: {},
                        carCalls: {}
                    };
                }
                
                if (!this.replayState.carCalls[carElevator]) {
                    this.replayState.carCalls[carElevator] = new Set();
                }
                
                this.replayState.carCalls[carElevator].add(carFloor);
                
                // Immediately trigger calls update to show car call
                return {
                    type: 'calls_update',
                    data: {
                        elevator_name: carElevator,
                        num_floors: 10,
                        car_calls: this.getCarCallsForElevator(carElevator),
                        hall_calls_up: this.getHallCallsUp(carElevator),
                        hall_calls_down: this.getHallCallsDown(carElevator)
                    }
                };
            
            case 'car_call_off':
                // Remove car call
                const carOffElevator = event.data.elevator;
                const carOffFloor = event.data.floor;
                
                if (this.replayState && this.replayState.carCalls[carOffElevator]) {
                    this.replayState.carCalls[carOffElevator].delete(carOffFloor);
                }
                
                // Immediately trigger calls update to hide car call
                return {
                    type: 'calls_update',
                    data: {
                        elevator_name: carOffElevator,
                        num_floors: 10,
                        car_calls: this.getCarCallsForElevator(carOffElevator),
                        hall_calls_up: this.getHallCallsUp(carOffElevator),
                        hall_calls_down: this.getHallCallsDown(carOffElevator)
                    }
                };
            
            case 'door_event':
                // Handle door events
                return {
                    type: 'event',
                    data: {
                        event_type: event.data.event,
                        elevator_name: event.data.elevator,
                        floor: event.data.floor,
                        timestamp: event.time
                    }
                };
            
            case 'passenger_waiting':
                // Simulate waiting passengers update
                const waitFloor = event.data.floor;
                const waitDirection = event.data.direction;
                
                if (!this.waitingPassengers[waitFloor]) {
                    this.waitingPassengers[waitFloor] = { UP: 0, DOWN: 0 };
                }
                this.waitingPassengers[waitFloor][waitDirection]++;
                
                return {
                    type: 'waiting_passengers_update',
                    data: this.waitingPassengers
                };
            
            case 'passenger_boarding':
                // Decrement waiting passengers
                const boardFloor = event.data.floor;
                const boardDirection = event.data.direction;
                
                if (this.waitingPassengers[boardFloor] && 
                    this.waitingPassengers[boardFloor][boardDirection] > 0) {
                    this.waitingPassengers[boardFloor][boardDirection]--;
                }
                
                return {
                    type: 'waiting_passengers_update',
                    data: this.waitingPassengers
                };
            
            default:
                // Ignore other event types
                return null;
        }
    }
    
    getCarCallsForElevator(elevator) {
        if (!this.replayState || !this.replayState.carCalls[elevator]) {
            return [];
        }
        return Array.from(this.replayState.carCalls[elevator]);
    }
    
    getHallCallsUp(elevator) {
        if (!this.replayState || !this.replayState.hallCalls[elevator]) {
            return [];
        }
        return Array.from(this.replayState.hallCalls[elevator].up);
    }
    
    getHallCallsDown(elevator) {
        if (!this.replayState || !this.replayState.hallCalls[elevator]) {
            return [];
        }
        return Array.from(this.replayState.hallCalls[elevator].down);
    }
    
    togglePlayPause() {
        if (!this.fileEventSource) return;
        
        if (this.isPlaying) {
            this.fileEventSource.pause();
            this.isPlaying = false;
            this.updateConnectionStatus('paused', 'Paused');
        } else {
            this.fileEventSource.resume();
            this.isPlaying = true;
            this.updateConnectionStatus('playing', 'Playing');
        }
        
        this.updatePlayPauseButton();
    }
    
    restart() {
        if (!this.fileEventSource) return;
        
        this.fileEventSource.seekTo(0);
        this.clearVisualization();
        
        if (!this.isPlaying) {
            this.fileEventSource.resume();
            this.isPlaying = true;
            this.updatePlayPauseButton();
        }
    }
    
    updatePlayPauseButton() {
        const btn = document.getElementById('btn-play-pause');
        if (btn) {
            btn.textContent = this.isPlaying ? '⏸ Pause' : '▶ Play';
        }
    }
    
    updatePlaybackDisplay() {
        if (this.currentMode !== 'replay' || !this.fileEventSource) return;
        
        const currentTime = this.fileEventSource.getCurrentTime();
        const duration = this.fileEventSource.getDuration();
        
        // Update time display
        const currentTimeEl = document.getElementById('current-time');
        const totalTimeEl = document.getElementById('total-time');
        
        if (currentTimeEl) {
            currentTimeEl.textContent = this.formatTime(currentTime);
        }
        if (totalTimeEl) {
            totalTimeEl.textContent = this.formatTime(duration);
        }
        
        // Update timeline slider
        const timelineSlider = document.getElementById('timeline-slider');
        if (timelineSlider && duration > 0) {
            const percentage = (currentTime / duration) * 100;
            timelineSlider.value = percentage;
        }
        
        // Update simulation time display
        if (this.simTimeElement) {
            this.simTimeElement.textContent = `${currentTime.toFixed(2)}s`;
        }
    }
    
    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
    
    formatSize(bytes) {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
    
    clearVisualization() {
        // Use the unified clearAllState method
        this.clearAllState();
        
        // Re-initialize placeholder elevators (for live mode)
        this.initializePlaceholderElevators();
    }
}

// Initialize application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.elevatorViz = new ElevatorVisualizer();
});

