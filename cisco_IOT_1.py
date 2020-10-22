import requests
import json
import socket
import pprint
import sys
import os
import csv
import time
import string
from collections import defaultdict
from datetime import date, datetime
from cryptography.fernet import Fernet
import logging

# disable the warnings for ignoring Self Signed Certificates
requests.packages.urllib3.disable_warnings()

def customer_menu(ng1_host, headers, cookies, apn_list, datacenter_list):
    # This function is an entry menu for entering new customer information.
    # It takes in a list of valid APNs and returns the user's entries as a profile dictionary.
    # Return False if the user messes up and wants to start over
    # Create an empty dictionary that will hold our customer menu entries.
    profile = {}
    # Create an empty list that will contain one or more APN entries.
    apn_entry_list = []
    # Initialize a variable to capture a user's yes or no reponse.
    user_entry = ''
    print('\nThis program takes input for customer attributes and creates a full configuration in nG1 to match')
    print("To cancel any changes, please type 'exit'")
    # Take the users input and verify that all APNs entered are valid, meaning they already exist.

    # User enters the customer name.
    user_entry = input("Please enter the Customer Name: ")
    if user_entry == '':
        profile['cust_name'] = 'Ring'
    elif user_entry.lower() == 'exit':
        exit()
    else:
        profile['cust_name'] = user_entry

    print("\nCurrent APNs available are: ")
    print(sorted(apn_list), '\n')

    # Initialize an empty list to hold user entered APNs
    apn_entry_list = []
    # User enters one or more APNs.
    # User enters the APN(s)
    user_entry = input("Please enter one or more APNs from the list separated by comma: ")
    if user_entry == '':
        # For testing, allow the user to just hit enter
        apn_entry_list.append('Ring')
    elif user_entry.lower() == 'exit':
        exit()
    else:
        # If more than one APN is entered, split the string into a list of APNs
        apn_entry_list = user_entry.split(',')
        # Remove any leading or trailing whitespace from list members
        i = 0
        for apn_entry in apn_entry_list:
            apn_entry_list[i] = apn_entry.strip()
            i += 1

    for apn_entry in apn_entry_list:
        if apn_entry not in apn_list:
            print(f"APN: {user_entry} does not yet exist")
            print(f"Please create APN: {user_entry} first and then run this program again")
            print("No nG1 modifications will be made. Exiting...")
            exit()

    profile['apn_list'] = apn_entry_list


    print('Please select the customer type:')
    print('[1] IOT')
    print('[2] Connected Car')
    while True:
        user_entry = input('Enter 1 or 2: ').lower()
        if user_entry == 'exit':
            exit()
        elif user_entry == '':
            # For testing, allow the user to just hit enter
            profile['customer_type'] = 'IOT'
            break
        elif user_entry == '1':
            profile['customer_type'] = 'IOT'
            break
        elif user_entry == '2':
            profile['customer_type'] = 'Connected Car'
            break
        else:
            print("Invalid entry, please enter either '1' or '2'")
            continue

    print("\nCurrent Datacenters available are: ")
    print(sorted(datacenter_list), '\n')
    # Initialize an empty list to hold user entered datacenters
    dc_entry_list = []
    # User enters one or more Datacenters.
    user_entry = input("Please enter one or more Datacenters from the list separated by comma: ")
    if user_entry == '':
        # For testing, allow the user to just hit enter
        dc_entry_list.append('Atlanta')
    elif user_entry.lower() == 'exit':
        exit()
    else:
        # If more than one datacenter is entered, split the string into a list of datacenters
        dc_entry_list = user_entry.split(',')
        # Remove any leading or trailing whitespace from list members
        i = 0
        for dc_entry in dc_entry_list:
            dc_entry_list[i] = dc_entry.strip()
            i += 1

    for dc_entry in dc_entry_list:
        if dc_entry not in datacenter_list:
            print(f"Datacenter: {dc_entry} does not yet exist")
            print(f"Please create Datacenter: {dc_entry} first and then run this program again")
            print("No nG1 modifications will be made. Exiting...")
            exit()

    profile['dc_list'] = dc_entry_list

    print('-------------------------------------------')
    print('Confirm new customer profile:')
    print(f"Customer Name: {profile['cust_name']}")
    for apn in apn_entry_list:
        print(f"APN: {apn}")
    print(f"Customer Type: {profile['customer_type']}")
    for dc in dc_entry_list:
        print(f"Datacenter: {dc}")
    print('-------------------------------------------')
    print("Enter 'y' to proceed with nG1 configuration")
    print("Enter 'n' to start over")
    print("Enter 'exit' to exit without configuration changes")
    while True:
        user_entry = input('y or n: ').lower()
        if user_entry == 'y':
            return profile
        elif user_entry == 'n':
            return False
        elif user_entry == 'exit':
            exit()
        else:
            print("Invalid entry, please enter 'y' or 'n'")
            continue


def open_session(ng1_host, headers, cookies, credentials):
    open_session_uri = "/ng1api/rest-sessions"
    open_session_url = "https://" + ng1_host + open_session_uri

    # For troubleshooting, you can print the url string prior to the post operation
    #print('Open Session URL: ' + request_url(open_session_url, headers))
    #split the credentials string into two parts; username and password
    ng1username = credentials.split(':')[0]
    ng1password_pl = credentials.split(':')[1]

    # perform the HTTPS API call to open the session with nG1 and return a session cookie
    try:
        if credentials == 'Null':
            # Null credentials tells us to use the token. We will use this post and pass in the cookies as the token.
            post = requests.request("POST", open_session_url, headers=headers, verify=False, cookies=cookies)
        elif cookies == 'Null':
            # Null cookies tells us to use the credentials string. We will use this post and pass in the credentials string.
            post = requests.request("POST", open_session_url, headers=headers, verify=False, auth=(ng1username, ng1password_pl))
        else:
            print('[FAIL] opening session')
            print('URL:', open_session_url)
            print('Unable to determine authentication by credentials or token')
            print('Exiting the program now...')

            # exit the script
            exit()
        if post.status_code == 200:
            # success
            print('[INFO] Opened Session Successfully')

            # utilize the returned cookie for future authentication
            cookies = post.cookies
            # print ('Cookie : ', cookies)
            return cookies

        else:
            # We reached the nG1, but request has failed
            print('[FAIL] opening session')
            print('URL:', open_session_url)
            print('Response Code:', post.status_code)
            print('Response Body:', post.text)
            print('Exiting the program now...')

            # exit the script
            exit()
    except:
        # This means we likely did not reach the nG1 at all. Check your VPN connection.
        print('[FAIL] opening session')
        print('Cannot Reach URL: ', open_session_url)
        print('Exiting the program now...')
        # exit the script
        exit()

def close_session(ng1_host, headers, cookies):
    close_session_uri = "/ng1api/rest-sessions/close"
    close_session_url = "https://" + ng1_host + close_session_uri
    # perform the HTTPS API call
    close = requests.request("POST", close_session_url, headers=headers, verify=False, cookies=cookies)

    if close.status_code == 200:
        # success
        print('[INFO] Closed Session Successfully')
        return True
    else:
        print('[FAIL] closing session')
        print('Response Code:', close.status_code)
        print('Response Body:', close.text)
        return False
    close_session_uri = "/ng1api/rest-sessions/close"
    close_session_url = "https://" + ng1_host + close_session_uri
    # perform the HTTPS API call
    close = requests.request("POST", close_session_url, headers=headers, verify=False, cookies=cookies)

    if close.status_code == 200:
        # success
        print('[INFO] Closed Session Successfully')
        return True
    else:
        print('[FAIL] closing session')
        print('Response Code:', close.status_code)
        print('Response Body:', close.text)
        return False

def request_url(baseurl, headers):
    # This function accepts a URL path and a params diction as inputs.
    # It calls requests.get() with those inputs,
    # and returns the full URL of the data you want to get.
    req = requests.Request(method = 'GET', url = baseurl, params = headers)
    prepped = req.prepare()
    return prepped.url

