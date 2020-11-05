import requests
import json
import socket
import pprint
import sys
import os
import csv
import time
import string
import re
from collections import defaultdict
from datetime import date, datetime
from cryptography.fernet import Fernet
import logging

# disable the warnings for ignoring Self Signed Certificates
requests.packages.urllib3.disable_warnings()

def extend_customer_profile(ng1_host, headers, cookies, profile, device_list):
    # This function takes in the user entered profile and the device_list.
    # It will use the datacenters entered by the user to filter the device list.
    # Then it will get all the interfaces (gateways) for each device belonging to those datacenters.
    # Then it will put all those gateway names in a list.
    # Then it will extend the current customer profile to include the list of gateways for each APN.
    # If Successful, it will return the extended profile as a dictionary to be appended to the customer...
    # json file.
    gateways = []
    extended_profile = {'name': profile['cust_name'], 'type': profile['customer_type'], 'APNs': [{}]}
    for datacenter in profile['dc_list']:
        for device_name in device_list:
            if datacenter[:2].upper() == device_name[:2].upper():
                interfaces_data = get_device_interfaces(ng1_host, headers, cookies, device_name)
                for interface in interfaces_data['interfaceConfigurations']:
                    interface_name = interface['interfaceName']
                    gateways.append(interface_name)
                    for apn_name in profile['apn_list']:
                        extended_profile['APNs'][0][apn_name] = gateways

    print(f'Extended profile is: {extended_profile}')
    exit()
    return True


def validate_apns_to_gateways(ng1_host, headers, cookies, profile, device_list):
    # This function takes in the user entered profile and the device_list.
    # It will use the datacenters entered by the user to filter the device list.
    # Then it will get all the interfaces (gateways) for each device belonging to those datacenters.
    # Then it will check each interface to make sure that the user entered APNs have been associated to them.
    for datacenter in profile['dc_list']:
        for device_name in device_list:
            if datacenter[:2].upper() == device_name[:2].upper():
                interfaces_data = get_device_interfaces(ng1_host, headers, cookies, device_name)
                for interface in interfaces_data['interfaceConfigurations']:
                    interface_number = str(interface['interfaceNumber'])
                    apn_data = get_apns_on_an_interface(ng1_host, headers, cookies, device_name, interface_number)
                    for apn_name in profile['apn_list']:
                        if apn_name not in apn_data['apnAssociations']:
                            print(f'APN Name: {apn_name} is not yet associated to Device: {device_name} Interface: {interface_number}')
                            print('Please associate the APN to the interface and run this program again. Exiting...')
                            exit()

    return True

def check_splcharacter(test, no_comma):
    # Function checks if the input string(test) contains any special character or not.
    # Some entries allow for a comma, but some such as customer name do not.
    # For enteries that do not allow commas, pass in no_comma set to True, otherwise set to False.
    if no_comma == True:
        for char in test:
            if char in "[@,!#$%^&*()<>?/\|}{~:]'":
                print("Entry cannot contain special characters: [@,!#$%^&*()<>?/\|}{~:]")
                return True
    else:
        for char in test:
            if char in "[@!#$%^&*()<>?/\|}{~:]'":
                print("Entry cannot contain special characters: [@!#$%^&*()<>?/\|}{~:]")
                return True

    return False

def domain_exists(domain_name, domain_tree_data):
    for domain in domain_tree_data['domain']:
        if domain_name == domain['serviceName']: # if True, the domain already exists, skip creating it
            skip = True
            print(f'[INFO] Domain: {domain_name} already exists, skipping')
            # Set the id for this existing domain as the parent_domain_id for the next domain child to use.
            parent_domain_id = domain['id']
            return skip, parent_domain_id
        else:
            skip = False

    parent_domain_id = ''
    return skip, parent_domain_id

def translate_dc_name_to_acronym(datacenter_name):
    # Translate the datacenter name into the 3 letter acronym that we need to match up to the app service name.
    if datacenter_name.startswith('Atl'):
        dc_acronym = 'ATL'
    elif datacenter_name.startswith('Pho'):
        dc_acronym = 'PHX'
    elif datacenter_name.startswith('San'):
        dc_acronym = 'SJC'
    elif datacenter_name.startswith('Tor'):
        dc_acronym = 'TOR'
    elif datacenter_name.startswith('Van'):
        dc_acronym = 'VAN'
    else:
        print('[Error] Unable to match datacenter name to its 3 letter acronym')
        return False
    return dc_acronym

def create_gateway_net_services(ng1_host, headers, cookies, network_service_name, apn_ids, apn_name, device_list, dc_acronym, net_service_ids):
    # Now create a network service for each interface (gateway) on each datacenter that the user specified.
    # The network service name is in the form of {datacenter_abbreviation}-NWS-{apn_name}-{gateway}.
    # The translation of interface name to gateway name is hardcoded here.
    # Perhaps in the future we can read a master file that has all the interface to gateway mapping
    for device in device_list:
        for device_interface in device_list[device][1]:
            if device.startswith(dc_acronym):
                gateway = device_interface['interfaceName']
                network_service_name = dc_acronym + '-NWS-' + apn_name + '-' + gateway

                # Initialize the dictionay that we will use to build up our network service definition.
                net_srv_config_data = {'serviceDetail': [{'alertProfileID': 2,
                'exclusionListID': -1,
                'id': -1,
                'isAlarmEnabled': False,
                'serviceName': network_service_name,
                'serviceType': 6}]}

                # Create a network service definition for each apn for each interface for each datacenter selected
                # This means that for each datacenter specified, we should have a list of network services for each...
                # interface on that datacenter ISNG device. Each network service is the combination of a single device...
                # interface and the APN location.
                net_srv_config_data['serviceDetail'][0]['serviceMembers'] = []

                net_srv_config_data['serviceDetail'][0]['serviceMembers'].append({'enableAlert': False,
                'interfaceNumber': device_interface['interfaceNumber'],
                'ipAddress': device_list[device][0],
                'locationKeyInfo': [{'asi1xType': '',
                'isLocationKey': True,
                'keyAttr': apn_ids[apn_name],
                'keyType': 4}],
                'meAlias': device_interface['alias'],
                'meName': device_interface['interfaceName']})

                # Create the new network service.
                create_service(ng1_host, headers, cookies, 'Null', network_service_name, net_srv_config_data, False)
                # We need to know the id number that was assigned to this new network service, so we get_service_detail on it.
                net_srv_config_data = get_service_detail(ng1_host, network_service_name, headers, cookies)
                net_srv_id = net_srv_config_data['serviceDetail'][0]['id']
                # Add this network service id to our dictionary so we can use it later to assign domain members.
                net_service_ids[network_service_name] = net_srv_id

    return net_service_ids


