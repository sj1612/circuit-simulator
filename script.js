
        const canvas = document.getElementById('circuit-canvas');
        const ctx = canvas.getContext('2d');
        const propertiesPanel = document.getElementById('properties-panel');
        const canvasContainer = document.getElementById('canvas-container');

        // --- State Management ---
        let components = [];
        let wires = [];
        let activeTool = 'select';
        let selectedComponent = null;
        let wireStartComponent = null;
        let nextComponentId = 0;
        let groundNodeId = null;

        const GRID_SIZE = 20;

        // --- Initialization ---
        function initialize() {
            resizeCanvas();
            setupEventListeners();
            setActiveTool('select');
            redrawCanvas();
        }

        function resizeCanvas() {
            const containerRect = canvasContainer.getBoundingClientRect();
            canvas.width = containerRect.width;
            canvas.height = containerRect.height;
            redrawCanvas();
        }

        function setupEventListeners() {
            window.addEventListener('resize', resizeCanvas);
            canvas.addEventListener('mousedown', onCanvasMouseDown);
            canvas.addEventListener('mousemove', onCanvasMouseMove);
            
            document.getElementById('tool-select').addEventListener('click', () => setActiveTool('select'));
            document.getElementById('tool-resistor').addEventListener('click', () => setActiveTool('resistor'));
            document.getElementById('tool-voltage').addEventListener('click', () => setActiveTool('voltage_source'));
            document.getElementById('tool-wire').addEventListener('click', () => setActiveTool('wire'));
            document.getElementById('tool-ground').addEventListener('click', () => setActiveTool('ground'));
            document.getElementById('tool-inductor').addEventListener('click', () => setActiveTool('inductor'));
            document.getElementById('tool-capacitor').addEventListener('click', () => setActiveTool('capacitor'));
            document.getElementById('tool-delete').addEventListener('click', () => setActiveTool('delete'));

            document.getElementById('run-simulation').addEventListener('click', runSimulation);
            document.getElementById('clear-canvas').addEventListener('click', clearCanvas);
            
            document.getElementById('close-modal-btn').addEventListener('click', hideResultsModal);
            document.getElementById('results-modal').addEventListener('click', (e) => {
                if(e.target.id === 'results-modal') hideResultsModal();
            });
        }
        
        function setActiveTool(tool) {
            activeTool = tool;
            document.querySelectorAll('.tool-btn').forEach(btn => btn.classList.remove('active'));
            
            let buttonId = tool;
            if (tool === 'voltage_source') buttonId = 'voltage';
            document.getElementById(`tool-${buttonId}`).classList.add('active');

            canvas.style.cursor = (tool === 'select' || tool === 'delete') ? 'default' : 'crosshair';
            selectedComponent = null;
            wireStartComponent = null;
            updatePropertiesPanel();
            redrawCanvas();
        }

        // --- Core Drawing Logic ---
        function redrawCanvas() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            wires.forEach(drawWire);
            components.forEach(drawComponent);
            
            if (selectedComponent && activeTool === 'select') {
                ctx.strokeStyle = '#3b82f6';
                ctx.lineWidth = 2;
                ctx.setLineDash([5, 5]);
                const { x, y, width, height } = selectedComponent;
                ctx.strokeRect(x - 5, y - 5, width + 10, height + 10);
                ctx.setLineDash([]);
            }
        }
        
        function drawComponent(comp) {
            ctx.lineWidth = 2;
            ctx.strokeStyle = '#2D3748';
            ctx.fillStyle = '#2D3748';
            
            const { x, y, type } = comp;

            switch(type) {
                case 'resistor':
                    drawResistor(x, y);
                    break;
                case 'voltage_source':
                    drawVoltageSource(x, y, comp);
                    break;   
                case 'ground':
                    drawGround(x, y);
                    break;
                case 'inductor':
                    drawInductor(x, y);
                    break;
                case 'capacitor':
                    drawCapacitor(x, y);
                    break;
            }
            
            comp.terminals.forEach(t => {
                ctx.beginPath();
                ctx.arc(t.x, t.y, 4, 0, 2 * Math.PI);
                ctx.fillStyle = '#f87171';
                ctx.fill();
            });
        }
        
        function drawResistor(x, y) {
            ctx.beginPath();
            ctx.moveTo(x, y + 20);
            ctx.lineTo(x + 10, y + 20);
            ctx.lineTo(x + 15, y + 10);
            ctx.lineTo(x + 25, y + 30);
            ctx.lineTo(x + 35, y + 10);
            ctx.lineTo(x + 45, y + 30);
            ctx.lineTo(x + 50, y + 20);
            ctx.lineTo(x + 60, y + 20);
            ctx.stroke();
        }

        function drawVoltageSource(x, y, comp) {
            const radius = 20;
            ctx.beginPath();
            ctx.arc(x + 30, y + 20, radius, 0, 2 * Math.PI);
            ctx.stroke();
            // Lines
            ctx.moveTo(x, y + 20);
            ctx.lineTo(x + 10, y + 20);
            ctx.moveTo(x + 50, y + 20);
            ctx.lineTo(x + 60, y + 20);
            // Plus/Minus
            ctx.font = '16px sans-serif';
            ctx.fillStyle = '#2D3748';
            ctx.fillText('+', x + 25, y + 15);
            ctx.fillText('-', x + 27, y + 35);
            ctx.stroke();
        }

        function drawGround(x, y) {
            ctx.beginPath();
            ctx.moveTo(x + 10, y);
            ctx.lineTo(x + 10, y + 10);
            ctx.moveTo(x, y+10);
            ctx.lineTo(x + 20, y + 10);
            ctx.moveTo(x + 5, y + 15);
            ctx.lineTo(x + 15, y + 15);
            ctx.moveTo(x + 8, y + 20);
            ctx.lineTo(x + 12, y + 20);
            ctx.stroke();
        }
        
        function drawWire(wire) {
            ctx.beginPath();
            ctx.moveTo(wire.start.x, wire.start.y);
            ctx.lineTo(wire.end.x, wire.end.y);
            ctx.strokeStyle = '#60a5fa';
            ctx.lineWidth = 3;
            ctx.stroke();
        }

        function drawInductor(x, y) {
           ctx.beginPath();
           ctx.moveTo(x, y + 20); 
           ctx.lineTo(x + 10, y + 20);
           const radius = 5;
           const coilCount = 4;
           for (let i = 0; i < coilCount; i++) {
                const centerX = x + 10 + (i * 2 + 1) * radius;
                 ctx.arc(centerX, y + 20, radius, Math.PI, 0);
           }
           ctx.lineTo(x + 60, y + 20);
           ctx.stroke();
        }

        function drawCapacitor(x, y) {
           ctx.beginPath();
           // Left wire
           ctx.moveTo(x, y + 20);
           ctx.lineTo(x + 25, y + 20);

           // Right wire
           ctx.moveTo(x + 35, y + 20);
           ctx.lineTo(x + 60, y + 20);

           // Left plate (a vertical line)
           ctx.moveTo(x + 25, y + 5);
           ctx.lineTo(x + 25, y + 35);

           // Right plate (another vertical line)
           ctx.moveTo(x + 35, y + 5);
           ctx.lineTo(x + 35, y + 35);

           ctx.stroke(); // Render all the lines
        }

        // --- Event Handlers ---
        function onCanvasMouseDown(e) {
            const rect = canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            const gridX = Math.round(mouseX / GRID_SIZE) * GRID_SIZE;
            const gridY = Math.round(mouseY / GRID_SIZE) * GRID_SIZE;

            const clickedComponent = findComponentAt(mouseX, mouseY);
            
            switch (activeTool) {
                case 'resistor':
                case 'voltage_source':
                case 'current_source':
                case 'ground':
                    if (!clickedComponent) createComponent(activeTool, gridX, gridY);
                    setActiveTool('select');
                    break;
                case 'wire':
                    if (clickedComponent) {
                       const clickedTerminal = findTerminalAt(clickedComponent, mouseX, mouseY);
                       console.log('Clicked Terminal:',clickedTerminal)
                       if(clickedTerminal) {
                           handleWireDrawing(clickedComponent, clickedTerminal);
                       }
                    }
                    break;
                case 'select':
                    selectedComponent = clickedComponent;
                    updatePropertiesPanel();
                    redrawCanvas();
                    break;
                case 'delete':
                    if (clickedComponent) deleteComponent(clickedComponent);
                    break;
                case 'inductor':
                case 'capacitor':
                    if (!clickedComponent) createComponent(activeTool, gridX, gridY);
                    setActiveTool('select');
                    break;
            }
        }
        
        function onCanvasMouseMove(e) {
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    if (activeTool === 'wire') {
        let overTerminal = false;
        for (const comp of components) {
            if (findTerminalAt(comp, mouseX, mouseY)) {
                overTerminal = true;
                break;
            }
        }
        canvas.style.cursor = overTerminal ? 'pointer' : 'crosshair';
    }

    if (activeTool === 'wire' && wireStartComponent) {
        redrawCanvas();
        
        ctx.beginPath();
        ctx.moveTo(wireStartComponent.terminal.x, wireStartComponent.terminal.y);
        ctx.lineTo(mouseX, mouseY);
        ctx.strokeStyle = 'var(--color-red-400)';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        ctx.stroke();
        ctx.setLineDash([]);
    }
}
        
        function handleWireDrawing(component, terminal) {
            if (!wireStartComponent) {
                wireStartComponent = { component, terminal };
            } else {
                const start = wireStartComponent.terminal;
                const end = terminal;

                if (wireStartComponent.component.id !== component.id) {
                    wires.push({ 
                        start: { x: start.x, y: start.y, componentId: wireStartComponent.component.id, terminalId: start.id },
                        end: { x: end.x, y: end.y, componentId: component.id, terminalId: end.id }
                    });
                }
                wireStartComponent = null;
                redrawCanvas();
            }
        }
        
        // --- Component Management ---
        function createComponent(type, x, y) {
            const id = nextComponentId++;
            let newComp;
            
            switch(type) {
                case 'resistor':
                    newComp = { id, type, x, y, width: 60, height: 40, value: 1000, terminals: [ {id:0, x:x, y:y+20}, {id:1, x:x+60, y:y+20} ] };
                    break;
                case 'voltage_source':
                     newComp = { id, type, x, y, width: 60, height: 40, value: 5, terminals: [ {id:0, x:x, y:y+20}, {id:1, x:x+60, y:y+20} ] };
                    break;
                case 'ground':
                    if (groundNodeId !== null) {
                       showSimulationError("Only one ground connection is allowed.");
                       return;
                    }
                    newComp = { id, type, x, y, width: 20, height: 20, terminals: [ {id:0, x:x+10, y:y} ] };
                    groundNodeId = id;
                    break;
                case 'inductor':
                    newComp = {id, type, x, y, width:60,height:40,value:1e-3,terminals:[{id:0,x:x,y:y+20},{id:1,x:x+60,y:y+20}]};
                    break;
                case 'capacitor':
                    newComp = { id, type, x, y, width: 60, height: 40, value: 1e-6, terminals: [ {id:0, x:x, y:y+20}, {id:1, x:x+60, y:y+20} ] };
                    break;   
                }
            components.push(newComp);
            redrawCanvas();
        }
        
        function deleteComponent(compToDelete) {
            components = components.filter(c => c.id !== compToDelete.id);
            if (compToDelete.type === 'ground') {
                groundNodeId = null;
            }

            wires = wires.filter(w => w.start.componentId !== compToDelete.id && w.end.componentId !== compToDelete.id);
            
            if (selectedComponent && selectedComponent.id === compToDelete.id) {
                selectedComponent = null;
                updatePropertiesPanel();
            }
            redrawCanvas();
        }

        function findComponentAt(x, y) {
            for (let i = components.length - 1; i >= 0; i--) {
                const comp = components[i];
                if (x >= comp.x && x <= comp.x + comp.width && y >= comp.y && y <= comp.y + comp.height) {
                    return comp;
                }
            }
            return null;
        }
        
        function findTerminalAt(component, x, y) {
            for (const terminal of component.terminals) {
                const dist = Math.sqrt((x - terminal.x)**2 + (y - terminal.y)**2);
                if (dist < 15) {
                    return terminal;
                }
            }
            return null;
        }
        
        function clearCanvas() {
            components = [];
            wires = [];
            selectedComponent = null;
            wireStartComponent = null;
            nextComponentId = 0;
            groundNodeId = null;
            updatePropertiesPanel();
            redrawCanvas();
        }
        
        // --- Properties Panel ---
        function updatePropertiesPanel() {
            if (!selectedComponent) {
                propertiesPanel.innerHTML = '<p>Select a component to see its properties.</p>';
                return;
            }
            
            let content = `<h3>${selectedComponent.type.replace('_', ' ')} #${selectedComponent.id}</h3>`;
            
            if (selectedComponent.type === 'resistor' || selectedComponent.type === 'voltage_source' || selectedComponent.type === 'inductor'||selectedComponent.type === 'capacitor') {
                let unit = 'Ohms';
                if(selectedComponent.type === 'voltage_source') unit = 'Volts';
                if(selectedComponent.type === 'inductor') unit = 'Henry';
                if(selectedComponent.type === 'capacitor') unit = 'Farads';

                content += `
                    <div class="prop-item">
                        <label for="comp-value">Value (${unit})</label>
                        <input type="number" id="comp-value" value="${selectedComponent.value}">
                    </div>
                `;
            } else {
                content += '<p style="margin-top: 0.5rem; font-size: 0.875rem; color: var(--color-gray-500);">This component has no editable properties.</p>';
            }
            
            propertiesPanel.innerHTML = content;

            if (document.getElementById('comp-value')) {
                document.getElementById('comp-value').addEventListener('input', (e) => {
                    if (selectedComponent) {
                        selectedComponent.value = parseFloat(e.target.value) || 0;
                    }
                });
            }
        }
        // --- Simulation Logic (Client Side) ---
        async function runSimulation() {
            const runButton = document.getElementById('run-simulation');
            runButton.disabled = true;
            runButton.textContent = 'Simulating...';

            try {
                
                const circuitData = { components, wires, groundNodeId, };

                // 2️⃣ Choose backend route
                backendUrl = 'http://127.0.0.1:5000/simulate';


                // 3️⃣ Send request
                await fetch(backendUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(circuitData),
                });

                
            } catch (error) {
                console.error('Simulation failed:', error);
                alert('Simulation failed. Check backend connection or console for details.');
            } finally {
                runButton.disabled = false;
                runButton.textContent = 'Run Simulation';
            }
        }

        // --- Start the application ---
        initialize();
    