def write_config_to_json(config_type, service_type, service_name, app_name, device_name, interface_id, location_name, config_data):
    # takes in config_type as type of config to determine what the filename will be
    # If you are writing out multiple services, devices, etc., then the service_name, device_name
    # interface_id, location_name you pass in should be "Null"
    # The contents of the json config file are read from config_data, converted to a string (serialized), and written to the json file

    # Determine what the filename will be based on the context of the call
    if config_type == 'get_services':
        if service_type == 'application':
            config_filename = 'all_app_services' + '.json'
        elif service_type == 'network':
            config_filename = 'all_net_services' + '.json'
        else:
            config_filename = 'all_services' + '.json'
    elif config_type == 'get_apns':
        config_filename = service_name + '.json'
    elif config_type == 'get_devices':
        config_filename = 'all_devices' + '.json'
    elif config_type == 'get_applications':
        config_filename = 'all_apps' + '.json'
    elif config_type == 'get_app_detail':
        config_filename = app_name + '.json'
    elif config_type == 'get_device_interfaces':
        config_filename = 'device_' + device_name + '_interfaces' + '.json'
    elif config_type == 'get_device_interface_locations':
        config_filename = 'device_' + device_name + '_interface_' + interface_id + '_locations' + '.json'
    elif config_type == 'get_service_detail' or config_type == 'get_domain_detail':
        config_filename = service_name + '.json'
    elif config_type == 'get_device':
        config_filename = device_name + '.json'
    elif config_type == 'get_device_interface':
        config_filename = interface_id + '.json'
    elif config_type == 'get_device_interface_location':
        config_filename = location_name + '.json'
    else:
        print('unable to determine filename to write, exiting...')
        exit()

    # write to a json file
    try:
        with open(config_filename,"w") as f:
            json.dump(config_data, f)
            print(f'[INFO] Writing config to JSON file:', config_filename)

            return True
    except IOError as e:
        print(f'[FAIL] Unable to write to the JSON config file:', config_filename)
        print("I/O error({0}): {1}".format(e.errno, e.strerror))
        return False
    except: #handle other exceptions such as attribute errors
        print(f'[FAIL] Unable to write to the JSON config file:', config_filename)
        print("Unexpected error:", sys.exc_info()[0])
        return False

def write_device_interfaces_locations_config_to_csv(name, mylist):
    filename = name + '_DeviceInterfacesLocations_' + str(date.today()) + '.csv'
    try:
        with open(filename,'w', encoding='utf-8', newline='') as f:
            fieldnames = ['locationKeyName', 'alias', 'locationKeyType', 'locationKeyID', 'status', 'interfaceSpeed', 'speedOverrideEnabled']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            # write list of dicts
            writer.writeheader()
            writer.writerows(mylist) #writerow(dict) if write one row at time
            print(f'[INFO] Writing Interface Locations to CSV file:', filename)
    except IOError as e:
        print(f'[FAIL] Unable to write Interface Locations to the CSV file:', filename)
        print("I/O error({0}): {1}".format(e.errno, e.strerror))
        return False
    except: #handle other exceptions such as attribute errors
        print(f'[FAIL] Unable to write Interface Locations to the CSV config file:', filename)
        print("Unexpected error:", sys.exc_info()[0])
        return False

def write_device_interfaces_config_to_csv(name, mylist):
    filename = name + '_DeviceInterfaces_ ' + str(date.today()) + '.csv'
    try:
        with open(filename,'w', encoding='utf-8', newline='') as f:
            fieldnames = ['interfacename', 'interfaceNumber', 'alias', 'interfaceSpeed', 'status', 'portSpeed', 'nBAnASMonitoring', 'activeInterfaces', 'inactiveInterfaces', 'interfaceLinkType', 'virtulization', 'alarmTemplatename']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            # write list of dicts
            writer.writeheader()
            writer.writerows(mylist) #writerow(dict) if write one row at time
            print(f'[INFO] Writing Device Interfaces to CSV file:', filename)
    except IOError as e:
        print(f'[FAIL] Unable to write Device Interfaces to the CSV file:', filename)
        print("I/O error({0}): {1}".format(e.errno, e.strerror))
        return False
    except: #handle other exceptions such as attribute errors
        print(f'[FAIL] Unable to write Device Interfaces to the CSV file:', filename)
        print("Unexpected error:", sys.exc_info()[0])
        return False

def read_config_from_json(config_type, service_type, service_name, app_name, device_name, interface_id, location_name):
    # If you are asking for multiple services, devices, etc. then the service_name,
    # device_name, interface_id, location_name you pass in should be 'Null'
    # The contents of the json config file are read into config_data, converted to a python dictionay object and returned

    if config_type == 'get_services':
        if service_type == 'application':
            config_filename = 'all_app_services' + '.json'
        elif service_type == 'network':
            config_filename = 'all_net_services' + '.json'
        elif service_type == 'all_services':
            config_filename = 'all_services' + '.json'
        else:
            print('Unable to determine the json filename')
            print('service_type must be set to application, network or all_services')
            return False, False
    elif config_type == 'get_service_detail':
        config_filename = service_name + '.json'
    elif config_type == 'create_service' or config_type == 'create_domain':
        config_filename = service_name  + '.json'
    elif config_type == 'get_devices':
        config_filename = 'all_devices' + '.json'
    elif config_type == 'get_applications':
        config_filename = 'all_apps' + '.json'
    elif config_type == 'get_app_detail':
        config_filename = app_name + '.json'
    elif config_type == 'create_app':
        config_filename = app_name  + '.json'
    elif config_type == 'get_datacenters':
        config_filename = service_name  + '.json'
    elif config_type == 'set_apns':
        config_filename = 'apn-list'  + '.json'
    elif config_type == 'get_device_interfaces':
        config_filename = 'device_' + device_name + '_interfaces' + '.json'
    elif config_type == 'get_device_interface_locations':
        config_filename = 'device_' + device_name + '_interface_' + interface_id + '_locations' + '.json'
    elif config_type == 'get_service_detail' or config_type == 'get_domain_detail':
        config_filename = service_name + '.json'
    elif config_type == 'get_device':
        config_filename = device_name + '.json'
    elif config_type == 'get_device_interface':
        config_filename = 'device_' + device_name + '_interface_' + interface_id + '.json'
    elif config_type == 'get_device_interface_location':
        config_filename = 'device_' + device_name + '_interface_' + interface_id + '_location_' + location_name + '.json'
    else:
        print('Unable to determine filename to read')
        print('No match for config_type')
        return False, False

    try:
        with open(config_filename) as f:
            # decoding the JSON data to a python dictionary object
            config_data = json.load(f)
            print(f'[INFO] Reading config data from JSON file: ', config_filename)

            return config_data, config_filename
    except IOError as e:
        print(f'[FAIL] Unable to read the JSON config file:', config_filename)
        print("I/O error({0}): {1}".format(e.errno, e.strerror))
        return False, False
    except: #handle other exceptions such as attribute errors
        print(f'[FAIL] Unable to read the JSON config file:', config_filename)
        print("Unexpected error:", sys.exc_info()[0])
        return False, False

