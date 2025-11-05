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
        
        this.initializeUI();
        this.initializeModeSelector();
        this.initializePlaybackControls();
        this.initializeDarkMode();
        this.initializeTabs();
        
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
        
        // Calculate shaft height
        const carHeight = 25; // px
        const shaftHeight = carHeight * (numFloors + 1);
        sharedFloorLabels.style.height = `${shaftHeight}px`;
        
        // Create floor labels with absolute positioning to match elevator floors
        for (let f = 1; f <= numFloors; f++) {
            const label = document.createElement('div');
            label.className = 'shared-floor-label';
            label.textContent = `${f}F`;
            
            // Position each label at the bottom of its floor (same as elevator car positioning)
            const bottomPercent = ((f - 1) / numFloors) * 100;
            label.style.bottom = `${bottomPercent}%`;
            
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
        
        // Create shaft
        const shaft = document.createElement('div');
        shaft.className = 'elevator-shaft';
        shaft.id = `shaft-${elevatorName}`;
        
        // Calculate shaft height
        const carHeight = 25; // px
        const numFloors = data.num_floors || 10;
        const shaftHeight = carHeight * (numFloors + 1);
        shaft.style.height = `${shaftHeight}px`;
        
        // Create elevator car (if not Hall)
        if (elevatorName !== 'Hall') {
            const car = document.createElement('div');
            car.className = 'elevator-car door-closed';
            car.id = `car-${elevatorName}`;
            car.innerHTML = `
                <div class="door door-left"></div>
                <div class="door door-right"></div>
            `;
            shaft.appendChild(car);
            
            // Position car at initial floor
            const floorPosition = ((data.floor - 1) / numFloors) * 100;
            car.style.bottom = `${floorPosition}%`;
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
        column.appendChild(shaft);
        if (elevatorName !== 'Hall') {
            const capacityDisplay = column.querySelector('.capacity-display');
            if (capacityDisplay) {
                column.appendChild(capacityDisplay);
            }
        }
        columnsContainer.appendChild(column);
        
        return column;
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
            carCalls: {}
        };
        
        // Clear waiting passengers
        this.waitingPassengers = {};
        
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
                const waitDirection = data.direction;
                
                if (!this.waitingPassengers[waitFloor]) {
                    this.waitingPassengers[waitFloor] = { UP: 0, DOWN: 0 };
                }
                this.waitingPassengers[waitFloor][waitDirection]++;
                
                // Trigger visualization update
                this.updateWaitingPassengers(this.waitingPassengers);
                break;
                
            case 'passenger_boarding':
                // Handle passenger boarding event for visualization
                // Decrement waiting passengers count
                const boardFloor = data.floor;
                const boardDirection = data.direction;
                
                if (this.waitingPassengers[boardFloor] && 
                    this.waitingPassengers[boardFloor][boardDirection] > 0) {
                    this.waitingPassengers[boardFloor][boardDirection]--;
                }
                
                // Trigger visualization update
                this.updateWaitingPassengers(this.waitingPassengers);
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
        
        // Update call indicators using new grid layout
        const callData = {
            ...data,
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
        const shaft = document.getElementById(`shaft-${elevatorName}`);
        if (!shaft) return;
        
        // Remove existing call indicators
        shaft.querySelectorAll('.call-indicator').forEach(el => el.remove());
        
        const numFloors = data.num_floors || this.numFloors || 10;
        
        // Add car call indicators
        if (data.car_calls && data.car_calls.length > 0) {
            data.car_calls.forEach(floor => {
                const indicator = document.createElement('div');
                indicator.className = 'call-indicator car-call-indicator';
                indicator.textContent = '●';
                indicator.title = `Car call: ${floor}F`;
                const bottomPercent = ((floor - 1) / numFloors) * 100;
                indicator.style.bottom = `${bottomPercent}%`;
                indicator.style.right = '5px';
                shaft.appendChild(indicator);
            });
        }
        
        // Add hall call UP indicators
        if (data.hall_calls_up && data.hall_calls_up.length > 0) {
            data.hall_calls_up.forEach(floor => {
                const indicator = document.createElement('div');
                indicator.className = 'call-indicator hall-call-up-indicator';
                indicator.textContent = '▲';
                indicator.title = `Hall call UP: ${floor}F`;
                // Position in lower half of floor cell
                const floorHeight = 100 / numFloors;
                const bottomPercent = ((floor - 1) / numFloors) * 100 + (floorHeight * 0.38);
                indicator.style.bottom = `${bottomPercent}%`;
                indicator.style.left = '5px';
                shaft.appendChild(indicator);
            });
        }
        
        // Add hall call DOWN indicators
        if (data.hall_calls_down && data.hall_calls_down.length > 0) {
            data.hall_calls_down.forEach(floor => {
                const indicator = document.createElement('div');
                indicator.className = 'call-indicator hall-call-down-indicator';
                indicator.textContent = '▼';
                indicator.title = `Hall call DOWN: ${floor}F`;
                // Position in lower half of floor cell, near bottom
                const floorHeight = 100 / numFloors;
                const bottomPercent = ((floor - 1) / numFloors) * 100 + (floorHeight * 0.02);
                indicator.style.bottom = `${bottomPercent}%`;
                indicator.style.left = '5px';
                shaft.appendChild(indicator);
            });
        }
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
        
        // Update Hall shaft with waiting passengers
        const hallShaft = document.getElementById('shaft-Hall');
        if (hallShaft) {
            // Remove existing waiting passenger indicators
            hallShaft.querySelectorAll('.waiting-passenger-indicator').forEach(el => el.remove());
            
            const numFloors = this.numFloors || 10;
            
            // Add waiting passenger indicators
            for (const [floor, directions] of Object.entries(waitingData)) {
                const floorNum = parseInt(floor);
                const bottomPercent = ((floorNum - 1) / numFloors) * 100;
                
                if (directions.UP > 0) {
                    const indicator = document.createElement('div');
                    indicator.className = 'waiting-passenger-indicator waiting-up';
                    indicator.textContent = `${directions.UP}👤▲`;
                    indicator.title = `${directions.UP} passengers waiting for UP`;
                    indicator.style.bottom = `${bottomPercent}%`;
                    indicator.style.left = '10px';
                    hallShaft.appendChild(indicator);
                }
                
                if (directions.DOWN > 0) {
                    const indicator = document.createElement('div');
                    indicator.className = 'waiting-passenger-indicator waiting-down';
                    indicator.textContent = `${directions.DOWN}👤▼`;
                    indicator.title = `${directions.DOWN} passengers waiting for DOWN`;
                    indicator.style.bottom = `${bottomPercent}%`;
                    indicator.style.right = '10px';
                    hallShaft.appendChild(indicator);
                }
            }
        }
        
        // Clear waiting areas from all elevator displays (kept for compatibility)
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
                        direction: event.data.direction || 'NO_DIRECTION',
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
                
                // Return event message for metrics (keeping original event structure)
                return {
                    type: 'passenger_waiting',
                    data: event.data
                };
            
            case 'passenger_boarding':
                // Decrement waiting passengers
                const boardFloor = event.data.floor;
                const boardDirection = event.data.direction;
                
                if (this.waitingPassengers[boardFloor] && 
                    this.waitingPassengers[boardFloor][boardDirection] > 0) {
                    this.waitingPassengers[boardFloor][boardDirection]--;
                }
                
                // Return event message for metrics (keeping original event structure)
                return {
                    type: 'passenger_boarding',
                    data: event.data
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
        }
        
        // Track occupancy from elevator_status events
        if (eventType === 'elevator_status') {
            const passengers = eventData.passengers || 0;
            const capacity = eventData.capacity || 10;
            const occupancy = (passengers / capacity) * 100;
            this.metrics.totalOccupancy += occupancy;
            this.metrics.occupancyCount++;
        }
        
        // Track journey metrics from passenger_alighting events
        if (eventType === 'passenger_alighting') {
            // Optional: Track riding time, total journey time, etc.
            // Can be used for future metrics
            const ridingTime = eventData.riding_time || 0;
            const totalJourneyTime = eventData.total_journey_time || 0;
            // Store for future use if needed
        }
        
        // Update UI
        this.refreshMetricsUI();
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
        
        // Total trips (placeholder)
        document.getElementById('metric-total-trips').textContent = 
            this.metrics.totalTrips;
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
        this.refreshMetricsUI();
    }
}

// Initialize application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.elevatorViz = new ElevatorVisualizer();
});

