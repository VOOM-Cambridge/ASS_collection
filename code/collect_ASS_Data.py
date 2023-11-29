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


def findMaterialUseData(frequency, item, numberInOrder):
    # find the equipment names with that order
    try:
        data = frepple.findAllPartsMaterials(item)
        materialUse =[]
        materialType = []
        for i in range(len(data)):
            material = data[i][0]
            if "ABS" in material:
                materialUse.append(data[i][1]*float(numberInOrder)*1020*0.00175*0.00175/4) # density*D^2/4*L = [kg]
            else:
                materialUse.append(data[i][1]*float(numberInOrder))
            materialType.append(material)
        if frequency == "per product":
            materialUse = [mat/float(numberInOrder) for mat in materialUse]
        return materialUse, materialType
    except Exception as e:
        return "", ""


def findJobTimesTracking(config_order_time, order):
    if config_order_time["method"] == "tracking" and order != "":
        timeStart, timeEnd = influxClient.jobLengthTime(order, 300)
    return timeStart, timeEnd 

def findJobTimesSignal(config_order_time, order):
    data = influxClient.jobLengthAndTimeFile(config_order_time['machine'], 300)
    return data

def create_json(dict_file):
    # Serializing json into a json file
    json_object = json.dumps(dict_file, indent=4)
    # Writing to sample.json
    script_dir = os.path.dirname(__file__) #<-- absolute dir the script is in
    rel_path = "/output/json/" + dict_file["name"].replace(".", "_") + ".json"
    rel_path = rel_path.replace(" ", "_")
    abs_file_path = script_dir + rel_path
    i = 1
    while os.path.isfile(abs_file_path) and os.access(abs_file_path, os.R_OK):
        with open(abs_file_path, "r") as outfile:
            data = json.load(outfile)
            if data["name"] == dict_file["name"] and data["start time"] == dict_file["start time"] and data["end time"] == dict_file["end time"]:
                #print("Data already added")
                return 1
        rel_path = "/output/json/" + dict_file["name"].replace(".", "_") + str(i) + ".json"
        rel_path = rel_path.replace(" ", "_")
        abs_file_path = script_dir + rel_path
        i = i+ 1 
    with open(abs_file_path, "w") as outfile:   
        outfile.write(json_object)
        return 0

def add_data_together(example, data, config):
    # remove extra element
    del example["submodelElements"][6]
    del example["submodelElements"][3]["value"][1]

    #factory name details 
    example["idShort"] = config["Factory"]["name"]
    example["submodelElements"][1]["value"][0]["value"] = config["Factory"]["name"]
    example["submodelElements"][1]["value"][1]["value"] = config["Factory"]["address"]
    example["submodelElements"][1]["value"][2]["value"] = config["Factory"]["email"]

    # Order details
    example["submodelElements"][0]["value"][0]["value"] = data["end time"]
    example["submodelElements"][0]["value"][1]["value"] = data["item"]
    example["submodelElements"][0]["value"][2]["value"] = data["quantity"]
    example["submodelElements"][0]["value"].append(example["submodelElements"][0]["value"][0])
    example["submodelElements"][0]["value"][3]["value"] = data["name"]
    example["submodelElements"][0]["value"][3]["idShort"] = "order_number"

    # Total energy
    example["submodelElements"][2]["value"] = data["energy use"]

    # Total material
    
    if type(data["material use"]) == list:
        i = 0
        for material in data["material use"]:
            matType = data["material type"][i]
            if i == 0:
                example["submodelElements"][3]["value"][0]["value"] = material
                example["submodelElements"][3]["value"][0]["idShort"] = matType
            else:
                example["submodelElements"][3]["value"].append(example["submodelElements"][3]["value"][0])
                example["submodelElements"][3]["value"][i]["value"] = material
                example["submodelElements"][3]["value"][i]["value"] = matType
            i +=1
    i = 0
    for proc in config["Factory"]["process"]:
        if i == 1:
            # Processes uses exisitng element
            example["submodelElements"][4]["value"][i]["value"] = proc
        else:
            # create new one
            example["submodelElements"][4]["value"].append(example["submodelElements"][4]["value"][0])
            example["submodelElements"][4]["value"][i]["value"] = proc
            example["submodelElements"][4]["value"][i]["idShort"] = "Process " + str(i)
        i +=1

    items = data["item"] 
    if type(items) == list and len(items) > 1:
        # multiple items to add
        j = 5
        for item in items:
            if j == 5:
            # Processes uses exisitng element
                example["submodelElements"][j]["idShort"]  = item
                try:
                    example["submodelElements"][j]["value"][0]["value"] = data["energy use"][0]
                    example["submodelElements"][j]["value"][1]["value"] = data["material use"][0]
                except:
                    example["submodelElements"][j]["value"][0]["value"] = "unknown"
                    example["submodelElements"][j]["value"][1]["value"] = "unknown"
            else:
                # create new one
                example["submodelElements"][j]= example["submodelElements"][5]
                example["submodelElements"][j]["idShort"] = item
                try:
                    example["submodelElements"][j]["value"][0]["value"] = data["energy use"][j-5]
                    example["submodelElements"][j]["value"][1]["value"] = data["material use"][j-5]
                except:
                    example["submodelElements"][j]["value"][0]["value"] = "unknown"
                    example["submodelElements"][j]["value"][1]["value"] = "unknown"
            
    else:
        # only one item to add
        example["submodelElements"][5]["idShort"]  = items
        try:
            example["submodelElements"][5]["value"][0]["value"] = data["energy data"]/data["quantity"]
            example["submodelElements"][5]["value"][1]["value"] = data["material data"]/data["quantity"]
        except:
            example["submodelElements"][5]["value"][0]["value"] = "unknown"
            example["submodelElements"][5]["value"][1]["value"] = "unknown"
    
    return example

