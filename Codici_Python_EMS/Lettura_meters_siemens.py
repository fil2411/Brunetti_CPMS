# from pymodbus.client import ModbusTcpClient
# import pyModbusTCP.utils as utils
from pyModbusTCP.client import ModbusClient
from datetime import datetime
import time
import keyboard
import struct

# INDIRIZZI IP DEI METER
#(al PC server assegnato IP 192.168.170.169)

#per vedere gli indirizzi IP dei meter siemens accedere dallo schermino del meter sul menu comunicazione, Modbus

IP_Meter_Centrale=    '192.168.170.170'       #meter centrale
IP_Meter_EV1_master=  '192.168.170.171'       #meter della colonnina EV1  62kWh
IP_Meter_EV2=         '192.168.170.172'       #meter della colonnina EV2  40kWh
IP_Meter_CDS=         '192.168.170.173'       #meter della colonnina CDS
IP_Meter_HH=          '192.168.170.174'       #meter del carico HH

IP_Meter_PV=         '192.168.170.175'       #meter del PV cinergia   (ANCORA DA IMPOSTARE IP SU METER!!!)


timeout_meter = 1
port = 502
granularity=0.5 #seconds
# DEFINIZIONE DEI METER: definisco i client che interrogano i meter implementati
#

# Mc=ModbusClient(host= IP_Meter_Centrale, port= 502)
Mc =        ModbusClient(host=IP_Meter_Centrale,       auto_open=True, auto_close=True, debug=False, timeout=timeout_meter) 
M_EV1 =     ModbusClient(host=IP_Meter_EV1_master,     auto_open=True, auto_close=True, debug=False, timeout=timeout_meter,port=port)
M_EV2 =     ModbusClient(host=IP_Meter_EV2,            auto_open=True, auto_close=True, debug=False, timeout=timeout_meter,port=port)
M_CDS =     ModbusClient(host=IP_Meter_CDS,            auto_open=True, auto_close=True, debug=False, timeout=timeout_meter,port=port)
M_HH =      ModbusClient(host=IP_Meter_HH,             auto_open=True, auto_close=True, debug=False, timeout=timeout_meter,port=port)
M_PV =    ModbusClient(host=IP_Meter_PV,             auto_open=True, auto_close=True, debug=False, timeout=timeout_meter,port=port)

client=Mc
client2=M_EV1
client3=M_EV2
client4=M_CDS
client5=M_HH    
client6=M_PV

while True:
     #client.connect()
     
    try: 
        rr = client.read_holding_registers(1,36) 
        test=[struct.unpack('!f', struct.pack('!I', (int(rr[idx]) << 16) | int(rr[idx+1])))[0] for idx in range(0,len(rr),2)]
    except TypeError:
        #test=[]
        print('error')
    
    try:
        rr2=client2.read_holding_registers(1,36)
        test2=[struct.unpack('!f', struct.pack('!I', (int(rr2[idx]) << 16) | int(rr2[idx+1])))[0] for idx in range(0,len(rr2),2)]
    except TypeError:
        print('error')

    try:
        rr3=client3.read_holding_registers(1,36)
        test3=[struct.unpack('!f', struct.pack('!I', (int(rr3[idx]) << 16) | int(rr3[idx+1])))[0] for idx in range(0,len(rr3),2)]
    except TypeError:
        print('error')

    try:
        rr4=client4.read_holding_registers(1,36)
        test4=[struct.unpack('!f', struct.pack('!I', (int(rr4[idx]) << 16) | int(rr4[idx+1])))[0] for idx in range(0,len(rr4),2)]
    except TypeError:
        print('error')

    try:
        rr5=client5.read_holding_registers(1,36)
        test5=[struct.unpack('!f', struct.pack('!I', (int(rr5[idx]) << 16) | int(rr5[idx+1])))[0] for idx in range(0,len(rr5),2)]
    except TypeError:
        print('error')

    try:
        rr6=client6.read_holding_registers(1,36)
        test6=[struct.unpack('!f', struct.pack('!I', (int(rr6[idx]) << 16) | int(rr6[idx+1])))[0] for idx in range(0,len(rr6),2)]
    except TypeError:
       print('error')

    
    print(test)
    print(test2)
    print(test3)
    print(test4)
    print(test5)
    print(test6)

    with open('M_C.csv','a') as file:
        file.write(datetime.now().isoformat()+','+str(test)[1:-1]+','+'meter Mc'+','+'\n')
    
    
    with open('M_EV1.csv','a') as file:
        file.write(datetime.now().isoformat()+','+str(test2)[1:-1]+','+'meter EV1'+','+'\n')  

        
    with open('M_EV2.csv','a') as file:
        file.write(datetime.now().isoformat()+','+str(test3)[1:-1]+','+'meter EV2'+','+'\n')


    with open('M_CDS.csv','a') as file:
        file.write(datetime.now().isoformat()+','+str(test4)[1:-1]+','+'meter CDS'+','+'\n')

        
    with open('M_HH.csv','a') as file:
        file.write(datetime.now().isoformat()+','+str(test5)[1:-1]+','+'meter HH'+','+'\n')
    time.sleep(granularity)

    with open('M_PV.csv','a') as file:
        file.write(datetime.now().isoformat()+','+str(test6)[1:-1]+','+'meter PV'+','+'\n')
    time.sleep(granularity)
    
    if keyboard.is_pressed('esc'):
        print('exit')
        break



 