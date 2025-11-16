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
            carCalls: {},    // {elevatorName: Set()}
            carCallPreviews: {}, // {elevatorName: Set()} - DCS destination previews
            forcedCalls: {}, // {elevatorName: {up: Set(), down: Set()}}
            moveCommands: {} // {elevatorName: targetFloor}
        };
        
        // Metrics tracking
        this.metrics = {
            totalPassengers: 0,
            totalWaitTime: 0,
            maxWaitTime: 0,
            boardingCount: 0,      // Count of passengers who boarded (for avg wait time)
            totalTrips: 0,
            totalOccupancy: 0,
            occupancyCount: 0
        };
        
        // Performance Monitor metrics (real-world compatible)
        this.performanceMetrics = {
            hallCalls: [],          // Track hall call registration and response
            responseTimes: [],      // Response times for completed hall calls
            longResponseCount: 0,   // Count of responses > 60s
            totalTrips: 0,          // Number of completed trips (passenger alightings)
            doorOperations: 0,      // Count of door open/close cycles
            elevatorDistances: {},  // Per-elevator travel distance
            elevatorTrips: {},      // Per-elevator trip count
            lastFloors: {}          // Track last floor for distance calculation
        };
        
        // Track elevator states for change detection
        this.elevatorStates = {};
        
        // Chart data management
        this.chartConfig = {
            updateInterval: 10,     // Aggregation interval in seconds (configurable)
            maxDataPoints: 50       // Maximum number of data points to display
        };
        
        this.chartData = {
            lastBucketEndTime: 0,   // Last bucket end time (to track which buckets to flush)
            currentBucket: {
                startTime: 0,       // Start time of current bucket (aligned to updateInterval)
                waitTimes: [],      // Wait times collected in this bucket
                sampleCount: 0      // Number of passengers in this bucket (for future display)
            }
        };
        
        // Event filter state
        this.eventFilters = {
            door: true,        // Default: ON (as requested)
            hall: false,
            car: false,
            passenger: false,
            elevator: true,    // Default: ON (as requested)
            command: false
        };
        
        this.initializeUI();
        this.initializeModeSelector();
        this.initializePlaybackControls();
        this.initializeDarkMode();
        this.initializeTabs();
        this.initializeChart();
        this.initializeEventFilters();
        
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
        // Initialize the new grid layout
        this.numFloors = 10; // Default number of floors
        this.initializeGridLayout(this.numFloors);
        
        // Create placeholder elevators to show from the start
        const placeholderElevators = ['Hall', 'Elevator_1', 'Elevator_2', 'Elevator_3'];
        
        placeholderElevators.forEach(elevatorName => {
            const placeholderData = {
                elevator_name: elevatorName,
                floor: 1,
                state: 'IDLE',
                direction: 'NO_DIRECTION',
                passengers: 0,
                capacity: elevatorName === 'Hall' ? 0 : 50,
                num_floors: 10,
                car_calls: [],
                hall_calls_up: [],
                hall_calls_down: []
            };
            
            // Create elevator column
            this.createElevatorColumn(elevatorName, placeholderData);
            this.elevators.set(elevatorName, placeholderData);
        });
    }
    
    initializeGridLayout(numFloors) {
        const sharedFloorLabels = document.getElementById('shared-floor-labels');
        if (!sharedFloorLabels) return;
        
        // Clear existing labels
        sharedFloorLabels.innerHTML = '';
        
        // Create floor labels using Flexbox (from top to bottom: 10F -> 1F)
        for (let f = numFloors; f >= 1; f--) {
            const label = document.createElement('div');
            label.className = 'shared-floor-label';
            label.textContent = `${f}F`;
            sharedFloorLabels.appendChild(label);
        }
    }
    
    createElevatorColumn(elevatorName, data) {
        const columnsContainer = document.getElementById('elevator-columns');
        if (!columnsContainer) return;
        
        // Check if column already exists
        let column = document.getElementById(`column-${elevatorName}`);
        if (column) return column;
        
        // Create new column
        column = document.createElement('div');
        column.id = `column-${elevatorName}`;
        column.className = 'elevator-column';
        column.setAttribute('data-elevator', elevatorName);
        
        // Create header with name and status
        const displayName = this.formatElevatorName(elevatorName);
        const header = document.createElement('div');
        header.className = 'elevator-column-header';
        // Hallの場合は見えないステータス要素を追加して高さを揃える
        if (elevatorName === 'Hall') {
            header.innerHTML = `
                <div class="elevator-name">${displayName}</div>
                <div class="elevator-status" style="visibility: hidden;" aria-hidden="true">
                    ○ IDLE
                </div>
            `;
        } else {
            header.innerHTML = `
                <div class="elevator-name">${displayName}</div>
                <div class="elevator-status" id="status-${elevatorName}">
                    ${this.getDirectionIcon(data.direction)} ${this.shortenState(data.state)}
                </div>
            `;
        }
        
        // Create shaft wrapper with new Flexbox structure
        const shaftWrapper = document.createElement('div');
        shaftWrapper.className = 'elevator-shaft-wrapper';
        shaftWrapper.id = `shaft-${elevatorName}`;
        
        const numFloors = data.num_floors || 10;
        
        // Create floors container (Flexbox)
        const floorsContainer = document.createElement('div');
        floorsContainer.className = 'elevator-floors';
        
        // Create floor elements (from top to bottom: 10F -> 1F)
        for (let floor = numFloors; floor >= 1; floor--) {
            const floorDiv = document.createElement('div');
            floorDiv.className = 'floor';
            floorDiv.setAttribute('data-floor', floor);
            
            // Left side: Hall calls (▲▼)
            const leftIcons = document.createElement('div');
            leftIcons.className = 'floor-icons-left';
            leftIcons.id = `floor-icons-left-${elevatorName}-${floor}`;
            
            // Center: Waiting passengers (for Hall only)
            const centerIcons = document.createElement('div');
            centerIcons.className = 'floor-icons-center';
            centerIcons.id = `floor-icons-center-${elevatorName}-${floor}`;
            
            // Right side: Car calls (●)
            const rightIcons = document.createElement('div');
            rightIcons.className = 'floor-icons-right';
            rightIcons.id = `floor-icons-right-${elevatorName}-${floor}`;
            
            floorDiv.appendChild(leftIcons);
            floorDiv.appendChild(centerIcons);
            floorDiv.appendChild(rightIcons);
            floorsContainer.appendChild(floorDiv);
        }
        
        shaftWrapper.appendChild(floorsContainer);
        
        // Create elevator car layer (if not Hall)
        if (elevatorName !== 'Hall') {
            const carLayer = document.createElement('div');
            carLayer.className = 'elevator-car-layer';
            
            const car = document.createElement('div');
            car.className = 'elevator-car door-closed';
            car.id = `car-${elevatorName}`;
            car.innerHTML = `
                <div class="door door-left"></div>
                <div class="door door-right"></div>
            `;
            
            // Position car at initial floor
            const floorPosition = ((data.floor - 1) / numFloors) * 100;
            car.style.bottom = `${floorPosition}%`;
            
            carLayer.appendChild(car);
            shaftWrapper.appendChild(carLayer);
        }
        
        // Add passenger capacity display (if not Hall)
        if (elevatorName !== 'Hall') {
            const capacityDisplay = document.createElement('div');
            capacityDisplay.className = 'capacity-display';
            capacityDisplay.id = `capacity-${elevatorName}`;
            capacityDisplay.innerHTML = `
                <div class="capacity-squares" id="capacity-squares-${elevatorName}"></div>
                <div class="capacity-text">
                    <span id="capacity-count-${elevatorName}">0/50</span>
                    <span id="capacity-percent-${elevatorName}">0%</span>
                </div>
            `;
            column.appendChild(capacityDisplay);
            
            // Initialize capacity visualization
            this.updateCapacityDisplay(elevatorName, data.passengers || 0, data.capacity || 50);
        }
        
        // Append elements
        column.appendChild(header);
        column.appendChild(shaftWrapper);
        if (elevatorName !== 'Hall') {
            const capacityDisplay = column.querySelector('.capacity-display');
            if (capacityDisplay) {
                column.appendChild(capacityDisplay);
            }
        }
        columnsContainer.appendChild(column);
        
        // Update elevator count for CSS dynamic sizing
        this.updateElevatorCount();
        
        return column;
    }
    
    updateElevatorCount() {
        const columnsContainer = document.getElementById('elevator-columns');
        if (columnsContainer) {
            const elevatorCount = columnsContainer.children.length;
            document.documentElement.style.setProperty('--elevator-count', elevatorCount);
            console.log(`[Hybrid] Updated elevator count: ${elevatorCount}`);
        }
    }
    
    updateCapacityDisplay(elevatorName, passengers, capacity) {
        const countElement = document.getElementById(`capacity-count-${elevatorName}`);
        const percentElement = document.getElementById(`capacity-percent-${elevatorName}`);
        const squaresContainer = document.getElementById(`capacity-squares-${elevatorName}`);
        
        if (countElement) {
            // Compact format: just numbers
            countElement.textContent = `${passengers}/${capacity}`;
        }
        
        if (percentElement) {
            const percent = Math.round((passengers / capacity) * 100);
            percentElement.textContent = `${percent}%`;
        }
        
        if (squaresContainer) {
            squaresContainer.innerHTML = '';
            const maxSquares = 10;
            const filledSquares = Math.round((passengers / capacity) * maxSquares);
            
            for (let i = 0; i < maxSquares; i++) {
                const square = document.createElement('div');
                square.className = i < filledSquares ? 'capacity-square filled' : 'capacity-square';
                squaresContainer.appendChild(square);
            }
        }
    }
    
    formatElevatorName(name) {
        // Format elevator names for display
        if (name === 'Hall') return '🏢 Hall';
        if (name.startsWith('Elevator_')) {
            const num = name.split('_')[1];
            return `Elv ${num}`;
        }
        return name;
    }
    
    shortenState(state) {
        const stateMap = {
            'IDLE': 'IDLE',
            'MOVING': 'MOVE',
            'STOPPING': 'STOP',
            'DECELERATING': 'DECEL'
        };
        return stateMap[state] || state;
    }
    
    getDirectionIcon(direction) {
        const iconMap = {
            'UP': '↑',
            'DOWN': '↓',
            'NO_DIRECTION': '○'
        };
        return iconMap[direction] || '○';
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
        const carHeight = 25; // px (must match CSS .elevator-car height)
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
            carCalls: {},
            carCallPreviews: {},
            forcedCalls: {},
            moveCommands: {}
        };
        
        // Clear waiting passengers
        this.waitingPassengers = {};
        
        // Update waiting passengers display (clear all indicators)
        this.updateWaitingPassengers(this.waitingPassengers);
        
        // Clear metrics
        this.resetMetrics();
        
        // Clear DOM: elevator columns (new grid layout)
        const elevatorColumns = document.getElementById('elevator-columns');
        if (elevatorColumns) {
            elevatorColumns.innerHTML = '';
        }
        
        // Clear shared floor labels
        const sharedFloorLabels = document.getElementById('shared-floor-labels');
        if (sharedFloorLabels) {
            sharedFloorLabels.innerHTML = '';
        }
        
        // Update elevator count
        this.updateElevatorCount();
        
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
        
        // Update metrics for all relevant messages
        // Pass the entire message (not just data) so updateMetrics can access message.type
        this.updateMetrics(message);
        
        switch (type) {
            case 'elevator_update':
                this.updateElevator(data);
                // Also handle status updates for event log
                this.handleElevatorStatusUpdate(data, message.time);
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
                
            case 'passenger_waiting':
                // Handle passenger waiting event for visualization
                // Update waiting passengers count
                const waitFloor = data.floor;
                let waitDirection = data.direction;
                
                // DCS: Calculate direction from destination if not provided
                if (!waitDirection && data.destination !== undefined) {
                    waitDirection = data.destination > waitFloor ? 'UP' : 'DOWN';
                }
                
                if (!this.waitingPassengers[waitFloor]) {
                    this.waitingPassengers[waitFloor] = { UP: 0, DOWN: 0 };
                }
                
                // Only increment if we have a valid direction
                if (waitDirection === 'UP' || waitDirection === 'DOWN') {
                this.waitingPassengers[waitFloor][waitDirection]++;
                }
                
                // Add to event log
                const logDirection = waitDirection || `→${data.destination}`;
                this.addLog('info', `${data.passenger_name || data.passenger} waiting at floor ${waitFloor} ${logDirection}`, message.time);
                
                // Trigger visualization update
                this.updateWaitingPassengers(this.waitingPassengers);
                break;
                
            case 'passenger_boarding':
                // Handle passenger boarding event for visualization
                // Decrement waiting passengers count
                const boardFloor = data.floor;
                let boardDirection = data.direction;
                
                // DCS: Calculate direction from destination if not provided
                if (!boardDirection && data.destination !== undefined) {
                    boardDirection = data.destination > boardFloor ? 'UP' : 'DOWN';
                }
                
                if (this.waitingPassengers[boardFloor] && 
                    (boardDirection === 'UP' || boardDirection === 'DOWN') &&
                    this.waitingPassengers[boardFloor][boardDirection] > 0) {
                    this.waitingPassengers[boardFloor][boardDirection]--;
                }
                
                // DCS: Remove car call preview when passenger boards (DCS destination preview should be removed)
                if (data.destination && data.elevator_name && this.replayState.carCallPreviews[data.elevator_name]) {
                    this.replayState.carCallPreviews[data.elevator_name].delete(data.destination);
                }
                
                // Add to event log
                this.addLog('success', `${data.passenger_name} boarded ${data.elevator_name} at floor ${boardFloor}`, message.time);
                
                // Trigger visualization update
                this.updateWaitingPassengers(this.waitingPassengers);
                
                // Update call indicators to reflect removed preview
                if (data.elevator_name) {
                    this.updateCallsOnly({
                        elevator_name: data.elevator_name,
                        car_calls: this.getCarCallsForElevator(data.elevator_name),
                        hall_calls_up: this.getHallCallsUp(data.elevator_name),
                        hall_calls_down: this.getHallCallsDown(data.elevator_name),
                        move_command_target_floor: this.replayState?.moveCommands?.[data.elevator_name],
                        forced_calls_up: this.replayState?.forcedCalls?.[data.elevator_name] ? Array.from(this.replayState.forcedCalls[data.elevator_name].up) : [],
                        forced_calls_down: this.replayState?.forcedCalls?.[data.elevator_name] ? Array.from(this.replayState.forcedCalls[data.elevator_name].down) : []
                    });
                }
                break;
                
            case 'passenger_alighting':
                // Handle passenger alighting event
                this.addLog('info', `${data.passenger_name} alighted from ${data.elevator_name} at floor ${data.floor}`, message.time);
                break;
            
            case 'hall_call_registered':
                // Handle hall call registration
                this.addLog('warning', `Hall call registered: Floor ${data.floor} ${data.direction}`, message.time);
                break;
            
            case 'hall_call_assignment':
                // Handle hall call assignment
                const assignmentMsg = data.destination 
                    ? `Hall call ${data.floor} ${data.direction} → ${data.destination}F assigned to ${data.elevator}`
                    : `Hall call ${data.floor} ${data.direction} assigned to ${data.elevator}`;
                this.addLog('info', assignmentMsg, message.time);
                
                // DCS: Add car call preview for destination floor
                if (data.destination && data.call_type === 'DCS') {
                    if (!this.replayState.carCallPreviews[data.elevator]) {
                        this.replayState.carCallPreviews[data.elevator] = new Set();
                    }
                    this.replayState.carCallPreviews[data.elevator].add(data.destination);
                }
                
                // Update call indicators (trigger calls_update)
                this.updateCallsOnly({
                    elevator_name: data.elevator,
                    car_calls: this.getCarCallsForElevator(data.elevator),
                    hall_calls_up: this.getHallCallsUp(data.elevator),
                    hall_calls_down: this.getHallCallsDown(data.elevator),
                    move_command_target_floor: this.replayState?.moveCommands?.[data.elevator],
                    forced_calls_up: this.replayState?.forcedCalls?.[data.elevator] ? Array.from(this.replayState.forcedCalls[data.elevator].up) : [],
                    forced_calls_down: this.replayState?.forcedCalls?.[data.elevator] ? Array.from(this.replayState.forcedCalls[data.elevator].down) : []
                });
                break;
            
            case 'hall_call_off':
                // Handle hall call off
                this.addLog('info', `Hall call off: Floor ${data.floor} ${data.direction} [${data.elevator}]`, message.time);
                // Update call indicators
                this.updateCallsOnly({
                    elevator_name: data.elevator,
                    car_calls: this.getCarCallsForElevator(data.elevator),
                    hall_calls_up: this.getHallCallsUp(data.elevator),
                    hall_calls_down: this.getHallCallsDown(data.elevator),
                    move_command_target_floor: this.replayState?.moveCommands?.[data.elevator],
                    forced_calls_up: this.replayState?.forcedCalls?.[data.elevator] ? Array.from(this.replayState.forcedCalls[data.elevator].up) : [],
                    forced_calls_down: this.replayState?.forcedCalls?.[data.elevator] ? Array.from(this.replayState.forcedCalls[data.elevator].down) : []
                });
                break;
            
            case 'car_call_registered':
                // Handle car call registration
                this.addLog('info', `[${data.elevator_name}] Car call to floor ${data.floor}`, message.time);
                
                // DCS: Remove preview when actual car call is registered
                if (this.replayState.carCallPreviews[data.elevator_name]) {
                    this.replayState.carCallPreviews[data.elevator_name].delete(data.floor);
                }
                
                // Update call indicators
                this.updateCallsOnly({
                    elevator_name: data.elevator_name,
                    car_calls: this.getCarCallsForElevator(data.elevator_name),
                    hall_calls_up: this.getHallCallsUp(data.elevator_name),
                    hall_calls_down: this.getHallCallsDown(data.elevator_name),
                    move_command_target_floor: this.replayState?.moveCommands?.[data.elevator_name],
                    forced_calls_up: this.replayState?.forcedCalls?.[data.elevator_name] ? Array.from(this.replayState.forcedCalls[data.elevator_name].up) : [],
                    forced_calls_down: this.replayState?.forcedCalls?.[data.elevator_name] ? Array.from(this.replayState.forcedCalls[data.elevator_name].down) : []
                });
                break;
            
            case 'car_call_off':
                // Handle car call off
                this.addLog('info', `[${data.elevator}] Car call off: Floor ${data.floor}`, message.time);
                // Update call indicators
                this.updateCallsOnly({
                    elevator_name: data.elevator,
                    car_calls: this.getCarCallsForElevator(data.elevator),
                    hall_calls_up: this.getHallCallsUp(data.elevator),
                    hall_calls_down: this.getHallCallsDown(data.elevator),
                    move_command_target_floor: this.replayState?.moveCommands?.[data.elevator],
                    forced_calls_up: this.replayState?.forcedCalls?.[data.elevator] ? Array.from(this.replayState.forcedCalls[data.elevator].up) : [],
                    forced_calls_down: this.replayState?.forcedCalls?.[data.elevator] ? Array.from(this.replayState.forcedCalls[data.elevator].down) : []
                });
                break;
            
            case 'forced_move_command':
                // Handle forced move command
                this.addLog('warning', `[${data.elevator}] Forced move command: Floor ${data.floor} ${data.direction}`, message.time);
                // Update call indicators
                this.updateCallsOnly({
                    elevator_name: data.elevator,
                    car_calls: this.getCarCallsForElevator(data.elevator),
                    hall_calls_up: this.getHallCallsUp(data.elevator),
                    hall_calls_down: this.getHallCallsDown(data.elevator),
                    move_command_target_floor: this.replayState?.moveCommands?.[data.elevator],
                    forced_calls_up: this.replayState?.forcedCalls?.[data.elevator] ? Array.from(this.replayState.forcedCalls[data.elevator].up) : [],
                    forced_calls_down: this.replayState?.forcedCalls?.[data.elevator] ? Array.from(this.replayState.forcedCalls[data.elevator].down) : []
                });
                break;
            
            case 'forced_call_off':
                // Handle forced call off
                this.addLog('info', `[${data.elevator}] Forced call off: Floor ${data.floor} ${data.direction}`, message.time);
                // Update call indicators
                this.updateCallsOnly({
                    elevator_name: data.elevator,
                    car_calls: this.getCarCallsForElevator(data.elevator),
                    hall_calls_up: this.getHallCallsUp(data.elevator),
                    hall_calls_down: this.getHallCallsDown(data.elevator),
                    move_command_target_floor: this.replayState?.moveCommands?.[data.elevator],
                    forced_calls_up: this.replayState?.forcedCalls?.[data.elevator] ? Array.from(this.replayState.forcedCalls[data.elevator].up) : [],
                    forced_calls_down: this.replayState?.forcedCalls?.[data.elevator] ? Array.from(this.replayState.forcedCalls[data.elevator].down) : []
                });
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
        
        // Get num_floors from elevator state if not provided
        const elevatorState = this.elevators.get(elevator_name);
        const num_floors = data.num_floors || elevatorState?.num_floors || this.numFloors || 10;
        
        // Update call indicators using new grid layout
        const callData = {
            ...data,
            num_floors: num_floors,
            car_calls: car_calls || [],
            hall_calls_up: hall_calls_up || [],
            hall_calls_down: hall_calls_down || []
        };
        
        this.updateCallIndicators(elevator_name, callData);
    }
    
    updateElevator(data) {
        const { elevator_name, floor, state, direction, passengers, capacity } = data;
        
        // Store elevator state
        this.elevators.set(elevator_name, data);
        
        // Ensure grid layout is initialized
        if (!document.getElementById('shared-floor-labels').hasChildNodes()) {
            this.initializeGridLayout(data.num_floors || 10);
        }
        
        // Ensure Hall column exists (create it first if this is the first elevator)
        if (!document.getElementById('column-Hall')) {
            const hallData = {
                elevator_name: 'Hall',
                floor: 1,
                state: 'IDLE',
                direction: 'NO_DIRECTION',
                passengers: 0,
                capacity: 0,
                num_floors: data.num_floors || 10,
                car_calls: [],
                hall_calls_up: [],
                hall_calls_down: []
            };
            this.createElevatorColumn('Hall', hallData);
        }
        
        // Create or update elevator column
        let column = document.getElementById(`column-${elevator_name}`);
        if (!column) {
            column = this.createElevatorColumn(elevator_name, data);
        }
        
        // Update status in header (Hallの場合はスキップ)
        if (elevator_name !== 'Hall') {
            const statusElement = document.getElementById(`status-${elevator_name}`);
            if (statusElement) {
                statusElement.textContent = `${this.getDirectionIcon(direction || 'NO_DIRECTION')} ${this.shortenState(state)}`;
            }
        }
        
        // Update capacity display
        if (elevator_name !== 'Hall') {
            this.updateCapacityDisplay(elevator_name, passengers || 0, capacity || 50);
        }
        
        // Update elevator car position
        const car = document.getElementById(`car-${elevator_name}`);
        if (car) {
            const numFloors = data.num_floors || this.numFloors || 10;
            const floorPosition = ((floor - 1) / numFloors) * 100;
            car.style.bottom = `${floorPosition}%`;
            
            // Update door animation
            if (state === 'STOPPING') {
                car.classList.remove('door-closed');
                car.classList.add('door-open');
            } else {
                car.classList.remove('door-open');
                car.classList.add('door-closed');
            }
        }
        
        // Update call indicators (car calls, hall calls)
        this.updateCallIndicators(elevator_name, data);
    }
    
    updateCallIndicators(elevatorName, data) {
        const numFloors = data.num_floors || this.numFloors || 10;
        
        // Clear all floor icons first (left, center, right)
        for (let floor = 1; floor <= numFloors; floor++) {
            const leftContainer = document.getElementById(`floor-icons-left-${elevatorName}-${floor}`);
            const centerContainer = document.getElementById(`floor-icons-center-${elevatorName}-${floor}`);
            const rightContainer = document.getElementById(`floor-icons-right-${elevatorName}-${floor}`);
            if (leftContainer) leftContainer.innerHTML = '';
            if (centerContainer) centerContainer.innerHTML = '';
            if (rightContainer) rightContainer.innerHTML = '';
        }
        
        // Add hall call indicators (LEFT side, vertical: ▲ on top, ▼ on bottom)
        if (data.hall_calls_up && data.hall_calls_up.length > 0) {
            data.hall_calls_up.forEach(floor => {
                const leftContainer = document.getElementById(`floor-icons-left-${elevatorName}-${floor}`);
                if (leftContainer) {
                    const indicator = document.createElement('span');
                    indicator.className = 'call-indicator hall-call-up-indicator';
                    indicator.textContent = '▲';
                    indicator.title = `Hall call UP: ${floor}F`;
                    leftContainer.appendChild(indicator);
                }
            });
        }
        
        if (data.hall_calls_down && data.hall_calls_down.length > 0) {
            data.hall_calls_down.forEach(floor => {
                const leftContainer = document.getElementById(`floor-icons-left-${elevatorName}-${floor}`);
                if (leftContainer) {
                    const indicator = document.createElement('span');
                    indicator.className = 'call-indicator hall-call-down-indicator';
                    indicator.textContent = '▼';
                    indicator.title = `Hall call DOWN: ${floor}F`;
                    leftContainer.appendChild(indicator);
                }
            });
        }
        
        // Add forced move command indicators (CENTER, orange filled square with direction)
        if (data.forced_calls_up && data.forced_calls_up.length > 0) {
            data.forced_calls_up.forEach(floor => {
                const centerContainer = document.getElementById(`floor-icons-center-${elevatorName}-${floor}`);
                if (centerContainer) {
                    const indicator = document.createElement('span');
                    indicator.className = 'call-indicator forced-move-command-indicator';
                    indicator.innerHTML = '◆<span class="direction-arrow">↑</span>';
                    indicator.title = `Forced move command: ${floor}F UP`;
                    centerContainer.appendChild(indicator);
                }
            });
        }
        
        if (data.forced_calls_down && data.forced_calls_down.length > 0) {
            data.forced_calls_down.forEach(floor => {
                const centerContainer = document.getElementById(`floor-icons-center-${elevatorName}-${floor}`);
                if (centerContainer) {
                    const indicator = document.createElement('span');
                    indicator.className = 'call-indicator forced-move-command-indicator';
                    indicator.innerHTML = '◆<span class="direction-arrow">↓</span>';
                    indicator.title = `Forced move command: ${floor}F DOWN`;
                    centerContainer.appendChild(indicator);
                }
            });
        }
        
        // Add move command indicator (CENTER, green empty square, no direction)
        if (data.move_command_target_floor && elevatorName !== 'Hall') {
            const floor = data.move_command_target_floor;
            const centerContainer = document.getElementById(`floor-icons-center-${elevatorName}-${floor}`);
            if (centerContainer) {
                const indicator = document.createElement('span');
                indicator.className = 'call-indicator move-command-indicator';
                indicator.textContent = '□';
                indicator.title = `Move command: ${floor}F`;
                centerContainer.appendChild(indicator);
            }
        }
        
        // Build a map of which floors have which indicators on the RIGHT side
        const rightIndicators = {}; // {floor: {preview: bool, carCall: bool}}
        
        // Check for car call previews (DCS destination previews)
        if (this.replayState.carCallPreviews[elevatorName]) {
            const previews = Array.from(this.replayState.carCallPreviews[elevatorName]);
            previews.forEach(floor => {
                // Skip if already registered as regular car call
                if (data.car_calls && data.car_calls.includes(floor)) {
                    return;
                }
                if (!rightIndicators[floor]) rightIndicators[floor] = {};
                rightIndicators[floor].preview = true;
            });
        }
        
        // Check for car calls
        if (data.car_calls && data.car_calls.length > 0) {
            data.car_calls.forEach(floor => {
                if (!rightIndicators[floor]) rightIndicators[floor] = {};
                rightIndicators[floor].carCall = true;
            });
        }
        
        // Add indicators with absolute positioning (no spacers needed)
        Object.keys(rightIndicators).forEach(floor => {
                const rightContainer = document.getElementById(`floor-icons-right-${elevatorName}-${floor}`);
            if (!rightContainer) return;
            
            const indicators = rightIndicators[floor];
            
            // Top position: Car call preview (■)
            if (indicators.preview) {
                const previewIndicator = document.createElement('span');
                previewIndicator.className = 'call-indicator car-call-preview-indicator';
                previewIndicator.textContent = '■';
                previewIndicator.title = `Car call preview (DCS destination): ${floor}F`;
                rightContainer.appendChild(previewIndicator);
                }
            
            // Bottom position: Car call (●)
            if (indicators.carCall) {
                const carCallIndicator = document.createElement('span');
                carCallIndicator.className = 'call-indicator car-call-indicator';
                carCallIndicator.textContent = '●';
                carCallIndicator.title = `Car call: ${floor}F`;
                rightContainer.appendChild(carCallIndicator);
        }
        });
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
        const { floor, state, passengers, capacity, num_floors, car_calls, hall_calls_up, hall_calls_down, direction } = data;
        
        // Get direction icon
        let directionIcon = '';
        if (direction === 'UP') {
            directionIcon = '↑ ';
        } else if (direction === 'DOWN') {
            directionIcon = '↓ ';
        } else if (direction === 'NO_DIRECTION') {
            directionIcon = '○ ';
        }
        
        // Shorten state names for display
        let displayState = state;
        if (state === 'MOVING') {
            displayState = 'MOVE';
        } else if (state === 'STOPPING') {
            displayState = 'STOP';
        } else if (state === 'DECELERATING') {
            displayState = 'DECEL';
        }
        // IDLE stays as IDLE
        
        // Update state badge with direction icon
        const stateBadge = element.querySelector('.elevator-state');
        stateBadge.textContent = directionIcon + displayState;
        stateBadge.className = `elevator-state state-${state.toLowerCase()}`;
        
        
        // Dynamically set shaft height based on number of floors
        const elevatorShaft = element.querySelector('.elevator-shaft');
        const floorLabelsContainer = element.querySelector('.floor-labels');
        const shaftContainer = element.querySelector('.elevator-shaft-container');
        const carHeight = 25; // px (must match CSS .elevator-car height)
        
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
        
        // Render car call indicators (◎ purple, small) and previews (■ orange, DCS)
        this.renderCarCalls(elevatorShaft, car_calls || [], num_floors, elevatorName);
        
        // Render hall call indicators (△ UP green, ▽ DOWN orange)
        this.renderHallCalls(elevatorShaft, hall_calls_up || [], hall_calls_down || [], num_floors);
        
        // Render passenger box
        this.renderPassengerBox(element, passengers, capacity);
        
        // Render waiting passengers
        this.renderWaitingPassengers(element, num_floors);
    }
    
    renderCarCalls(shaftElement, carCalls, numFloors, elevatorName = null) {
        // Remove existing car call indicators (both regular and preview)
        const existing = shaftElement.querySelectorAll('.car-call-indicator, .car-call-preview-indicator');
        existing.forEach(el => el.remove());
        
        if (!numFloors) return;
        
        const floorHeight = 100 / numFloors; // Height of each floor slot (%)
        
        // Add regular car call indicators
        if (carCalls && carCalls.length > 0) {
        carCalls.forEach(targetFloor => {
            const indicator = document.createElement('div');
            indicator.className = 'car-call-indicator';
            indicator.textContent = '●';
            indicator.title = `Car call to floor ${targetFloor}`;
            
            // Position indicator at the CENTER of the target floor
            const bottomPercent = ((targetFloor - 1) / numFloors) * 100 + (floorHeight / 2);
            indicator.style.bottom = `${bottomPercent}%`;
            
            shaftElement.appendChild(indicator);
        });
        }
        
        // Note: Preview car call indicators are handled by updateCallIndicators (grid layout)
        // This renderCarCalls is for old layout only, so we don't render previews here
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
    
    updateWaitingPassengersFromDoorEvent(floor, waitingPassengerNames) {
        // Update waiting passengers based on actual queue state from door event
        // waitingPassengerNames is an array of passenger names waiting at this floor
        
        if (!this.waitingPassengers[floor]) {
            this.waitingPassengers[floor] = { UP: 0, DOWN: 0 };
        }
        
        // Set the count directly from the queue (this is the ground truth)
        // Note: We don't know the direction split from door event alone,
        // so we'll just show total count in UP direction for now
        const totalWaiting = waitingPassengerNames ? waitingPassengerNames.length : 0;
        
        // For now, show all waiting passengers as "waiting" (use UP direction for display)
        this.waitingPassengers[floor].UP = totalWaiting;
        this.waitingPassengers[floor].DOWN = 0;
        
        // Trigger visual update
        this.updateWaitingPassengers(this.waitingPassengers);
    }
    
    updateWaitingPassengers(waitingData) {
        console.log('[DEBUG] updateWaitingPassengers called with data:', JSON.stringify(waitingData));
        this.waitingPassengers = waitingData;
        
        const numFloors = this.numFloors || 10;
        
        // Clear all Hall floor center icons first
        for (let floor = 1; floor <= numFloors; floor++) {
            const centerContainer = document.getElementById(`floor-icons-center-Hall-${floor}`);
            if (centerContainer) {
                centerContainer.innerHTML = '';
            }
        }
        
        // Add waiting passenger indicators to Hall floor center icons (vertical layout)
        for (const [floor, directions] of Object.entries(waitingData)) {
            const floorNum = parseInt(floor);
            const centerContainer = document.getElementById(`floor-icons-center-Hall-${floorNum}`);
            
            if (centerContainer) {
                if (directions.UP > 0) {
                    const indicator = document.createElement('span');
                    indicator.className = 'waiting-passenger-indicator waiting-up';
                    indicator.textContent = `${directions.UP}👤▲`;
                    indicator.title = `${directions.UP} passengers waiting for UP`;
                    centerContainer.appendChild(indicator);
                }
                
                if (directions.DOWN > 0) {
                    const indicator = document.createElement('span');
                    indicator.className = 'waiting-passenger-indicator waiting-down';
                    indicator.textContent = `${directions.DOWN}👤▼`;
                    indicator.title = `${directions.DOWN} passengers waiting for DOWN`;
                    centerContainer.appendChild(indicator);
                }
            }
        }
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
                            // Note: Waiting passengers are managed by passenger/waiting and passenger/boarding events
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
        
        // Determine category and add as data attribute
        const category = this.getEventCategory(message);
        logEntry.dataset.category = category;
        
        // Apply filter immediately
        if (!this.eventFilters[category]) {
            logEntry.style.display = 'none';
        }
        
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
    
    handleElevatorStatusUpdate(data, time) {
        const elevator = data.elevator_name || data.elevator;
        const currentFloor = data.floor;
        const currentState = data.state;
        const direction = data.direction;
        const passengers = data.passengers;
        
        if (!elevator || currentFloor === undefined || !currentState) {
            return; // Invalid data
        }
        
        // Initialize tracking if needed
        if (!this.elevatorStates[elevator]) {
            this.elevatorStates[elevator] = {
                floor: currentFloor,
                state: currentState,
                direction: direction
            };
            // Log initial state
            this.addLog('info', `[${elevator}] Initial state: ${currentState} at floor ${currentFloor}, ${direction}, ${passengers} pax`, time);
            return;
        }
        
        const lastState = this.elevatorStates[elevator];
        
        // Check for state transitions
        if (lastState.state !== currentState) {
            // Important state transitions to log
            
            // Movement started
            if (currentState === 'MOVING' && lastState.state !== 'MOVING') {
                this.addLog('info', `[${elevator}] ▲ Started moving ${direction} from floor ${currentFloor}`, time);
            }
            
            // Arrived at floor (entered STOPPING state at a new floor)
            if (currentState === 'STOPPING' && lastState.state === 'DECELERATING') {
                this.addLog('info', `[${elevator}] ✓ Arrived at floor ${currentFloor} (${direction})`, time);
            }
            
            // Became idle
            if (currentState === 'IDLE' && lastState.state !== 'IDLE') {
                this.addLog('info', `[${elevator}] ○ Now IDLE at floor ${currentFloor}`, time);
            }
            
            // Decelerating (approaching floor)
            if (currentState === 'DECELERATING' && lastState.state === 'MOVING') {
                this.addLog('info', `[${elevator}] ⊙ Decelerating, approaching floor ${currentFloor}`, time);
            }
        }
        
        // Check for floor changes during movement
        if (lastState.floor !== currentFloor && currentState === 'MOVING') {
            this.addLog('info', `[${elevator}] → Passing floor ${currentFloor} ${direction}`, time);
        }
        
        // Update stored state
        this.elevatorStates[elevator] = {
            floor: currentFloor,
            state: currentState,
            direction: direction
        };
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
            
            // Update chart colors for dark mode
            this.updateChartColors(isDarkMode);
            
            // Save preference
            localStorage.setItem('darkMode', isDarkMode);
        });
    }
    
    updateChartColors(isDarkMode) {
        if (!this.waitTimeChart) return;
        
        const textColor = isDarkMode ? '#e2e8f0' : '#1e293b';
        const gridColor = isDarkMode ? 'rgba(148, 163, 184, 0.1)' : 'rgba(0, 0, 0, 0.1)';
        
        // Update chart options
        this.waitTimeChart.options.plugins.legend.labels.color = textColor;
        this.waitTimeChart.options.scales.x.title.color = textColor;
        this.waitTimeChart.options.scales.x.ticks.color = textColor;
        this.waitTimeChart.options.scales.x.grid.color = gridColor;
        this.waitTimeChart.options.scales.y.title.color = textColor;
        this.waitTimeChart.options.scales.y.ticks.color = textColor;
        this.waitTimeChart.options.scales.y.grid.color = gridColor;
        
        // Re-render chart
        this.waitTimeChart.update();
        
        console.log('[Chart] Colors updated for dark mode:', isDarkMode);
    }
    
    initializeEventFilters() {
        // Get all filter checkboxes
        const filterCheckboxes = document.querySelectorAll('.event-filter');
        
        // Set initial state based on eventFilters
        filterCheckboxes.forEach(checkbox => {
            const category = checkbox.dataset.category;
            checkbox.checked = this.eventFilters[category];
        });
        
        // Add event listeners to checkboxes
        filterCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const category = e.target.dataset.category;
                this.eventFilters[category] = e.target.checked;
                this.applyEventFilters();
            });
        });
        
        // Select All button
        const btnSelectAll = document.getElementById('btn-select-all-filters');
        btnSelectAll.addEventListener('click', () => {
            Object.keys(this.eventFilters).forEach(category => {
                this.eventFilters[category] = true;
            });
            filterCheckboxes.forEach(checkbox => {
                checkbox.checked = true;
            });
            this.applyEventFilters();
        });
        
        // Deselect All button
        const btnDeselectAll = document.getElementById('btn-deselect-all-filters');
        btnDeselectAll.addEventListener('click', () => {
            Object.keys(this.eventFilters).forEach(category => {
                this.eventFilters[category] = false;
            });
            filterCheckboxes.forEach(checkbox => {
                checkbox.checked = false;
            });
            this.applyEventFilters();
        });
    }
    
    getEventCategory(message) {
        // Determine event category from message content
        const lowerMessage = message.toLowerCase();
        
        if (lowerMessage.includes('door') || lowerMessage.includes('opening') || lowerMessage.includes('closing')) {
            return 'door';
        }
        if (lowerMessage.includes('hall call')) {
            return 'hall';
        }
        if (lowerMessage.includes('car call')) {
            return 'car';
        }
        if (lowerMessage.includes('waiting') || lowerMessage.includes('boarded') || lowerMessage.includes('alighted')) {
            return 'passenger';
        }
        if (lowerMessage.includes('forced')) {
            return 'command';
        }
        // Elevator status: movement, state changes, arrival, etc.
        if (lowerMessage.includes('moving') || 
            lowerMessage.includes('arrived') || 
            lowerMessage.includes('idle') ||
            lowerMessage.includes('decelerating') ||
            lowerMessage.includes('passing') ||
            lowerMessage.includes('started') ||
            lowerMessage.includes('initial state') ||
            message.includes('▲') || 
            message.includes('✓') || 
            message.includes('○') || 
            message.includes('⊙') || 
            message.includes('→')) {
            return 'elevator';
        }
        // Default to elevator for other messages
        return 'elevator';
    }
    
    applyEventFilters() {
        // Apply filters to all existing log entries
        const logEntries = this.logContainer.querySelectorAll('.log-entry');
        
        logEntries.forEach(entry => {
            const category = entry.dataset.category;
            if (category && this.eventFilters[category] !== undefined) {
                entry.style.display = this.eventFilters[category] ? '' : 'none';
            }
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
        
        // DO NOT auto-start live polling
        // User should manually start a simulation to generate simulation_log.jsonl
        this.addLog('system', 'Live mode: Ready. Start a simulation to begin.');
        this.updateConnectionStatus('disconnected', 'Ready');
        
        this.currentMode = 'live';
    }
    
    startLiveFilePolling() {
        console.log('[App] Starting live file polling...');
        
        // Create LiveFileEventSource (filename, apiBaseUrl, pollInterval)
        this.fileEventSource = new LiveFileEventSource(
            'simulation_log.jsonl',
            this.API_BASE_URL,
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
        
        // Stop live polling if active
        if (this.fileEventSource) {
            console.log('[App] Stopping existing event source...');
            this.fileEventSource.stop();
            // Wait a bit to ensure polling stops completely
            await new Promise(resolve => setTimeout(resolve, 200));
            this.fileEventSource = null;
        }
        
        // Disconnect WebSocket
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        
        // Show/hide panels
        document.getElementById('playback-controls').style.display = 'block';
        
        // Clear visualization COMPLETELY
        console.log('[App] Clearing all state for Replay mode...');
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
            // Initialize badge with default value (will be updated when metadata is loaded)
            this.updateCallSystemBadge('TRADITIONAL');
            
            await this.switchToReplayMode(filename);
            
            // Create file event source
            this.fileEventSource = new FileEventSource(this.API_BASE_URL);
            
            // Subscribe to events
            this.fileEventSource.subscribe((event) => this.handleReplayEvent(event));
            
            // Load file
            const info = await this.fileEventSource.loadFile(filename);
            this.addLog('system', `Loaded ${info.eventCount} events from ${filename}`);
            
            // Ready to play (do NOT auto-play)
            this.isPlaying = false;
            this.updatePlayPauseButton();
            this.updateConnectionStatus('paused', 'Ready - Press Play');
            
        } catch (error) {
            console.error('[App] Error loading replay file:', error);
            this.addLog('error', `Failed to load ${filename}: ${error.message}`);
            this.updateConnectionStatus('error', 'Error');
        }
    }
    
    handleReplayEvent(event) {
        // Convert FileEventSource events to the format expected by handleMessage
        if (event.type === 'metadata') {
            // Handle metadata and update call system badge
            console.log('[Replay] Metadata:', event.data);
            if (event.data && event.data.config && event.data.config.call_system_type) {
                this.updateCallSystemBadge(event.data.config.call_system_type);
            }
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
            case 'metadata':
                // Handle metadata event (simulation configuration)
                if (event.data && event.data.config) {
                    // Use setTimeout to ensure DOM is ready
                    setTimeout(() => {
                        this.updateCallSystemBadge(event.data.config.call_system_type);
                    }, 100);
                }
                return null; // Don't pass metadata as a regular message
            
            case 'elevator_status':
                // Track forced_calls and move_commands in replay state
                const elevatorName = event.data.elevator;
                
                // Initialize forced calls tracking if needed
                if (!this.replayState.forcedCalls[elevatorName]) {
                    this.replayState.forcedCalls[elevatorName] = {
                        up: new Set(),
                        down: new Set()
                    };
                }
                
                // Initialize move commands tracking if needed
                if (this.replayState.moveCommands[elevatorName] === undefined) {
                    this.replayState.moveCommands[elevatorName] = null;
                }
                
                // Note: forced_calls are now managed by forced_move_command (ON) and forced_call_off (OFF) events
                // No need to process from elevator_status
                
                // Track move command (set when not null/undefined)
                if (event.data.move_command_target_floor !== null && event.data.move_command_target_floor !== undefined) {
                    this.replayState.moveCommands[elevatorName] = event.data.move_command_target_floor;
                } else if (event.data.move_command_target_floor === null) {
                    // Explicitly null means cleared
                    delete this.replayState.moveCommands[elevatorName];
                }
                
                return {
                    type: 'elevator_update',
                    data: {
                        elevator_name: elevatorName,
                        floor: event.data.floor,
                        state: event.data.state,
                        direction: event.data.direction || 'NO_DIRECTION',
                        passengers: event.data.passengers,
                        capacity: event.data.capacity,
                        num_floors: 10, // Default
                        car_calls: this.getCarCallsForElevator(elevatorName),
                        hall_calls_up: this.getHallCallsUp(elevatorName),
                        hall_calls_down: this.getHallCallsDown(elevatorName),
                        move_command_target_floor: this.replayState.moveCommands[elevatorName],
                        forced_calls_up: Array.from(this.replayState.forcedCalls[elevatorName].up),
                        forced_calls_down: Array.from(this.replayState.forcedCalls[elevatorName].down)
                    }
                };
            
            case 'hall_call_registered':
                // Return hall_call_registered event for event log
                return {
                    type: 'hall_call_registered',
                    data: {
                        floor: event.data.floor,
                        direction: event.data.direction
                    },
                    time: event.time
                };
            
            case 'hall_call_assignment':
                // Track hall call assignment
                const elevator = event.data.elevator;
                const floor = event.data.floor;
                const direction = event.data.direction;
                const destination = event.data.destination; // DCS destination
                const call_type = event.data.call_type; // DCS or Traditional
                
                if (!this.replayState) {
                    this.replayState = {
                        hallCalls: {},
                        carCalls: {},
                        carCallPreviews: {}
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
                
                // DCS: Add car call preview for destination floor
                if (destination && call_type === 'DCS') {
                    if (!this.replayState.carCallPreviews[elevator]) {
                        this.replayState.carCallPreviews[elevator] = new Set();
                    }
                    this.replayState.carCallPreviews[elevator].add(destination);
                }
                
                // Return hall_call_assignment event for event log
                return {
                    type: 'hall_call_assignment',
                    data: {
                        elevator: elevator,
                        floor: floor,
                        direction: direction,
                        destination: destination,
                        call_type: call_type
                    },
                    time: event.time
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
                
                // Return hall_call_off event for event log
                return {
                    type: 'hall_call_off',
                    data: {
                        elevator: offElevator,
                        floor: offFloor,
                        direction: offDirection
                    },
                    time: event.time
                };
            
            case 'car_call_registered':
                // Track car call
                const carElevator = event.data.elevator;
                const carFloor = event.data.floor;
                
                if (!this.replayState) {
                    this.replayState = {
                        hallCalls: {},
                        carCalls: {},
                        carCallPreviews: {}
                    };
                }
                
                if (!this.replayState.carCalls[carElevator]) {
                    this.replayState.carCalls[carElevator] = new Set();
                }
                
                this.replayState.carCalls[carElevator].add(carFloor);
                
                // DCS: Remove preview when actual car call is registered
                if (this.replayState.carCallPreviews[carElevator]) {
                    this.replayState.carCallPreviews[carElevator].delete(carFloor);
                }
                
                // Return car_call_registered event for event log
                return {
                    type: 'car_call_registered',
                    data: {
                        elevator_name: carElevator,
                        floor: carFloor
                    },
                    time: event.time
                };
            
            case 'car_call_off':
                // Remove car call
                const carOffElevator = event.data.elevator;
                const carOffFloor = event.data.floor;
                
                if (this.replayState && this.replayState.carCalls[carOffElevator]) {
                    this.replayState.carCalls[carOffElevator].delete(carOffFloor);
                }
                
                // Return car_call_off event for event log
                return {
                    type: 'car_call_off',
                    data: {
                        elevator: carOffElevator,
                        floor: carOffFloor
                    },
                    time: event.time
                };
            
            case 'door_event':
                // Handle door events
                return {
                    type: 'event',
                    data: {
                        event_type: event.data.event,
                        elevator_name: event.data.elevator,
                        floor: event.data.floor,
                        waiting_passengers: event.data.waiting_passengers,  // Include waiting passengers for queue-based display
                        timestamp: event.time
                    }
                };
            
            case 'passenger_waiting':
                // Return event message for metrics
                // NOTE: Count will be updated in handleMessage to avoid double counting
                return {
                    type: 'passenger_waiting',
                    data: event.data,
                    time: event.time  // Add time for consistency
                };
            
            case 'passenger_boarding':
                // Return event message for metrics
                // NOTE: Count will be updated in handleMessage to avoid double counting
                return {
                    type: 'passenger_boarding',
                    data: event.data,
                    time: event.time  // Add time for chart
                };
            
            case 'passenger_alighting':
                // Return event message for metrics (trips counting)
                return {
                    type: 'passenger_alighting',
                    data: event.data,
                    time: event.time  // Add time for consistency
                };
            
            case 'forced_move_command':
                // Add forced call to replay state (ON event)
                const onElevator = event.data.elevator;
                const onFloor = event.data.floor;
                const onDirection = event.data.direction;
                
                if (!this.replayState.forcedCalls[onElevator]) {
                    this.replayState.forcedCalls[onElevator] = {
                        up: new Set(),
                        down: new Set()
                    };
                }
                
                if (onDirection === 'UP') {
                    this.replayState.forcedCalls[onElevator].up.add(onFloor);
                } else {
                    this.replayState.forcedCalls[onElevator].down.add(onFloor);
                }
                
                console.log(`[Replay] forced_move_command: ${onElevator} floor ${onFloor} ${onDirection} - ON`);
                
                // Return forced_move_command event for event log
                return {
                    type: 'forced_move_command',
                    data: {
                        elevator: onElevator,
                        floor: onFloor,
                        direction: onDirection
                    },
                    time: event.time
                };
            
            case 'forced_call_off':
                // Remove forced call from replay state (OFF event)
                const forcedOffElevator = event.data.elevator;
                const forcedOffFloor = event.data.floor;
                const forcedOffDirection = event.data.direction;
                
                if (this.replayState && this.replayState.forcedCalls[forcedOffElevator]) {
                    if (forcedOffDirection === 'UP') {
                        this.replayState.forcedCalls[forcedOffElevator].up.delete(forcedOffFloor);
                    } else {
                        this.replayState.forcedCalls[forcedOffElevator].down.delete(forcedOffFloor);
                    }
                }
                
                console.log(`[Replay] forced_call_off: ${forcedOffElevator} floor ${forcedOffFloor} ${forcedOffDirection} - OFF`);
                
                // Return forced_call_off event for event log
                return {
                    type: 'forced_call_off',
                    data: {
                        elevator: forcedOffElevator,
                        floor: forcedOffFloor,
                        direction: forcedOffDirection
                    },
                    time: event.time
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
    
    // ==========================================
    // Tab Management
    // ==========================================
    
    initializeTabs() {
        const tabButtons = document.querySelectorAll('.tab-nav-btn');
        
        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const targetTab = button.getAttribute('data-tab');
                this.switchTab(targetTab);
            });
        });
    }
    
    switchTab(tabName) {
        // Remove active class from all buttons and panes
        document.querySelectorAll('.tab-nav-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.remove('active');
        });
        
        // Add active class to selected button and pane
        const selectedButton = document.querySelector(`.tab-nav-btn[data-tab="${tabName}"]`);
        const selectedPane = document.getElementById(`tab-${tabName}`);
        
        if (selectedButton && selectedPane) {
            selectedButton.classList.add('active');
            selectedPane.classList.add('active');
        }
    }
    
    // ==========================================
    // Metrics Management
    // ==========================================
    
    updateMetrics(message) {
        // Note: message structure from _add_event_log has fields nested in 'data'
        // Message structure: { time: X, type: 'event_type', data: {...} }
        const eventType = message.type || message.event_type;  // Support both formats
        const eventData = message.data || message;  // Data might be nested or flat
        
        // Track total passengers from passenger_waiting events
        if (eventType === 'passenger_waiting') {
            console.log('[Metrics] passenger_waiting event received:', message);
            this.metrics.totalPassengers++;
        }
        
        // Track wait time from passenger_boarding events
        if (eventType === 'passenger_boarding') {
            console.log('[Metrics] passenger_boarding event received:', message);
            const waitTime = eventData.wait_time || 0;
            console.log('[Metrics] Wait time:', waitTime);
            this.metrics.totalWaitTime += waitTime;
            this.metrics.maxWaitTime = Math.max(this.metrics.maxWaitTime, waitTime);
            this.metrics.boardingCount++;  // Count passengers who boarded
            
            // Add wait time to chart bucket
            this.addWaitTimeToChart(waitTime, message.time || this.simulationTime);
        }
        
        // Track occupancy from elevator_update events
        if (eventType === 'elevator_update') {
            const passengers = eventData.passengers || 0;
            const capacity = eventData.capacity || 50;
            if (capacity > 0) {
                const occupancy = (passengers / capacity) * 100;
                this.metrics.totalOccupancy += occupancy;
                this.metrics.occupancyCount++;
            }
        }
        
        // Track journey metrics from passenger_alighting events
        if (eventType === 'passenger_alighting') {
            // Count completed trips (each passenger alighting completes a trip)
            this.metrics.totalTrips++;
            console.log('[Metrics] passenger_alighting event - Total trips:', this.metrics.totalTrips);
            
            // Performance metrics: Count trips per elevator
            const elevator = eventData.elevator_name || eventData.elevator;
            if (elevator) {
                this.performanceMetrics.totalTrips++;
                this.performanceMetrics.elevatorTrips[elevator] = (this.performanceMetrics.elevatorTrips[elevator] || 0) + 1;
            }
            
            // Optional: Track riding time, total journey time, etc.
            // Can be used for future metrics
            const ridingTime = eventData.riding_time || 0;
            const totalJourneyTime = eventData.total_journey_time || 0;
            // Store for future use if needed
        }
        
        // Performance metrics: Track hall call registration
        if (eventType === 'hall_call_registered') {
            const callKey = `${eventData.floor}_${eventData.direction}`;
            this.performanceMetrics.hallCalls.push({
                floor: eventData.floor,
                direction: eventData.direction,
                registeredTime: message.time || this.simulationTime,
                key: callKey
            });
        }
        
        // Performance metrics: Calculate response time from passenger boarding
        if (eventType === 'passenger_boarding') {
            const floor = eventData.floor;
            const direction = eventData.direction;
            const callKey = `${floor}_${direction}`;
            const boardingTime = message.time || this.simulationTime;
            
            // Find the matching hall call
            const hallCallIndex = this.performanceMetrics.hallCalls.findIndex(call => call.key === callKey);
            if (hallCallIndex >= 0) {
                const hallCall = this.performanceMetrics.hallCalls[hallCallIndex];
                const responseTime = boardingTime - hallCall.registeredTime;
                this.performanceMetrics.responseTimes.push(responseTime);
                
                // Count long responses (>60s)
                if (responseTime > 60) {
                    this.performanceMetrics.longResponseCount++;
                }
                
                // Remove this hall call from tracking
                this.performanceMetrics.hallCalls.splice(hallCallIndex, 1);
            }
        }
        
        // Performance metrics: Count door operations
        if (eventType === 'door_event' || (eventType === 'event' && eventData.event_type)) {
            const doorEventType = eventData.event_type || eventData.event;
            // Count DOOR_OPENING_COMPLETE as one operation (open + close cycle counted when open)
            if (doorEventType === 'DOOR_OPENING_COMPLETE' || doorEventType === 'DOOR_OPENED') {
                this.performanceMetrics.doorOperations++;
            }
        }
        
        // Performance metrics: Track elevator movement distance
        // Only count when elevator arrives at a new floor (state becomes STOPPING)
        if (eventType === 'elevator_update' || eventType === 'elevator_status') {
            const elevator = eventData.elevator_name || eventData.elevator;
            const currentFloor = eventData.floor;
            const state = eventData.state;
            
            if (elevator && currentFloor !== undefined) {
                // Initialize if needed
                if (!this.performanceMetrics.elevatorDistances[elevator]) {
                    this.performanceMetrics.elevatorDistances[elevator] = 0;
                    this.performanceMetrics.elevatorTrips[elevator] = this.performanceMetrics.elevatorTrips[elevator] || 0;
                }
                
                // Track last position for all states
                if (!this.performanceMetrics.lastFloors[elevator]) {
                    this.performanceMetrics.lastFloors[elevator] = currentFloor;
                }
                
                // Calculate distance only when arriving at a floor (STOPPING state)
                if (state === 'STOPPING' && this.performanceMetrics.lastFloors[elevator] !== currentFloor) {
                    const distance = Math.abs(currentFloor - this.performanceMetrics.lastFloors[elevator]);
                    this.performanceMetrics.elevatorDistances[elevator] += distance;
                    this.performanceMetrics.lastFloors[elevator] = currentFloor;
                    console.log(`[Performance] ${elevator} moved ${distance} floors to floor ${currentFloor}. Total: ${this.performanceMetrics.elevatorDistances[elevator]}`);
                }
            }
        }
        
        // Update UI
        this.refreshMetricsUI();
        this.updatePerformanceMonitor();
    }
    
    refreshMetricsUI() {
        // Total passengers
        document.getElementById('metric-total-passengers').textContent = 
            this.metrics.totalPassengers;
        
        // Average wait time (use boardingCount instead of totalPassengers)
        const avgWaitTime = this.metrics.boardingCount > 0 
            ? (this.metrics.totalWaitTime / this.metrics.boardingCount).toFixed(1)
            : '0.0';
        document.getElementById('metric-avg-wait-time').textContent = 
            `${avgWaitTime}s`;
        
        // Max wait time
        document.getElementById('metric-max-wait-time').textContent = 
            `${this.metrics.maxWaitTime.toFixed(1)}s`;
        
        // Average occupancy
        const avgOccupancy = this.metrics.occupancyCount > 0
            ? (this.metrics.totalOccupancy / this.metrics.occupancyCount).toFixed(1)
            : '0.0';
        document.getElementById('metric-avg-occupancy').textContent = 
            `${avgOccupancy}%`;
        
        // Total trips (completed passenger journeys)
        document.getElementById('metric-total-trips').textContent = 
            this.metrics.totalTrips;
    }
    
    updatePerformanceMonitor() {
        // Calculate average response time
        const responseTimes = this.performanceMetrics.responseTimes;
        const avgResponseTime = responseTimes.length > 0
            ? (responseTimes.reduce((sum, time) => sum + time, 0) / responseTimes.length).toFixed(1)
            : '-';
        const avgElement = document.getElementById('perf-avg-response-time');
        if (avgElement) {
            avgElement.textContent = avgResponseTime !== '-' ? `${avgResponseTime}s` : '-';
        }
        
        // Calculate max response time
        const maxResponseTime = responseTimes.length > 0
            ? Math.max(...responseTimes).toFixed(1)
            : '-';
        const maxElement = document.getElementById('perf-max-response-time');
        if (maxElement) {
            maxElement.textContent = maxResponseTime !== '-' ? `${maxResponseTime}s` : '-';
        }
        
        // Long response count
        const longResponseElement = document.getElementById('perf-long-response-count');
        if (longResponseElement) {
            longResponseElement.textContent = `${this.performanceMetrics.longResponseCount} calls`;
        }
        
        // Total trips
        const tripsElement = document.getElementById('perf-total-trips');
        if (tripsElement) {
            tripsElement.textContent = this.performanceMetrics.totalTrips;
        }
        
        // Door operations
        const doorElement = document.getElementById('perf-door-operations');
        if (doorElement) {
            doorElement.textContent = this.performanceMetrics.doorOperations;
        }
        
        // Total distance (sum of all elevators, convert floors to meters, assuming 3.5m per floor)
        const totalDistance = Object.values(this.performanceMetrics.elevatorDistances)
            .reduce((sum, dist) => sum + dist, 0) * 3.5;
        const distanceElement = document.getElementById('perf-total-distance');
        if (distanceElement) {
            distanceElement.textContent = totalDistance > 0 ? `${totalDistance.toFixed(1)} m` : '0 m';
        }
        
        // Per-elevator stats
        this.updatePerElevatorStats();
    }
    
    updatePerElevatorStats() {
        const container = document.getElementById('per-elevator-stats');
        if (!container) return;
        
        const elevatorNames = Object.keys(this.performanceMetrics.elevatorTrips).sort();
        
        if (elevatorNames.length === 0) {
            container.innerHTML = '<p style="color: var(--text-secondary); font-style: italic;">No data available yet...</p>';
            return;
        }
        
        container.innerHTML = '';
        elevatorNames.forEach(elevatorName => {
            const trips = this.performanceMetrics.elevatorTrips[elevatorName] || 0;
            const distance = (this.performanceMetrics.elevatorDistances[elevatorName] || 0) * 3.5; // Convert to meters
            
            const statItem = document.createElement('div');
            statItem.className = 'elevator-stat-item';
            statItem.innerHTML = `
                <span class="elevator-stat-name">${elevatorName}</span>
                <span class="elevator-stat-value">${trips} trips, ${distance.toFixed(1)}m</span>
            `;
            container.appendChild(statItem);
        });
    }
    
    resetMetrics() {
        this.metrics = {
            totalPassengers: 0,
            totalWaitTime: 0,
            maxWaitTime: 0,
            boardingCount: 0,
            totalTrips: 0,
            totalOccupancy: 0,
            occupancyCount: 0
        };
        
        // Reset performance metrics
        this.performanceMetrics = {
            hallCalls: [],
            responseTimes: [],
            longResponseCount: 0,
            totalTrips: 0,
            doorOperations: 0,
            elevatorDistances: {},
            elevatorTrips: {},
            lastFloors: {}
        };
        
        // Reset elevator state tracking
        this.elevatorStates = {};
        
        this.refreshMetricsUI();
        this.updatePerformanceMonitor();
        this.resetChartData();  // Also reset chart data
    }
    
    // ==========================================
    // Chart Management
    // ==========================================
    
    addWaitTimeToChart(waitTime, currentTime) {
        const interval = this.chartConfig.updateInterval;
        
        // Calculate which bucket this time belongs to (aligned to interval)
        const currentBucketStart = Math.floor(currentTime / interval) * interval;
        
        // Flush all completed buckets between lastBucketEndTime and currentBucketStart
        // This includes empty buckets (which will show as 0 seconds)
        while (this.chartData.lastBucketEndTime < currentBucketStart) {
            const bucketStart = this.chartData.lastBucketEndTime;
            this.flushChartBucket(bucketStart);
            this.chartData.lastBucketEndTime += interval;
        }
        
        // Update current bucket start time if needed
        if (this.chartData.currentBucket.startTime !== currentBucketStart) {
            this.chartData.currentBucket.startTime = currentBucketStart;
            this.chartData.currentBucket.waitTimes = [];
            this.chartData.currentBucket.sampleCount = 0;
        }
        
        // Add wait time to current bucket
        this.chartData.currentBucket.waitTimes.push(waitTime);
        this.chartData.currentBucket.sampleCount++;
    }
    
    flushChartBucket(bucketStartTime) {
        // Calculate average wait time for this bucket
        // If no passengers, show 0 seconds (no one waiting = 0 wait time)
        const bucket = this.chartData.currentBucket;
        let avgWaitTime = 0;
        let sampleCount = 0;
        
        if (bucket.startTime === bucketStartTime && bucket.waitTimes.length > 0) {
            // This is the current bucket with data
            avgWaitTime = bucket.waitTimes.reduce((sum, wt) => sum + wt, 0) / bucket.waitTimes.length;
            sampleCount = bucket.sampleCount;
        }
        // else: empty bucket, avgWaitTime stays 0
        
        // Format time label (e.g., "0:00", "0:10", "0:20")
        const minutes = Math.floor(bucketStartTime / 60);
        const seconds = Math.floor(bucketStartTime % 60);
        const timeLabel = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        
        // Add data point to chart
        if (this.waitTimeChart) {
            this.waitTimeChart.data.labels.push(timeLabel);
            this.waitTimeChart.data.datasets[0].data.push(avgWaitTime);
            
            // Limit data points to maxDataPoints
            if (this.waitTimeChart.data.labels.length > this.chartConfig.maxDataPoints) {
                this.waitTimeChart.data.labels.shift();
                this.waitTimeChart.data.datasets[0].data.shift();
            }
            
            // Update chart
            this.waitTimeChart.update('none'); // 'none' for no animation (smoother)
            
            if (sampleCount > 0) {
                console.log(`[Chart] Added data point: ${timeLabel} = ${avgWaitTime.toFixed(2)}s (${sampleCount} samples)`);
            } else {
                console.log(`[Chart] Added data point: ${timeLabel} = 0.00s (no passengers)`);
            }
        }
    }
    
    resetChartData() {
        // Clear chart data
        if (this.waitTimeChart) {
            this.waitTimeChart.data.labels = [];
            this.waitTimeChart.data.datasets[0].data = [];
            this.waitTimeChart.update('none');
            console.log('[Chart] Chart data cleared');
        }
        
        // Reset bucket and tracking
        this.chartData.lastBucketEndTime = 0;
        this.chartData.currentBucket = {
            startTime: 0,
            waitTimes: [],
            sampleCount: 0
        };
    }
    
    initializeChart() {
        const canvas = document.getElementById('waitTimeChart');
        if (!canvas) {
            console.warn('[Chart] Canvas element not found');
            return;
        }
        
        // Get computed styles for dark mode compatibility
        const isDarkMode = document.body.classList.contains('dark-mode');
        const textColor = isDarkMode ? '#e2e8f0' : '#1e293b';
        const gridColor = isDarkMode ? 'rgba(148, 163, 184, 0.1)' : 'rgba(0, 0, 0, 0.1)';
        
        const ctx = canvas.getContext('2d');
        this.waitTimeChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [], // Time labels (will be populated later)
                datasets: [{
                    label: 'Average Wait Time (s)',
                    data: [], // Wait time data (will be populated later)
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.1)',
                    borderWidth: 2,
                    tension: 0, // Straight lines (not curved)
                    fill: true,
                    pointRadius: 3,
                    pointHoverRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        labels: {
                            color: textColor,
                            font: {
                                size: 12
                            }
                        }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: function(context) {
                                return `Wait Time: ${context.parsed.y.toFixed(1)}s`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Time',
                            color: textColor
                        },
                        ticks: {
                            color: textColor,
                            maxRotation: 45,
                            minRotation: 0
                        },
                        grid: {
                            color: gridColor
                        }
                    },
                    y: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Wait Time (seconds)',
                            color: textColor
                        },
                        ticks: {
                            color: textColor
                        },
                        grid: {
                            color: gridColor
                        },
                        beginAtZero: true
                    }
                },
                interaction: {
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                }
            }
        });
        
        console.log('[Chart] Wait time chart initialized');
    }
    
    updateCallSystemBadge(callSystemType) {
        const badge = document.getElementById('call-system-badge');
        const badgeText = document.getElementById('call-system-type');
        const badgeIcon = badge.querySelector('.badge-icon');
        
        if (!badge || !badgeText) {
            console.warn('[CallSystem] Badge elements not found in DOM');
            return;
        }
        
        // Remove existing type classes
        badge.classList.remove('traditional', 'dcs-full', 'dcs-hybrid');
        
        // Define display names and configurations
        const systemConfigs = {
            'TRADITIONAL': {
                displayName: 'Conventional Up-Down System',
                icon: '🔼🔽',
                className: 'traditional'
            },
            'FULL_DCS': {
                displayName: 'Full Destination Control System',
                icon: '🎯',
                className: 'dcs-full'
            },
            'HYBRID_DCS': {
                displayName: 'Hybrid Destination Control System',
                icon: '🔀',
                className: 'dcs-hybrid'
            },
            'UNKNOWN': {
                displayName: 'Unknown System',
                icon: '❓',
                className: 'traditional'
            }
        };
        
        // If no callSystemType provided, default to TRADITIONAL
        const config = systemConfigs[callSystemType] || systemConfigs['TRADITIONAL'];
        
        badgeText.textContent = config.displayName;
        badgeIcon.textContent = config.icon;
        badge.classList.add(config.className);
        
        console.log(`[CallSystem] Updated badge: ${config.displayName} (type: ${callSystemType})`);
    }
}

// Initialize application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.elevatorViz = new ElevatorVisualizer();
});


