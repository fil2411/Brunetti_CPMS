# programma per gestione combinata dei tre EVSEs (Quasar DC o "DCb", Alfen AC o "ACuPP", Autel AC o "ACuMS")

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

from pyModbusTCP.client import ModbusClient
from datetime import datetime
import struct
import math

#indirizzi registri meter simulato Autel (ACuMS)
APP_POWER: int = 19
VOLTAGE: int = 1

#Definizione di tutti gli indirizzi IP usati nel setup sperimentale
IP_Mc = '192.168.170.170' #meter centrale
IP_M_ACuMS = '192.168.170.171' #meter Autel
IP_M_ACuPP = '192.168.170.172' #meter Alfen
IP_M_DCb = '192.168.170.173' #meter Quasar
IP_M_home_HH = '192.168.170.174' #meter load emulator HH
IP_M_PV = '192.168.170.175' #meter CINERGIA
IP_ACuPP = '192.168.170.120' #EVSE Alfen
IP_DCb = '192.168.170.18' #EVSE Quasar
#IP_MOXA = '192.168.170.180'
#IP_PC = '192.168.170.253'

Mc = ModbusTcpClient(host = IP_Mc, port = 502) #meter centrale
#client1 = ModbusTcpClient(host = IP_M_ACuMS, port = 502) #meter Autel
M_ACuMS = ModbusTcpClient(host = IP_M_ACuMS, port = 502) #meter Autel
M_ACuPP = ModbusTcpClient(host = IP_M_ACuPP, port = 502) #meter Alfen
M_DCb = ModbusTcpClient(host = IP_M_DCb, port = 502) #meter Quasar
M_home_HH = ModbusTcpClient(host = IP_M_home_HH, port = 502) #meter load emulator HH
M_PV = ModbusTcpClient(host = IP_M_PV, port = 502) #meter CINERGIA
ACuPP = ModbusTcpClient(host = IP_ACuPP, port = 502) #EVSE Alfen
DCb = ModbusTcpClient(host = IP_DCb, port = 502) #EVSE Quasar 

#Definizione POTENZA FORNITURA
P_forn = float(9000) #[W]
#Riserva di carica % per Autel
Ris = float(5) #per l'Autel pongo la riserva di carica al minimo 5%
#calcolo della p_allocabile per la Autel
P_allocabile = P_forn-0.05*P_forn-(Ris/100)*P_forn #p_allocabile è quella massima resa disponibile alla Autel
#potenza ricarica max EV AUTEL
P_ricarica_max = float(6500)  #es: 6,6 kW per Nissan Leaf, 7,4 kW se usi modello EV monofase da CDS

I_max_DCb_address: int = 258 #indirizzo modbus su cui scrivere setpoint corrente DCb
I_max_ACuPP_address: int = 1210 #indirizzo modbus su cui scrivere setpoint corrente ACuPP

#settaggio per scrittura registri meter simulato Autel (ACuMS)
HoldingRegisters = ModbusSequentialDataBlock(64514, [0]*1)
InputRegisters = ModbusSequentialDataBlock(0, [0]*25)
lock = threading.Lock()

#inizia il thread "server", dedicato alla costruzione e comunicazione con il meter simulato per la Autel AC
def server():
    # Define your Modbus Slave Context
    store = ModbusSlaveContext(
        hr=HoldingRegisters,                                # Holding Registers
        ir=InputRegisters)                                  # Input Registers

    context = ModbusServerContext(slaves=store, single=True)
    StartSerialServer(context=context, framer=ModbusRtuFramer, port='COM6', baudrate=9600)

def stop():
    #stop ricarica per DCb
    while(True):
        #print("Premere ALT per stop DCb")
        if keyboard.is_pressed('alt'):  #se invece stoppare la ricarica
            lock.acquire()
            Quasar_WriteRegister(I_max_DCb_address,6) #scrittura su DCb 6A, in modo che al prossimo lancio di ricarica questo parte da 6A
            Quasar_WriteRegister(257,2) #scrittura su DCb
            lock.release()
            #Quasar_WriteRegister(DCb,I_max_DCb_address,6) #imponi 6A come limite max per prossima ripartenza
            print("Ricarica DCb stoppata")
            time.sleep(5) #per lasciare il tempo di stoppare la ricarica


def WriteInputRegister(addr, val):    #usata per scrittura registro seriale RS485 su meter simulato per controllo Autel AC
    builder = BinaryPayloadBuilder(wordorder=Endian.LITTLE, byteorder=Endian.BIG)    
    builder.reset()
    builder.add_32bit_float(val)
    payload = builder.to_registers()
    #print(val)
    temp = payload[1]
    payload[1] = payload[0]
    payload[0] = temp
    InputRegisters.setValues(addr,  payload)

#definisco la funzione di lettura meter Siemens del registro 25+26 (potenza attiva su L1)
def SiemensReadPower (siemens):
    if (siemens.connect()):
        reg = siemens.read_holding_registers(25, 2, slave=1) #legge il registro della potenza attiva della wallbox
        decoder = BinaryPayloadDecoder.fromRegisters(reg.registers, Endian.BIG, wordorder=Endian.BIG)
        f = decoder.decode_32bit_float()
        siemens.close()
        #return f 
    return f 
    
