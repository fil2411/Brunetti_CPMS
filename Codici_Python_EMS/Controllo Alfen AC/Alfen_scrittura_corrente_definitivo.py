# programma per il comando della ALFEN EVE SINGLE MONOFASE 7,4 kW tramite scrittura registri Modbus (modalità EMS)

import time
import threading
import keyboard

from pymodbus.server import StartSerialServer
from pymodbus.transaction import ModbusRtuFramer
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
    print("ACuPP sta assorbendo", "%.2f" % current1, "A")

    while True:
    #chiede da tastiera il valore di corrente max desiderato per poter modulare l'erogazione della ACuPP
        I_ACuPP_max_str = input('Inserisci corrente ACuPP, tra 6 e 32 [A]:')
  
        I_ACuPP_max = float(I_ACuPP_max_str)

    #ACuPP.connect()  #client connection is ok
    
        Alfen_WriteRegister(ACuPP,I_max_ACuPP_address,I_ACuPP_max) #scrittura su Alfen
    #Lettura meter P_wallbox 
    #power = SiemensRead(M_ACuPP, 25)   #con lettura Siemens
    #current = SiemensRead(M_ACuPP, 13) #con lettura Siemens

        print("Attendere 4 secondi")
        time.sleep(4)  #attende 4 secondi: nel frattempo la colonnina modula e si assesta al nuovo setpoint ordinato
        power1 = AlfenRead(ACuPP, 344)       #con lettura Alfen potenza attiva
        current1 = AlfenRead(ACuPP, 320)     #con lettura Alfen corrente
        max_current = AlfenRead(ACuPP, 1206) #con lettura Alfen max corrente attuale (quella del setpoint)
        while True:
            print("ACuPP sta assorbendo", "%.2f" % power1, "W e", "%.2f" % current1, "A. Attuale massima corrente", "%.2f" % max_current, "A. ESC per nuovo setpoint.")
            if keyboard.is_pressed('esc'):  #se invece vuoi interrompere tu
                break
    
    
##########################################################################################################################

    



