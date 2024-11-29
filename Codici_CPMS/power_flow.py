import numpy as np
import pandas as pd

def power_flow(power_G2V, power_V2G, power_pv, power_consumption):
    # Matrice di incidenza per la descrizione della topologia dell'impianto elettrico
    L = np.matrix([
        [-1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 0, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 0, 0, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 0, 0, 0, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 0, 0, 0, 0, 0, -1, 0, 0, 0, 0, 0, 0, 0],
        [1, 0, 0, 0, 0, 0, 0, -1, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 1, -1, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 1, 0, -1, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, -1, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, -1, 0],
        [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, -1]
    ])
    Linv = np.linalg.inv(L)

    # Definizione delle grandezze base per il sistema in esame
    Vbase = 400  # V
    Sbase = 630  # kVA
    Zbase = Vbase ** 2 / (Sbase * 10 ** 3)  # Ohm
    Ibase = Sbase * 10 ** 3 / Vbase  # A

    # Matrice delle impedenze
    impedances = [
        (2.62 + 9.815j) * 10 ** -3 / Zbase,
        (14.4 + 1.63j) * 10 ** -3 / Zbase,
        (32.4 + 3.68j) * 10 ** -3 / Zbase,
        (126 + 5.718j) * 10 ** -3 / Zbase,
        (63 + 2.859j) * 10 ** -3 / Zbase,
        (108 + 4.901j) * 10 ** -3 / Zbase,
        (153 + 6.943j) * 10 ** -3 / Zbase,
        (7.5 + 4.084j) * 10 ** -3 / Zbase,
        (36 + 1.63j) * 10 ** -3 / Zbase,
        (81 + 3.68j) * 10 ** -3 / Zbase,
        (78.8 + 5.72j) * 10 ** -3 / Zbase,
        (36 + 1.63j) * 10 ** -3 / Zbase,
        (81 + 3.68j) * 10 ** -3 / Zbase,
        (78.8 + 5.72j) * 10 ** -3 / Zbase
    ]
    Z = np.diag(impedances)

    #definizione vettore potenze S
    # Potenza netta direttamente connessa al nodo 1 (QGBT)
   
    S1_net = (power_consumption-power_pv) / (Sbase)  # kVA base, per cui le potenze power_consumptione e power_pv devono essere in kW

    # Potenza ai nodi da 2 a 14 (colonnine), deve essere un vettore colonna! La potenza deve essere espressa in kW
    S = np.array([
        S1_net,
        (power_G2V[0]-power_V2G[0]) / (Sbase),  #DC
        (power_G2V[1]-power_V2G[1]) / (Sbase),  #DC
        (power_G2V[2]-power_V2G[2]) / (Sbase),  #AC
        (power_G2V[3]-power_V2G[3])/ (Sbase),   #AC
        (power_G2V[4]-power_V2G[4]) / (Sbase),  #AC
        (power_G2V[5]-power_V2G[5]) / (Sbase),  #AC
        (0 + 0j) / (Sbase),
        (power_G2V[6]-power_V2G[6]) / (Sbase),   #AC
        (power_G2V[7]-power_V2G[7]) / (Sbase),   #AC
        (power_G2V[8]-power_V2G[8]) / (Sbase),  #AC
        (power_G2V[9]-power_V2G[9]) / (Sbase),  #AC
        (power_G2V[10]-power_V2G[10]) / (Sbase),  #AC
        (power_G2V[11]-power_V2G[11]) / (Sbase)  #AC
    ]).reshape(14, 1)


    # Vettore delle tensioni nodali di inizializzazione
    Vini = np.array([1] * len(Linv)).reshape(len(Linv), 1)

    # Errore accettabile
    epsilon = 10 ** -17

    def ZIPcurrent(coeff=0, voltage=1, impedance=1, apparent_power=1):
        current = apparent_power.conjugate() / voltage.conjugate()
        return current

    def backward(voltage, apparent_power=S):
        current_node = ZIPcurrent(voltage=voltage, apparent_power=apparent_power, impedance=Z)
        curr_line = Linv.T * current_node
        return curr_line

    def foreward(curr_line):
        V = Vini - Linv * Z * curr_line
        return V

    def error(voltage, voltage_old):
        error = abs(voltage - voltage_old) / abs(voltage_old)
        return np.max(error)

    voltage = Vini
    voltage_old = voltage
    max_iter = 1000

    for k in range(max_iter):
        curr_line = backward(voltage=voltage, apparent_power=S)
        voltage_old = voltage
        voltage = foreward(curr_line=curr_line)
        if error(voltage, voltage_old) < epsilon:
            break

    results = pd.DataFrame(voltage, columns=["V"])
    results['I'] = curr_line
    results['Node'] = range(1, len(voltage) + 1)
    results.set_index('Node', inplace=True)

    # Calcolo del valore efficace
    results['V_eff'] = np.abs(results['V']) * Vbase  # Valore efficace delle tensioni
    results['I_eff'] = np.abs(results['I']) * Ibase  # Valore efficace delle correnti

     # Filtrare per nodi dal 2 al 14, escludendo il nodo 8
    filtered_results = results.loc[[i for i in range(2, 15) if i != 8], 'V_eff']

    return filtered_results