#definisco la funzione di lettura meter Siemens dei registri qualsiasi addr e addr+1 
def SiemensRead (siemens, addr):
    if (siemens.connect()):
        reg = siemens.read_holding_registers(addr, 2, slave=1) #legge il registro della potenza attiva della wallbox
        decoder = BinaryPayloadDecoder.fromRegisters(reg.registers, Endian.BIG, wordorder=Endian.BIG)
        f = decoder.decode_32bit_float()
        siemens.close()
        #return f 
    return f 
        
#definisco la funzione di lettura registri su EVSE ACuPP (Alfen AC)
def AlfenRead (addr):
    err = True
    f = 0.0
    ret = {"err": err, "f": f}
    
    if (ACuPP.connect()):
        reg = ACuPP.read_holding_registers(addr, 2, slave=1) #legge il registro addr e addr+1
        decoder = BinaryPayloadDecoder.fromRegisters(reg.registers, Endian.BIG, wordorder=Endian.BIG)
        f = decoder.decode_32bit_float()
        ACuPP.close()
        err = False
        ret["err"] = err
        ret["f"] = f
    else:
        for maxIter in range(10):
            time.sleep(1)
            print('Tentativi connessione Alfen',maxIter)
            if(ACuPP.connect()):
                reg = ACuPP.read_holding_registers(addr, 2, slave=1) #legge il registro addr e addr+1
                decoder = BinaryPayloadDecoder.fromRegisters(reg.registers, Endian.BIG, wordorder=Endian.BIG)
                f = decoder.decode_32bit_float()
                ACuPP.close()
                err = False
                ret["err"] = err
                ret["f"] = f
                break
        
    return ret 
    
#definisco la funzione di scrittura registri su EVSE ACuPP (Alfen AC) 
#If you need to write floating point values, you'll have to build a payload and then write it to the registers   
def Alfen_WriteRegister(addr, val):
    if (ACuPP.connect()):
        builder = BinaryPayloadBuilder(wordorder=Endian.BIG, byteorder=Endian.BIG)    
        builder.add_32bit_float(val)
        payload = builder.to_registers()
        ACuPP.write_registers(addr, payload, slave=1)
        ACuPP.close()


#definisco la funzione di lettura registri su EVSE DCb (Quasar DC)
def QuasarRead (addr):
    f = 0.0
    lock.acquire()
    if (DCb.connect()):
        reg = DCb.read_holding_registers(addr, 1, slave=1) #legge il registro addr
        decoder = BinaryPayloadDecoder.fromRegisters(reg.registers, Endian.BIG, wordorder=Endian.BIG)
        f = decoder.decode_16bit_int()
        DCb.close()
    lock.release()
    return f 
    
#definisco la funzione di scrittura registri su EVSE DCb (Quasar DC) 
def Quasar_WriteRegister(addr, val):
    if (DCb.connect()):
        DCb.write_register(addr, val, slave=1)
        DCb.close()

#Output per DCb
def Output_DCb():
    power_DCb = SiemensReadPower(M_DCb)       #con lettura DCb potenza attiva
    power_DCb_kW = float(power_DCb/1000)
    currentDCb = SiemensRead(M_DCb, 13)     #con lettura Quasar corrente
    setpointDCb = QuasarRead(I_max_DCb_address) #DCb
    soc = QuasarRead(538) #EV SOC
    print("DCb assorbe", "%.2f" % power_DCb_kW, "kW e", "%.2f" % currentDCb, "A. Setpoint DCB", setpointDCb,"A. SOC", soc,"%")

#Output per ACuPP
def Output_ACuPP():
    #powerACuPP = AlfenRead(344)       #con lettura Alfen potenza attiva
    powerACuPP = SiemensReadPower(M_ACuPP)
    power_ACuPP_kW = float(powerACuPP/1000)
    
    currentACuPP = SiemensRead(M_ACuPP, 13)

       
    #max_currentACuPP = AlfenRead(1210)
    #if (not max_currentACuPP["err"]):
       # print("ACuPP assorbe", "%.2f" % power_ACuPP_kW, "kW e", "%.2f" % currentACuPP, "A. Setpoint ACuPP",  max_currentACuPP["f"], "A")
        
    #else:
        #print ("Error in Alfen_Read")
    print("ACuPP assorbe", "%.2f" % power_ACuPP_kW, "kW e", "%.2f" % currentACuPP, "A. Setpoint ACuPP")
#Output per ACuMS
def Output_ACuMS(setpoint_ACuMS):
    powerACuMS = SiemensReadPower (M_ACuMS)
    powerACuMS_kW = float(powerACuMS/1000)
    P_desiderata_kW = setpoint_ACuMS/1000
    print("ACuMS assorbe:", "%.2f" % powerACuMS_kW, "kW Setpoint ACuMS", "%.2f" % P_desiderata_kW, "kW" )