def create_all_ggsns_net_service(ng1_host, headers, cookies, network_service_name, apn_ids, apn_name, device_list, dc_acronym):
    # Initialize the dictionay that we will use to build up our network service definition.
    net_srv_config_data = {'serviceDetail': [{'alertProfileID': 2,
    'exclusionListID': -1,
    'id': -1,
    'isAlarmEnabled': False,
    'serviceName': network_service_name,
    'serviceType': 6}]}
    # Initialize an empty service members list to put all the interfaces in
    net_srv_config_data['serviceDetail'][0]['serviceMembers'] = []
    for device in device_list:
        # Find all the devices that exist in this datacenter
        if device.startswith(dc_acronym):
            for device_interface in device_list[device][1]:
                net_srv_config_data['serviceDetail'][0]['serviceMembers'].append({'enableAlert': False,
                'interfaceNumber': device_interface['interfaceNumber'],
                'ipAddress': device_list[device][0],
                'locationKeyInfo': [{'asi1xType': '',
                'isLocationKey': True,
                'keyAttr': apn_ids[apn_name],
                'keyType': 4}],
                'meAlias': device_interface['alias'],
                'meName': device_interface['interfaceName']})
    # Create the new network service.
    create_service(ng1_host, headers, cookies, 'Null', network_service_name, net_srv_config_data, False)
    # We need to know the id number that was assigned to this new network service, so we get_service_detail on it.
    net_srv_config_data = get_service_detail(ng1_host, network_service_name, headers, cookies)
    net_srv_id = net_srv_config_data['serviceDetail'][0]['id']
    return net_srv_id


def customer_menu(ng1_host, headers, cookies, apn_list, datacenter_list, customer_list, device_list):
    # This function is an entry menu for entering new customer information.
    # It takes in a customer name, a list of APNs, the customer type and a list of valid datacenters.
    # It returns the user's entries as a profile dictionary.
    # Return False if the user messes up and wants to start over

    # Create an empty dictionary that will hold our customer menu entries.
    profile = {}
    # Create an empty list that will contain one or more APN entries.
    apn_entry_list = []
    # Initialize a variable to capture a user's yes or no reponse.
    user_entry = ''
    print('\nThis program takes input for customer attributes and creates a full configuration in nG1 to match')
    print("To cancel any changes, please type 'exit'")

    print("\nCustomers already input are: ")
    print(sorted(customer_list), '\n')

    # User enters the customer name.
    while True:
        user_entry = input("Please enter the new Customer Name: ")
        if user_entry in customer_list:
            print(f"Customer: {user_entry} already exists")
            print("Please enter a customer that is not already in the list")
            continue
        elif check_splcharacter(user_entry, True) == True:
            continue
        else:
            break

    if user_entry == '':
        profile['cust_name'] = 'Giles'
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
    while True:
        user_entry = input("Please enter one or more APNs from the list separated by comma: ")
        if check_splcharacter(user_entry, False) == True:
            continue
        else:
            break
    if user_entry == '':
        # For testing, allow the user to just hit enter
        apn_entry_list.append('Onstar01')
        apn_entry_list.append('Onstar02')
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
            print(f"APN: {apn_entry} does not yet exist")
            print(f"Please create APN: {apn_entry} first and then run this program again")
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
            profile['customer_type'] = 'Connected Car'
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
    while True:
        # User enters one or more Datacenters.
        user_entry = input("Please enter one or more Datacenters from the list separated by comma: ")
        if check_splcharacter(user_entry, False) == True:
            continue
        else:
            break
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
            print(f"[Error] Datacenter: {dc_entry} does not yet exist")
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
    elif config_type == 'get_datacenters' or config_type == 'get_customers':
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

def get_app_detail(ng1_host, headers, cookies, app_name):
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
    app_data = get_app_detail(ng1_host, headers, cookies, app_name)
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
    app_data = get_app_detail(ng1_host, headers, cookies, app_name)
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
    app_data = get_app_detail(ng1_host, headers, cookies, app_name)
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

def get_apns_on_an_interface(ng1_host, headers, cookies, device_name, interface_number):
    uri = "/ng1api/ncm/devices/"
    url = "https://" + ng1_host + uri + device_name + "/interfaces/" + interface_number + "/associateapns"

    # perform the HTTPS API call to get the APN detail information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print(f"[INFO] get_apns_on_an_interface for device: {device_name} interface number: {interface_number} Successful")

        # return the json object that contains the APN detail information
        return get.json()

    else:
        print(f"[FAIL] get_apns_on_an_interface for device: {device_name} interface number: {interface_number} Failed")
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

