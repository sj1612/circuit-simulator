CIRCUIT SIMULATOR.
This project is a simple GUI based circuit simulator, where one can make circuits with resistors, capacitors, inductors and voltage sources as the components. The simulator will return the values of node voltages and currents for dc analysis, as well as the plots of currents through resistors,inductors,capacitors and voltage sources through transient analysis for a given amount of time as specified by the user. The frontend(GUI) was made using HTML,CSS, and Javascript while the backend was made using MATLAB and python. Python was used for generating netlist of the simulated circuit and for integrating the frontend and backend with ease. Modified Nodal Analysis is used for calculation of voltages and currents in the MATLAB backend.


HOW TO RUN?

1)Clone the github repo into your pc.

2)Open the project in VS code. In VS code terminal, run the following commands- "pip install flask numpy" and "pip install flask-cors".

3)In the VS code terminal, run "python backend1.py". Next, go to the file index.html and right click on it and click on the "Open with live server" option.

4)Install the extension "Live Server" by Ritwick Dey in VS Code if not done already.

5)Run the circuit simulator. Draw the required circuit.

6)Run the MATLAB code. Type "output.txt" when asked for the netlist file.

7)The output plots and values of required currents and voltages are generated in MATLAB.
