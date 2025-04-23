import os
import sys
from collections import defaultdict
from queue import Queue
import numpy as np
import matplotlib.pyplot as plt


if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("Please declare environment variable 'SUMO_HOME'")

import traci


def get_queue_length(edge_id):
    count = 0
    i = 0
    while True:
        id = edge_id + f'_{i}'
        if id not in LANEAREA_IDS:
            break
        count += traci.lanearea.getLastStepVehicleNumber(id)
        i += 1
    return count


def get_current_phase(tls_id):
    return traci.trafficlight.getPhase(tls_id)


def set_current_phase(tls_id, phase):
    traci.trafficlight.setPhase(tls_id, phase)


def get_in_lanes(tls_id):
    return traci.trafficlight.getControlledLanes(tls_id)


def control_tl(tls_id):
    """
    The main sotl-request algorithm that controls the traffic lights.
    It uses the following variables:
    - Lane specific variables:
        - ki: number of vehicles waiting on each edge
        - pi: time the light has been in same state on each edge
    - Junction specific variables:
        - requests: queue of requests for green light for a junction
    - pmin: minimum green time
    - p_y: yellow time
    - theta: minimum number of vehicles to wait for before green light
    """
    global wt_history, atwt, num_vehicles

    lanes = get_in_lanes(tls_id)
    # print("hey1", end=" ")
    edges = list(set([traci.lane.getEdgeID(lane) for lane in lanes]))
    # print("hey2", end=" ")
    cur_phase = get_current_phase(tls_id)
    # print("hey3", end=" ")

    for edge in edges:
        # print(edge, end=" ")
        g = edge_green_state[edge]
        pi[edge] += TIME_STEP

        if g == cur_phase: # Green phase
            if pi[edge] >= pmin and not requests[tls_id].empty():
                set_current_phase(tls_id, cur_phase + 1)
                pi[edge] = 0

        elif g + 1 == cur_phase: # Yellow phase
            if pi[edge] >= p_y:
                req = requests[tls_id].get()
                set_current_phase(tls_id, edge_green_state[req])

                wt_history.append(ki[req] * pi[req] * .5)
                num_vehicles += ki[req]
                pi[edge] = 0
                pi[req] = 0

        else: # Red phase
            ki[edge] = get_queue_length(edge)
            if ki[edge] > theta and edge not in requests[tls_id].queue:
                requests[tls_id].put(edge)
            elif ki[edge] > 0 and requests[tls_id].empty():
                requests[tls_id].put(edge)
    # print()


TIME_STEP = 0.2 # seconds

atwts = []

for itr in range(1, 5):

    sumo_config = [
        'sumo',
        '-c', 'sotl_network/4lane.sumocfg',
        '-r', f'sotl_network/4lane_{itr}.rou.xml',
        '--step-length', str(TIME_STEP),
        '--delay', '0',
        '--lateral-resolution', '0'
    ]

    traci.start(sumo_config)

    LANEAREA_IDS = traci.lanearea.getIDList()


    #####################
    #   Plotting vars   #
    #####################

    # Total vehicles waiting time in past 10 minutes
    wt_history = []
    # Vehicles waiting time averaged over 10 minutes
    atwt = [0]
    # Number of vehicles waiting in the last 10 minutes
    num_vehicles = 0


    #####################
    #   SOTL Variables  #
    #####################

    # Maps from edge id to number of vehicles waiting.
    ki = defaultdict(lambda: 0)
    # Maps from edge id to time it has been green.
    pi = defaultdict(lambda: 0)
    # Minimum green time
    pmin = 30
    # Yellow time
    p_y = 3
    # Minimum cars to wait for before green light
    theta = 2
    # Requests for green light for a junction
    requests = defaultdict(Queue)


    #####################
    #   SOTL Algorithm  #
    #####################

    junctions = ['C']

    edge_green_state = {
        '1C' : 0,
        '2C' : 2,
        '3C' : 4,
        '4C' : 6
    }

    update_time = 0

    while traci.simulation.getMinExpectedNumber() > 0:
        for j in junctions:
            control_tl(j)

        # Compute the average waiting time for the last 10 minutes
        # and reset the waiting time history and number of vehicles
        if update_time >= 600:
            wt = sum(wt_history) / num_vehicles
            atwt.append(wt)
            wt_history = []
            num_vehicles = 0
            update_time = 0

        traci.simulationStep()
        update_time += TIME_STEP

    atwts.append(atwt)

    traci.close()
    print(f"Simulation {itr:2d} finished.\n")


x = np.arange(0, 61, 10)
## Plotting each atwt
for i, atwt in enumerate(atwts):
    plt.plot(x, atwt, label=f'Simulation {i+1}')

plt.xlabel('Time (minutes)')
plt.ylabel('Average Waiting Time (seconds)')
plt.title('Average Waiting Time vs Time')
plt.legend()
plt.grid()
plt.show()