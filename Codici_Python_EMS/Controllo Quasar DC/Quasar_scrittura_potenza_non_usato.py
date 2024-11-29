# programma per il comando della QUASAR DC 7,4 kW tramite scrittura registri Modbus

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
def QuasarRead (clt, addr):
    if (clt.connect()):
        f = clt.read_holding_registers(addr, 1, slave=1) #legge il registro addr
        #decoder = BinaryPayloadDecoder.fromRegisters(reg.registers, Endian.BIG, wordorder=Endian.BIG)
        #f = decoder.decode_32bit_float()
        clt.close()
        return f 

#definisco la funzione di scrittura registri Alfen 
#If you need to write floating point values, you'll have to build a payload and then write it to the registers   
def Quasar_WriteRegister(client, addr, val):
    if (client.connect()):
        #builder = BinaryPayloadBuilder(wordorder=Endian.BIG, byteorder=Endian.BIG)    
        #builder.add_32bit_float(val)
        #payload = builder.to_registers()
        result = client.write_registers(addr, val, slave=1)
        

###################################################################################################################################

#QUASAR (DCb) 

#SCRITTURA REGISTRO CORRENTE MAX SU COLONNINA QUASAR (7,4 kW) DCb

#IP meter Quasar
IP_M_DCb = '192.168.170.173'
#Definizione client che interroga il meter della QUASAR (DCb)
M_DCb = ModbusTcpClient(host=IP_M_DCb, port=502)

#IP EVSE Quasar
IP_DCb = '192.168.170.18'  
#Definizione del client che interroga la DCb 
DCb = ModbusClient.ModbusTcpClient(host=IP_DCb, port=502)

#Primo indirizzo del registro su cui scrivere la corrente (258)
I_max_DCb_address: int = 258

#DA ATTIVARE SE VUOI USARE METER SIEMENS PER LETTURA
#current = SiemensRead(M_DCb, 13)
#power = SiemensRead(M_DCb, 25)
#power_kW = float(power/1000)   
#print("La wallbox sta assorbendo", "%.2f" % power_kW, "kW e", "%.2f" % current, "A.")

#Qui lo fai se usi la lettura direttamente dalla DCb
if (DCb.connect()):
    current1 = QuasarRead(DCb, 519)
    power1 = QuasarRead(DCb, 526)
    power1_kW = power1/1000
    print("DCb sta assorbendo", "%.2f" % power1_kW, "kW e", "%.2f" % current1, "A")


    while True:
        voltage1 = QuasarRead(DCb, 522) #AC voltage RMS L1
        #chiede da tastiera il valore di potenza max desiderato per poter modulare l'erogazione della DCb
        P_DCb_max_str = input('Inserisci potenza max DCb, tra 1,4 e 7,4 [kW]:')
        P_DCb_max = float(P_DCb_max_str)
        P_DCb_max_W = float(P_DCb_max*1000)
        P_DCb_max_W_int = int(P_DCb_max_W)
        I_DCb_max = int(P_DCb_max_W_int/voltage1)
        Quasar_WriteRegister(DCb,I_max_DCb_address,I_DCb_max) #scrittura su DCb della corrente massima

        print("Attendere 4 secondi")
        time.sleep(4)  #attende 4 secondi: nel frattempo la DCb modula e si assesta al nuovo setpoint ordinato
        power1 = QuasarRead(DCb, 526)       #con lettura Quasar potenza attiva
        power1_kW = power1/1000
        current1 = QuasarRead(DCb, 519)     #con lettura Quasar corrente
        max_current = QuasarRead(DCb, 512) #con lettura Quasar max corrente AC attuale (quella del setpoint)
        max_power = QuasarRead(DCb, 514) #con lettura Quasar max power AC attuale (quella del setpoint)
        max_power_kW = max_power/1000
        while True:
            print("DCb sta assorbendo", "%.2f" % power1_kW, "kW e", "%.2f" % current1, "A. Attuale massima potenza", "%.2f" % max_power_kW, "kW. ESC per nuovo setpoint.")
            if keyboard.is_pressed('esc'):  #se invece vuoi interrompere tu
                break
    
##########################################################################################################################


    