#inizia il thread "application", dedicato alla parte principale dell'algoritmo di gestione
def application ():
  

    HoldingRegisters.setValues(1, 0)   #settaggio holding register "ignoto" per funzionamento Autel
    WriteInputRegister(VOLTAGE, 230.0) #scrittura tensione su registro meter simulato Autel
    
    VALUE = 0 #inizializzi #così la wallbox va a caricare al massimo valore a cui può arrivare (P_allocabile se P_allocabile < P_ricarica_max //&// P_ricarica_max se P_allocabile > P_ricarica_max)
    WriteInputRegister(APP_POWER, VALUE)  #scrittura iniziale potenza Autel (con 0 la EVSE va ad erogare la max potenza possibile)

    #Alfen_WriteRegister(I_max_ACuPP_address,6) #inizializzo la Alfen a 6 A massimi

    #DEFINIZIONE P1 Quasar DC

    #Lettura SOC con Quasar
    def Setpoint_Quasar():
        
        
        #Lettura bilancio netto produzione PV/assorbimento HOME
        #P_load = SiemensReadPower (M_PV) #[W], positiva: PV > HOME (PRODUZIONE); negativa: PV < HOME (ASSORBIMENTO)
        P_DCb = QuasarRead(526)       #con lettura Quasar potenza attiva
        P_DCb_meter = SiemensReadPower(M_DCb)
        soc = QuasarRead(538) #lettura EV SOC  #addr. 538
        voltage = SiemensRead (Mc, 1) #lettura tensione fase 1 da meter centrale siemens

        #Condizioni di imposizione setpoint di potenza alla Quasar (in base a SOC e disponibilità fornitura)        
        if (((P_forn - P_load)>= 1380) and (P_DCb_meter > 100)): 
            
            if(soc > 90):
                I_D = int(6)
                
            elif(40 <= soc <= 90):
                I_D = math.floor((-0.52*soc)+52.8)  #equazione retta
                
            elif(soc < 40):
                I_D = int(32)
               
            elif(soc == 99): #metto 99 perchè non voglio rischiare che mi interrompa la prova in malomodo. forse questa condizione non è necessaria siccome l'EV interrompe in automatico la ricarica quando è carico
                lock.acquire()
                Quasar_WriteRegister(257,2) #stoppi ricarica
                lock.release()
                I_D = int(0)
                print("EV DCb carico al 100 %")
                
        elif((P_forn - P_load) < 1380):
            lock.acquire()
            Quasar_WriteRegister(257,2) #impone stato di interruzione ricarica
            lock.release()
            I_D = int(0)
            print("Potenza fornitura insufficiente, impossibile avviare ricarica DCb")
            
        elif(P_DCb_meter < 100):
            print("DCb non collegata all'EV")
            #I_D = int(0) #stoppi ricarica
            I_D = int(3) #stoppi ricarica

        I_disp = math.floor((P_forn - P_load)/voltage) #math.floor approssima all'intero inferiore
        I_setpoint_DCb = min(I_D,I_disp)
        return I_setpoint_DCb
    

    
    
    #nelle funzioni setpoint ALFEN e AUTEL verifica quali dei due caricatori sono in ricarica, calcolo potenza disponibile rimasta e attribuisci la quota desiderata 
    def Setpoint_Alfen_e_Autel():
        P_DCb_meter = SiemensReadPower (M_DCb)
        P_ACuPP_meter = SiemensReadPower (M_ACuPP)
        P_ACuMS = SiemensReadPower (M_ACuMS) #[W]
        voltage_ACuPP = SiemensRead(M_ACuPP, 1)

        if((P_DCb_meter > 1300) and (P_ACuPP_meter > 1300) and (P_ACuMS > 1300)):  #tutte e tre stanno caricando
            print("DCb, ACuPP, ACuMS stanno caricando")
            I_set_DCb = Setpoint_Quasar()
            P_set_DCb = I_set_DCb*voltage_ACuPP
            n = 2 #n. caricatori in ricarica oltre alla DCb
            P_disponibile = math.floor(P_forn - P_load - P_set_DCb)
            I_disponibile = math.floor(P_disponibile/voltage_ACuPP)

            if(P_disponibile >= 2800):
                I_setpoint_ACuPP = math.floor(I_disponibile/n) #setpoint Alfen
                #P_ACuMS_max1 = ((I_disponibile - I_setpoint_ACuPP)*voltage_ACuPP)
                P_ACuMS_max1 = P_disponibile/n #setpoint Autel
                P_ACuMS_max = round(P_ACuMS_max1, 1)
            elif(1400 <= P_disponibile < 2800):
                #I_setpoint_ACuPP = float(I_disponibile) #setpoint Alfen
                I_setpoint_ACuPP = I_disponibile
                P_ACuMS_max = float(0) #setpoint Autel
                print("ACuMS non può ricaricare, potenza disponibile insufficiente")
            else:
                I_setpoint_ACuPP = float(0) #setpoint Alfen
                P_ACuMS_max = float(0) #setpoint Autel
                print("ACuPP e ACuMS non possono ricaricare, potenza disponibile insufficiente")
        

        elif((P_DCb_meter > 1300) and (P_ACuPP_meter > 1300) and (P_ACuMS < 1000)):  #Quasar e Alfen stanno caricando
            print("DCb e ACuPP stanno caricando")
            I_set_DCb = Setpoint_Quasar()
            P_set_DCb = I_set_DCb*voltage_ACuPP
            n = 1 #n. caricatori in ricarica oltre alla DCb
            P_disponibile = math.floor(P_forn - P_load - P_set_DCb)
            I_disponibile = math.floor(P_disponibile/voltage_ACuPP)

            if(P_disponibile >= 1400):
                #I_setpoint_ACuPP = float(I_disponibile/n) #setpoint Alfen
                I_setpoint_ACuPP = math.floor(I_disponibile/n) #setpoint Alfen
                P_ACuMS_max = float(0) #setpoint Autel
            else:
                I_setpoint_ACuPP = float(0) #setpoint Alfen
                P_ACuMS_max = float(0) #setpoint Autel
                print("ACuPP non può ricaricare, potenza disponibile insufficiente")


        elif((P_DCb_meter > 1300) and (P_ACuPP_meter < 1000) and (P_ACuMS > 1300)):  #Quasar e Autel stanno caricando
            print("DCb e ACuMS stanno caricando")
            I_set_DCb = Setpoint_Quasar()
            P_set_DCb = I_set_DCb*voltage_ACuPP
            n = 1 #n. caricatori in ricarica oltre alla DCb
            P_disponibile = math.floor(P_forn - P_load - P_set_DCb)
            I_disponibile = math.floor(P_disponibile/voltage_ACuPP)

            if(P_disponibile >= 1400):
                I_setpoint_ACuPP = float(6) #setpoint Alfen
                #P_ACuMS_max1 = ((I_disponibile - I_setpoint_ACuPP)*voltage_ACuPP)
                P_ACuMS_max1 = float(P_disponibile/n) #setpoint Autel
                P_ACuMS_max = round(P_ACuMS_max1, 1)
            else:
                I_setpoint_ACuPP = float(0) #setpoint Alfen
                P_ACuMS_max = float(0) #setpoint Autel
                print("ACuMS non può ricaricare, potenza disponibile insufficiente")


        elif((P_DCb_meter < 1000) and (P_ACuPP_meter > 1300) and (P_ACuMS > 1300)):  #Alfen e Autel stanno caricando
            print("ACuPP e ACuMS stanno caricando")
            P_set_DCb = 0 #le dici di fregarsene del setpoint della DCb, considerandolo nullo
            n = 2 #n. caricatori in ricarica oltre alla DCb
            P_disponibile = math.floor(P_forn - P_load - P_set_DCb)
            I_disponibile = math.floor(P_disponibile/voltage_ACuPP)

            if(P_disponibile >= 2800):
                I_setpoint_ACuPP = math.floor(I_disponibile/n) #setpoint Alfen
                #P_ACuMS_max1 = ((I_disponibile - I_setpoint_ACuPP)*voltage_ACuPP)
                P_ACuMS_max1 = float(P_disponibile/n) #setpoint Autel
                P_ACuMS_max = round(P_ACuMS_max1, 1) #setpoint Autel
            elif(1400 <= P_disponibile < 2800):
                I_setpoint_ACuPP = math.floor(I_disponibile) #setpoint Alfen
                P_ACuMS_max = float(0) #setpoint Autel
                print("ACuMS non può ricaricare, potenza disponibile insufficiente")
            else:
                I_setpoint_ACuPP = float(0) #setpoint Alfen
                P_ACuMS_max = float(0) #setpoint Autel
                print("ACuPP e ACuMS non possono ricaricare, potenza disponibile insufficiente")


        elif((P_DCb_meter < 1000) and (P_ACuPP_meter > 1300) and (P_ACuMS < 1300)):  #Alfen sta caricando
            print("ACuPP sta caricando")
            P_set_DCb = 0 #le dici di fregarsene del setpoint della DCb, considerandolo nullo
            n = 1 #n. caricatori in ricarica oltre alla DCb
            P_disponibile = math.floor(P_forn - P_load - P_set_DCb)
            I_disponibile = math.floor(P_disponibile/voltage_ACuPP)

            if(P_disponibile >= 1400):
                I_setpoint_ACuPP = math.floor(I_disponibile/n) #setpoint Alfen
                P_ACuMS_max = float(0) #setpoint Autel
            else:
                I_setpoint_ACuPP = float(0) #setpoint Alfen
                P_ACuMS_max = float(0) #setpoint Autel
                print("ACuPP non può ricaricare, potenza disponibile insufficiente")


        elif((P_DCb_meter < 1000) and (P_ACuPP_meter < 1300) and (P_ACuMS > 1300)):  #Autel sta caricando
            print("ACuMS sta caricando")
            P_set_DCb = 0 #le dici di fregarsene del setpoint della DCb, considerandolo nullo
            n = 1 #n. caricatori in ricarica oltre alla DCb
            P_disponibile = math.floor(P_forn - P_load - P_set_DCb)
            I_disponibile = math.floor(P_disponibile/voltage_ACuPP)

            if(P_disponibile >= 1400):
                I_setpoint_ACuPP = float(6) #setpoint Alfen
                P_ACuMS_max1 = float(P_disponibile/n) #setpoint Autel
                P_ACuMS_max = round(P_ACuMS_max1, 1) #setpoint Autel
            else:
                I_setpoint_ACuPP = float(0) #setpoint Alfen
                P_ACuMS_max = float(0) #setpoint Autel
                print("ACuMS non può ricaricare, potenza disponibile insufficiente")

        elif((P_DCb_meter > 1300) and (P_ACuPP_meter < 1300) and (P_ACuMS < 1300)):  #Quasar sta caricando
            print("DCb sta caricando")
            I_set_DCb = Setpoint_Quasar()
            P_set_DCb = I_set_DCb*voltage_ACuPP 
            n = 0 #n. caricatori in ricarica oltre alla DCb
            P_disponibile = math.floor(P_forn - P_load - P_set_DCb)
            I_disponibile = math.floor(P_disponibile/voltage_ACuPP)

            if(P_disponibile >= 1400):
                I_setpoint_ACuPP = float(6) #setpoint Alfen
                P_ACuMS_max = float(1400) #setpoint Autel
            else:
                I_setpoint_ACuPP = float(0) #setpoint Alfen
                P_ACuMS_max = float(0) #setpoint Autel
                print("ACuMS non può ricaricare, potenza disponibile insufficiente")

        else:
            print("Nessuna delle tre sta caricando")
            I_setpoint_ACuPP = float(6) #setpoint Alfen
            P_ACuMS_max = float(0) #setpoint Autel

        
        return I_setpoint_ACuPP, P_ACuMS_max
       
     
    I_DCb_max_old = 0
    I_ACuPP_max_old = 0
        
    while(True):
        P_load = SiemensReadPower (M_PV) #[W], positiva: PV > HOME (PRODUZIONE); negativa: PV < HOME (ASSORBIMENTO)
        P_ACuPP = SiemensReadPower(M_ACuPP) #[W] 
        P_ACuMS = SiemensReadPower (M_ACuMS) #[W]

        if(P_ACuPP < 1300):
            Alfen_WriteRegister(I_max_ACuPP_address,6) #scrittura su ACuPP 

        

        #Assegnazione setpoint Quasar
        I_DCb_max = Setpoint_Quasar()
        if(I_DCb_max != I_DCb_max_old):
            lock.acquire()
            Quasar_WriteRegister(I_max_DCb_address,I_DCb_max) #scrittura su DCb
            lock.release()
            I_DCb_max_old = I_DCb_max
        
        time.sleep(2)
        
        res = Setpoint_Alfen_e_Autel()
        #Assegnazione setpoint Alfen
        I_ACuPP_max = res[0]
        #Assegnazione setpoint Autel
        P_desiderata = res[1]
        #if(I_ACuPP_max != I_ACuPP_max_old): #ho tolto la condizione perchè altrimenti dopo il validity time la ACuPP andava alla safe current. così no, rimane al setpoint desiderato
        Alfen_WriteRegister(I_max_ACuPP_address,I_ACuPP_max) #scrittura su ACuPP 
        ##I_ACuPP_max_old = I_ACuPP_max 
                     
        #P_ACuMS = SiemensReadPower (M_ACuMS) #[W]
        if (P_ACuMS > 50):
            #time.sleep(1)  #superfluo
            P_desiderata_old = SiemensReadPower(M_ACuMS) 
        
        #if(P_desiderata != P_desiderata_old): #aggiungi range sopra e sotto
            #if((P_desiderata < (P_desiderata_old - 100)) or (P_desiderata > (P_desiderata_old + 100))):
            if((P_desiderata < (P_desiderata_old - 250)) or (P_desiderata > (P_desiderata_old + 250))):
            #1    #se P_desiderata è maggiore o uguale di P_ricarica_max con P_allocabile > o = P_ricarica_max
                if ((P_desiderata >= P_ricarica_max) and (P_allocabile >= P_ricarica_max)):
                    y = float(P_ricarica_max/100) #variabile piccola (circa 65)
                    flag_count = 0
                    while(True):
                    #scrivo su registro modbus del meter simulato 0
                        P_apparent_meter = 0 #la wallbox va a caricare alla P_ricarica_max
                        VALUE = P_apparent_meter
                        WriteInputRegister(APP_POWER, VALUE) #assegni input register
                    #y = float(P_ricarica_max/100) #variabile piccola 
                    #aa=float(200)
                    #while(True):
                        power = SiemensReadPower (M_ACuMS)  #lettura p_wallbox (che cresce progressivamente)
                        print("ACuMS assorbe1:", "%.2f" % power,"W")
                        power_kW = power/1000
                        flag_count +=1

                        if(0 < power < 50):
                            flag_count = 0 #reinizializzo a 0 per nuovo loop
                            print("ACuMS sta assorbendo", "%.2f" % power_kW, "kW: ricarica fermata")
                            break

                    #power_Mc = SiemensReadPower (client_Mc) #lettura potenza assorbita complessiva al nodo generale primario (sta aumentando anche lei)
                
                    #quando p_wallbox arriva in un certo range (P_ricarica_max - quota piccola) o contatore 3000, aggiorno la condizione
                        elif((power > P_ricarica_max - y) or flag_count == 150): #si mette contatore per evitare che loop vada all'infinito casomai non si verifichi perfettamente la condizione
                    #if(power > P_ricarica_max - 100): prova al limite questo, in modo che sia sempre dentro questo if e non esca mai al di fuori
                    #scrivo su registro modbus del meter simulato p_allocabile per fissare la p_wallbox
                            P_apparent_meter = P_allocabile
                            VALUE = P_apparent_meter
                            WriteInputRegister(APP_POWER, VALUE)
                            power = SiemensReadPower (M_ACuMS) #lettura potenza assorbita da Autel
                            power_kW = power/1000
                            print("ACuMS sta assorbendo", "%.2f" % power_kW, "kW: potenza max")
                            flag_count = 0 #reinizializzo a 0 per nuovo loop
                            break
                    P_desiderata_old = power #in [W]
                
                
            #2    #se P_desiderata è uguale a P_wallbox a meno di 100 W (vale sia per P_allocabile < P_ric_max sia P__allocabile > P_ric_max)
                #elif ((P_desiderata >= P_desiderata_old - 100) and (P_desiderata <= P_desiderata_old + 100)):
                elif ((P_desiderata >= P_desiderata_old - 250) and (P_desiderata <= P_desiderata_old + 250)):
            #elif ((P_desiderata >= power - 100) and (P_desiderata <= power + 100)):

                    P_apparent_meter = P_allocabile #la wallbox rimane a caricare alla stessa potenza
                    VALUE = P_apparent_meter
                    WriteInputRegister(APP_POWER, VALUE) #assegno input register
                    power = SiemensReadPower (M_ACuMS)
                    power_kW = power/1000
                    print("ACuMS assorbe2", "%.2f" % power_kW, "kW, NESSUNA MODULAZIONE")
                
                    P_desiderata_old = power #in [W]
                 
            
       
            #3    #se P_desiderata è minore di P_wallbox - 100 (vale sia per P_allocabile < P_ric_max sia P__allocabile > P_ric_max)
                #elif (P_desiderata < P_desiderata_old - 100):
                elif (P_desiderata < P_desiderata_old - 250):
                    x = 100 #variabile piccola
                    flag_count = 0
                    while(True):            
                        P_apparent_meter = P_allocabile + float(P_desiderata_old - P_desiderata) #la wallbox inizia a ridurre la potenza (bruscamente)
                        VALUE = P_apparent_meter            
                        WriteInputRegister(APP_POWER, VALUE)#assegni valore input register
                #x = 100 #variabile piccola
                #while(True):
                        power = SiemensReadPower (M_ACuMS)
                        print("ACuMS assorbe3:", "%.2f" % power,"W")
                        power_kW = power/1000
                        flag_count +=1
                        if(0 < power < 50):
                            flag_count = 0 #reinizializzo a 0 per nuovo loop
                            print("ACuMS sta assorbendo", "%.2f" % power_kW, "kW: ricarica fermata")
                            break
                    #quando questa è minore di P_desiderata + 33 o contatore a 3000, aggiorno la condizione e assegno registro
                        elif ((power < P_desiderata + float(x/3)) or flag_count == 150): #P_desiderata + 33
                            P_apparent_meter = P_allocabile 
                            VALUE = P_apparent_meter
                            WriteInputRegister(APP_POWER, VALUE) #assegno input register
                            power = SiemensReadPower (M_ACuMS)
                            power_kW = power/1000
                            print("ACuMS sta assorbendo", "%.2f" % power_kW, "kW")
                            flag_count = 0
                            break
                    P_desiderata_old = power #in [W]
                
                    
            #4    #se P_desiderata è maggiore di P_wallbox + 100 ma minore di P_ricarica_max con P_allocabile > o = P_ric_max
                #elif ((P_desiderata > P_desiderata_old + 100) and (P_desiderata < P_ricarica_max) and (P_allocabile >= P_ricarica_max)):
                elif ((P_desiderata > P_desiderata_old + 250) and (P_desiderata < P_ricarica_max) and (P_allocabile >= P_ricarica_max)):    
                    z = 100 #variabile piccola
                    flag_count = 0
                    while(True):
                        P_apparent_meter = P_allocabile - float(P_desiderata - P_desiderata_old) #la wallbox inizia a aumentare la potenza (bruscamente)
                        VALUE = P_apparent_meter            
                        WriteInputRegister(APP_POWER, VALUE)#assegni valore input register
                #while(True):
                        power = SiemensReadPower (M_ACuMS)
                        print("ACuMS assorbe4:", " %.2f" % power,"W")
                        power_kW = power/1000
                        flag_count +=1
                        if(0 < power < 50):
                            flag_count = 0 #reinizializzo a 0 per nuovo loop
                            print("ACuMS sta assorbendo", "%.2f" % power_kW, "kW: ricarica fermata")
                            break
                    #quando questa è maggiore di P_desiderata - 33 o contatore a 3000, aggiorno la condizione e assegno registro
                        elif ((power > P_desiderata - float(z/3)) or flag_count == 150): #P_desiderata - 33
                            P_apparent_meter = P_allocabile 
                            VALUE = P_apparent_meter
                            WriteInputRegister(APP_POWER, VALUE) #assegno input register
                            power = SiemensReadPower (M_ACuMS)
                            power_kW = power/1000
                            print("ACuMS assorbe:", "%.2f" % power_kW, "kW")
                            flag_count = 0
                            break
                    P_desiderata_old = power #in [W]
                


        #condizioni aggiuntive se caso P_allocabile < P_ricarica_max_EV

            #5   #se P_desiderata è maggiore o uguale di P_allocabile con P_allocabile < P_ricarica_max
                elif ((P_desiderata >= P_allocabile) and (P_allocabile < P_ricarica_max)):
                    a = float(P_ricarica_max/100)
                    aa=float(200)
                    flag_count = 0
                    while(True):
                        P_apparent_meter = 0 #la wallbox va a caricare alla P_ricarica_max
                        VALUE = P_apparent_meter
                        WriteInputRegister(APP_POWER, VALUE) #assegni input register
            #a = float(P_ricarica_max/100)
            #aa=float(200)
            #while(True):
                        power = SiemensReadPower (M_ACuMS)
                        print("ACuMS assorbe5:",power,"W")
                        power_kW = power/1000
                        flag_count +=1
                        if(0 < power < 50):
                            flag_count = 0 #reinizializzo a 0 per nuovo loop
                            print("ACuMS sta assorbendo", "%.2f" % power_kW, "kW: ricarica fermata")
                            break
                #quando questa arriva in un certo range (P_allocabile) o contatore 3000,  aggiorno la condizione
                        elif((power > P_allocabile - a - aa) or flag_count == 150): 
                            P_apparent_meter = P_allocabile
                            VALUE = P_apparent_meter
                            WriteInputRegister(APP_POWER, VALUE)
                            power = SiemensReadPower (M_ACuMS)
                            power_kW = power/1000
                            print("ACuMS sta assorbendo", "%.2f" % power_kW, "kW: EV non può assorbire di più")
                            flag_count = 0
                            break
                    P_desiderata_old = power #in [W]
                
                        
                    
        
            #6    #se P_desiderata è maggiore di P_wallbox + 100 ma minore di P_allocabile con P_allocabile < P_ric_max
                #elif ((P_desiderata > P_desiderata_old + 100) and (P_desiderata < P_allocabile) and (P_allocabile < P_ricarica_max)):
                elif ((P_desiderata > P_desiderata_old + 250) and (P_desiderata < P_allocabile) and (P_allocabile < P_ricarica_max)):
                    b = 100 #variabile piccola
                    flag_count = 0
                    while(True):
                        P_apparent_meter = P_allocabile - float(P_desiderata - P_desiderata_old) #la wallbox inizia a aumentare la potenza (bruscamente)
                        VALUE = P_apparent_meter            
                        WriteInputRegister(APP_POWER, VALUE)#assegni valore input register
            #while(True):
                        power = SiemensReadPower (M_ACuMS)
                        print("ACuMS assorbe6:", "%.2f" % power,"W")
                        power_kW = power/1000
                        flag_count +=1
                        if(0 < power < 50):
                            flag_count = 0 #reinizializzo a 0 per nuovo loop
                            print("ACuMS sta assorbendo", "%.2f" % power_kW, "kW: ricarica fermata")
                            break
                #quando questa è maggiore di P_desiderata - 33 o contatore 3000, aggiorno la condizione e assegno registro
                        elif ((power > P_desiderata - float(b/3)) or flag_count == 150): #P_desiderata - 33
                            P_apparent_meter = P_allocabile 
                            VALUE = P_apparent_meter
                            WriteInputRegister(APP_POWER, VALUE) #assegno input register
                            power = SiemensReadPower (M_ACuMS)
                            power_kW = power/1000
                            print("ACuMS assorbe:", "%.2f" % power_kW, "kW")
                            flag_count = 0
                            break
                    P_desiderata_old = power #in [W]
               
       
            else:
                print("ACuMS NON VARIA il suo setpoint")
        
        

        #OUTPUTS
        Output_DCb()
        Output_ACuPP()
        Output_ACuMS(P_desiderata)
        

        power_disp_wallboxes = P_forn - P_load
        print("P. disp x wallboxes:", "%.2f" % power_disp_wallboxes, "W")