def build_domain_tree(ng1_host, headers, cookies, domain_name, parent_domain_id, domain_member_ids):
    # Create one layer of a domain hierarchy
    parent_config_data = {"domainDetail": [{
                                          "domainName": domain_name,
                                          "id": "-1",
                                          "parentID": parent_domain_id}]}
    # If domain members were passed in, add them as members to this domain
    if domain_member_ids != None:
        # Create an empty list of domain members that we can append to
        parent_config_data['domainDetail'][0]['domainMembers'] = []
        # Now iterate through the list of domain members passed in and add them as domain memembers
        for domain_member in domain_member_ids:
            parent_config_data['domainDetail'][0]['domainMembers'].append({'id': domain_member_ids[domain_member],
                                                  'serviceDefMonitorType': 'ADM_MONITOR_ENT_ADM',
                                                  'serviceName': domain_member,
                                                  'serviceType': 1})

    # Optionally Write the config_data to a JSON configuration file.
    #write_config_to_json(config_type, 'Null', domain_name, 'Null', 'Null', 'Null', 'Null', parent_config_data)
    # Create the parent domain.
    if create_domain(ng1_host, domain_name, headers, cookies, parent_config_data) == True:
        # Fetch the id of the domain we just created so that we can use it to add child domains.
        #parent_config_data = get_domain_detail(ng1_host, domain_name, headers, cookies)
        domain_tree_data = get_domains(ng1_host, headers, cookies)
        for domain in domain_tree_data['domain']:
            # Skip the Enterprise domain as it has no parent id number.
            if domain['serviceName'] != 'Enterprise':
                if domain['serviceName'] == domain_name and str(parent_domain_id) in str(domain['parent']):
                    #print('I found my own domain id')
                    parent_domain_id = domain['id']
    else:
        print(f'Unable to create domain: {domain_name} Exiting...')
        exit()

    return parent_domain_id

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
        if 'Not found domain' in get.text: # Don't print fail if the domain does not yet exist
            print(f'[INFO] Domain {domain_name} does not yet exist')
        else:
            print('[FAIL] get_domain_detail for', domain_name, 'Failed')
            print('URL:', url)
            print('Response Code:', get.status_code)
            print('Response Body:', get.text)

        return False

def create_domain(ng1_host, domain_name, headers, cookies, parent_config_data):
    # Create a new dashboard domain using parent_config_data that contain all the attributes.
    service_uri = "/ng1api/ncm/domains/"
    url = "https://" + ng1_host + service_uri
    # use json.dumps to provide a serialized json object (a string actually).
    # This json_string will become our new configuration for this domain_name.
    json_string = json.dumps(parent_config_data)
    # print('New domain data =')
    # print(json_string)

    # perform the HTTPS API Post call with the serialized json object service_data
    # this will create the domain configuration in nG1 for this domain_name)
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

def create_service(ng1_host, headers, cookies, service_type, service_name, config_data, save):
    # Create a new service using the config_data attributes passed into the function.
    # Optionally write a copy of the config to a json file

    # Set the config_type to create_service in case we are saving this to a json file
    config_type = 'create_service'

    service_uri = "/ng1api/ncm/services/"

    url = "https://" + ng1_host + service_uri

    # if the save option is True, then save a copy of this configuration to a json file
    if save == True:
        write_config_to_json(config_type, 'Null', service_name, 'Null', 'Null', 'Null', 'Null', config_data)
    # use json.dumps to provide a serialized json object (a string actually)
    # this json_string will become our new configuration for this service_name
    json_string = json.dumps(config_data)
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

def get_device_interfaces(ng1_host, headers, cookies, device_name):
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

def get_device_interface(ng1_host, headers, cookies, device_name, interface_id):
    device_uri = "/ng1api/ncm/devices/" + device_name + "/interfaces/" + interface_id
    url = "https://" + ng1_host + device_uri
    #params = interface_id
    # perform the HTTPS API call to get the device information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

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
    interfaces_data = get_device_interfaces(ng1_host, headers, cookies, device_name)
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

# Create the logging function.
# Use this option to log to stdout and stderr using systemd. You must also import os.
#logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
# Use this option to log to a file in the same directory as the .py python program is running
logging.basicConfig(filename="ng1_add_cisco_iot_customer.log", format='%(asctime)s %(message)s', filemode='a+')
# Creating a logger object.
logger = logging.getLogger()
# Set the logging level to the lowest setting so that all logging messages get logged.
logger.setLevel(logging.INFO) # Allowable options include INFO, WARNING, ERROR, and CRITICAL.
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

# This ng1 host IP address is for San Jose lab nG1.
# ng1_host = "10.8.8.3"
# This ng1 host IP address is for the F5 lab nG1.
# ng1_host = "54.185.154.36"

# You can use your username and password (plain text) in the authorization header (basic authentication).
# In this case cookies must be set to 'Null'.
# If you are using the authentication Token, then credentials = 'Null'.
# credentials = 'jgiles', 'netscout1'.
# cookies = 'Null'.

# You can use an authentication token named NSSESSIONID obtained from the User Management module in nGeniusONE (open the user and click Generate New Key).
# If we are using the token rather than credentials, we will set credentials to 'Null'.
if use_token == True:
    credentials = 'Null'

    cookies = {
        'NSSESSIONID': ng1token_pl, # In this case we will use the token read from the cred_filename file.
        }
        # This user token is for jgiles user on the San Jose Lab nG1.
        #cookies = {
        #    'NSSESSIONID': 'cqDYQ7FFMtuonYyFHmBztqVtSIcM4S+jzV6iOyNwBwD/vCu88+gYTjuBvFDGUzPcwcNnhRv8GMNR5PSSYJb1JhQTpQi8VYdsb0Kw7ow1J5c=',
        #}
