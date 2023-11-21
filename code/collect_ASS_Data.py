import tomli, csv
import os
from fetchDataInflux import fetchData
from freppleAPImodule import freppleConnect 
import json
from datetime import datetime, timedelta
import time
import pytz
utc=pytz.UTC

# collect data on
#  1. Energy Use
#  2. Material Waste
#  3. Prodcut Scrap
#  4. Material Use
#  5. Order timeing 
    
def findEnergyData(config, orderNum, sTimeIn, eTimeIn):
    # find the equipment names with that order

    #machine_list = ["LR_Mate_3", "M6_cell_3"]
    machine_list = config["machine_list"]
    approxTime = 300
    diff = 150
    energyTotalFull =0
    try:
        sTime, eTime = influxClient.jobLengthTime(orderNum, 200)
    except:
        print("no order found")
    if config["frequency"] == "per product":
        dataBack = frepple.ordersIn("GET", {"name": str(orderNum)})
        if dataBack != None:
            numberInOrder = dataBack["quantity"]
    else: # frequency is per order or assumed to be per order type
        numberInOrder = 1
    
    for name in machine_list:
        energyTotal = 0
        
        if config["method"] == "tracking":
            # try tracking infomraiton 
            energyTotal = influxClient.findEnergyData(sTime, eTime, name)
        
        elif config["method"] == "signal":
            # try singal processing method
            output, diffarray = influxClient.findEnergyDataAssembly(sTime, eTime, name, approxTime, diff)
            energyTotal = influxClient.findEnergyData(output[0], output[1], name)

        elif config["method"] == "machine":
            energyTotal = influxClient.findEnergyData(sTimeIn, eTimeIn, name)

        elif config["method"] == "MES":
            print("MES has no energy date")

        energyTotalFull += energyTotal

    return energyTotalFull/numberInOrder


def findMaterialUseData(frequency, orderNum):
    # find the equipment names with that order

    #machine_list = ["LR_Mate_3", "M6_cell_3"]
    sTime, eTime = influxClient.jobLengthTime(orderNum, 200)
    dataBack = frepple.ordersIn("GET", {"name": str(orderNum)})
    itemName = dataBack["item"]
    if frequency == "per product":
        if dataBack != None:
            numberInOrder = dataBack["quantity"]
    else: # frequency is per order or assumed to be per order type
        numberInOrder = 1
        materialUse = {}
        data = freppleConnect.findAllPartsMaterials(itemName)
        for i in range(len(data)):
            material = data[i][0]
            if "ABS" in material:
                materialUse[material] = data[i][1]*numberInOrder*0.00175*0.00175/4
            else:
                materialUse[material] = data[i][1]*numberInOrder

    return materialUse

def findJobTimesTracking(config_order_time, order):
    if config_order_time["method"] == "tracking" and order != "":
        timeStart, timeEnd = influxClient.jobLengthTime(order, 300)
    return timeStart, timeEnd 

def findJobTimesSignal(config_order_time, order):
    data = influxClient.jobLengthAndTimeFile(config_order_time['machine'], 300)
    print(data)
    return data


def create_json(dict_file):
    # Serializing json
    json_object = json.dumps(dict_file, indent=4)
    # Writing to sample.json
    script_dir = os.path.dirname(__file__) #<-- absolute dir the script is in
    rel_path = "/output/" + dict_file["name"].replace(".", "_") + ".json"
    abs_file_path = script_dir + rel_path
    i = 1
    while os.path.isfile(abs_file_path) and os.access(abs_file_path, os.R_OK):
        rel_path = "/output/" + dict_file["name"].replace(".", "_") + str(i) + ".json"
        abs_file_path = script_dir + rel_path
        i = i+ 1  
        with open(abs_file_path, "w") as outfile:
            outfile.write(json_object)