def get_applications(ng1_host, headers, cookies):
    app_uri = "/ng1api/ncm/applications/"
    url = "https://" + ng1_host + app_uri

    # perform the HTTPS API call to get the Services information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_applications Successful')

        # return the json object that contains the Services information
        return get.json()

    else:
        print('[FAIL] get_applications Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def get_app_detail(ng1_host, app_name, headers, cookies):
    service_uri = "/ng1api/ncm/applications/"
    url = "https://" + ng1_host + service_uri + app_name

    # perform the HTTPS API call to get the Service information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_app_detail Successful')

        # return the json object that contains the Service information
        return get.json()

    else:
        print('[FAIL] get_app_detail Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def update_app(ng1_host, app_name, attribute, attribute_value, headers, cookies):
    service_uri = "/ng1api/ncm/applications/"
    url = "https://" + ng1_host + service_uri + app_name

    # First we will pull the details of the app and then update the desired field
    app_data = get_app_detail(ng1_host, app_name, headers, cookies)
    # Next, we need to determine the applicationType as the different types require
    # different mandatory fields in the input app_data
    application_type = app_data["applicationConfigurations"][0]["applicationType"]
    print('application type is: ', application_type)
    # Next, we need to determine the parentProtocolTypeCode to determine if this is
    # a parent app (TCP, UDP, IP) or a child app with serverAddresses
    parentProtocolTypeCode = app_data["applicationConfigurations"][0]["parentProtocolTypeCode"]
    # If application_type is Well Known Apps, then first determine if it is a child app or not
    # If it is a child app, we have to read the serverAddresses field and copy the value
    # back into the app_data as a field called hostAddresses. If it is a parent_app, then we
    # need to convert the parentProtocolTypeCode into the parentApplication
    if application_type == 'Well Known Apps':
        if(parentProtocolTypeCode == 'TCP'):
            applicationTypeCode = app_data["applicationConfigurations"][0]["applicationTypeCode"]
        elif(parentProtocolTypeCode == 'UDP'):
            applicationTypeCode = app_data["applicationConfigurations"][0]["applicationTypeCode"]
        elif(parentProtocolTypeCode == 'IP'):
            applicationTypeCode = app_data["applicationConfigurations"][0]["applicationTypeCode"]
        else:
            host_addresses = app_data["applicationConfigurations"][0]["serverAddresses"]
            app_data["applicationConfigurations"][0]["HostAddresses"] = host_addresses
            del app_data["applicationConfigurations"][0]["serverAddresses"]
    elif application_type == 'URL Application':
        #app_data["applicationConfigurations"][0]["ParentApplication"] = 'HTTP'
        #del app_data["applicationConfigurations"][0]["serverAddresses"]
        del app_data["applicationConfigurations"][0]["applicationPort"]


    # update the app attribute with the attribute_value
    app_data["applicationConfigurations"][0][attribute] = attribute_value

    # Serialize the python_object into json bytes
    json_string = json.dumps(app_data, indent=4)
    print('Attributes to update =')
    print(json_string)
    # perform the HTTPS API Put call with the serialized json object
    # this will update only the single attribute and its value that we passed in
    put = requests.put(url, headers=headers, data=json_string, verify=False, cookies=cookies)

    if put.status_code == 200:
        # success
        print('[INFO] update_app', app_name, 'Successful')
        return True

    else:
        print('[FAIL] update_app', app_name, 'Failed')
        print('URL:', url)
        print('Response Code:', put.status_code)
        print('Response Body:', put.text)

        return False

def activate_app(ng1_host, app_name, headers, cookies):
    service_uri = "/ng1api/ncm/applications/"
    url = "https://" + ng1_host + service_uri + "activate"

    # First we will pull the details of the app to get the applicationTypeCode
    app_data = get_app_detail(ng1_host, app_name, headers, cookies)
    # Next, we need to determine the applicationTypeCode as the api post will require
    # us to pass in at least that info. We can also string together multiple applicationTypeCodes
    # if we wanted to activate a bunch of apps at once
    application_type_code = app_data["applicationConfigurations"][0]["applicationTypeCode"]
    print('application type code is: ', application_type_code)
    # perform the HTTPS API Post call with just the url
    # this will activate the app app_name if found
    app_data_short = {"applicationConfigurations": [{"applicationTypeCode": application_type_code}]}
    # use json.dumps to provide a serialized json object (a string actually)
    # this json_string will tell the api which app we want to activate
    json_string = json.dumps(app_data_short)
    post = requests.post(url, headers=headers, data=json_string, verify=False, cookies=cookies)
    if post.status_code == 200:
        # success
        print('[INFO] activate_app', app_name, 'Successful')
        return True

    else:
        print('[FAIL] activate_app', app_name, 'Failed')
        print('URL:', url)
        print('Response Code:', post.status_code)
        print('Response Body:', post.text)

        return False


def deactivate_app(ng1_host, app_name, headers, cookies):
    service_uri = "/ng1api/ncm/applications/"
    url = "https://" + ng1_host + service_uri + "deactivate"
    # First we will pull the details of the app to get the applicationTypeCode
    app_data = get_app_detail(ng1_host, app_name, headers, cookies)
    # Next, we need to determine the applicationTypeCode as the api post will require
    # us to pass in at least that info. We can also string together multiple applicationTypeCodes
    # if we wanted to deactivate a bunch of apps at once
    application_type_code = app_data["applicationConfigurations"][0]["applicationTypeCode"]
    print('application type code is: ', application_type_code)
    # perform the HTTPS API Post call with just the url
    # this will deactivate the app app_name if found
    app_data_short = {"applicationConfigurations": [{"applicationTypeCode": application_type_code}]}
    # use json.dumps to provide a serialized json object (a string actually)
    # this json_string will tell the api which app we want to deactivate
    json_string = json.dumps(app_data_short)
    post = requests.post(url, headers=headers, data=json_string, verify=False, cookies=cookies)
    # perform the HTTPS API Post call with just the url
    # this will deactivate the app app_name if found
    post = requests.post(url, headers=headers, verify=False, cookies=cookies)
    if post.status_code == 200:
        # success
        print('[INFO] deactivate_app', app_name, 'Successful')
        return True

    else:
        print('[FAIL] deactivate_app', app_name, 'Failed')
        print('URL:', url)
        print('Response Code:', post.status_code)
        print('Response Body:', post.text)

        return False

def create_app(ng1_host, app_name, headers, cookies):
    # Create a new app by reading in a file that contains all the attributes
    # Set the read_config_from_json parameters to "Null" that we don't need
    config_type = 'create_app'
    service_name = 'Null'
    service_type = 'Null'
    device_name = 'Null'
    interface_id = 'Null'
    location_name = 'Null'
    service_uri = "/ng1api/ncm/applications/"

    # Read in the json file to get all the app attributes
    app_data, config_filename = read_config_from_json(config_type, service_type, service_name, app_name, device_name, interface_id, location_name)
    url = "https://" + ng1_host + service_uri

    # Add the parent_app passed into the function as an additional application attribute
    # app_data["applicationConfigurations"][0]["ParentApplication"] = parent_app

    # use json.dumps to provide a serialized json object (a string actually)
    # this json_string will become our new configuration for this app_name
    json_string = json.dumps(app_data)
    # print('New app data =')
    # print(json_string)

    # perform the HTTPS API Post call with the serialized json object service_data
    # this will create the service configuration in nG1 for this config_filename (the new service_name)
    post = requests.post(url, headers=headers, data=json_string, verify=False, cookies=cookies)

    if post.status_code == 200:
        # success
        print('[INFO] create_app', app_name, 'Successful')
        return True

    else:
        print('[FAIL] create_app', app_name, 'Failed')
        print('URL:', url)
        print('Response Code:', post.status_code)
        print('Response Body:', post.text)

        return False

def delete_app(ng1_host, app_name, headers, cookies):
    service_uri = "/ng1api/ncm/applications/"
    url = "https://" + ng1_host + service_uri + app_name
    # Perform the HTTPS API Delete call by passing the app_name.
    # This will delete the specific application configuration for this app_name.
    delete = requests.delete(url, headers=headers, verify=False, cookies=cookies)

    if delete.status_code == 200:
        # success
        print('[INFO] delete_app', app_name, 'Successful')
        return True

    else:
        print('[FAIL] delete_app', app_name, 'Failed')
        print('URL:', url)
        print('Response Code:', delete.status_code)
        print('Response Body:', delete.text)

        return False

def get_apns(ng1_host, headers, cookies):
    uri = "/ng1api/ncm/apns/"
    url = "https://" + ng1_host + uri

    # perform the HTTPS API call to get the All APNs information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_apns Successful')

        # return the json object that contains the All APNs information
        return get.json()

    else:
        print('[FAIL] get_apns Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def get_apn_detail(ng1_host, headers, cookies, apn_name):
    uri = "/ng1api/ncm/apns/"
    url = "https://" + ng1_host + uri + apn_name

    # perform the HTTPS API call to get the APN detail information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_apn_detail for', apn_name, 'Successful')

        # return the json object that contains the APN detail information
        return get.json()

    else:
        print('[FAIL] get_apn_detail for', apn_name, 'Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def set_apns(ng1_host, headers, cookies):
    # Add a list of APN groups to nG1 based on an existing json file definition
    # Set the read_config_from_json parameters to "Null" that we don't need
    config_type = 'set_apns'
    app_name = 'Null'
    device_name = 'Null'
    interface_id = 'Null'
    location_name = 'Null'
    service_uri = "/ng1api/ncm/apns/"

    # Read in the json file to get all the service attributes
    service_data, config_filename = read_config_from_json(config_type, service_type, service_name, app_name, device_name, interface_id, location_name)
    url = "https://" + ng1_host + service_uri

    # use json.dumps to provide a serialized json object (a string actually)
    # this json_string will become our new configuration for this service_name
    json_string = json.dumps(service_data)
    # print('New service data =')
    # print(json_string)

    # perform the HTTPS API Post call with the serialized json object service_data
    # this will create the apn group configuration in nG1 for this apn_filename (the new service_name)
    post = requests.post(url, headers=headers, data=json_string, verify=False, cookies=cookies)

    if post.status_code == 200:
        # success
        print('[INFO] set_apns Successful')
        return True

    else:
        print('[FAIL] set_apns Failed')
        print('URL:', url)
        print('Response Code:', post.status_code)
        print('Response Body:', post.text)

        return False


def get_domains(ng1_host, headers, cookies):
    service_uri = "/ng1api/ncm/domains/"
    url = "https://" + ng1_host + service_uri

    # perform the HTTPS API call to get the Domains information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_domains Successful')

        # return the json object that contains the Domains information
        return get.json()

    else:
        print('[FAIL] get_domains Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def get_domain_detail(ng1_host, domain_name, headers, cookies):
    service_uri = "/ng1api/ncm/domains/"
    url = "https://" + ng1_host + service_uri + domain_name

    # perform the HTTPS API call to get the Service information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_domain_detail for', domain_name, 'Successful')

        # return the json object that contains the Domain information
        return get.json()

    else:
        print('[FAIL] get_domain_detail for', domain_name, 'Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def create_domain(ng1_host, domain_name, headers, cookies):
    # Create a new dashboard domain by reading in a file that contains all the attributes
    # Set the read_config_from_json parameters to "Null" that we don't need
    config_type = 'create_domain'
    service_type = 'Null'
    app_name = 'Null'
    device_name = 'Null'
    interface_id = 'Null'
    location_name = 'Null'
    service_uri = "/ng1api/ncm/domains/"

    # Read in the json file to get all the service attributes
    domain_data, config_filename = read_config_from_json(config_type, service_type, domain_name, app_name, device_name, interface_id, location_name)
    url = "https://" + ng1_host + service_uri

    # use json.dumps to provide a serialized json object (a string actually)
    # this json_string will become our new configuration for this domain_name
    json_string = json.dumps(domain_data)
    # print('New domain data =')
    # print(json_string)

    # perform the HTTPS API Post call with the serialized json object service_data
    # this will create the service configuration in nG1 for this config_filename (the new service_name)
    post = requests.post(url, headers=headers, data=json_string, verify=False, cookies=cookies)

    if post.status_code == 200:
        # success
        print('[INFO] create_domain: ', domain_name, 'Successful')
        return True

    else:
        print('[FAIL] create_domain: ', domain_name, 'Failed')
        print('URL:', url)
        print('Response Code:', post.status_code)
        print('Response Body:', post.text)

        return False

def delete_domain(ng1_host, domain_name, headers, cookies):
    service_uri = "/ng1api/ncm/domains/"
    url = "https://" + ng1_host + service_uri + domain_name
    # Perform the HTTPS API Delete call by passing the service_name.
    # This will delete the specific service configuration for this service_name.
    delete = requests.delete(url, headers=headers, verify=False, cookies=cookies)

    if delete.status_code == 200:
        # success
        print('[INFO] delete_domain', domain_name, 'Successful')
        return True

    else:
        print('[FAIL] delete_service', domain_name, 'Failed')
        print('URL:', url)
        print('Response Code:', delete.status_code)
        print('Response Body:', delete.text)

        return False

def get_devices(ng1_host, headers, cookies):
    device_uri = "/ng1api/ncm/devices/"
    url = "https://" + ng1_host + device_uri
    # perform the HTTPS API call to get the device information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_devices request Successful')

        # return the json object that contains the device information
        return get.json()

    else:
        print('[FAIL] get_devices request failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def get_device_detail(ng1_host, headers, cookies, device_name):
    uri = "/ng1api/ncm/devices/"
    url = "https://" + ng1_host + uri + device_name
    # perform the HTTPS API call to get the device information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_device_detail request for', device_name, 'Successful')

        # return the json object that contains the device information
        return get.json()

    else:
        print('[FAIL] get_device_detail request for', device_name, 'failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def get_services(ng1_host, service_type, headers, cookies):
    service_uri = "/ng1api/ncm/services/"
    url = "https://" + ng1_host + service_uri
    # Check to see if we are fetching app, network or all services
    if service_type == 'all':
        service_type = 'Null'

    params = "type=" + service_type

    # perform the HTTPS API call to get the Services information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies, params=params)

    # if service_type is Null, set it back to 'all' for the success or error message
    if service_type == 'Null':
        service_type = 'all'

    if get.status_code == 200:
        # success
        print('[INFO] get_services for service type', service_type, 'Successful')

        # return the json object that contains the Services information
        return get.json()

    else:
        print('[FAIL] get_services for service type', service_type, 'Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def get_service_detail(ng1_host, service_name, headers, cookies):
    service_uri = "/ng1api/ncm/services/"
    url = "https://" + ng1_host + service_uri + service_name

    # perform the HTTPS API call to get the Service information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_service_detail for', service_name, 'Successful')

        # return the json object that contains the Service information
        return get.json()

    else:
        print('[FAIL] get_service_detail for', service_name, 'Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def update_service(ng1_host, service_name, service_type, me_name, protocol_or_group_code, attribute, attribute_value, headers, cookies):
    service_uri = "/ng1api/ncm/services/"
    url = "https://" + ng1_host + service_uri + service_name

    # It seems that the service ID number is required to make an update_app
    # So we have to first pull the details of the service and then update the desired field
    service_data = get_service_detail(ng1_host, service_name, headers, cookies)

    # update the service attribute with the attribute_value
    service_data["serviceDetail"][0][attribute] = attribute_value

    # Serialize the python_object into json bytes
    json_string = json.dumps(service_data, indent=4)
    print('Attributes to update =')
    print(json_string)

    # perform the HTTPS API Put call with the serialized json object
    # this will update only the single attribute and its value that we passed in
    put = requests.put(url, headers=headers, data=json_string, verify=False, cookies=cookies)
    if put.status_code == 200:
        # success
        print('[INFO] update_service', service_name, 'Successful')
        return True

    else:
        print('[FAIL] update_service', service_name, 'Failed')
        print('URL:', url)
        print('Response Code:', put.status_code)
        print('Response Body:', put.text)

        return False

def create_service(ng1_host, service_type, service_name, headers, cookies):
    # Create a new service by reading in a file that contains all the attributes
    # Set the read_config_from_json parameters to "Null" that we don't need
    config_type = 'create_service'
    app_name = 'Null'
    device_name = 'Null'
    interface_id = 'Null'
    location_name = 'Null'
    service_uri = "/ng1api/ncm/services/"

    # Read in the json file to get all the service attributes
    service_data, config_filename = read_config_from_json(config_type, service_type, service_name, app_name, device_name, interface_id, location_name)
    url = "https://" + ng1_host + service_uri

    # use json.dumps to provide a serialized json object (a string actually)
    # this json_string will become our new configuration for this service_name
    json_string = json.dumps(service_data)
    # print('New service data =')
    # print(json_string)

    # perform the HTTPS API Post call with the serialized json object service_data
    # this will create the service configuration in nG1 for this config_filename (the new service_name)
    post = requests.post(url, headers=headers, data=json_string, verify=False, cookies=cookies)

    if post.status_code == 200:
        # success
        print('[INFO] create_service', service_name, 'Successful')
        return True

    else:
        print('[FAIL] create_service', service_name, 'Failed')
        print('URL:', url)
        print('Response Code:', post.status_code)
        print('Response Body:', post.text)

        return False

def delete_service(ng1_host, service_name, headers, cookies):
    service_uri = "/ng1api/ncm/services/"
    url = "https://" + ng1_host + service_uri + service_name
    # Perform the HTTPS API Delete call by passing the service_name.
    # This will delete the specific service configuration for this service_name.
    delete = requests.delete(url, headers=headers, verify=False, cookies=cookies)

    if delete.status_code == 200:
        # success
        print('[INFO] delete_service', service_name, 'Successful')
        return True

    else:
        print('[FAIL] delete_service', service_name, 'Failed')
        print('URL:', url)
        print('Response Code:', delete.status_code)
        print('Response Body:', delete.text)

        return False

def get_devices(ng1_host, headers, cookies):
    device_uri = "/ng1api/ncm/devices/"
    url = "https://" + ng1_host + device_uri
    # perform the HTTPS API call to get the device information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_devices request Successful')

        # return the json object that contains the device information
        return get.json()

    else:
        print('[FAIL] get_devices request failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def get_device(ng1_host, device_name, headers, cookies):
    device_uri = "/ng1api/ncm/device/"
    url = "https://" + ng1_host + device_uri
    # perform the HTTPS API call to get the device information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_device for', device_name, 'Successful')

        # return the json object that contains the device information
        return get.json()

    else:
        print('[FAIL] get_device for', device_name, 'Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def get_device_interfaces(ng1_host, device_name, headers, cookies):
    device_uri = "/ng1api/ncm/devices/" + device_name + "/interfaces"
    url = "https://" + ng1_host + device_uri
    # perform the HTTPS API call to get the device information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_device_interfaces for', device_name, 'Successful')

        # return the json object that contains the device information
        return get.json()

    else:
        print('[FAIL] get_device_interfaces for', device_name, 'Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def get_device_interface(ng1_host, device_name, interface_id, headers, cookies):
    device_uri = "/ng1api/ncm/devices/" + device_name + "/interfaces"
    url = "https://" + ng1_host + device_uri
    params = interface_id
    # perform the HTTPS API call to get the device information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies, params=params)

    if get.status_code == 200:
        # success
        print('[INFO] get_device_interface for', device_name, 'Successful')

        # return the json object that contains the device information
        return get.json()

    else:
        print('[FAIL] get_device_interface for', device_name, 'Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def get_device_interface_locations(ng1_host, device_name, interface_id, headers, cookies):
    device_uri = "/ng1api/ncm/devices/" + device_name + "/interfaces/" + interface_id + "/locations"
    url = "https://" + ng1_host + device_uri
    # perform the HTTPS API call to get the device information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_device_interface_locations for', device_name, 'Interface', interface_id, 'Successful')

        # return the json object that contains the device information
        return get.json()

    else:
        print('[FAIL] get_device_interface_locations for ', device_name, 'Interface', interface_id, 'Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def get_device_interface_location(ng1_host, device_name, interface_id, location_name, headers, cookies):
    device_uri = "/ng1api/ncm/devices/" + device_name + "/interfaces/" + interface_id + "/locations/" + location_name
    url = "https://" + ng1_host + device_uri
    # perform the HTTPS API call to get the device information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_device_interface_location from', device_name, 'Successful')

        # return the json object that contains the device information
        return get.json()

    else:
        print('[FAIL] get_device_interface_location from', device_name, 'Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def update_device(ng1_host, device_name, attribute, attribute_value, headers, cookies):
    device_uri = "/ng1api/ncm/devices/"
    url = "https://" + ng1_host + device_uri + device_name
    device_data = get_device(ng1_host, device_name, headers, cookies)

    # update the specific attribute within device_data with the attribute_value
    device_data["deviceConfigurations"][0][attribute] = attribute_value
    # Print the modified value for reference
    # print(attribute, "now = ", device_data["deviceConfigurations"][0][attribute])

    # use json.dump to provide a json object (a string actually)
    # We will use this json_string to overwrite the configuration for this device_name
    json_string = json.dumps(device_data, indent=4)
    print('new device data =')
    print(json_string)

    # perform the HTTPS API call with the serialized json object
    # overwrite the current configuration for device_name with the modified configuration
    put = requests.put(url, headers=headers, data=json_string, verify=False, cookies=cookies)

    if put.status_code == 200:
        # success
        print('[INFO] update_device', device_name, 'Successful', put.status_code)
        return put.status_code

    else:
        print('[FAIL] update_device', device_name, 'Failed')
        print('URL:', url)
        print('Response Code:', put.status_code)
        print('Response Body:', put.text)

        return False

def device_menu(ng1_host, headers, cookies):
    device_count = 0
    # Get info on all devices, returned as a python object
    devices_data = get_devices(ng1_host, headers, cookies)
    # Create a list of dictionaries that we can interate over
    devices_list = devices_data['deviceConfigurations']
    # Interate over the devices in devices_list and print a menu for the user to select a device from
    for device in devices_list:
        print('[', device_count + 1, ']', devices_list[device_count]['deviceName'])
        device_count += 1

    # Offer an 'All Devices' option in the menu
    print('[', device_count + 1, '] All Devices')
    device_count += 1

    # Take the users input and verify that it is one of the possible menu selections
    while True:
        try:
            # Take the users input and convert to integer
            selection = int(input('Please select the Device you want location data on: '))
        except:
            print('Not an integer entry, exiting...')
            # to avoid an endless loop situation, we will exit if they don't enter an integer
            exit()
        if selection not in range(1, device_count+1):
            # User has entered an integer that is higher than any of the menu options
            print('Out of range entry, please enter the number of the device you are selecting')
            continue
        elif selection == device_count:
            # User has selected All Devices. We will iterate through each device
            # and produce independant CSV files. So we will return the list of devices.
            print('You selected: All Devices')
            # Set selection to -1 as an indicater to the caller that 'All Devices' was selected
            selection = -1
            return devices_list, selection
        else:
            # The user properly selected one of the menu options
            selection -= 1
            device_name = devices_list[selection]['deviceName']
            print('You selected: ', device_name)
            # We will need to interate over the devices_list in case the user selected 'All Devices'
            # So in this case we will return the devices_list along with the selection as an index
            return devices_list, selection

def get_devices_interfaces_vlans_sorted(ng1_host, device_name, headers, cookies):

    # For the device_name, get info on all the interfaces on that Device
    interfaces_data = get_device_interfaces(ng1_host, device_name, headers, cookies)
    # Create a list of dictionaries that we can interate over
    interfaces_list = interfaces_data['interfaceConfigurations']
    # Initialize new lists that we can place our results into
    all_interface_locations = []
    filtered_all_interface_locations = []

    # Iterate through all the interfaces on a device and put all the locations into one big list
    for interface in interfaces_list:
        # Pull out the interface_id for this interface so we can query that for its locations
        interface_id = str(interface['interfaceNumber'])
        # Query the interface_id for its locations
        interface_locations = get_device_interface_locations(ng1_host, device_name, interface_id, headers, cookies)
        # Create a list of dictionaries that contain the locations on this interface
        interface_locations_list = interface_locations['locationKeyConfigurations']
        # Merge the interface locations list for each interface into one big list for all interfaces on this device
        all_interface_locations = all_interface_locations + interface_locations_list

    # Filter the locations list to just VLAN locations
    for location in all_interface_locations:
        if location['locationKeyType'] == "VLAN":
            filtered_all_interface_locations.append(location)

    # Sort the locations by VLAN number
    filtered_all_interface_locations = sorted(filtered_all_interface_locations, key = lambda i: i['locationKeyID'])

    # Return the list of all interface locations on this device filtered by VLAN and sorted by VLAN number
    return filtered_all_interface_locations

# ---------- Code Driver section below ----------------------------------------

now = datetime.now()
date_time = now.strftime("%Y_%m_%d_%H%M%S")

# Create logging function_
logging.basicConfig(filename="ng1sync.log", format='%(asctime)s %(message)s', filemode='a+')
# Creating an object
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.info(f"*** Start of logs {date_time} ***")

cred_filename = 'CredFile.ini'
ng1key_file = 'ng1key.key'

# Retrieve credentials.
with open(ng1key_file, 'r') as ng1key_in:
    ng1key = ng1key_in.read().encode()
    fng1 = Fernet(ng1key)
with open(cred_filename, 'r') as cred_in:
    lines = cred_in.readlines()
    ng1token = lines[2].partition('=')[2].rstrip("\n")
    #Check to see if we are expected to use an API Token or Username:Password
    if len(ng1token) > 1:
        use_token = True
        ng1token_pl = fng1.decrypt(ng1token.encode()).decode()
    else:
        use_token = False
        ng1username = lines[3].partition('=')[2].rstrip("\n")
        ng1password = lines[4].partition('=')[2].rstrip("\n")
        ng1password_pl = fng1.decrypt(ng1password.encode()).decode()
    ng1destination = lines[5].partition('=')[2].rstrip("\n")
    ng1destPort = lines[6].partition('=')[2].rstrip("\n")


# This one is for TTEC-WCCE Global Manager
# ng1_host = "den01mgmtngn01.mgmt.webexcce.com"

# This one is for San Jose lab nG1
# ng1_host = "10.8.8.3"
# This one is for the F5 Lab
# ng1_host = "54.185.154.36"

# You can use your username and password (plain text) in the authorization header (basic authentication)
# In this case cookies must be set to 'Null'
# If you are using the authentication Token, then credentials = 'Null'
# credentials = 'jgiles', 'netscout1'
# cookies = 'Null'

# You can use an authentication token named NSSESSIONID obtained from the User Management module in nGeniusONE (open the user and click Generate New Key)
# If we are using the token rather than credentials, we will set credentials to 'Null'
if use_token == True:
    credentials = 'Null'

    cookies = {
        'NSSESSIONID': ng1token_pl,
        }
        # This user token is for jgiles user on the San Jose Lab nG1
        #cookies = {
        #    'NSSESSIONID': 'cqDYQ7FFMtuonYyFHmBztqVtSIcM4S+jzV6iOyNwBwD/vCu88+gYTjuBvFDGUzPcwcNnhRv8GMNR5PSSYJb1JhQTpQi8VYdsb0Kw7ow1J5c=',
        #}

        # This user token is for Chris Weisinger on the TTEC-WCCE global manager
        # cookies = {
        #     'NSSESSIONID': 'vNiSgerZ7HTlrVLE2XtneVEUkd9CtVseJ13VSBdAg67GSRMLgxdS/hpzbudVXEsx8aDfahSL/HAGhMi5X0/76SM9N56sC/sxNBE9+7RyG5x6PgZIJD6ypPSB1YPv0L5Y',
        # }
# Otherwise set the credentials to username:password and use that instead of an API token
else:
    cookies = 'Null'
    credentials = ng1username + ':' + ng1password_pl

#ng1_host = ng1destination + ':' + ng1destPort
ng1_host = ng1destination
# Supply the name of the service to use on get_service_detail, update_service, delete_service or create_service
#service_name = 'app_service_gilestest'

# Supply the name of the dashboard domain to use on get_domain_detail, update_domain, delete_domain or create_domain
#domain_name = 'Cisco IOT'

# Supply the type of service to get from get_services (application, network or all).
#service_type = 'get_domain_detail'

# Supply the name of the application to use on get_app_detail, update_app, delete_app or create_app
#app_name = 'MyHTTPSApp'
# app_name = '10-8-8-APP'

# Supply the device name for get_device, update_device, get_device_interfaces, get_device_interface, get_device_interface_locations, get_device_interface_location
#device_name = 'isng4795'
# device_name = "usden01mgmtnif01"

# Supply the interface number for get_device_interface or get_device_interface_location, get_device_interface_locations
#interface_id = "3"

# Supply the attribute and attribute_value that you want to pass into one of the update functions
#attribute = 'responseTime'
#attribute_value = 'Disabled'

# Supply the name of the location for get_device_interface_location
#location_name = "Boston Division"

# supply the the me_name and protocol_or_group_code for update_service
#me_name = 'isng4795:if3'
#protocol_or_group_code = 'HTTP'

# Supply the type of config request you are making
# get_device, get_devices, get_services, get_service_detail, get_device_interface
# get_device_interfaces, get_device_interface_location, get_device_interface_locations
# config_type = "get_service_detail"
#config_type = 'get_domain_detail'

# specify the headers to use in the API call
headers = {
    'Cache-Control': "no-cache",
    'Accept': "application/json",
    'Content-Type': "application/json"
}

# To use username and password, pass in your credentials and set cookies = 'Null'
# To use a token, pass in your cookies and set credentials = 'Null'
# print ('cookies = ', cookies, ' and credentials = ', credentials)
#
cookies = open_session(ng1_host, headers, cookies, credentials)

# Put a modification to a specific device
# update_device(ng1_host, device_name, headers, cookies)

# Get info on all devices, returned as a python object
# devices_data = get_devices(ng1_host, headers, cookies)
# pprint.pprint(devices_data)

# Get info on a specific device, returned as a python object
# device_data = get_device(ng1_host, device_name, headers, cookies)
# pprint.pprint(device_data)

# Get info on all the interface on a specific Device
# interfaces_data = get_device_interfaces(ng1_host, device_name, headers, cookies)
# pprint.pprint(interfaces_data)

# interface_data = get_device_interface(ng1_host, device_name, interface_id, headers, cookies)
# pprint.pprint(interface_data)

# interface_locations = get_device_interface_locations(ng1_host, device_name, interface_id, headers, cookies)
# pprint.pprint(interface_locations)

# interface_data = get_device_interface_location(ng1_host, device_name, interface_id, location_name, headers, cookies)
# pprint.pprint(interface_data)

# Get info on all dashboard domains. Returned as a python object.
#config_data = get_domains(ng1_host, headers, cookies)
#pprint.pprint(config_data)

# Get info on a specific domain, returned as a python object
#config_data = get_domain_detail(ng1_host, domain_name, headers, cookies)
#pprint.pprint(config_data)

# Put an update to a specific domain
# update_domain(ng1_host, domain_name, me_name, protocol_or_group_code, attribute, attribute_value, headers, cookies)

# Delete a specific domain
# delete_domain(ng1_host, domain_name, headers, cookies)

# Set all APN locations based on a filename apn-list.json
#set_apns(ng1_host, headers, cookies)
#exit()

# Initialize an empty apn list that we will use later to verify user input
apn_list = []
# Get info on all APN locations
apn_configs = get_apns(ng1_host, headers, cookies)
if apn_configs != False:
    for apn in apn_configs["apns"]:
        apn_name = apn["name"]
        apn_list.append(apn_name)
else:
    print('Unable to fetch APNs, exiting....')
    exit()

# Initialize an empty datacenter list that we will use later to verify user input
datacenter_list = ["Atlanta", "Phoenix", "San Jose", "Toronto", "Vancouver"]
# Get info on all datacenters
#datacenter_configs, config_filename = read_config_from_json('get_datacenters', 'Null', 'CiscoIOT-DataCenters', 'Null', 'Null', 'Null', 'Null')
#if datacenter_configs != False:
#    for datacenter in datacenter_configs["Data Centers"]:
#        datacenter_name = datacenter["name"]
#        datacenter_list.append(datacenter_name)
#else:
#    print('Unable to fetch Datacenter and Customers list, exiting....')
#    exit()
#print('DataCenter list is: ', datacenter_list)

#service_name = 'All-NWS-Ring'
#config_data = get_service_detail(ng1_host, service_name, headers, cookies)
#pprint.pprint(config_data)
#exit()

# Get the new customer profile from the user
while True:
    profile = customer_menu(ng1_host, headers, cookies, apn_list, datacenter_list)
    if profile != False:
        print(f"Profile is : {profile}")
        break
    # If the user does not confirm the new customer profile, let them start over
    else:
        print('New customer profile discarded, starting over...')
        print('')
        continue

# Fetch the APN id number that matches with each APN in the customer profile
apn_ids = {}
for apn_name in profile['apn_list']:
    apn_config = get_apn_detail(ng1_host, headers, cookies, apn_name)
    if apn_config != False:
        apn_ids[apn_name] = apn_config['id']
    else:
        print('Unable to fetch APN ID number for ', apn_name)
        print('Exiting...')
        exit()

# Create a network service for each APN specified that includes all availalbe MEs.
# Start by just getting all interfaces on our one test vStream.
net_service_ids = {}
device_list = {"Atlanta" : ["", []], "Phoenix" : ["", []]}
all_interfaces_data = []
for device_name in device_list:
    # We need the ip address of each device to fill in the network service members later.
    device_detail = get_device_detail(ng1_host, headers, cookies, str(device_name))
    if device_detail != False:
        # Save the IP Address for each device in the devices list so that we can use them later.
        device_list[device_name][0] = device_detail['deviceConfigurations'][0]['deviceIPAddress']
        device_interfaces = get_device_interfaces(ng1_host, device_name, headers, cookies)
        device_interfaces = device_interfaces['interfaceConfigurations']
        # Save the current interface list for each device in the device_list to use later
        device_list[device_name][1] = device_interfaces
        # Accumulate a master dictionary that includes all interfaces for all devices
        #print('\ndevice interfaces data', device_interfaces)
        for item in device_interfaces:
            all_interfaces_data.append(item)
        #print('\nall interfaces data', all_interfaces_data)

# Build the network services needed for each APN that the user specified for this new customer
for apn_name in apn_ids:
    # The first network service we will create is for All device interfaces for each apn specified
    # The network service name takes the form of All-NWS-{apn_name}
    # Initialize the dictionay that we will use to build up our network service definition.
    net_srv_config_data = {'serviceDetail': [{'alertProfileID': 2,
    'exclusionListID': -1,
    'id': -1,
    'isAlarmEnabled': False,
    'serviceName': 'All-NWS-' + apn_name,
    'serviceType': 6}]}

    # Add service members to the network service definition for each apn on every interface in the system
    net_srv_config_data['serviceDetail'][0]['serviceMembers'] = []
    # So we must interate through the master list of all interfaces and add them to our network servce...
    # as individual members.
    for device_interface in all_interfaces_data:
        net_srv_config_data['serviceDetail'][0]['serviceMembers'].append({'enableAlert': False,
        'interfaceNumber': device_interface['interfaceNumber'],
        'ipAddress': device_list[device_name][0],
        'locationKeyInfo': [{'asi1xType': '',
        'isLocationKey': True,
        'keyAttr': apn_ids[apn_name],
        'keyType': 4}],
        'meAlias': device_interface['alias'],
        'meName': device_interface['interfaceName']})

    # Write the config_data to a JSON configuration file.
    config_type = 'get_service_detail'
    network_service_name = 'All-NWS-' + apn_name
    write_config_to_json(config_type, 'Null', network_service_name, 'Null', 'Null', 'Null', 'Null', net_srv_config_data)
    # Create the new network service.
    create_service(ng1_host, 'Null', network_service_name, headers, cookies)
    # We need to know the id number that was assigned to this new network service, so we get_service_detail on it.
    net_srv_config_data = get_service_detail(ng1_host, network_service_name, headers, cookies)
    net_srv_id = net_srv_config_data['serviceDetail'][0]['id']
    # Add this network service id to our dictionary so we can use it later to assign domain members.
    net_service_ids[network_service_name] = net_srv_id
    #pprint.pprint(device_list)

    # Now create a network service for each GSSN (All ISNG interfaces) for the datacenters that the user specified.
    # The network service name is in the form of {datacenter_abbreviation}-NWS-{apn_name}-All-GGSNs.
    for datacenter in profile['dc_list']:
        if datacenter.startswith('Atl'):
            network_service_name = 'ATL-NWS-' + apn_name + '-All-GGSNs'
        elif datacenter.startswith('Pho'):
            network_service_name = 'PHX-NWS-' + apn_name + '-All-GGSNs'
        elif datacenter.startswith('San'):
            network_service_name = 'SJC-NWS-' + apn_name + '-All-GGSNs'
        elif datacenter.startswith('Tor'):
            network_service_name = 'TOR-NWS-' + apn_name + '-All-GGSNs'
        elif datacenter.startswith('Van'):
            network_service_name = 'VAN-NWS-' + apn_name + '-All-GGSNs'

        # Initialize the dictionay that we will use to build up our network service definition.
        net_srv_config_data = {'serviceDetail': [{'alertProfileID': 2,
        'exclusionListID': -1,
        'id': -1,
        'isAlarmEnabled': False,
        'serviceName': network_service_name,
        'serviceType': 6}]}

        # Add service members to the network service definition for each apn on every interface for that single device
        # This means that for each datacenter specified, we should have a list of network services for each...
        # interface on that datacenter ISNG device. Each network service is the combination of the device interface...
        # and the APN location
        net_srv_config_data['serviceDetail'][0]['serviceMembers'] = []

        for device_interface in device_list[datacenter][1]:
            net_srv_config_data['serviceDetail'][0]['serviceMembers'].append({'enableAlert': False,
            'interfaceNumber': device_interface['interfaceNumber'],
            'ipAddress': device_list[datacenter][0],
            'locationKeyInfo': [{'asi1xType': '',
            'isLocationKey': True,
            'keyAttr': apn_ids[apn_name],
            'keyType': 4}],
            'meAlias': device_interface['alias'],
            'meName': device_interface['interfaceName']})

        # Write the config_data to a JSON configuration file.
        config_type = 'get_service_detail'
        write_config_to_json(config_type, 'Null', network_service_name, 'Null', 'Null', 'Null', 'Null', net_srv_config_data)
        # Create the new network service.
        create_service(ng1_host, 'Null', network_service_name, headers, cookies)
        # We need to know the id number that was assigned to this new network service, so we get_service_detail on it.
        net_srv_config_data = get_service_detail(ng1_host, network_service_name, headers, cookies)
        net_srv_id = net_srv_config_data['serviceDetail'][0]['id']
        # Add this network service id to our dictionary so we can use it later to assign domain members.
        net_service_ids[network_service_name] = net_srv_id
        #pprint.pprint(net_service_ids)
exit()
#Lists of existing applications we intend to use. Could pull this from a file.
app_service_list = ['GTPv0', 'GTPv1', 'GTPv2']
app_service_ids = {}

# Interate through the network service list and create services for use later in domain "Control".
for network_service in network_service_list:
    # We need to fetch the ids of each network service.
    net_srv_config_data = get_service_detail(ng1_host, network_service, headers, cookies)
    # Extract the id from the service config data
    net_srv_id = net_srv_config_data['serviceDetail'][0]['id']
    # Add this network service id to a dictionay of ids.
    network_service_ids[network_service] = net_srv_id
    # For writing each app service configuration to the json file, first set the config_type.
    config_type = 'get_service_detail'
    # Iterate throught the app_service_list and create a new app service for each app in the app_service_list.
    for app_serv in app_service_list:
        application_service_name = 'App Service ' + app_serv + ' ' + network_service
        app_srv_config_data = {'serviceDetail': [{'alertProfileID': 1,
                    'exclusionListID': -1,
                    'id': -1,
                    'isAlarmEnabled': False,
                    'serviceDefMonitorType': 'ADM_MONITOR_ENT_ADM',
                    'serviceMembers': [{'enableAlert': False,
                                        'interfaceNumber': -1,
                                        'isNetworkDomain': True,
                                        'melID': -1,
                                        'networkDomainID': net_srv_id,
                                        'networkDomainName': network_service,
                                        'protocolOrGroupCode': app_serv}],
                    'serviceName': application_service_name,
                    'serviceType': 1}]}
        # Write the config_data to a JSON configuration file.
        write_config_to_json(config_type, 'Null', application_service_name, 'Null', 'Null', 'Null', 'Null', app_srv_config_data)
        # Create the new app service.
        create_service(ng1_host, service_type, application_service_name, headers, cookies)
        # We need to know the id number that was assigned to this new app service.
        app_srv_config_data = get_service_detail(ng1_host, application_service_name, headers, cookies)
        app_srv_id = app_srv_config_data['serviceDetail'][0]['id']
        # Add this app service id to our dictionary so we can use it later to assign domain members.
        app_service_ids[application_service_name] = app_srv_id

# Create the App Services 'Web App Group' to be used by the User Donmain
# Create one for each network service
for network_service in network_service_list:
    application_service_name = 'Web App Group ' + network_service
    # Fetch the network service id number from our list network_service_ids
    net_srv_id = network_service_ids[network_service] = net_srv_id
    app_srv_config_data = {'serviceDetail': [{'alertProfileID': 1,
            'exclusionListID': -1,
            'id': -1,
            'isAlarmEnabled': False,
            'serviceDefMonitorType': 'ADM_MONITOR_ENT_ADM',
            'serviceMembers': [{'enableAlert': False,
                                'interfaceNumber': -1,
                                'isNetworkDomain': True,
                                'isProtocolGroup': True,
                                'melID': -1,
                                'networkDomainID': net_srv_id,
                                'networkDomainName': network_service,
                                'protocolOrGroupCode': 'WEB'}],
            'serviceName': application_service_name,
            'serviceType': 1}]}
    # Write the config_data to a JSON configuration file.
    write_config_to_json(config_type, 'Null', application_service_name, 'Null', 'Null', 'Null', 'Null', app_srv_config_data)
    # Create the new app service.
    create_service(ng1_host, service_type, application_service_name, headers, cookies)
    # We need to know the id number that was assigned to this new app service.
    app_srv_config_data = get_service_detail(ng1_host, application_service_name, headers, cookies)
    app_srv_id = app_srv_config_data['serviceDetail'][0]['id']
    # Add this app service id to our dictionary so we can use it later to assign domain members.
    app_service_ids[application_service_name] = app_srv_id

exit()

# Create an empty domain under the root "Enterprise".
domain_name = 'Cisco IOT'
parent_config_data = {"domainDetail": [{
                                      "domainName": domain_name,
                                      "id": "-1",
                                      "parentID": 1}]}
# Write the config_data to a JSON configuration file.
write_config_to_json(config_type, 'Null', domain_name, 'Null', 'Null', 'Null', 'Null', parent_config_data)
# Create the parent domain.
create_domain(ng1_host, domain_name, headers, cookies)
parent_config_data = get_domain_detail(ng1_host, domain_name, headers, cookies)
# Fetch the id of the domain we just created so that we can use it to add children domains.
parent_domain_id = parent_config_data['domainDetail'][0]['id']
# Create an empty child domain under "Cisco IOT".
domain_name = 'APNs'
child_config_data = {"domainDetail": [{
                                      "domainName": domain_name,
                                      "id": "-1",
                                      "parentID": parent_domain_id}]}
# Write the config_data to a JSON configuration file.
write_config_to_json(config_type, 'Null', domain_name, 'Null', 'Null', 'Null', 'Null', child_config_data)
# Create a child domain.
create_domain(ng1_host, domain_name, headers, cookies)
parent_config_data = get_domain_detail(ng1_host, domain_name, headers, cookies)
# Fetch the id of the domain we just created so that we can use it to add childern domains.
parent_domain_id = parent_config_data['domainDetail'][0]['id']

# Create an empty child domain under "APNs".
domain_name = 'Connected Cars'
child_config_data = {"domainDetail": [{
                                      "domainName": domain_name,
                                      "id": "-1",
                                      "parentID": parent_domain_id}]}
# Write the config_data to a JSON configuration file.
write_config_to_json(config_type, 'Null', domain_name, 'Null', 'Null', 'Null', 'Null', child_config_data)
# Create a child domain.
create_domain(ng1_host, domain_name, headers, cookies)
parent_config_data = get_domain_detail(ng1_host, domain_name, headers, cookies)
# Fetch the id of the domain we just created so that we can use it to add childern domains.
parent_domain_id = parent_config_data['domainDetail'][0]['id']

# Create a child domain that has the name of the user entered vehicle manufacturer.
domain_name = car_co
child_config_data = {"domainDetail": [{
                                      "domainName": domain_name,
                                      "id": "-1",
                                      "parentID": parent_domain_id}]}
# Write the config_data to a JSON configuration file.
write_config_to_json(config_type, 'Null', domain_name, 'Null', 'Null', 'Null', 'Null', child_config_data)
# Create a child domain
create_domain(ng1_host, domain_name, headers, cookies)
parent_config_data = get_domain_detail(ng1_host, domain_name, headers, cookies)
# Fetch the id of the domain we just created so that we can use it to add childern domains.
parent_domain_id = parent_config_data['domainDetail'][0]['id']

# Create a child domain under the vehicle manufacturer domain.
domain_name = 'Control'
child_config_data = {"domainDetail": [{
                                      "domainName": domain_name,
                                      "id": "-1",
                                      "parentID": parent_domain_id}]}
# Write the config_data to a JSON configuration file.
write_config_to_json(config_type, 'Null', domain_name, 'Null', 'Null', 'Null', 'Null', child_config_data)
# Create a child domain
create_domain(ng1_host, domain_name, headers, cookies)
parent_config_data = get_domain_detail(ng1_host, domain_name, headers, cookies)
# Fetch the id of the domain we just created so that we can use it to add childern domains.
control_domain_id = parent_config_data['domainDetail'][0]['id']

# Create a child domain under the vehicle manufacturer domain.
domain_name = 'User'
child_config_data = {"domainDetail": [{
                                      "domainName": domain_name,
                                      "id": "-1",
                                      "parentID": parent_domain_id}]}
# Write the config_data to a JSON configuration file.
write_config_to_json(config_type, 'Null', domain_name, 'Null', 'Null', 'Null', 'Null', child_config_data)
# Create a child domain
create_domain(ng1_host, domain_name, headers, cookies)

# Create a child domain under the vehicle manufacturer domain.
domain_name = 'DNS'
child_config_data = {"domainDetail": [{
                                      "domainName": domain_name,
                                      "id": "-1",
                                      "parentID": parent_domain_id}]}
# Write the config_data to a JSON configuration file.
write_config_to_json(config_type, 'Null', domain_name, 'Null', 'Null', 'Null', 'Null', child_config_data)
# Create a child domain.
create_domain(ng1_host, domain_name, headers, cookies)

# Create three domains under the parent domain "Control". These domains will have members.
# Interate through the list of network services as there will be a child domain for each one.
for network_service in network_service_list:
    domain_name = network_service
    domain_member_ids = []
    # Iterate through the list of app services as there will be a domainMember for each one.
    for app_serv in app_service_list:
        application_service_name = 'App Service ' + app_serv + ' ' + network_service
        # Create a list of app service ids as we will need to include them in the domainMember definitions.
        domain_member_ids.append(app_service_ids[application_service_name])
    # Specify the domain configuration data that includes domainMembers.
    child_config_data = {'domainDetail': [{'domainMembers': [{'id': domain_member_ids[0],
                                          'serviceDefMonitorType': 'ADM_MONITOR_ENT_ADM',
                                          'serviceName': 'App Service ' + app_service_list[0] + ' ' + network_service,
                                          'serviceType': 1},
                                         {'id': domain_member_ids[1],
                                          'serviceDefMonitorType': 'ADM_MONITOR_ENT_ADM',
                                          'serviceName': 'App Service ' + app_service_list[1] + ' ' + network_service,
                                          'serviceType': 1},
                                         {'id': domain_member_ids[2],
                                          'serviceDefMonitorType': 'ADM_MONITOR_ENT_ADM',
                                          'serviceName': 'App Service ' + app_service_list[2] + ' ' + network_service,
                                          'serviceType': 1}],
                       'domainName': domain_name,
                       'id': -1,
                       'parentID': control_domain_id}]}
    # Write the config_data to a JSON configuration file.
    write_config_to_json(config_type, 'Null', domain_name, 'Null', 'Null', 'Null', 'Null', child_config_data)
    # Create a child domain.
    create_domain(ng1_host, domain_name, headers, cookies)

#FOR TESTING: Delete everything
#domain_name = 'Cisco IOT'
#delete_domain(ng1_host, domain_name, headers, cookies)

# Get info on all services; application, network or both. Returned as a python object.
# config_data = get_services(ng1_host, service_type, headers, cookies)
# pprint.pprint(config_data)

# services_list = config_data['service']
# pprint.pprint(services_list)

# Get info on a specific service, returned as a python object
# config_data = get_service_detail(ng1_host, service_name, headers, cookies)
# pprint.pprint(config_data)

# Put an update to a specific service
# update_service(ng1_host, service_name, service_type, me_name, protocol_or_group_code, attribute, attribute_value, headers, cookies)

# Delete a specific service
# delete_service(ng1_host, service_name, headers, cookies)

# Create a specific service
# create_service(ng1_host, service_type, service_name, headers, cookies)

# Get all applications
# config_data = get_applications(ng1_host, headers, cookies)
# pprint.pprint(config_data)

# Get info on a specific application
#config_data = get_app_detail(ng1_host, app_name, headers, cookies)
#if config_data != False:
    #pprint.pprint(config_data)

# Put an update to a specific application
# update_app(ng1_host, app_name, attribute, attribute_value, headers, cookies)

# Activate a specific application
# activate_app(ng1_host, app_name, headers, cookies)

# Dectivate a specific application
# deactivate_app(ng1_host, app_name, headers, cookies)

# Delete a specific app
# delete_app(ng1_host, app_name, headers, cookies)

# Create a specific app
# create_app(ng1_host, app_name, headers, cookies)

# Set all APN locations based on a filename
# set_apns(ng1_host, headers, cookies)

# Get info on all APN locations
# get_apns(ng1_host, headers, cookies)

# Get info on a specific APN location
# get_apn_detail(ng1_host, headers, cookies, apn_name)

# Read the JSON configuration file and create a JSON object we can parse
# If you are reading multiple services, devices, etc. then the service_name, device_name
# interface_id, location_name you pass in should be "Null"
# config_data = read_config_from_json(config_type, service_type, service_name, app_name, device_name, interface_id, location_name)
# print(config_data)
#
# config_data = read_config_from_json(config_type, service_type, 'Null', app_name, 'Null', 'Null', 'Null')
# pprint.pprint(config_data)

# Write the config_data to a JSON configuration file
# If you are writing out multiple services, devices, etc., then the service_name, device_name
# interface_id, location_name you pass in should be "Null"
# write_config_to_json(config_type, service_type, service_name, app_name, device_name, interface_id, location_name, config_data)
# write_config_to_json(config_type, 'Null', 'Null', app_name, 'Null', 'Null', 'Null', config_data)

# Take the data read from the API and write it out to a local CSV file
# write_config_to_csv(service_name, config_data)

# devices_list, selection = device_menu(ng1_host, headers, cookies)
# If the user selected "All Devices" then we need to iterate over the list and produce mulitple CSV files
#if selection == -1:
#    for device in devices_list:
#        device_name = device['deviceName']
#        # For each device, get the list of sorted VLAN locations for all interfaces
#        filtered_all_interface_locations = get_devices_interfaces_vlans_sorted(ng1_host, device_name, headers, cookies)
#        #Take the combined locations list for a device and save it to CSV
#        write_device_interfaces_locations_config_to_csv(device_name, filtered_all_interface_locations)
## Else the user has selected one of the devices and we will use 'selection' to get the device_name from the list
#else:
#    device_name = devices_list[selection]['deviceName']
#    filtered_all_interface_locations = get_devices_interfaces_vlans_sorted(ng1_host, device_name, headers, cookies)
#    # Take the combined locations list for a device and save it to CSV
#    write_device_interfaces_locations_config_to_csv(device_name, filtered_all_interface_locations)

close_session(ng1_host, headers, cookies)