# Otherwise set the credentials to username:password and use that instead of an API token.
else:
    cookies = 'Null'
    credentials = ng1username + ':' + ng1password_pl

# set ng1_host to what was read out of the credentials .ini file.
# ng1_host = ng1destination + ':' + ng1destPort.
ng1_host = ng1destination

# specify the headers to use in the API calls.
headers = {
    'Cache-Control': "no-cache",
    'Accept': "application/json",
    'Content-Type': "application/json"
}

# To use username and password, pass in your credentials and set cookies = 'Null'.
# To use a token, pass in your cookies and set credentials = 'Null'.
# print ('cookies = ', cookies, ' and credentials = ', credentials)
#
cookies = open_session(ng1_host, headers, cookies, credentials)

# next three lines for TESTING only.
#config_data = get_service_detail(ng1_host, 'test4', headers, cookies)
#pprint.pprint(config_data)
#exit()

# Initialize an empty datacenter list that we will use later to verify user input.
datacenter_list = []
# Initialize an empty device list that we will use later to hold their ip adresses, dict of interfaces...
# and each interface (gateway) has a list of APNs associated to it
device_list = defaultdict(list)

filename = 'CiscoIOT-DataCenters' # The name of the master datacenter to gateways mapping json file.

# Get info on all datacenters
datacenter_configs, config_filename = read_config_from_json('get_datacenters', 'Null', filename, 'Null', 'Null', 'Null', 'Null')
if datacenter_configs != False: # The mapping file was not empty
    # Fetch the devices that exist in the system
    devices_data = get_devices(ng1_host, headers, cookies)
    # For every device in the system, fetch the IP address and list of interfaces.
    # We will need to pull from this dictionary later to create services.
    # Loop through each device and add it to our dictionary
    for device in devices_data['deviceConfigurations']:
        #pprint.pprint(f'Device is {device}')
        device_name = device['deviceName']
        # We need the ip address of each device to fill in the network service members later.
        device_list[device_name].append({'deviceIPAddress': device['deviceIPAddress']})
        # Each device will have a list of interfaces, so initialize that empty list.
        device_list[device_name].append({'interfaces': []})
        # Get all the info for all the interfaces on this device.
        device_interfaces = get_device_interfaces(ng1_host, headers, cookies, device_name)
        if device_interfaces == False: # Failed to get device interfaces.
            print(f'[CRITICAL] Unable to fetch interfaces from {device_name}. Exiting....')
            exit()
        else: # get device interfaces was successful.
            # Pull out the interface list from the device_interfaces data.
            device_interfaces = device_interfaces['interfaceConfigurations']
            # Initialize a counter for appending APNs to the correct interface in our dictionary.
            interface_count = 0
        # Loop through each interface and append its attributes to our dictionary.
        for device_interface in device_interfaces:
            interface_name = device_interface['interfaceName']
            # Initialize the list that will contain the interfaces of this device.
            device_list[device_name][1]['interfaces'].append({interface_name: []})
            # Initialize the list that will contain the APNs for each interface.
            device_list[device_name][1]['interfaces'][interface_count][interface_name].append({'APNs': []})
            interface_number = str(device_interface['interfaceNumber'])
            # Fetch all the APNs associated to this interface.
            apn_data = get_apns_on_an_interface(ng1_host, headers, cookies, device_name, interface_number)
            if apn_data == {}: # There are no APNs associated to this interface.
                print(f'[INFO] There are no APNs associated to interface {interface_number} on Device {device_name}')
            else: # There is one or more APNs associated to this interface.
                for apn in apn_data['apnAssociations']:
                    # Add the APN to the interface attributes in our dictionay.
                    device_list[device_name][1]['interfaces'][interface_count][interface_name][0]['APNs'].append(apn)
            # Increment the interface count for the next loop in case there is more than one.
            interface_count += 1

    # Build the list of available datacenters for the user to select from in customer_menu.
    for datacenter in datacenter_configs["Data Centers"]:
        datacenter_name = datacenter["name"]
        datacenter_list.append(datacenter_name)

else: # The mapping file was empty or there was some other exception in reading the data in.
    print('[CRITICAL] Unable to fetch Datacenters from CiscoIOT-DataCenters.json file. Exiting....')
    exit()

# Initialize an empty customer list that we will use later to verify user input.
customer_list = []
filename = 'CiscoIOT-Customers' # The name of the master datacenter to gateways mapping json file.

# Get info on all existing customers
customer_configs, config_filename = read_config_from_json('get_customers', 'Null', filename, 'Null', 'Null', 'Null', 'Null')
if customer_configs != False: # The mapping file was not empty.
    # Build up a list of all existing customers
    for customer in customer_configs["Customers"]:
        customer_name = customer["name"]
        customer_list.append(customer_name)
else: # The mapping file was empty or there was some other exception in reading the data in.
    print('Unable to fetch Customers from CiscoIOT-Customers.json file. Exiting...')
    exit()

# Initialize an empty apn list that we will use later to verify user input.
apn_list = []
# Get info on all APN locations system-wide.
apn_configs = get_apns(ng1_host, headers, cookies)
if apn_configs != False:
    for apn in apn_configs["apns"]:
        apn_name = apn["name"]
        apn_list.append(apn_name)
else:
    print('Unable to fetch APNs, exiting....')
    exit()

