# programma per la gestione AUTOMATICA del meter simulato tramite Moxa  
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

APP_POWER: int = 19
VOLTAGE: int = 1


HoldingRegisters = ModbusSequentialDataBlock(64514, [0]*1)
InputRegisters = ModbusSequentialDataBlock(0, [0]*25)

def server():
    # Define your Modbus Slave Context
    store = ModbusSlaveContext(
        hr=HoldingRegisters,                                # Holding Registers
        ir=InputRegisters)                                  # Input Registers

    context = ModbusServerContext(slaves=store, single=True)
    StartSerialServer(context=context, framer=ModbusRtuFramer, port='COM6', baudrate=9600)

def WriteInputRegister(addr, val):
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
def SiemensReadPower (clt):
    if (clt.connect()):
        reg = clt.read_holding_registers(25, 2, slave=1) #legge il registro della potenza attiva della wallbox
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
    

def application ():
    HoldingRegisters.setValues(1, 0)
    WriteInputRegister(VOLTAGE, 230.0)
    
    VALUE = 0 #inizializzi #così la wallbox va a caricare al massimo valore a cui può arrivare (P_allocabile se P_allocabile < P_ricarica_max //&// P_ricarica_max se P_allocabile > P_ricarica_max)
    WriteInputRegister(APP_POWER, VALUE)

    pd_str = input('Inserisci potenza disponibile fornitura (App Autel) in kW (INTERO): ')
    P_disp_kW = float(pd_str)
    P_disp=P_disp_kW*1000
    str_p_disp="P_disponibile = %.2f W" % P_disp
    print(str_p_disp)
   
    #ris_str = input('Inserisci riserva di carica (App) in percentuale (INTERO TRA 5-50): ')
    #Ris = float(ris_str)
    
    Ris = float(5)
    
    #str_ris="Riserva di carica = %.2f " % Ris
    str_ris=("Riserva di carica =", "%.2f" % Ris, "%")
    
    #print(str_ris)

    P_allocabile = P_disp-0.05*P_disp-(Ris/100)*P_disp #p_allocabile è quella massima resa disponibile alla Autel
    P_allocabile_kW=P_allocabile/1000
    str_pall="Potenza allocabile = %.2f kW" % P_allocabile_kW
    print(str_pall)
    

    prm_str = input('Inserisci potenza ricarica max veicolo in kW: ')
    
    P_ricarica_max_kW = float(prm_str)  #es: 6,6 kW per Nissan Leaf, 7,4 kW se usi modello EV monofase da CDS
    P_ricarica_max= P_ricarica_max_kW*1000

    avvio_str = input("Avviare la ricarica e poi premere INVIO quando questa si è stabilizzata")

    #definizione client
    client1 = ModbusTcpClient(host='192.168.170.171',port=502) #meter wallbox Autel
    client_Mc = ModbusTcpClient(host='192.168.170.170',port=502) #meter centrale
    client_home_HH = ModbusTcpClient(host='192.168.170.174',port=502) #meter home load
    #client_PV = ModbusTcpClient(host='192.168.170.20',port=502) #meter PV
    client_alfen = ModbusTcpClient(host='192.168.170.172',port=502) #meter alfen  in seguito si può usare lettura registro modbus della EVSE direttamente invece che il meter

    power = SiemensReadPower (client1)
    power_kW = power/1000
     
    power_alfen = SiemensReadPower (client_alfen)
    power_home_HH = SiemensReadPower (client_home_HH)
    #power_PV = SiemensReadPower (client_PV)
    power_PV = 0
    p_other_loads_initial = float(power_home_HH + power_PV + power_alfen)
    p_other_loads_initial_kW = p_other_loads_initial/1000
    
    
    #Lettura meter P_wallbox  
    print("La wallbox sta assorbendo", "%.2f" % power_kW, "kW")
    print("Gli altri carichi stanno assorbendo", "%.2f" % p_other_loads_initial_kW, "kW")
    

    pdes_str = input(f"Inserisci potenza ricarica desiderata, in kW, minore o uguale a {P_ricarica_max_kW:.2f} kW: ")
    P_desiderata_kW= float(pdes_str) 
    P_desiderata=P_desiderata_kW*1000 #in W

    
    #FASE ITERATIVA per comandare la wallbox ad una potenza desiderata
    while(True): 
        print("Potenza desiderata:", "%.2f" % P_desiderata, "W")
        print("La wallbox sta assorbendo", "%.2f" % power_kW, "kW")
        print("Gli altri carichi stanno assorbendo", "%.2f" % p_other_loads_initial_kW, "kW")
        

        
    #1    #se P_desiderata è maggiore o uguale di P_ricarica_max con P_allocabile > o = P_ricarica_max

        if ((P_desiderata >= P_ricarica_max) and (P_allocabile >= P_ricarica_max)):
            y = float(P_ricarica_max/100) #variabile piccola 
            while(True):
            #scrivo su registro modbus del meter simulato 0
                P_apparent_meter = 0 #la wallbox va a caricare alla P_ricarica_max
                VALUE = P_apparent_meter
                WriteInputRegister(APP_POWER, VALUE) #assegni input register
                #y = float(P_ricarica_max/100) #variabile piccola 
            #aa=float(200)
            #while(True):
                power = SiemensReadPower (client1)  #lettura p_wallbox (che cresce progressivamente)
                print("La wallbox assorbe:", "%.2f" % power,"W")
                power_kW = power/1000
                #power_Mc = SiemensReadPower (client_Mc) #lettura potenza assorbita complessiva al nodo generale primario (sta aumentando anche lei)
                
                #quando p_wallbox arriva in un certo range (P_ricarica_max - quota piccola) aggiorno la condizione
                if(power > P_ricarica_max - y): 
                #if(power > P_ricarica_max - 100): prova al limite questo, in modo che sia sempre dentro questo if e non esca mai al di fuori
                    #scrivo su registro modbus del meter simulato p_allocabile per fissare la p_wallbox
                    P_apparent_meter = P_allocabile
                    VALUE = P_apparent_meter
                    WriteInputRegister(APP_POWER, VALUE)
                    
                    #lettura ciclica
                    while(True):
                        power = SiemensReadPower (client1) #lettura potenza assorbita da Autel
                        power_kW = power/1000
                        print("La wallbox sta assorbendo", "%.2f" % power_kW, "kW: il veicolo non può assorbire di più, ESC per nuovo setpoint")
                    
                    
                        #ragionare su altri carichi: se questi cambiano, esci da ciclo while e si ha nuova p-desiderata data da combinazione
                        #lettura meter centrale
                        #se questa cambia oltre un certo range allora esci da while true interno (rimane in quello esterno) e wallbox attende nuova p-desiderata: la imponi uguale a qualcosa definito in funzione delle altre wallbox e dei carichi e rientri in un'altra condizione
                    
                        power_alfen = SiemensReadPower (client_alfen)
                        power_home_HH = SiemensReadPower (client_home_HH)
                        #power_PV = SiemensReadPower (client_PV)
                        power_PV = 0
                        p_other_loads = float(power_home_HH + power_PV + power_alfen) #in W
                    
                    
                        #se nel frattempo gli altri carichi cambiano (loro assorbimento è superiore o inferiore di 100 W a quello originario), devo adattare la p-desiderata
                        if ((p_other_loads < p_other_loads_initial - float(100)) or (p_other_loads > p_other_loads_initial + float(100))):
                    
                            P_desiderata = P_disp - p_other_loads #dove p_altri_carichi è somma di p_alfen + p_home_load + p_pv
                            p_other_loads_initial = p_other_loads  #aggiorni p_other_loads_initial
                            p_other_loads_initial_kW = p_other_loads/1000
                            break
                        elif keyboard.is_pressed('esc'):  #se invece vuoi interrompere tu
                            pdes_str = input(f"Inserisci potenza ricarica desiderata, in kW, minore o uguale a {P_ricarica_max_kW:.2f} kW: ")
                            P_desiderata_kW= float(pdes_str) 
                            P_desiderata=P_desiderata_kW*1000 #in W
                            break 
                    break
                    
           

    #2    #se P_desiderata è uguale a P_wallbox a meno di 100 W (vale sia per P_allocabile < P_ric_max sia P__allocabile > P_ric_max)
        elif ((P_desiderata >= power - 100) and (P_desiderata <= power + 100)):

            P_apparent_meter = P_allocabile #la wallbox rimane a caricare alla stessa potenza
            VALUE = P_apparent_meter
            WriteInputRegister(APP_POWER, VALUE) #assegno input register
            while(True):
                power = SiemensReadPower (client1)
                power_kW = power/1000
                print("La wallbox assorbe", "%.2f" % power_kW, "kW, NESSUNA MODULAZIONE, ESC per nuovo setpoint")
                
                power_alfen = SiemensReadPower (client_alfen)
                power_home_HH = SiemensReadPower (client_home_HH)
                #power_PV = SiemensReadPower (client_PV)
                power_PV = 0
                p_other_loads = float(power_home_HH + power_PV + power_alfen) #in W

                #se nel frattempo gli altri carichi cambiano (loro assorbimento è superiore o inferiore di 100 W a quello originario), devo adattare la p-desiderata
                if ((p_other_loads < p_other_loads_initial - float(100)) or (p_other_loads > p_other_loads_initial + float(100))):
                    
                    P_desiderata = P_disp - p_other_loads #dove p_altri_carichi è somma di p_alfen + p_home_load + p_pv
                    p_other_loads_initial = p_other_loads  #aggiorni p_other_loads_initial
                    p_other_loads_initial_kW = p_other_loads/1000
                    break
                elif keyboard.is_pressed('esc'):  #se invece vuoi interrompere tu
                    pdes_str = input(f"Inserisci potenza ricarica desiderata, in kW, minore o uguale a {P_ricarica_max_kW:.2f} kW: ")
                    P_desiderata_kW= float(pdes_str) 
                    P_desiderata=P_desiderata_kW*1000 #in W
                    break 
            
       
    #3    #se P_desiderata è minore di P_wallbox - 100 (vale sia per P_allocabile < P_ric_max sia P__allocabile > P_ric_max)
        elif (P_desiderata < power - 100):
            x = 100 #variabile piccola
            
            flag_count = 0
            while(True):            
                P_apparent_meter = P_allocabile + float(power - P_desiderata) #la wallbox inizia a ridurre la potenza (bruscamente)
                VALUE = P_apparent_meter            
                WriteInputRegister(APP_POWER, VALUE)#assegni valore input register
            #x = 100 #variabile piccola
            #while(True):
                power = SiemensReadPower (client1)
                print("La wallbox assorbe:", "%.2f" % power,"W")
                power_kW = power/1000
                flag_count +=1
                if(0 < power < 50):
                    flag_count = 0 #reinizializzo a 0 per nuovo loop
                    print("ACuMS sta assorbendo", "%.2f" % power_kW, "kW: ricarica fermata")
                    break
                #quando questa è minore di P_desiderata + 33 o contatore a 3000, aggiorno la condizione e assegno registro
                elif ((power < P_desiderata + float(x/3)) or flag_count == 3000): #P_desiderata + 33
               
                    
                    P_apparent_meter = P_allocabile 
                    VALUE = P_apparent_meter
                    WriteInputRegister(APP_POWER, VALUE) #assegno input register
                    #lettura ciclica
                    while(True):
                        power = SiemensReadPower (client1)
                        power_kW = power/1000

                        print("La wallbox sta assorbendo", "%.2f" % power_kW, "kW, ESC per nuovo setpoint")
                    
                        power_alfen = SiemensReadPower (client_alfen)
                        power_home_HH = SiemensReadPower (client_home_HH)
                        #power_PV = SiemensReadPower (client_PV)
                        power_PV = 0
                        p_other_loads = float(power_home_HH + power_PV + power_alfen) #in W
                        flag_count = 0
                    
                        #se nel frattempo gli altri carichi cambiano (loro assorbimento è superiore o inferiore di 100 W a quello originario), devo adattare la p-desiderata
                        if ((p_other_loads < p_other_loads_initial - float(100)) or (p_other_loads > p_other_loads_initial + float(100))):
                    
                            P_desiderata = P_disp - p_other_loads #dove p_altri_carichi è somma di p_alfen + p_home_load + p_pv
                            p_other_loads_initial = p_other_loads  #aggiorni p_other_loads_initial
                            p_other_loads_initial_kW = p_other_loads/1000
                            break
                        elif keyboard.is_pressed('esc'):  #se invece vuoi interrompere tu
                            pdes_str = input(f"Inserisci potenza ricarica desiderata, in kW, minore o uguale a {P_ricarica_max_kW:.2f} kW: ")
                            P_desiderata_kW= float(pdes_str) 
                            P_desiderata=P_desiderata_kW*1000 #in W
                            break 
                    break
                    

    #4    #se P_desiderata è maggiore di P_wallbox + 100 ma minore di P_ricarica_max con P_allocabile > o = P_ric_max
        elif ((P_desiderata > power + 100) and (P_desiderata < P_ricarica_max) and (P_allocabile >= P_ricarica_max)):

            z = 100 #variabile piccola
            flag_count = 0
            while(True):
                P_apparent_meter = P_allocabile - float(P_desiderata - power) #la wallbox inizia a aumentare la potenza (bruscamente)
                VALUE = P_apparent_meter            
                WriteInputRegister(APP_POWER, VALUE)#assegni valore input register
            #while(True):
                power = SiemensReadPower (client1)
                print("La wallbox assorbe:", " %.2f" % power,"W")
                power_kW = power/1000
                flag_count +=1
                #quando questa è maggiore di P_desiderata - 33 o il contatore ha raggiunto 3000 aggiorno la condizione e assegno registro
                if ((power > P_desiderata - float(z/3)) or flag_count == 3000): #P_desiderata - 33
                    P_apparent_meter = P_allocabile 
                    VALUE = P_apparent_meter
                    WriteInputRegister(APP_POWER, VALUE) #assegno input register

                    #lettura ciclica
                    while(True):
                        power = SiemensReadPower (client1)
                        power_kW = power/1000
                        print("La wallbox assorbe:", "%.2f" % power, "W, ESC per nuovo setpoint")

                        power_alfen = SiemensReadPower (client_alfen)
                        power_home_HH = SiemensReadPower (client_home_HH)
                        #power_PV = SiemensReadPower (client_PV)
                        power_PV = 0
                        p_other_loads = float(power_home_HH + power_PV + power_alfen) #in W
                        flag_count = 0

                        #se nel frattempo gli altri carichi cambiano (loro assorbimento è superiore o inferiore di 100 W a quello originario), devo adattare la p-desiderata
                        if ((p_other_loads < p_other_loads_initial - float(100)) or (p_other_loads > p_other_loads_initial + float(100))):
                    
                            P_desiderata = P_disp - p_other_loads #dove p_altri_carichi è somma di p_alfen + p_home_load + p_pv
                            p_other_loads_initial = p_other_loads  #aggiorni p_other_loads_initial
                            p_other_loads_initial_kW = p_other_loads/1000
                            break
                        elif keyboard.is_pressed('esc'):  #se invece vuoi interrompere tu
                            pdes_str = input(f"Inserisci potenza ricarica desiderata, in kW, minore o uguale a {P_ricarica_max_kW:.2f} kW: ")
                            P_desiderata_kW= float(pdes_str) 
                            P_desiderata=P_desiderata_kW*1000 #in W
                            break 
                    break

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
                power = SiemensReadPower (client1)
                print("La wallbox assorbe:",power,"W")
                power_kW = power/1000
                flag_count +=1
                #quando questa arriva in un certo range (P_allocabile) o contatore raggiunge 3000, aggiorno la condizione
                if((power > P_allocabile - a - aa) or flag_count == 3000): 
                    P_apparent_meter = P_allocabile
                    VALUE = P_apparent_meter
                    WriteInputRegister(APP_POWER, VALUE)

                    #lettura ciclica
                    while(True):
                        power = SiemensReadPower (client1)
                        power_kW = power/1000
                        print("La wallbox sta assorbendo", "%.2f" % power_kW, "kW: il veicolo non può assorbire di più, ESC per nuovo setpoint")
                        
                        power_alfen = SiemensReadPower (client_alfen)
                        power_home_HH = SiemensReadPower (client_home_HH)
                        #power_PV = SiemensReadPower (client_PV)
                        power_PV = 0
                        p_other_loads = float(power_home_HH + power_PV + power_alfen) #in W
                        flag_count = 0

                        #se nel frattempo gli altri carichi cambiano (loro assorbimento è superiore o inferiore di 100 W a quello originario), devo adattare la p-desiderata
                        if ((p_other_loads < p_other_loads_initial - float(100)) or (p_other_loads > p_other_loads_initial + float(100))):
                    
                            P_desiderata = P_disp - p_other_loads #dove p_altri_carichi è somma di p_alfen + p_home_load + p_pv
                            p_other_loads_initial = p_other_loads  #aggiorni p_other_loads_initial
                            p_other_loads_initial_kW = p_other_loads/1000
                            break
                        elif keyboard.is_pressed('esc'):  #se invece vuoi interrompere tu
                            pdes_str = input(f"Inserisci potenza ricarica desiderata, in kW, minore o uguale a {P_ricarica_max_kW:.2f} kW: ")
                            P_desiderata_kW= float(pdes_str) 
                            P_desiderata=P_desiderata_kW*1000 #in W
                            break 
                    break
        
    #6    #se P_desiderata è maggiore di P_wallbox + 100 ma minore di P_allocabile con P_allocabile < P_ric_max
        elif ((P_desiderata > power + 100) and (P_desiderata < P_allocabile) and (P_allocabile < P_ricarica_max)):
            
            b = 100 #variabile piccola
            flag_count = 0
            while(True):
                P_apparent_meter = P_allocabile - float(P_desiderata - power) #la wallbox inizia a aumentare la potenza (bruscamente)
                VALUE = P_apparent_meter            
                WriteInputRegister(APP_POWER, VALUE)#assegni valore input register
            #while(True):
                power = SiemensReadPower (client1)
                print("La wallbox assorbe:", "%.2f" % power,"W")
                power_kW = power/1000
                flag_count +=1
                #quando questa è maggiore di P_desiderata - 33 o contatore raggiunge 3000aggiorno la condizione e assegno registro
                if ((power > P_desiderata - float(b/3)) or flag_count == 3000): #P_desiderata - 33
                    P_apparent_meter = P_allocabile 
                    VALUE = P_apparent_meter
                    WriteInputRegister(APP_POWER, VALUE) #assegno input register
                    #lettura ciclica
                    while(True):
                        power = SiemensReadPower (client1)
                        power_kW = power/1000
                        print("La wallbox assorbe:", "%.2f" % power, "W, ESC per nuovo setpoint")

                        power_alfen = SiemensReadPower (client_alfen)
                        power_home_HH = SiemensReadPower (client_home_HH)
                        #power_PV = SiemensReadPower (client_PV)
                        power_PV = 0
                        p_other_loads = float(power_home_HH + power_PV + power_alfen) #in W
                        flag_count = 0
                        
                        #se nel frattempo gli altri carichi cambiano (loro assorbimento è superiore o inferiore di 100 W a quello originario), devo adattare la p-desiderata
                        if ((p_other_loads < p_other_loads_initial - float(100)) or (p_other_loads > p_other_loads_initial + float(100))):
                    
                            P_desiderata = P_disp - p_other_loads #dove p_altri_carichi è somma di p_alfen + p_home_load + p_pv
                            p_other_loads_initial = p_other_loads  #aggiorni p_other_loads_initial
                            p_other_loads_initial_kW = p_other_loads/1000
                            break
                        elif keyboard.is_pressed('esc'):  #se invece vuoi interrompere tu
                            pdes_str = input(f"Inserisci potenza ricarica desiderata, in kW, minore o uguale a {P_ricarica_max_kW:.2f} kW: ")
                            P_desiderata_kW= float(pdes_str) 
                            P_desiderata=P_desiderata_kW*1000 #in W
                            break
                    break
       
            
        else:
            print("Non si è fatto niente")

        

       
    

    


if __name__ == "__main__":
    thread1 = threading.Thread(target = server)
    #thread1.daemon = True
    thread1.start()
    thread2 = threading.Thread(target = application)
    thread2.start()
    thread2.join()    
    thread1.join()
    
