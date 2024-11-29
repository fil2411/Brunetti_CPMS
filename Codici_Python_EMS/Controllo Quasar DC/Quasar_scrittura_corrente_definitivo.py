# programma per il comando della QUASAR DC 7,4 kW tramite scrittura registri Modbus TCP/IP

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

#definisco la funzione di lettura registri Quasar
def QuasarRead (clt, addr):
    if (clt.connect()):
        reg = clt.read_holding_registers(addr, 1, slave=1) #legge il registro addr
        decoder = BinaryPayloadDecoder.fromRegisters(reg.registers, Endian.BIG, wordorder=Endian.BIG)
        f = decoder.decode_16bit_int()
        clt.close()
        return f 
    
    

#definisco la funzione di scrittura registri Quasar 
def Quasar_WriteRegister(client, addr, val):
    if (client.connect()):
        result = client.write_register(addr, val, slave=1)
        

###################################################################################################################################

#QUASAR (DCb) 

#SCRITTURA REGISTRO CORRENTE MAX SU COLONNINA QUASAR (7,4 kW) DCb

#IP meter Quasar
IP_M_DCb = '192.168.170.173'
#Definizione client che interroga il meter del Quasar (M_Quasar)
M_DCb = ModbusTcpClient(host=IP_M_DCb, port=502)

#IP EVSE Quasar
IP_DCb = '192.168.170.18'  
#Definizione del client che interroga la DCb 
DCb = ModbusClient.ModbusTcpClient(host=IP_DCb, port=502)

#Primo indirizzo del registro su cui scrivere la corrente (258)
I_max_DCb_address: int = 258
Control_type_address: int = 81 #il registro vuole scritto 1 per poter abilitare scrittura di corrente


#DA ATTIVARE SE VUOI USARE METER SIEMENS PER LETTURA
#current = SiemensRead(M_DCb, 13)
#power = SiemensRead(M_DCb, 25)
#power_kW = float(power/1000)   
#print("La wallbox sta assorbendo", "%.2f" % power_kW, "kW e", "%.2f" % current, "A.")

#Qui lo fai se usi la lettura direttamente dalla DCb
if (DCb.connect()):
    current1 = QuasarRead(DCb, 519) #AC current RMS L1
    power1 = QuasarRead(DCb, 526) #AC active power RMS L1
    power1_kW = power1/1000
    soc = QuasarRead(DCb, 538) #EV SOC
    print("DCb sta assorbendo, lato AC", "%.2f" % power1_kW, "kW e", "%.2f" % current1, "A")
    print("SOC", "%.2f" % soc, "%")
    
    #Quasar_WriteRegister(DCb,Control_type_address,1) #scrittura su Control type (vuole 1)
    control = QuasarRead(DCb, 81) #control (deve essere 1)
    print("control", "%.2f" % control)
    setpoint_type = QuasarRead(DCb, 83) #setpoint type (deve essere 0)
    print("setpoint type", "%.2f" % setpoint_type)

    while True:
    #chiede da tastiera il valore di corrente max desiderato per poter modulare l'erogazione della DCb
        I_DCb_max_str = input('Inserisci corrente DCb, INTERO tra 6 e 32 [A]:') #chiede AC max charging current
        I_DCb_max = int(I_DCb_max_str)
        Quasar_WriteRegister(DCb,I_max_DCb_address,I_DCb_max) #scrittura su DCb
        status = QuasarRead(DCb, 537) #lettura charger status
        if(status == 4):
            print("Attendere, riavvio caricatore in corso")
            Quasar_WriteRegister(DCb,257,1) #fai ripartire la ricarica
            time.sleep(18) #per lasciare il tempo alla DCb di ripartire
        #I_DCb_max = int(I_DCb_max_str)
        
        #Quasar_WriteRegister(DCb,I_max_DCb_address,I_DCb_max) #scrittura su DCb
        
   
        print("Attendere 10 secondi")
        time.sleep(10)  #attende 10 secondi: nel frattempo la DCb modula e si assesta al nuovo setpoint ordinato
        power1 = QuasarRead(DCb, 526)       #con lettura Quasar potenza attiva
        power1_kW = power1/1000
        current1 = QuasarRead(DCb, 519)     #con lettura Quasar corrente
        max_current = QuasarRead(DCb, 512) #con lettura Quasar max corrente AC attuale (quella del setpoint)
        max_power = QuasarRead(DCb, 514) #con lettura Quasar max power AC attuale (quella del setpoint)
        setpoint = QuasarRead(DCb,I_max_DCb_address)
        soc = QuasarRead(DCb, 538) #EV SOC
        while True:
            print("DCb sta assorbendo", "%.2f" % power1_kW, "kW e", "%.2f" % current1, "A. Attuale Setpoint","%.2f" % setpoint,"A. SOC", "%.2f" % soc,"%""  ESC: nuovo setpoint. ALT: stop charging")
            if keyboard.is_pressed('esc'):  #se invece vuoi interrompere tu
                break
            elif keyboard.is_pressed('alt'):  #se invece stoppare la ricarica
                Quasar_WriteRegister(DCb,257,2) #scrittura su DCb
                print("Ricarica stoppata, attendere")
                time.sleep(10) #per lasciare il tempo di stoppare la ricarica
                break
    
##########################################################################################################################


    