# Get the new customer profile from the user
while True:
    profile = customer_menu(ng1_host, headers, cookies, apn_list, datacenter_list, customer_list, device_list)
    if profile != False: # We made it through the menu Successfully.
        print(f"Profile is : {profile}") # Display the customer attributes that the user entered.
        break
    # If the user does not confirm the new customer profile, let them start over
    else:
        print('New customer profile discarded, starting over...')
        print('')
        continue

# Fetch the APN id number that matches with each APN in the customer profile
apn_ids = {} #Initialize an empty dictionay to hold our APN Name : APN id key-value pairs
for apn_name in profile['apn_list']:
    apn_config = get_apn_detail(ng1_host, headers, cookies, apn_name)
    if apn_config != False:
        apn_ids[apn_name] = apn_config['id']
    else:
        print('Unable to fetch APN ID number for ', apn_name)
        print('Exiting...')
        exit()

# Create a network service for each APN specified that includes all availalbe MEs.
# Start by just getting all interfaces on our vStreams.
net_service_ids = {}


print(f'Device list is: {device_list}')
exit()
#extended_profile = extend_customer_profile(ng1_host, headers, cookies, profile, device_list)

# Build the network services needed for each APN that the user specified for this new customer
for apn_name in apn_ids:
    # Create a network service for all GSSNs (All ISNG interfaces) for the datacenters that the user specified.
    # The network service name is in the form of {datacenter_abbreviation}-NWS-{apn_name}-All-GGSNs.
    # For every device in that datacenter, gather up the interfaces and add them as members to this network service.

    # For every datacenter that the user specified, create a single All-GSSNs network service.
    if 'Atlanta' in profile['dc_list']:
        network_service_name = 'ATL-NWS-' + apn_name + '-All-GGSNs'
        dc_acronym = 'ATL'
        # Create the network service and add the network service id to our dictionary...
        # so we can use it later to assign to domain members.
        net_service_ids[network_service_name] = create_all_ggsns_net_service(ng1_host, headers, cookies, network_service_name, apn_ids, apn_name, device_list, dc_acronym)
        # Now create the network services equal to each device interface (gateway) for all devices in this datacenter
        net_service_ids = create_gateway_net_services(ng1_host, headers, cookies, network_service_name, apn_ids, apn_name, device_list, dc_acronym, net_service_ids)
    elif 'ATL-NTCT-INF-01' in device_list:
        network_service_name = 'ATL-NWS-' + apn_name + '-All-GGSNs'
        dc_acronym = 'ATL'
        # Create the network service and add the network service id to our dictionary...
        # so we can use it later to assign to domain members.
        net_service_ids[network_service_name] = create_all_ggsns_net_service(ng1_host, headers, cookies, network_service_name, apn_ids, apn_name, device_list, dc_acronym)

    if 'Phoenix' in profile['dc_list']:
        network_service_name = 'PHX-NWS-' + apn_name + '-All-GGSNs'
        dc_acronym = 'PHX'
        # Create the network service and add the network service id to our dictionary...
        # so we can use it later to assign domain members.
        net_service_ids[network_service_name] = create_all_ggsns_net_service(ng1_host, headers, cookies, network_service_name, apn_ids, apn_name, device_list, dc_acronym)
        # Now create the network services equal to each device interface (gateway) for all devices in this datacenter
        net_service_ids = create_gateway_net_services(ng1_host, headers, cookies, network_service_name, apn_ids, apn_name, device_list, dc_acronym, net_service_ids)
    elif 'PHX-NTCT-INF-01' in device_list:
        network_service_name = 'PHX-NWS-' + apn_name + '-All-GGSNs'
        dc_acronym = 'PHX'
        # Create the network service and add the network service id to our dictionary...
        # so we can use it later to assign to domain members.
        net_service_ids[network_service_name] = create_all_ggsns_net_service(ng1_host, headers, cookies, network_service_name, apn_ids, apn_name, device_list, dc_acronym)

    if 'San Jose' in profile['dc_list']:
        network_service_name = 'SJC-NWS-' + apn_name + '-All-GGSNs'
        dc_acronym = 'SJC'
        # Create the network service and add the network service id to our dictionary...
        # so we can use it later to assign domain members.
        net_service_ids[network_service_name] = create_all_ggsns_net_service(ng1_host, headers, cookies, network_service_name, apn_ids, apn_name, device_list, dc_acronym)
        # Now create the network services equal to each device interface (gateway) for all devices in this datacenter
        net_service_ids = create_gateway_net_services(ng1_host, headers, cookies, network_service_name, apn_ids, apn_name, device_list, dc_acronym, net_service_ids)
    elif 'SJC-NTCT-INF-01' in device_list:
        network_service_name = 'SJC-NWS-' + apn_name + '-All-GGSNs'
        dc_acronym = 'SJC'
        # Create the network service and add the network service id to our dictionary...
        # so we can use it later to assign to domain members.
        net_service_ids[network_service_name] = create_all_ggsns_net_service(ng1_host, headers, cookies, network_service_name, apn_ids, apn_name, device_list, dc_acronym)

    if 'Toronto' in profile['dc_list']:
        network_service_name = 'TOR-NWS-' + apn_name + '-All-GGSNs'
        dc_acronym = 'TOR'
        # Create the network service and add the network service id to our dictionary...
        # so we can use it later to assign domain members.
        net_service_ids[network_service_name] = create_all_ggsns_net_service(ng1_host, headers, cookies, network_service_name, apn_ids, apn_name, device_list, dc_acronym)
        # Now create the network services equal to each device interface (gateway) for all devices in this datacenter
        net_service_ids = create_gateway_net_services(ng1_host, headers, cookies, network_service_name, apn_ids, apn_name, device_list, dc_acronym, net_service_ids)
    elif 'TOR-NTCT-INF-01' in device_list:
        network_service_name = 'TOR-NWS-' + apn_name + '-All-GGSNs'
        dc_acronym = 'TOR'
        # Create the network service and add the network service id to our dictionary...
        # so we can use it later to assign to domain members.
        net_service_ids[network_service_name] = create_all_ggsns_net_service(ng1_host, headers, cookies, network_service_name, apn_ids, apn_name, device_list, dc_acronym)

    if 'Vancouver' in profile['dc_list']:
        network_service_name = 'VAN-NWS-' + apn_name + '-All-GGSNs'
        dc_acronym = 'VAN'
        # Create the network service and add the network service id to our dictionary...
        # so we can use it later to assign domain members.
        net_service_ids[network_service_name] = create_all_ggsns_net_service(ng1_host, headers, cookies, network_service_name, apn_ids, apn_name, device_list, dc_acronym)
        # Now create the network services equal to each device interface (gateway) for all devices in this datacenter
        net_service_ids = create_gateway_net_services(ng1_host, headers, cookies, network_service_name, apn_ids, apn_name, device_list, dc_acronym, net_service_ids)
    elif 'VAN-NTCT-INF-01' in device_list:
        network_service_name = 'VAN-NWS-' + apn_name + '-All-GGSNs'
        dc_acronym = 'VAN'
        # Create the network service and add the network service id to our dictionary...
        # so we can use it later to assign to domain members.
        net_service_ids[network_service_name] = create_all_ggsns_net_service(ng1_host, headers, cookies, network_service_name, apn_ids, apn_name, device_list, dc_acronym)