def meter():
    # INDIRIZZI IP DEI METER
#(al PC server assegnato IP 192.168.170.169)

    IP_Meter_Centrale = '192.168.170.170'       #meter centrale
    IP_Meter_ACuMS= '192.168.170.171'       #meter della colonnina Autel AC  
    IP_Meter_ACuPP = '192.168.170.172'       #meter della colonnina Alfen AC
    IP_Meter_DCb = '192.168.170.173'       #meter della colonnina Quasar DC
    IP_Meter_HH = '192.168.170.174'       #meter del carico domestico HH
    IP_Meter_PV = '192.168.170.175'       #meter del PV cinergia   


    timeout_meter = 1
    port = 502
    granularity=0.5 #seconds
# DEFINIZIONE DEI METER: definisco i client che interrogano i meter implementati
#

# Mc=ModbusClient(host= IP_Meter_Centrale, port= 502)
    M_C = ModbusClient(host = IP_Meter_Centrale, auto_open=True, auto_close=True, debug=False, timeout=timeout_meter) 
    M_ACuMS = ModbusClient(host = IP_Meter_ACuMS, auto_open=True, auto_close=True, debug=False, timeout=timeout_meter,port=port)
    M_ACuPP = ModbusClient(host = IP_Meter_ACuPP, auto_open=True, auto_close=True, debug=False, timeout=timeout_meter,port=port)
    M_DCb = ModbusClient(host = IP_Meter_DCb, auto_open=True, auto_close=True, debug=False, timeout=timeout_meter,port=port)
    M_HH = ModbusClient(host = IP_Meter_HH, auto_open=True, auto_close=True, debug=False, timeout=timeout_meter,port=port)
    M_PV = ModbusClient(host = IP_Meter_PV, auto_open=True, auto_close=True, debug=False, timeout=timeout_meter,port=port)


    while True:
     #client.connect()
     
        try: 
            rr = M_C.read_holding_registers(1,36) 
            test=[struct.unpack('!f', struct.pack('!I', (int(rr[idx]) << 16) | int(rr[idx+1])))[0] for idx in range(0,len(rr),2)]
        except TypeError:
        #test=[]
            print('error')
    
        try:
            rr2=M_ACuMS.read_holding_registers(1,36)
            test2=[struct.unpack('!f', struct.pack('!I', (int(rr2[idx]) << 16) | int(rr2[idx+1])))[0] for idx in range(0,len(rr2),2)]
        except TypeError:
            print('error')

        try:
            rr3=M_ACuPP.read_holding_registers(1,36)
            test3=[struct.unpack('!f', struct.pack('!I', (int(rr3[idx]) << 16) | int(rr3[idx+1])))[0] for idx in range(0,len(rr3),2)]
        except TypeError:
            print('error')

        try:
            rr4=M_DCb.read_holding_registers(1,36)
            test4=[struct.unpack('!f', struct.pack('!I', (int(rr4[idx]) << 16) | int(rr4[idx+1])))[0] for idx in range(0,len(rr4),2)]
        except TypeError:
            print('error')

        try:
            rr5=M_HH.read_holding_registers(1,36)
            test5=[struct.unpack('!f', struct.pack('!I', (int(rr5[idx]) << 16) | int(rr5[idx+1])))[0] for idx in range(0,len(rr5),2)]
        except TypeError:
            print('error')

        try:
            rr6=M_PV.read_holding_registers(1,36)
            test6=[struct.unpack('!f', struct.pack('!I', (int(rr6[idx]) << 16) | int(rr6[idx+1])))[0] for idx in range(0,len(rr6),2)]
        except TypeError:
            print('error')

        with open('M_C.csv','a') as file:
            file.write(datetime.now().isoformat()+','+str(test)[1:-1]+','+'meter Mc'+','+'\n')
    
    
        with open('M_ACuMS.csv','a') as file:
            file.write(datetime.now().isoformat()+','+str(test2)[1:-1]+','+'meter ACuMS'+','+'\n')  

        
        with open('M_ACuPP.csv','a') as file:
            file.write(datetime.now().isoformat()+','+str(test3)[1:-1]+','+'meter ACuPP'+','+'\n')


        with open('M_DCb.csv','a') as file:
            file.write(datetime.now().isoformat()+','+str(test4)[1:-1]+','+'meter DCb'+','+'\n')

        
        with open('M_HH.csv','a') as file:
            file.write(datetime.now().isoformat()+','+str(test5)[1:-1]+','+'meter HH'+','+'\n')
        

        with open('M_PV.csv','a') as file:
            file.write(datetime.now().isoformat()+','+str(test6)[1:-1]+','+'meter PV'+','+'\n')
        time.sleep(granularity)
    
        if keyboard.is_pressed('esc'):
            print('exit')
            break   
       
    

    


if __name__ == "__main__":
    thread3 = threading.Thread(target = meter)
    thread4 = threading.Thread(target = stop)
    thread3.start()
    thread4.start()
    thread1 = threading.Thread(target = server)
    #thread1.daemon = True
    thread1.start()
    thread2 = threading.Thread(target = application)
    thread2.start()
    thread2.join()    
    thread1.join()
    thread3.join()
    thread4.join()