def add_to_excel(dict_file, csv_file):
    if type(dict_file)==list:
        mydict =dict_file
    else:
        mydict = [dict_file]
    fields = ['name', 'item', 'start time', 'end time', 'energy time', 'energy use', 'machine', 'material use']
    script_dir = os.path.dirname(__file__) #<-- absolute dir the script is in
    rel_path = csv_file
    abs_file_path = os.path.join(script_dir, rel_path)
    if not os.path.isfile(abs_file_path) and not os.access(abs_file_path, os.R_OK):
        with open(abs_file_path, 'w', newline='') as file: 
            writer = csv.DictWriter(file, fieldnames = fields)
            # writing headers (field names)
            writer.writeheader()
            writer.writerows(mydict)
    else:
      with open(abs_file_path, 'a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames = fields)
            writer.writerows(mydict)


def updateExcelorDict(config, freppleConnect, timeSinceLast, fileType):
    # update or add to JSON files or excel of both
    # find the order number or name of file if none
    # search for all complete orders in MES first
    # find days/time back since last reading
    last_reading_stored = datetime.now() - timedelta(seconds= timeSinceLast)
    last_reading_stored = utc.localize(last_reading_stored)
    timeSinceLast = str(round(timeSinceLast)) + "s"
    if config["Factory"]["name"] == "3D Printing":
        machine = config["Factory"]["machine"]
        for machin in machine:
            data = influxClient.jobLengthEnergyWithSignal(machin, timeSinceLast)
            #data = [ startTime [0], endTime [1], duration [2], jobFile/barcode [3], complete [4], energyUse [5], machine [6]]
            #data = findJobTimesSignal(config["order_time_taken"], [])
            for dat in data:
                if dat[4] != False:
                    dictionaryOdASSData = {}
                    dictionaryOdASSData["name"] = dat[3]
                    dictionaryOdASSData["item"] = dat[3]
                    dictionaryOdASSData["start time"] = dat[0].strftime("%Y-%m-%d %H:%M:%S") 
                    dictionaryOdASSData["end time"] = dat[1].strftime("%Y-%m-%d %H:%M:%S") 
                    dictionaryOdASSData["energy use"] = dat[5]
                    dictionaryOdASSData["machine"] = dat[6]
                    dictionaryOdASSData["material use"] = "" #findMaterialUseData(config["material_use"]["frequency"], dat[3])
                    # create Json file 
                    # create Json or excel file 
                    if fileType == "json" or fileType == "JSON":
                        create_json(dictionaryOdASSData)
                    elif fileType == "both" or fileType == "Both":
                        add_to_excel(dictionaryOdASSData,"output/AAS_Data.csv")
                        create_json(dictionaryOdASSData)
                    elif fileType == "csv" or fileType == "CSV":
                        add_to_excel(dictionaryOdASSData, "output/AAS_Data.csv")
                    dat[0] =dat[0].replace(tzinfo=utc)
                    #dat[0] = utc.localize(dat[0])

                    if dat[0] > last_reading_stored:
                        last_reading_stored = dat[0]
                        
    elif config["Factory"]["name"] == "Manual Assembly":
        machine = config["Factory"]["machine"]
        for machin in machine:
            data = influxClient.jobLengthEnergyWithTracking(machin, timeSinceLast)
            for dat in data:
                # create new file
                dictionaryOdASSData = {}
                dictionaryOdASSData["name"] = dat[3]
                dictionaryOdASSData["item"] = freppleConnect.ordersIn("GET", {"name": dat[3]})
                dictionaryOdASSData["start time"] = dat[0].strftime("%Y-%m-%d %H:%M:%S") 
                dictionaryOdASSData["end time"] = dat[1].strftime("%Y-%m-%d %H:%M:%S") 
                dictionaryOdASSData["energy use"] = dat[2]
                dictionaryOdASSData["material use"] = findMaterialUseData(config["material_use"]["frequency"], dat[3])
                
                # create Json or excel file 
                if fileType == "json" or fileType == "JSON":
                    create_json(dictionaryOdASSData)
                elif fileType == "both" or fileType == "Both":
                    create_json(dictionaryOdASSData)
                    add_to_excel(dictionaryOdASSData,"output/AAS_Data.csv")
                elif fileType == "csv" or fileType == "CSV":
                    add_to_excel(dictionaryOdASSData, "output/AAS_Data.csv")

                #dat[0] = utc.localize(dat[0])
                if dat[0] > last_reading_stored:
                        last_reading_stored = dat[0]
    else:
        print("file found")

    return last_reading_stored
        
if __name__ == "__main__":
    script_dir = os.path.dirname(__file__) #<-- absolute dir the script is in
    rel_path = "config/config.toml"
    abs_file_path = os.path.join(script_dir, rel_path)

    with open(abs_file_path, mode="rb") as fp:
        config = tomli.load(fp)

    # connect to MES
    user =config["frepple_info"]["user"]
    password = config["frepple_info"]["password"]
    URL = config["frepple_info"]["URL"]

    configInflux = config["influx_info"]

    # intialise the connection to the database and MES
    influxClient = fetchData(configInflux)
    frepple = freppleConnect(user, password, URL)
    script_dir = os.path.dirname(__file__) #<-- absolute dir the script is in
    rel_path = "output/AAS_Data.csv"
    abs_file_path = os.path.join(script_dir, rel_path)
    dateLastUpdate = utc.localize(datetime.now() - timedelta(hours = 100))
    if os.path.isfile(abs_file_path) and os.access(abs_file_path, os.R_OK):
        with open(abs_file_path, newline='') as file: 
            reader = csv.reader(file)
            i = 0
            for row in reader:
                i +=1
                if i > 2:
                    newDate = utc.localize(datetime.strptime(row[2], '%Y-%m-%d %H:%M:%S'))
                    if newDate > dateLastUpdate:
                        dateLastUpdate = newDate
                
    while True:
        print("Started")
        if (utc.localize(datetime.now()) - dateLastUpdate).total_seconds() / 1 > 10:
            timeSinceLast = (utc.localize(datetime.now()) - dateLastUpdate + timedelta(seconds= 1)).total_seconds()
            print(timeSinceLast)
            dateLastUpdate = updateExcelorDict(config, frepple, timeSinceLast, 'csv')
            print("completed, last reading at" + dateLastUpdate.strftime("%Y-%m-%d %H:%M:%S"))
            
        else:
            time.sleep(10)

    