# This is a list of existing applications we intend to use. Could pull this from a file.
app_list = ['GTPv0/', 'GTPv1-Create-PDP/GTP_V1C:65538', 'GTPv1-Update-PDP/GTP_V1C:65546', 'GTPv1-Delete-PDP/GTP_V1C:65539', 'GTPv2-CSR/GTP_V2C:131081',
           'GTPv2-UBR/GTP_V2C:131104', 'GTPv2-MBR/GTP_V2C:131096', 'GTPv2-DSR/GTP_V2C:131087', 'Web/', 'DNS/']
app_service_ids = {}

# Now create create the application services for GTPv0, GTPv1 and GTPv2 for each interface on each datacenter entered.
for apn_name in apn_ids:
    for app_name in app_list:
        protocol_or_group_code = app_name.partition('/')[2] # scrape off the protocol code after the '/'
        #print(f'The protocol or group code is: {protocol_or_group_code}')
        app_name = app_name.partition('/')[0] # scrape off the app name before the '/'
        for datacenter in profile['dc_list']:
            if datacenter.startswith('Atl'):
                application_service_name = 'ATL-AS-' + app_name + '-' + apn_name
            elif datacenter.startswith('Pho'):
                application_service_name = 'PHX-AS-' + app_name + '-' + apn_name
            elif datacenter.startswith('San'):
                application_service_name = 'SJC-AS-' + app_name + '-' + apn_name
            elif datacenter.startswith('Tor'):
                application_service_name = 'TOR-AS-' + app_name + '-' + apn_name
            elif datacenter.startswith('Van'):
                application_service_name = 'VAN-AS-' + app_name + '-' + apn_name

            # Initialize the dictionay that we will use to build up our application service definition.
            app_srv_config_data = {'serviceDetail': [{'alertProfileID': 2,
            'exclusionListID': -1,
            'id': -1,
            'isAlarmEnabled': False,
            'serviceName': application_service_name,
            'serviceType': 1}]}

            # Add members to the service that is each interface for each datacenter.
            app_srv_config_data['serviceDetail'][0]['serviceMembers'] = []
            # The protocol or group code for each service member is the app name limited to 10 chars.
            if app_name == 'Web':
                protocol_or_group_code = 'WEB'
                is_message_type = False
                is_protocol_group = True
                is_message_type = False
                message_id = 0
            elif app_name == 'DNS':
                protocol_or_group_code_list = ['DNS_TCP', 'A_DNS', 'DNSIX', 'UDP_MDNS', 'MS-DNS_U']
                is_message_type = False
                is_protocol_group = False
                is_message_type = False
                message_id = 0
            elif app_name == 'GTPv0':
                protocol_or_group_code = 'GTP'
                is_message_type = False
                message_id = 0
                is_protocol_group = False
            else:
                is_message_type = True
                message_id = int(protocol_or_group_code.partition(':')[2])# Scrape off the message id after the ':'.
                is_protocol_group = False
            #print('\nProtocol or group code is: ', protocol_or_group_code)

            for network_service in net_service_ids:
                # Filter down the list of network_service_ids to just the interfaces for the current datacenter...
                # loop and just those interfaces for the current APN loop. The goal is to create an app service...
                # that is specific to an APN + datacenter combination and add the related interface network...
                # services as members of this app service.
                #print(f'\nNetwork Service is: {network_service}')
                #print(f'\nNetwork Service IDs is: {net_service_ids}')
                #print(f'\nApplication Service Name is: {application_service_name}')
                if 'All-' not in network_service and apn_name in network_service and network_service.startswith(application_service_name[:2]):
                    net_srv_id = net_service_ids[network_service]
                    #print(f'\nNetwork Service is: {network_service}')
                    #print(f'\nNetwork Service ID is: {net_srv_id}')
                    #print(f'\nApplication Service Name is: {application_service_name}')
                    if app_name == 'DNS': # We need to append a service member for each type of DNS app desired.
                        for protocol_or_group_code in protocol_or_group_code_list:
                            app_srv_config_data['serviceDetail'][0]['serviceMembers'].append({'enableAlert': False,
                                                'interfaceNumber': -1,
                                                'isNetworkDomain': True,
                                                'isMessageType': is_message_type,
                                                'messageID': message_id,
                                                'isProtocolGroup': is_protocol_group,
                                                'melID': -1,
                                                'networkDomainID': net_srv_id,
                                                'networkDomainName': network_service,
                                                'protocolOrGroupCode': protocol_or_group_code})
                    else: # This is not app_name 'DNS', so we only need one service member for the other applications
                        app_srv_config_data['serviceDetail'][0]['serviceMembers'].append({'enableAlert': False,
                                            'interfaceNumber': -1,
                                            'isNetworkDomain': True,
                                            'isMessageType': is_message_type,
                                            'messageID': message_id,
                                            'isProtocolGroup': is_protocol_group,
                                            'melID': -1,
                                            'networkDomainID': net_srv_id,
                                            'networkDomainName': network_service,
                                            'protocolOrGroupCode': protocol_or_group_code})
            # Create the new application service.
            create_service(ng1_host, headers, cookies, 'Null', application_service_name, app_srv_config_data, False)
            # We need to know the id number that was assigned to this new app service, so we get_service_detail on it.
            app_srv_config_data = get_service_detail(ng1_host, application_service_name, headers, cookies)
            #print(f'\nApp service config data is: {app_srv_config_data}')
            app_srv_id = app_srv_config_data['serviceDetail'][0]['id']
            # Add this application service id to our dictionary so we can use it later to assign domain members.
            app_service_ids[application_service_name] = app_srv_id

