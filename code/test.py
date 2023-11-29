import json
import os

script_dir = os.path.dirname(__file__) #<-- absolute dir the script is in
rel_path = "/output/AAS/Submodel.json"
abs_file_path = script_dir + rel_path
with open(abs_file_path) as json_file:
    example = json.load(json_file)

# dispatch time
print(example["submodelElements"][0]["value"][0]["value"])
# Lab name
print(example["submodelElements"][1]["value"][0]["value"])
# Lab address
print(example["submodelElements"][1]["value"][1]["value"])
# Lab email
print(example["submodelElements"][1]["value"][2]["value"])
# Total energy
print(example["submodelElements"][2]["value"])
# Total material
print(example["submodelElements"][3]["value"][0]["value"])
# Processes 
print(example["submodelElements"][4]["value"][0]["value"])
# make new process 
# process = example["submodelElements"][4]["value"][0]
# example["submodelElements"][4]["value"][0]["value"] = "processName"
# example["submodelElements"][4]["value"][0]["idShort"] = "Process2"

# data per part in [5] and [6] in example
print(example["submodelElements"][5]["value"][1]["value"])
# copy example["submodelElements"][5]
# example["submodelElements"][5]["idShort"] = "name of part"
# example["submodelElements"][5]["value"][0]["value"] = "energy per part"
# example["submodelElements"][5]["value"][1]["value"] = "material per part"
# del example["submodelElements"][6] if one part