def add_to_aas(dict_file_in, config):
    # open json file of aas template
    script_dir = os.path.dirname(__file__) #<-- absolute dir the script is in
    rel_path = "/config/Submodel.json"
    abs_file_path = script_dir + rel_path
    with open(abs_file_path) as json_file:
        data_example = json.load(json_file)

    # add dict_file data to ass template
    dict_file = add_data_together(data_example,dict_file_in, config)

    # Serializing json
    json_object = json.dumps(dict_file, indent=4)
    # Writing to sample.json
    script_dir = os.path.dirname(__file__) #<-- absolute dir the script is in
    rel_path = "/output/AAS/" + dict_file_in["name"].replace(".", "_") + ".json"
    rel_path = rel_path.replace(" ", "_")
    abs_file_path = script_dir + rel_path
    i = 1
    while os.path.isfile(abs_file_path) and os.access(abs_file_path, os.R_OK):
        with open(abs_file_path, "r") as outfile:
            data = json.load(outfile)
            if data == dict_file: 
                #print("Data already added")
                return 1
        rel_path = "/output/AAS/" + dict_file_in["name"].replace(".", "_") + str(i) + ".json"
        rel_path = rel_path.replace(" ", "_")
        abs_file_path = script_dir + rel_path
        i = i+ 1 
    with open(abs_file_path, "w") as outfile:   
        outfile.write(json_object)
        return 0