# Fetch the existing domain tree data so that we know what domains already exist.
domain_tree_data = get_domains(ng1_host, headers, cookies)
#print(f'Domain tree is: {domain_tree_data}')
domain_name = 'Cisco IOT'

# This is a domain layer that is common to all customers. If it exists, don't overwrite it
skip, existing_parent_domain_id = domain_exists(domain_name, domain_tree_data)

if skip == False: # The domain does not yet exist, create it
    # Create the domain.
    # Initialize an empty list of domain member ids for use when we add domains that have members.
    domain_member_ids = {}
    parent_domain_id = 1 # This is the parentID of the default 'Enterprise' domain at the top.
    parent_domain_id = build_domain_tree(ng1_host, headers, cookies, domain_name, parent_domain_id, domain_member_ids)

domain_name = 'APNs'
# This is a domain layer that is common to all customers. If it exists, don't overwrite it
skip, existing_parent_domain_id = domain_exists(domain_name, domain_tree_data)
if skip == False: # The domain does not yet exist, create it
    # Create the domain.
    # Initialize an empty list of domain member ids for use when we add domains that have members.
    domain_member_ids = {}
    parent_domain_id = build_domain_tree(ng1_host, headers, cookies, domain_name, parent_domain_id, domain_member_ids)
else:
    # The domain already eists, set the parent_domain_id to the existing domain.
    parent_domain_id = existing_parent_domain_id

domain_name = profile['customer_type'] + ' APNs' # This will be either 'Connected Car' or 'IOT'.
# This is a domain layer that is common to all customers. If it exists, don't overwrite it
skip, existing_parent_domain_id = domain_exists(domain_name, domain_tree_data)
if skip == False: # The domain does not yet exist, create it
    # Create the domain.
    # Initialize an empty list of domain member ids for use when we add domains that have members.
    domain_member_ids = {}
    parent_domain_id = build_domain_tree(ng1_host, headers, cookies, domain_name, parent_domain_id, domain_member_ids)
else:
    # The domain already eists, set the parent_domain_id to the existing domain.
    parent_domain_id = existing_parent_domain_id

domain_name = profile['cust_name'] # Set the domain name to be the customer name as entered in the menu

# This is a domain layer that should be unique to one customer name. If it exists, exit out.
skip, existing_parent_domain_id = domain_exists(domain_name, domain_tree_data)

if skip == False: # The domain does not yet exist, create it
    # # Create the domain.
    # The members for this customer domain will be all of the network interfaces for each APN.
    domain_member_ids = {} # Reset the list of domain members
    # If there is only one APN, then add all datacenter interfaces for this one APN as members...
    # of the customer domain. Otherwise, these will be added to the APN named domains.
    if len(apn_ids) == 1: # There is only one user entered APN name.
        for network_service_name in net_service_ids:
            for apn_name in apn_ids:
                if apn_name + '-All-GGSNs' in network_service_name:
                    domain_member_ids[network_service_name] = net_service_ids[network_service_name]
    # Create the customer domain using the customer name entered in the menu.
    # Make it a child domain of either IOT APNs or Connected Car APNs.
    customer_parent_domain_id  = build_domain_tree(ng1_host, headers, cookies, domain_name, parent_domain_id, domain_member_ids)
else:
    # The domain already exists. This should not be the case, customer names have to be unique. Exit.
    print('The customer name entered must be unique. Exiting...')
    exit()

