# programma per il comando della ALFEN EVE SINGLE MONOFASE 7,4 kW tramite scrittura registri Modbus (modalità EMS)

import time
import threading
import keyboard

#from pymodbus.server import StartSerialServer
#from pymodbus.transaction import ModbusRtuFramer
from pymodbus.datastore import  (ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext)
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadBuilder
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.client import ModbusTcpClient
import pymodbus.client as ModbusClient


  
    
#definisco la funzione di lettura meter Siemens
def SiemensRead(clt, addr):
    if (clt.connect()):
        reg = clt.read_holding_registers(addr, 2, slave=1) #legge il registro addr e addr+1
        decoder = BinaryPayloadDecoder.fromRegisters(reg.registers, Endian.BIG, wordorder=Endian.BIG)
        f = decoder.decode_32bit_float()
        clt.close()
        return f 

#definisco la funzione di lettura registri Alfen

#NB: si è notato come se il codice viene lasciato in esecuzione per tempi superiori a 10 minuti, a volte la funzione alfen read dà 
#errore siccome la colonnina perde per un istante la connessione Modbus: per ovviare a questo si consiglia di usare la lettura del meter siemens e non quella della colonnina diretta
def AlfenRead (clt, addr):
    if (clt.connect()):
        reg = clt.read_holding_registers(addr, 2, slave=1) #legge il registro addr e addr+1
        decoder = BinaryPayloadDecoder.fromRegisters(reg.registers, Endian.BIG, wordorder=Endian.BIG)
        f = decoder.decode_32bit_float()
        clt.close()
        return f 

#definisco la funzione di scrittura registri Alfen 
#If you need to write floating point values, you'll have to build a payload and then write it to the registers   
def Alfen_WriteRegister(client, addr, val):
    if (client.connect()):
        builder = BinaryPayloadBuilder(wordorder=Endian.BIG, byteorder=Endian.BIG)    
        builder.add_32bit_float(val)
        payload = builder.to_registers()
        result = client.write_registers(addr, payload, slave=1)
        #print(result)


###################################################################################################################################

#ALFEN 

#SCRITTURA REGISTRO CORRENTE MAX SU COLONNINA ALFEN (EVE Single Pro Line 7,4 kW) ACuPP
#NB: su ACE Service Installer bisogna portare la EVSE in questione in modalità EMS (no meter). Si fa nel terzo riquadro (menù Active Load Balancing)

timeout_alfen = 0.3 

#IP meter Alfen
IP_M_ACuPP = '192.168.170.172'
#Definizione client che interroga il meter dell'Alfen (M_ACuPP)
M_ACuPP = ModbusTcpClient(host=IP_M_ACuPP, port=502)



#IP EVSE Alfen ACuPP
IP_ACuPP = '192.168.170.120'  #ora cambiato, prima era  in 192.168.100.148
#Definizione del client che interroga la ACuPP (la colonnina è server/slave)
ACuPP = ModbusClient.ModbusTcpClient(host=IP_ACuPP, port=502)

#Primo indirizzo del registro su cui scrivere la corrente (sono il 1210 e il 1211)
I_max_ACuPP_address: int = 1210

#DA ATTIVARE SE VUOI USARE METER SIEMENS PER LETTURA
#current = SiemensRead(M_ACuPP, 13)
#print("La wallbox sta assorbendo", "%.2f" % current, "A")

#Qui lo fai se usi la lettura direttamente dalla Alfen
if (ACuPP.connect()):
    current1 = AlfenRead(ACuPP, 320)
    power1 = AlfenRead(ACuPP, 344)
    power1_kW = float(power1/1000)
    print("ACuPP sta assorbendo", "%.2f" % power1_kW, "kW e", "%.2f" % current1, "A")

    while True:
        voltage1 = AlfenRead(ACuPP, 306)
        #chiede da tastiera il valore di potenza max desiderato per poter modulare l'erogazione della ACuPP
        P_ACuPP_max_str = input('Inserisci potenza max ACuPP, tra 1,4 e 7,4 [kW]:')
        P_ACuPP_max = float(P_ACuPP_max_str)
        P_ACuPP_max_W = float(P_ACuPP_max*1000)
        I_ACuPP_max = float(P_ACuPP_max_W/voltage1)
        Alfen_WriteRegister(ACuPP,I_max_ACuPP_address,I_ACuPP_max) #scrittura su Alfen della corrente massima
  
        print("Attendere 4 secondi")
        time.sleep(4)  #attende 4 secondi: nel frattempo la colonnina modula e si assesta al nuovo setpoint ordinato
        power1 = AlfenRead(ACuPP, 344)       #con lettura Alfen potenza attiva
        power1_kW = float(power1/1000)
        current1 = AlfenRead(ACuPP, 320)     #con lettura Alfen corrente
        max_current = AlfenRead(ACuPP, 1206) #con lettura Alfen max corrente attuale (quella del setpoint)
        max_power = float(max_current*voltage1)
        max_power_kW = float(max_power/1000)
        while True:
            print("ACuPP sta assorbendo", "%.2f" % power1_kW, "kW e", "%.2f" % current1, "A. Attuale massima potenza", "%.2f" % max_power_kW, "kW. ESC per nuovo setpoint.")
            if keyboard.is_pressed('esc'):  #se invece vuoi interrompere tu
                break
    #Lettura meter P_wallbox 
    #power = SiemensRead(M_ACuPP, 25)   #con lettura Siemens
    #current = SiemensRead(M_ACuPP, 13) #con lettura Siemens
       
    
    
##########################################################################################################################