def add_to_excel(dict_file, csv_file):
    if type(dict_file)==list:
        mydict =dict_file
    else:
        mydict = [dict_file]
    
    fields = ['name', 'item', 'quantity', 'start time', 'end time',  'job duration', 'energy use', 'machine', 'material use', 'material type']
    script_dir = os.path.dirname(__file__) #<-- absolute dir the script is in
    rel_path = csv_file
    abs_file_path = os.path.join(script_dir, rel_path)
    if os.path.isfile(abs_file_path) and os.access(abs_file_path, os.R_OK):
        with open(abs_file_path, newline='') as file: 
            reader = csv.reader(file)
            dataOld = list(reader)

    if not os.path.isfile(abs_file_path) and not os.access(abs_file_path, os.R_OK):
        with open(abs_file_path, 'w', newline='') as file: 
            writer = csv.DictWriter(file, fieldnames = fields)
            # writing headers (field names)
            writer.writeheader()
            writer.writerows(mydict)
    else:
      with open(abs_file_path, 'a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames = fields)
            notInFile = True
            for mydictrows in mydict:
                for datarows in dataOld:
                    if mydictrows[fields[0]] == datarows[0] and mydictrows[fields[1]] == datarows[1] and mydictrows[fields[3]] == datarows[3] and mydictrows[fields[4]] == datarows[4]:
                        notInFile =False
                if notInFile:
                    writer.writerow(mydictrows)

def findOrderInfo(barcode):
    dataBack = frepple.ordersIn("GET", {"name": str(barcode)})
    if len(dataBack) !=0:
        if type(dataBack) == list:
            itemName = dataBack[0]["item"]
            quantity = dataBack[0]["quantity"]
        else:
            itemName = dataBack["item"]
            quantity = dataBack["quantity"]
        return itemName, quantity
        # no order data from frepple try to find item informaiton based on file
    dataBack = frepple.itemsFunc("GETALL", {"decritpion": str(barcode)})
    if len(dataBack) !=0:
        if type(dataBack) == list:
            itemName = dataBack[0]["item"]
            quantity = dataBack[0]["quantity"]
        else:
            itemName = dataBack["item"]
            quantity = dataBack["quantity"]
        return itemName, quantity
    itemName = ""
    quantity = 1
    
    return itemName, quantity

def createDictAndSave(dat, last_reading_stored, config):
    dictionaryOdASSData = {}
    dictionaryOdASSData["name"] = dat[3]
    itemName, quantity = findOrderInfo(dat[3])
    dictionaryOdASSData["item"] = itemName
    dictionaryOdASSData["quantity"] = quantity
    dictionaryOdASSData["start time"] = dat[0].strftime("%Y-%m-%d %H:%M:%S") 
    dictionaryOdASSData["end time"] = dat[1].strftime("%Y-%m-%d %H:%M:%S") 
    dictionaryOdASSData["job duration"] = (dat[1]-dat[0]).total_seconds()
    dictionaryOdASSData["energy use"] = dat[5]
    dictionaryOdASSData["machine"] = dat[6]
    materialUse, materialType = findMaterialUseData(config["material_use"]["frequency"], itemName, quantity)
    dictionaryOdASSData["material use"] = materialUse
    dictionaryOdASSData["material type"] = materialType
    # create Json file 
    # create Json or excel file 
                    
    if "json" in fileType or "JSON" in fileType:
        create_json(dictionaryOdASSData)
    if "csv" in fileType or "CSV" in fileType:
        add_to_excel(dictionaryOdASSData, "output/csv/AAS_Data.csv")
    if "aas" in fileType or "AAS" in fileType:
        add_to_aas(dictionaryOdASSData, config)
    dat[0] =dat[0].replace(tzinfo=utc)
    #dat[0] = utc.localize(dat[0])

    if dat[0] > last_reading_stored:
        last_reading_stored = dat[0]
    return last_reading_stored


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
                    last_reading_stored = createDictAndSave(dat, last_reading_stored, config)
    elif config["Factory"]["name"] == "Manual Assembly":
        machine = config["Factory"]["machine"]
        for machin in machine:
            data = influxClient.jobLengthEnergyWithTracking(machin, timeSinceLast, config["order_time_taken"]["start_location"], config["order_time_taken"]["end_location"])
            for dat in data:
                # create new file
                last_reading_stored = createDictAndSave(dat, last_reading_stored, config)
    elif config["Factory"]["name"] == "Robot Lab":
        machine = config["Factory"]["machine"]
        for machin in machine:
            data = influxClient.jobLengthEnergyWithTracking(machin, timeSinceLast, config["order_time_taken"]["start_location"], config["order_time_taken"]["end_location"])
            for dat in data:
                # create new file
                print(dat)
                last_reading_stored = createDictAndSave(dat, last_reading_stored, config)
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
    fileType = config["Factory"]["fileType"]
    # intialise the connection to the database and MES
    influxClient = fetchData(configInflux)
    try:
        frepple = freppleConnect(user, password, URL)
    except:
        print("No MES connection")
        frepple =""
    script_dir = os.path.dirname(__file__) #<-- absolute dir the script is in
    dateLastUpdate = utc.localize(datetime.now() - timedelta(hours = config["Factory"]["first_check"]))
    if fileType == "JSON" or fileType == "json":
        rel_path = "output/json/"
        abs_file_path = os.path.join(script_dir, rel_path)
        most_recent_file = None
        most_recent_time = 0
        fileFound = False
        for entry in os.scandir(abs_file_path):
            if entry.is_file():
                fileFound = True
                # get the modification time of the file using entry.stat().st_mtime_ns
                mod_time = entry.stat().st_mtime_ns
                if mod_time > most_recent_time:
                    # update the most recent file and its modification time
                    most_recent_file = entry.name
                    most_recent_time = mod_time
        if fileFound:
            rel_path = "output/json/" + most_recent_file 
            abs_file_path = os.path.join(script_dir, rel_path)
            with open(abs_file_path, "r") as outfile:
                data = json.load(outfile)
                dateLastUpdate = utc.localize(datetime.strptime(data["start time"], '%Y-%m-%d %H:%M:%S'))
    
    else: # not json file look for csv file if it exisits 
        rel_path = "output/csv/AAS_Data.csv"
        abs_file_path = os.path.join(script_dir, rel_path)
        if os.path.isfile(abs_file_path) and os.access(abs_file_path, os.R_OK):
            with open(abs_file_path, newline='') as file: 
                reader = csv.reader(file)
                i = 0
                for row in reader:
                    i +=1
                    if i > 2:
                        newDate = utc.localize(datetime.strptime(row[3], '%Y-%m-%d %H:%M:%S'))
                        if newDate > dateLastUpdate:
                            dateLastUpdate = newDate
                
    timLastupdate = utc.localize(datetime.now())
    while True:
        print("Started")
        timeWait = config["Factory"]["frequencyUpdate"]
        if ((utc.localize(datetime.now()) - timLastupdate ).total_seconds()/5)> timeWait:
            print("updating ...")
            dateLastUpdate = utc.localize(datetime(year = dateLastUpdate.year, 
                                       month = dateLastUpdate.month, 
                                       day = dateLastUpdate.day, hour =0, minute =0, second =1))
            timeSinceLast = (utc.localize(datetime.now()) - dateLastUpdate).total_seconds()
            # print(timeSinceLast)
            dateLastUpdate = updateExcelorDict(config, frepple, timeSinceLast, fileType)
            print("completed, last reading at" + dateLastUpdate.strftime("%Y-%m-%d %H:%M:%S"))
            timLastupdate = utc.localize(datetime.now())
        else:
            time.sleep(10)


    