# If there are more than one APN entered, we need to create domains for each named APN.
for apn_name in apn_ids:
    if len(apn_ids) > 1: # There are more than one user entered APN name
        domain_name = apn_name
        domain_member_ids = {} # Reset the list of domain members
        # Add the All GGSNs network services as members to this domain, but only include those that...
        # contain the APN name in this for loop.
        for network_service_name in net_service_ids:
            if apn_name + '-All-GGSNs' in network_service_name:
                domain_member_ids[network_service_name] = net_service_ids[network_service_name]
        # Create the APN named domain including the All GGSNs network services as domain members.
        apn_parent_domain_id = build_domain_tree(ng1_host, headers, cookies, domain_name, customer_parent_domain_id, domain_member_ids)
    else: # There is only one user entered APN name.
        apn_parent_domain_id = customer_parent_domain_id

    # Create a child domain 'Control' under the customer name domain or under each APN if more than one.
    domain_member_ids = {} # Reset the list of domain members
    domain_name = 'Control'
    control_parent_domain_id = build_domain_tree(ng1_host, headers, cookies, domain_name, apn_parent_domain_id, domain_member_ids)

    # Create a child domain under 'Control' for each datacenter name that the user entered.
    for datacenter in profile['dc_list']:
        domain_name = datacenter
        domain_member_ids = {} # Reset the list of domain members
        # Build the domain for this datacenter name that will contain the GTPvx domains. Place it as a child of 'Control'.
        dc_parent_domain_id = build_domain_tree(ng1_host, headers, cookies, domain_name, control_parent_domain_id, domain_member_ids)
        dc_acronym = translate_dc_name_to_acronym(datacenter)

        #Add the GTPvx domains including the associated application services.
        # These domains will have members, so we will build up a list to pass to build_domain_tree.
        domain_member_ids = {} # Reset the list of domain members
        # Look for any application service name that includes both the GTP app name, the APN name and the datacenter acronym.
        for application_service_name in app_service_ids:
            if 'GTPv0' in application_service_name and dc_acronym in application_service_name and apn_name in application_service_name:
                domain_member_ids[application_service_name] = app_service_ids[application_service_name]

        domain_name = 'GTPv0' # Hardcoding the domain name based on the same list of apps for all customers.
        parent_domain_id = build_domain_tree(ng1_host, headers, cookies, domain_name, dc_parent_domain_id, domain_member_ids)

        domain_member_ids = {} # Reset the list of members.
        # Look for any application service name that includes both the GTP app name, the APN name and the datacenter acronym.
        for application_service_name in app_service_ids:
            if 'GTPv1' in application_service_name and dc_acronym in application_service_name and apn_name in application_service_name:
                domain_member_ids[application_service_name] = app_service_ids[application_service_name]

        domain_name = 'GTPv1' # Hardcoding the domain name based on the same list of apps for all customers.
        parent_domain_id = build_domain_tree(ng1_host, headers, cookies, domain_name, dc_parent_domain_id, domain_member_ids)

        domain_member_ids = {} # Reset the list of members.
        # Look for any application service name that includes both the GTP app name, the APN name and the datacenter acronym.
        for application_service_name in app_service_ids:
            if 'GTPv2' in application_service_name and dc_acronym in application_service_name and apn_name in application_service_name:
                domain_member_ids[application_service_name] = app_service_ids[application_service_name]

        domain_name = 'GTPv2' # Hardcoding the domain name based on the same list of apps for all customers.
        parent_domain_id = build_domain_tree(ng1_host, headers, cookies, domain_name, dc_parent_domain_id, domain_member_ids)

    domain_member_ids = {} # Reset the list of members
    for datacenter in profile['dc_list']:
        dc_acronym = translate_dc_name_to_acronym(datacenter)
        # Add the User domain as a child to the customer domain if only one APN.
        # If more than one APN, the User domain is a child to each APN named domain.

        # Look for any application service name that includes both the Web app name, the APN name and the datacenter acronym.
        for application_service_name in app_service_ids:
            if 'Web' in application_service_name and dc_acronym in application_service_name and apn_name in application_service_name:
                domain_member_ids[application_service_name] = app_service_ids[application_service_name]

    domain_name = 'User' # Hardcoding the domain name based on the same list of Control, User and DNS for all customers.
    user_parent_domain_id = build_domain_tree(ng1_host, headers, cookies, domain_name, apn_parent_domain_id, domain_member_ids)

    domain_member_ids = {} # Reset the list of members
    for datacenter in profile['dc_list']:
        dc_acronym = translate_dc_name_to_acronym(datacenter)
        # Add the DNS domain as a child to the customer domain if only one APN.
        # If more than one APN, the User domain is a child to each APN named domain.

        # Look for any application service name that includes both the DNS app name, the APN name and the datacenter acronym.
        for application_service_name in app_service_ids:
            if 'DNS' in application_service_name and dc_acronym in application_service_name and apn_name in application_service_name:
                domain_member_ids[application_service_name] = app_service_ids[application_service_name]

    domain_name = 'DNS' # Hardcoding the domain name based on the same list of Control, User and DNS for all customers.
    dns_parent_domain_id = build_domain_tree(ng1_host, headers, cookies, domain_name, apn_parent_domain_id, domain_member_ids)

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
# create_service(ng1_host, headers, cookies, service_type, service_name, config_data, save)

# Get all applications
# config_data = get_applications(ng1_host, headers, cookies)
# pprint.pprint(config_data)

# Get info on a specific application
#config_data = get_app_detail(ng1_host, headers, cookies, app_name)
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
# Put a modification to a specific device
# update_device(ng1_host, device_name, headers, cookies)

# Get info on all devices, returned as a python object
# devices_data = get_devices(ng1_host, headers, cookies)
# pprint.pprint(devices_data)

# Get info on a specific device, returned as a python object
# device_data = get_device(ng1_host, device_name, headers, cookies)
# pprint.pprint(device_data)

# Get info on all the interface on a specific Device
# interfaces_data = get_device_interfaces(ng1_host, headers, cookies, device_name)
# pprint.pprint(interfaces_data)

# interface_data = get_device_interface(ng1_host, headers, cookies, device_name, interface_id)
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


close_session(ng1_host, headers, cookies)
