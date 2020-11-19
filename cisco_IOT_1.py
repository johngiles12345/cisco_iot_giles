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

def build_apn_ids_dict(profile):
    apn_ids = {} #Initialize an empty dictionary to hold our APN Name : APN id key-value pairs.
    for apn in profile['APNs'][0]['APN']:
        apn_name = apn['name']
        apn_config = get_apn_detail(ng1_host, headers, cookies, apn_name)
        if apn_config != False:
            apn_ids[apn_name] = apn_config['id']
        else:
            print(f'[CRITICAL] Unable to fetch APN ID number for {apn_name}. Exiting...')
            exit()
    return apn_ids

def get_customer_apps_from_file(app_list_filename):
    # Get info on all customer applications by reading from the current customers json file.
    if os.path.isfile(app_list_filename):
        app_configs = read_config_from_json(app_list_filename)
        if app_configs != False: # The app json file was not empty.
            return app_configs
        else: # The application json file was empty or there was some other exception in reading the data in.
            print(f'[CRITICAL] Unable to fetch Applications from {app_list_filename} file. Exiting...')
            exit()
    else:
        print(f'[CRITICAL] Application list definition file: {app_list_filename} not found. Exiting...')
        exit()

def get_existing_customers_from_file(current_customers_filename):
    # Get info on all existing customers by reading from the current customers json file.
    # Initialize an empty customer list that we will use later to verify user input.
    customer_list = []
    if os.path.isfile(current_customers_filename):
        customer_configs = read_config_from_json(current_customers_filename)
        if customer_configs != False: # The mapping file was not empty.
            # Build up a list of all existing customers
            for customer in customer_configs["Customers"]:
                customer_name = customer["name"]
                customer_list.append(customer_name)
        else: # The mapping file was empty or there was some other exception in reading the data in.
            print(f'[CRITICAL] Unable to fetch Customers from {current_customers_filename}.json file. Exiting...')
            exit()
    else:
        print(f'[INFO] Current customer definition file: {current_customers_filename} not found')
        print('[INFO] A new Customer definition file will be created')
        # Initialize an empty customer config dictionary to append our new customer data to.
        customer_configs = {"Customers": []}

    return customer_configs, customer_list


def build_device_list(current_datacenters_filename):
    # Initialize an empty device list that we will use later to hold their ip adresses, dict of interfaces...
    # and each interface (gateway) has a list of APNs associated to it
    device_list = defaultdict(list)
    datacenter_configs = read_config_from_json(current_datacenters_filename)
    if datacenter_configs != False: # The mapping file was not empty
        # Fetch the devices that exist in the system
        devices_data = get_devices(ng1_host, headers, cookies)
        # For every device in the system, fetch the IP address and list of interfaces.
        # We will need to pull from this dictionary later to create services.
        # Loop through each device and add it to our dictionary
        for device in devices_data['deviceConfigurations']:
            device_name = device['deviceName']
            device_status = device['status']
            device_type = device['deviceType']
            device_name = device['deviceName']
            if device_status == 'Active': # Only include Active devices.
                # Only include devices that are types; Infinistream, vStream or vStream Embedded.
                if device_type == 'InfiniStream' or device_type == 'vSTREAM' or device_type == 'vSTREAM Embedded':
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
                        if device_interface['status'] == 'ACT': # Only include Active interfaces.
                            interface_name = device_interface['interfaceName']
                            # Initialize the list that will contain the interfaces of this device.
                            device_list[device_name][1]['interfaces'].append({interface_name: []})
                            # Initialize the list that will contain the APNs for each interface.
                            device_list[device_name][1]['interfaces'][interface_count][interface_name].append({'APNs': []})
                            interface_number = str(device_interface['interfaceNumber'])
                            # Add the interface number to the device_list to use later when creating network services.
                            device_list[device_name][1]['interfaces'][interface_count][interface_name][0]['interfaceNumber'] = interface_number
                            interface_alias = str(device_interface['alias'])
                            # Add the interface alias to the device_list to use later when creating network services.
                            device_list[device_name][1]['interfaces'][interface_count][interface_name][0]['alias'] = interface_alias
                            # Fetch all the APNs associated to this interface.
                            apn_data = get_apns_on_an_interface(ng1_host, headers, cookies, device_name, interface_number)
                            if apn_data == {}: # There are no APNs associated to this interface.
                                print(f'[INFO] There are no APNs associated to interface {interface_number} on Device {device_name}')
                            else: # There is one or more APNs associated to this interface.
                                for apn in apn_data['apnAssociations']:
                                    # Add the APN to the interface attributes in our dictionary.
                                    device_list[device_name][1]['interfaces'][interface_count][interface_name][0]['APNs'].append(apn)
                            # Increment the interface count for the next loop in case there is more than one.
                            interface_count += 1
                else:
                    print(f'[INFO] Device: {device_name} type is: {device_type}. Skipping...')
            else:
                print(f'[INFO] Device: {device_name} status is: {device_status}. Skipping...')

        # Initialize an empty datacenter list that we will use later to verify user input.
        datacenter_list = []
        # Build the list of available datacenters for the user to select from in customer_menu.
        for datacenter in datacenter_configs["Data Centers"]:
            datacenter_name = datacenter["name"]
            datacenter_list.append(datacenter_name)
        return device_list, datacenter_list

    else: # The mapping file was empty or there was some other exception in reading the data in.
        print(f'[CRITICAL] Unable to fetch Datacenters from {current_datacenters_filename} file. Exiting....')
        exit()


def build_valid_dc_and_gateway_lists(apn_entry_list, datacenter_list, device_list):
    # Build up a list of valid datatcenters where each entered APN is associated to one or more interfaces.
    # Build up a list of valid gateways where each entered APN is associated to one or more interfaces.
    apn_loop_counter = 0
    valid_datacenters = []
    valid_gateways = []
    for apn_entry in apn_entry_list:
        valid_datacenters.append({apn_entry:[]})
        valid_gateways.append({apn_entry:[]})
        for datacenter in datacenter_list:
            for device_name in device_list:
                dc_acronym = translate_dc_name_to_acronym(datacenter) # Get the 3 letter acronym for this DC.
                if dc_acronym == device_name[:3].upper(): # Only include devices within this DC.
                    # Loop through all the interfaces for this device.
                    for interface in device_list[device_name][1]['interfaces']:
                        # Pull out just the interface dictionary values for each interface in the loop.
                        interface_values = list(interface.values())[0][0]
                        # The gateway name is really the assigned 'alias' attribute.
                        gateway = interface_values['alias']
                        # Get the list of APNs associated to this interface.
                        gateway_apns = interface_values['APNs']
                        # Check if this APN is in this list of APNs for this gateway.
                        if apn_entry in gateway_apns:
                            # We have a match, include this gateway into the list of valid gateways...
                            # for this APN. We will show them this list in the user menu later.
                            valid_gateways[apn_loop_counter][apn_entry].append(gateway)
                            # If we have not already added this datacenter to the list of valid datacenters...
                            # then add it now. We will show them this list in the user menu later.
                            if datacenter not in valid_datacenters[apn_loop_counter][apn_entry]:
                                valid_datacenters[apn_loop_counter][apn_entry].append(datacenter)
                        else:
                            apn_entry_in_gateway = False

        apn_loop_counter += 1 # Needed to walk to the next APN in the list of APN dictionaries.
    return valid_datacenters, valid_gateways

def save_cust_config_to_file(customer_configs, new_customers_filename, current_customers_filename, old_customers_filename):
    # write to a json file
    try:
        with open(config_filename,"w") as f:
            json.dump(customer_configs, f)
            print(f'[INFO] Writing customer config to JSON file:', config_filename)
    except IOError as e:
        print(f'[ERROR] Unable to write to the customer JSON config file:', config_filename)
        print("I/O error({0}): {1}".format(e.errno, e.strerror))
        return False
    except: #handle other exceptions such as attribute errors
        print(f'[ERROR] Unable to write to the customer JSON config file:', config_filename)
        print("Unexpected error:", sys.exc_info()[0])
        return False
    # if old exists read, rename and cp new to old then return ....  else rename new to old for future iterations, retun.
    if os.path.isfile(current_customers_filename):
        os.rename(current_customers_filename, old_customers_filename + '_' + str(date_time) + '.json')
        print(f"[INFO] Backing up file {current_customers_filename} to {old_customers_filename}")
        os.rename(new_customers_filename, current_customers_filename)
        print(f"[INFO] Renaming file {new_customers_filename} to {current_customers_filename}")
        #time.sleep(3)
    else:
        os.rename(new_customers_filename, current_customers_filename)
        print(f"[INFO] Renaming file {new_customers_filename} to {current_customers_filename}")
        #time.sleep(3)

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

def validate_cust_domains_exist(customer_configs, domain_tree_data):
    #customer_records_missing = []
    customer_domains_missing = []
    # Check to see if there is a domain for all the customers listed in the customer_configs dictionary.
    for customer in customer_configs['Customers']:
        customer_name = customer['name']
        # print(f'Validating customer name: {customer_name}')
        # Set the found flag to False until we find the customer in the domain tree.
        customer_found = False
        for domain in domain_tree_data['domain']:
            #print(f'domain is : {domain}')
            if customer_name == domain['serviceName']: # if True, the customer domain exits.
                customer_found = True
                # Set the id for this existing domain as the parent_domain_id for the next domain child to use.
                # parent_domain_id = domain['id']
        # If the customer was not found in the domain tree, add it to the list of missing domians.
        if customer_found == False:
            customer_domains_missing.append(customer_name)
    # Check to see if there is a record in the customer_configs dictionary for all the domains in the system.
    #for domain in domain_tree_data['domain']:
        #customer_domain = domain['serviceName']

        #print(f'Validating customer domain: {customer_domain}')
        # Set the found flag to False until we find the customer domain in the customer configs.
        #customer_found = False
        #for customer in customer_configs['Customers']:
            #customer_name = customer['name']
            #if customer_name == customer_domain: # if True, the customer config data record exits.
                #customer_found = True
                # Set the id for this existing domain as the parent_domain_id for the next domain child to use.
                # parent_domain_id = domain['id']
        # If the domain was not found in the customer config data, add it to the list of missing customer records.
        #if customer_found == False:
            #customer_records_missing.append(customer_name)

    return customer_domains_missing

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
        print('[ERROR] Unable to match datacenter name to its 3 letter acronym')
        return False
    return dc_acronym

def create_app_services(ng1_host, headers, cookies, apn_ids, app_data, net_service_ids, dc_entry_list):
    # Create create the application services the apps passed in on the app_data dictionary.
    # Create app service definitions for each APN on each valid gateway on each datacenter entered.
    # Initialize an empty dictionary to hold the app service ID numbers. Add to this dict as we create app services.
    app_service_ids = {}
    for apn_name in apn_ids: # Loop through each APN the user entered.
        for app in app_data['Applications']: # Loop through each app dictionary.
            app_name = app['name']
            if app['type'] == 'multi_member': #This is a list of app members, for example DNS.
                protocol_or_group_code_list = app['member_list'] # Get the list of apps to place as service members.

            for dc_entry in dc_entry_list: # Loop through each datacenter the user entered.
                dc_acronym = translate_dc_name_to_acronym(dc_entry)
                application_service_name = dc_acronym + '-AS-' + app_name + '-' + apn_name

                # Initialize the dictionary that we will use to build up our application service definition.
                app_srv_config_data = {'serviceDetail': [{'alertProfileID': 2,
                'exclusionListID': -1,
                'id': -1,
                'isAlarmEnabled': False,
                'serviceDefMonitorType': app['serviceDefMonitorType'],
                'serviceName': application_service_name,
                'serviceType': 1}]}

                # Add members to the service that is each valid gateway for each datacenter.
                app_srv_config_data['serviceDetail'][0]['serviceMembers'] = []
                # The protocol or group code for each service member is the app name limited to 10 chars.
                if app_name == 'Web':
                    protocol_or_group_code = 'WEB'
                    is_message_type = False
                    is_protocol_group = True
                    is_message_type = False
                    message_id = 0
                elif app_name == 'DNS':
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
                    protocol_or_group_code = app['message'] # This is a message-based app.
                    message_id = app['message'].partition(':')[2]# Scrape off the message id after the ':'.
                    is_protocol_group = False

                for network_service in net_service_ids:
                    # Filter down the list of network_service_ids to just the gateways for the current datacenter.
                    # loop and just those interfaces for the current APN loop. The goal is to create an app service...
                    # that is specific to an APN + datacenter combination and add the related interface network...
                    # services as members of this app service.
                    if 'All-' not in network_service and apn_name in network_service and network_service.startswith(application_service_name[:3]):
                        net_srv_id = net_service_ids[network_service]
                        if app['type'] == 'multi_member': # We need to append a service member for each app listed.
                            for protocol_or_group_code in protocol_or_group_code_list: # Loop through the list of apps.
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
                        else: # This is not a list of apps, so we only need one service member.
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
                create_service(ng1_host, headers, cookies, application_service_name, app_srv_config_data, False)
                # We need to know the id number that was assigned to this new app service, so we get_service_detail on it.
                app_srv_config_data = get_service_detail(ng1_host, application_service_name, headers, cookies)
                #print(f'\nApp service config data is: {app_srv_config_data}')
                app_srv_id = app_srv_config_data['serviceDetail'][0]['id']
                # Add this application service id to our dictionary so we can use it later to assign domain members.
                app_service_ids[application_service_name] = app_srv_id

    return app_service_ids

def create_gateway_net_services(ng1_host, headers, cookies, apn_ids, apn_name, device_list, profile, net_service_ids, dc_entry_list):
    # Now create a network service for each interface (gateway) that the user specified.
    # The network service name is in the form of {datacenter_abbreviation}-NWS-{apn_name}-{gateway}.
    # We will use a counter to index each APN in the customer profile.
    # The valid gateways can be different for each APN.
    apn_loop_counter = 0
    for apn_name in apn_ids: # Go through each APN that the user entered.
        # Initialize a list to hold the list of valid gateways as we loop through each APN the customer entered.
        valid_gateway_list_for_this_APN = []
        for gateway_name in profile['APNs'][0]['APN'][apn_loop_counter]['gateways'][0]['gateway']:
            valid_gateway_list_for_this_APN.append(gateway_name['name'])
        for dc_entry in dc_entry_list:
            dc_acronym = translate_dc_name_to_acronym(dc_entry)
            for device in device_list: # Go through all the available devices
                # We need to pull interface details from the device list to populate service member attributes.
                for device_interface_data in device_list[device][1]['interfaces']: # For each interface on each device.
                    for device_interface in device_interface_data:
                        # The gateway is really the interface 'alias' attribute, so pull that out of device_interface_data.
                        device_interface_gateway = device_interface_data[device_interface][0]['alias']
                        # Filter the global list of interfaces down to just those that are both associated...
                        # to the APN we are looping on and the datacenter name we are looping on.
                        # In other words, any interface in this datacenter that is also associated to this APN.
                        if device_interface_gateway in valid_gateway_list_for_this_APN and dc_acronym in device_interface_gateway:
                            interface_number = device_interface_data[device_interface][0]['interfaceNumber']
                            interface_alias = device_interface_data[device_interface][0]['alias']
                            gateway = device_interface_gateway
                            network_service_name = dc_acronym + '-NWS-' + apn_name + '-' + gateway

                            # Initialize the dictionary that we will use to build up our network service definition.
                            net_srv_config_data = {'serviceDetail': [{'alertProfileID': 2,
                            'exclusionListID': -1,
                            'id': -1,
                            'isAlarmEnabled': False,
                            'serviceName': network_service_name,
                            'serviceType': 6}]}

                            # Create a network service definition for each apn for each valid gateway selected
                            # Each network service is the combination of a single device interface and the APN location.
                            net_srv_config_data['serviceDetail'][0]['serviceMembers'] = []

                            net_srv_config_data['serviceDetail'][0]['serviceMembers'].append({'enableAlert': False,
                            'interfaceNumber': interface_number,
                            'ipAddress': device_list[device][0],
                            'locationKeyInfo': [{'asi1xType': '',
                            'isLocationKey': True,
                            'keyAttr': apn_ids[apn_name],
                            'keyType': 4}],
                            'meAlias': interface_alias,
                            'meName': device_interface})

                            # Create the new network service.
                            create_service(ng1_host, headers, cookies, network_service_name, net_srv_config_data, False)
                            # We need to know the id number that was assigned to this new network service, so we get_service_detail on it.
                            net_srv_config_data = get_service_detail(ng1_host, network_service_name, headers, cookies)
                            net_srv_id = net_srv_config_data['serviceDetail'][0]['id']
                            # Add this network service id to our dictionary so we can use it later to assign domain members.
                            net_service_ids[network_service_name] = net_srv_id
        apn_loop_counter += 1

    return net_service_ids


def create_all_ggsns_net_service(ng1_host, headers, cookies, apn_ids, device_list, profile, net_service_ids, dc_entry_list):
    # This function will build network services that include all GGSNs (interfaces) for each APN on...
    # every valid datacenter. Datacenters are validated using the gateway_list as a filter.
    # The format for naming each network service is {datacenter_abbreviation}-NWS-{apn_name}-All-GGSNs.

    # We will use a counter to index each APN in the customer profile.
    # The valid gateways can be different for each APN.
    apn_loop_counter = 0
    # Use the gateway_list to determine what are the valid datacenters
    for apn_name in apn_ids: # Go through each APN that the user entered.
        # Initialize a list to hold the list of valid gateways as we loop through each APN the customer entered.
        valid_gateway_list_for_this_APN = []
        for gateway_name in profile['APNs'][0]['APN'][apn_loop_counter]['gateways'][0]['gateway']:
            valid_gateway_list_for_this_APN.append(gateway_name['name'])

        for dc_entry in dc_entry_list:
            dc_acronym = translate_dc_name_to_acronym(dc_entry)
            network_service_name = dc_acronym + '-NWS-' + apn_name + '-All-GGSNs'

            # Initialize the dictionary that we will use to build up our network service definition.
            net_srv_config_data = {'serviceDetail': [{'alertProfileID': 2,
            'exclusionListID': -1,
            'id': -1,
            'isAlarmEnabled': False,
            'serviceName': network_service_name,
            'serviceType': 6}]}
            # Initialize an empty service members list to put all the gateways (interfaces) in.
            net_srv_config_data['serviceDetail'][0]['serviceMembers'] = []
            # Add service members to the All-GGSNs service definition.
            for device in device_list:
                # We need to pull interface details from the device list to populate service member attributes.
                for device_interface_data in device_list[device][1]['interfaces']: # For each interface on each device.
                    for device_interface in device_interface_data:
                        # The gateway is really the interface 'alias' attribute, so pull that out of device_interface_data.
                        device_interface_gateway = device_interface_data[device_interface][0]['alias']
                        # Filter the global list of interfaces down to just those that are both associated...
                        # to the APN we are looping on and the datacenter name we are looping on.
                        # In other words, any interface in this datacenter that is also associated to this APN.

                        if device_interface_gateway in valid_gateway_list_for_this_APN and dc_acronym in device_interface_gateway:
                            interface_number = device_interface_data[device_interface][0]['interfaceNumber']
                            interface_alias = device_interface_data[device_interface][0]['alias']
                            net_srv_config_data['serviceDetail'][0]['serviceMembers'].append({'enableAlert': False,
                            'interfaceNumber': interface_number,
                            'ipAddress': device_list[device][0],
                            'locationKeyInfo': [{'asi1xType': '',
                            'isLocationKey': True,
                            'keyAttr': apn_ids[apn_name],
                            'keyType': 4}],
                            'meAlias': interface_alias,
                            'meName': device_interface})
            # Create the new network service.
            create_service(ng1_host, headers, cookies, network_service_name, net_srv_config_data, False)
            # We need to know the id number that was assigned to this new network service.
            net_srv_config_data = get_service_detail(ng1_host, network_service_name, headers, cookies)
            net_srv_id = net_srv_config_data['serviceDetail'][0]['id']
            # Add this network service id to our dictionary so we can use it later to assign domain members.
            net_service_ids[network_service_name] = net_srv_id
        apn_loop_counter += 1

    return net_service_ids


def customer_menu(ng1_host, headers, cookies, apn_list, datacenter_list, customer_list, device_list):
    # This function is an entry menu for entering new customer information.
    # It takes in a customer name, a list of APNs, the customer type and a list of valid datacenters.
    # It returns the user's entries as a profile dictionary.
    # Return False if the user messes up and wants to start over

    # Create an empty dictionary that will hold our customer menu entries.
    profile = {'name':"", 'type':"", 'APNs':[{'APN':[]}]}
    # Create an empty list that will contain one or more APN entries.
    apn_entry_list = []
    # Initialize a variable to capture a user's yes or no reponse.
    user_entry = ''
    print('\nThis program takes input for customer attributes and creates a full configuration in nG1 to match')
    print("To cancel any changes, please type 'exit'")
    if customer_list == []: # If the current customer definition file was not found.
        print("\nThere are no customers in the system yet")
    else:
        print("\nCustomers already input are: ")
        print(sorted(customer_list), '\n')
    # User enters the customer name.
    while True:
        user_entry = input("Please enter the new Customer Name: ")
        if user_entry.lower() in [x.lower() for x in customer_list]:
            print(f"Customer: {user_entry} already exists")
            print("Please enter a customer that is not already in the list")
            continue
        if check_splcharacter(user_entry, True) == True:
            continue
        else:
            break

    if user_entry == '': # For testing, allow the user just to hit enter for a default value.
        profile['name'] = 'Giles'
    elif user_entry.lower() == 'exit':
        exit()
    else:
        profile['name'] = user_entry

    print('Please select the customer type:')
    print('[1] IOT')
    print('[2] Connected Cars')
    while True:
        user_entry = input('Enter 1 or 2: ').lower()
        if user_entry == 'exit':
            exit()
        elif user_entry == '': # For testing, allow the user to just hit enter.
            profile['type'] = 'Connected Cars'
            break
        elif user_entry == '1':
            profile['type'] = 'IOT'
            break
        elif user_entry == '2':
            profile['type'] = 'Connected Cars'
            break
        else:
            print("Invalid entry, please enter either '1' or '2'")
            continue

    print("\nCurrent APNs available are: ")
    print(sorted(apn_list), '\n')

    # Initialize an empty list to hold user entered APNs.
    apn_entry_list = []

    # User enters one or more APNs.
    while True:
        user_entry = input("Please enter one or more APNs from the list separated by comma: ")
        if check_splcharacter(user_entry, False) == True:
            continue
        else:
            break
    if user_entry == '': # For testing, allow the user to just hit enter.
        apn_entry_list.append('Onstar01')
        apn_entry_list.append('Onstar02')
    elif user_entry.lower() == 'exit':
        exit()
    else:
        # If more than one APN is entered, split the string into a list of APNs.
        apn_entry_list = user_entry.split(',')
        # Remove any leading or trailing whitespace from list members.
        i = 0
        for apn_entry in apn_entry_list:
            apn_entry_list[i] = apn_entry.strip()
            i += 1

    # Check to see if the entered APNs are in the list of available system-wide APNs.
    for apn_entry in apn_entry_list:
        if apn_entry not in apn_list: # These are case sensitive. only allow perfect matches.
            # We have checked every APN entry against every system-wide APN. Not found.
            print(f"[CRITICAL] APN: {apn_entry} does not yet exist")
            print(f"Please create APN: {apn_entry} first and then run this program again")
            print("No nG1 modifications will be made. Exiting...")
            exit()

    # Build up a list of valid datatcenters where each entered APN is associated to one or more interfaces.
    # Build up a list of valid gateways where each entered APN is associated to one or more interfaces.
    valid_datacenters, valid_gateways = build_valid_dc_and_gateway_lists(apn_entry_list, datacenter_list, device_list)

    # Add the user entered APNs to the customer profile dictionary.
    for apn_entry in apn_entry_list:
        profile['APNs'][0]['APN'].append({'name':apn_entry, 'gateways':[{'gateway':[]}]})

    # Create a list of valid datacenters for each APN that the user can select from.
    apn_loop_counter = 0
    for apn_entry in apn_entry_list:
        valid_datacenters_list = valid_datacenters[apn_loop_counter][apn_entry]
        valid_gateways_list = valid_gateways[apn_loop_counter][apn_entry]

        print(f"\nDatacenters associated to APN {apn_entry} are: {valid_datacenters_list}")

        # Initialize an empty list to hold user entered datacenters
        dc_entry_list = []
        while True:
            # User enters one or more Datacenters.
            user_entry = input("Please enter one or more Datacenters from the list separated by comma or all: ")
            if check_splcharacter(user_entry, False) == True:
                continue
            else:
                break
        if user_entry == '': # For testing, allow the user to just hit enter.
            dc_entry_list = valid_datacenters_list
        elif user_entry.lower() == 'all':
            # User selects all of the valid datacenters listed.
            dc_entry_list = valid_datacenters_list
        elif user_entry.lower() == 'exit':
            exit()
        else:
            # If more than one datacenter is entered, split the string into a list of datacenters.
            dc_entry_list = user_entry.split(',')
            # Remove any leading or trailing whitespace from list members.
            i = 0
            for dc_entry in dc_entry_list:
                dc_entry_list[i] = dc_entry.strip()
                i += 1

        # Check to see if the entered datacenters are in the list of available system-wide datacenters.
        for dc_entry in dc_entry_list:
            if dc_entry not in valid_datacenters_list: # You must capitalize the dc entry or we will not allow it.
                # We have checked every Datacenter entry against every valid datacenter. Not found.
                print(f"[CRITICAL] Datacenter: {dc_entry} is not in the list of valid datacenters {valid_datacenters_list}")
                print(f"Please create Datacenter: {dc_entry} first and then run this program again")
                print("No nG1 modifications will be made. Exiting...")
                exit()

        # Produce a list of valid gateways that have the APN entered associated to them.
        # Only list those APN associated gateways (interfaces) for the user entered datacenters.
        for dc_entry in dc_entry_list:
            filtered_gateways_list = []
            for valid_gateway in valid_gateways_list:
                dc_acronym = translate_dc_name_to_acronym(dc_entry)
                if dc_acronym in valid_gateway:
                    filtered_gateways_list.append(valid_gateway)
            print(f"\nGateways associated to APN {apn_entry} in {dc_entry} are: {filtered_gateways_list}")
            while True:
                # User enters one or more Gateways.
                user_entry = input("Please enter one or more Gateways from the list separated by comma or all: ")
                user_entry = user_entry.upper() # Allow entry of lower case characters, but make the variables all upper case.
                if check_splcharacter(user_entry, False) == True:
                    continue
                else:
                    break
            if user_entry == '': # For testing, allow the user to just hit enter.
                gateway_entry_list = filtered_gateways_list
            elif user_entry.lower() == 'exit':
                exit()
            elif user_entry.lower() == 'all':
                gateway_entry_list = filtered_gateways_list
            else:
                # If more than one gateway is entered, split the string into a list of gateways.
                gateway_entry_list = user_entry.split(',')
                i = 0
                for gateway_entry in gateway_entry_list:
                    gateway_entry = gateway_entry.upper() # make sure the whole entery is in caps.
                    gateway_entry_list[i] = gateway_entry.strip() # Remove leading or trailing whitespace.
                    i += 1
            # Check to make sure that what the user entered is in the list of valid gateways.
            for gateway_entry in gateway_entry_list:
                if gateway_entry not in valid_gateways_list: # Check if this gateway has this APN associated with it.
                    print(f"[CRITICAL] Gateway: {gateway_entry} is not in the list of valid gateways {valid_gateways_list}")
                    print(f"Please create Gateway: {gateway_entry} first and then run this program again")
                    print("No nG1 modifications will be made. Exiting...")
                    exit()

            # Add the user entered Gateways to the customer profile dictionary.
            for gateway_entry in gateway_entry_list:
                profile['APNs'][0]['APN'][apn_loop_counter]['gateways'][0]['gateway'].append({'name':gateway_entry})
        apn_loop_counter += 1

    #print(f'\nCustomer profile is: {profile}')

    print('-------------------------------------------')
    print('Confirm new customer profile:')
    print(f"Customer Name: {profile['name']}")
    print(f"Customer Type: {profile['type']}")
    for apn in profile['APNs'][0]['APN']:
        apn_gateway_list = []
        print(f"APN name: {apn['name']}")
        for apn_gateway in apn['gateways'][0]['gateway']:
            apn_gateway_list.append(apn_gateway['name'])
        print(f"APN {apn['name']} gateways: {apn_gateway_list}")
    print('-------------------------------------------')
    print("Enter 'y' to proceed with nG1 configuration")
    print("Enter 'n' to start over")
    print("Enter 'exit' to exit without configuration changes")
    while True:
        user_entry = input('y or n: ').lower()
        if user_entry == 'y':
            return profile, dc_entry_list
        elif user_entry == 'n':
            return False, False
        elif user_entry == 'exit':
            exit()
        else:
            print("Invalid entry, please enter 'y' or 'n'")
            continue

def open_session(ng1_host, headers, cookies, credentials):
    open_session_uri = "/ng1api/rest-sessions"
    open_session_url = ng1_host + open_session_uri

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
            print(f'[CRITICAL] opening session to URL: {open_session_url} failed')
            print('Unable to determine authentication by credentials or token')
            print('Exiting the program now...')
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
            print(f'[CRITICAL] opening session to URL: {open_session_url} failed')
            print('Response Code:', post.status_code)
            print('Response Body:', post.text)
            print('Exiting the program now...')
            exit()
    except:
        # This means we likely did not reach the nG1 at all. Check your VPN connection.
        print('[CRITICAL] opening session failed')
        print(f'Cannot reach URL: {open_session_url}')
        print('Check your connection')
        print('Exiting the program now...')
        exit()

def close_session(ng1_host, headers, cookies):
    close_session_uri = "/ng1api/rest-sessions/close"
    close_session_url = ng1_host + close_session_uri
    # perform the HTTPS API call
    close = requests.request("POST", close_session_url, headers=headers, verify=False, cookies=cookies)

    if close.status_code == 200:
        # success
        print('[INFO] Closed Session Successfully')
        return True
    else:
        print('[ERROR] closing session')
        print('Response Code:', close.status_code)
        print('Response Body:', close.text)
        return False

def write_config_to_json(config_filename, config_data):
    # The config_data that is passed in is converted to a string (serialized) and written to the json file

    # write to a json file
    try:
        with open(config_filename,"w") as f:
            json.dump(config_data, f)
            print(f'[INFO] Writing config to JSON file:', config_filename)
            return True
    except IOError as e:
        print(f'[ERROR] Unable to write to the JSON config file:', config_filename)
        print("I/O error({0}): {1}".format(e.errno, e.strerror))
        return False
    except: #handle other exceptions such as attribute errors
        print(f'[ERROR] Unable to write to the JSON config file:', config_filename)
        print("Unexpected error:", sys.exc_info()[0])
        return False

def read_config_from_json(config_filename):
    # The contents of the json config file are read into config_data, converted to a python dictionary object and returned
    try:
        with open(config_filename) as f:
            # decoding the JSON data to a python dictionary object
            config_data = json.load(f)
            print(f'[INFO] Reading config data from JSON file: ', config_filename)
            return config_data
    except IOError as e:
        print(f'[ERROR] Unable to read the JSON config file:', config_filename)
        print("I/O error({0}): {1}".format(e.errno, e.strerror))
        return False
    except: #handle other exceptions such as attribute errors
        print(f'[ERROR] Unable to read the JSON config file:', config_filename)
        print("Unexpected error:", sys.exc_info()[0])
        return False

def get_apns(ng1_host, headers, cookies):
    uri = "/ng1api/ncm/apns/"
    url = ng1_host + uri

    # perform the HTTPS API call to get the All APNs information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_apns Successful')

        # return the json object that contains the All APNs information
        return get.json()

    else:
        print('[ERROR] get_apns Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def get_apn_detail(ng1_host, headers, cookies, apn_name):
    uri = "/ng1api/ncm/apns/"
    url = ng1_host + uri + apn_name

    # perform the HTTPS API call to get the APN detail information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_apn_detail for', apn_name, 'Successful')

        # return the json object that contains the APN detail information
        return get.json()

    else:
        print('[ERROR] get_apn_detail for', apn_name, 'Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def get_apns_on_an_interface(ng1_host, headers, cookies, device_name, interface_number):
    uri = "/ng1api/ncm/devices/"
    url = ng1_host + uri + device_name + "/interfaces/" + interface_number + "/associateapns"

    # perform the HTTPS API call to get the APN detail information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print(f"[INFO] get_apns_on_an_interface for device: {device_name} interface number: {interface_number} Successful")

        # return the json object that contains the APN detail information
        return get.json()

    else:
        print(f"[ERROR] get_apns_on_an_interface for device: {device_name} interface number: {interface_number} Failed")
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def set_apns(ng1_host, headers, cookies):
    # Add a list of APN groups to nG1 based on an existing json file definition
    service_uri = "/ng1api/ncm/apns/"

    # Read in the json file to get all the service attributes
    service_data = read_config_from_json('set_apns.json')
    url = ng1_host + service_uri

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
        print('[ERROR] set_apns Failed')
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

    # Create the parent domain.
    if create_domain(ng1_host, domain_name, headers, cookies, parent_config_data) == True:
        # Fetch the id of the domain we just created so that we can use it to add child domains.
        #parent_config_data = get_domain_detail(ng1_host, domain_name, headers, cookies)
        domain_tree_data = get_domains(ng1_host, headers, cookies)
        for domain in domain_tree_data['domain']:
            # Skip the Enterprise domain as it has no parent id number.
            if domain['serviceName'] != 'Enterprise':
                if domain['serviceName'] == domain_name and str(parent_domain_id) in str(domain['parent']):
                    #if domain_name == 'Onstar03':
                        #print(f'domain_tree_data is: {domain_tree_data}')
                        #print(f"domain['serviceName'] is {domain['serviceName']}")
                        #print(f"str(parent_domain_id) is {str(parent_domain_id)}")
                        #print(f"str(domain['parent'] is {str(domain['parent'])}")

                    parent_domain_id = domain['id']
    else:
        print(f'[CRITICAL] Unable to create domain: {domain_name} Exiting...')
        exit()

    return parent_domain_id

def get_domains(ng1_host, headers, cookies):
    service_uri = "/ng1api/ncm/domains/"
    url = ng1_host + service_uri

    # perform the HTTPS API call to get the Domains information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_domains Successful')

        # return the json object that contains the Domains information
        return get.json()

    else:
        print('[ERROR] get_domains Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def get_domain_detail(ng1_host, domain_name, headers, cookies):
    service_uri = "/ng1api/ncm/domains/"
    url = ng1_host + service_uri + domain_name

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
            print('[ERROR] get_domain_detail for', domain_name, 'Failed')
            print('URL:', url)
            print('Response Code:', get.status_code)
            print('Response Body:', get.text)

        return False

def create_domain(ng1_host, domain_name, headers, cookies, parent_config_data):
    # Create a new dashboard domain using parent_config_data that contain all the attributes.
    service_uri = "/ng1api/ncm/domains/"
    url = ng1_host + service_uri
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
        print('[ERROR] create_domain: ', domain_name, 'Failed')
        print('URL:', url)
        print('Response Code:', post.status_code)
        print('Response Body:', post.text)

        return False

def delete_domain(ng1_host, domain_name, headers, cookies):
    service_uri = "/ng1api/ncm/domains/"
    url = ng1_host + service_uri + domain_name
    # Perform the HTTPS API Delete call by passing the service_name.
    # This will delete the specific service configuration for this service_name.
    delete = requests.delete(url, headers=headers, verify=False, cookies=cookies)

    if delete.status_code == 200:
        # success
        print('[INFO] delete_domain', domain_name, 'Successful')
        return True

    else:
        print('[ERROR] delete_service', domain_name, 'Failed')
        print('URL:', url)
        print('Response Code:', delete.status_code)
        print('Response Body:', delete.text)

        return False

def get_devices(ng1_host, headers, cookies):
    device_uri = "/ng1api/ncm/devices/"
    url = ng1_host + device_uri
    # perform the HTTPS API call to get the device information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_devices request Successful')

        # return the json object that contains the device information
        return get.json()

    else:
        print('[ERROR] get_devices request failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def get_device_detail(ng1_host, headers, cookies, device_name):
    uri = "/ng1api/ncm/devices/"
    url = ng1_host + uri + device_name
    # perform the HTTPS API call to get the device information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_device_detail request for', device_name, 'Successful')

        # return the json object that contains the device information
        return get.json()

    else:
        print('[ERROR] get_device_detail request for', device_name, 'failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def get_service_detail(ng1_host, service_name, headers, cookies):
    service_uri = "/ng1api/ncm/services/"
    url = ng1_host + service_uri + service_name

    # perform the HTTPS API call to get the Service information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_service_detail for', service_name, 'Successful')

        # return the json object that contains the Service information
        return get.json()

    else:
        print('[ERROR] get_service_detail for', service_name, 'Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def create_service(ng1_host, headers, cookies, service_name, config_data, save):
    # Create a new service using the config_data attributes passed into the function.
    # Optionally write a copy of the config to a json file if 'save' is equal to True.

    service_uri = "/ng1api/ncm/services/"

    url = ng1_host + service_uri

    # if the save option is True, then save a copy of this configuration to a json file.
    if save == True:
        write_config_to_json(service_name + '.json', config_data)
    # use json.dumps to provide a serialized json object (a string actually).
    # this json_string will become our new configuration for this service_name.
    json_string = json.dumps(config_data)

    # perform the HTTPS API Post call with the serialized json object service_data.
    # This will create the service configuration in nG1 for this service_name.
    post = requests.post(url, headers=headers, data=json_string, verify=False, cookies=cookies)

    if post.status_code == 200: # Create Service was successful.
        print(f'[INFO] create_service: {service_name} Successful')
        return True

    else: # Create Service has failed.
        # If the service exists, don't post an error message, just show as info.
        # These services can be used by many customers without creating user specific services.
        if 'exists' in post.text:
            print(f'[INFO] create_service: {service_name}. Service already exists')
        else:
            print('[ERROR] create_service', service_name, 'Failed')
            print('URL:', url)
            print('Response Code:', post.status_code)
            print('Response Body:', post.text)

        return False

def get_devices(ng1_host, headers, cookies):
    device_uri = "/ng1api/ncm/devices/"
    url = ng1_host + device_uri
    # perform the HTTPS API call to get the device information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_devices request Successful')

        # return the json object that contains the device information
        return get.json()

    else:
        print('[ERROR] get_devices request failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def get_device(ng1_host, device_name, headers, cookies):
    device_uri = "/ng1api/ncm/device/"
    url = ng1_host + device_uri
    # perform the HTTPS API call to get the device information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_device for', device_name, 'Successful')

        # return the json object that contains the device information
        return get.json()

    else:
        print('[ERROR] get_device for', device_name, 'Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def get_device_interfaces(ng1_host, headers, cookies, device_name):
    device_uri = "/ng1api/ncm/devices/" + device_name + "/interfaces"
    url = ng1_host + device_uri
    # perform the HTTPS API call to get the device information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_device_interfaces for', device_name, 'Successful')

        # return the json object that contains the device information
        return get.json()

    else:
        print('[ERROR] get_device_interfaces for', device_name, 'Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def get_device_interface_locations(ng1_host, device_name, interface_id, headers, cookies):
    device_uri = "/ng1api/ncm/devices/" + device_name + "/interfaces/" + interface_id + "/locations"
    url = ng1_host + device_uri
    # perform the HTTPS API call to get the device information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_device_interface_locations for', device_name, 'Interface', interface_id, 'Successful')

        # return the json object that contains the device information
        return get.json()

    else:
        print('[ERROR] get_device_interface_locations for ', device_name, 'Interface', interface_id, 'Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def get_applications(ng1_host, headers, cookies):
    uri = "/ng1api/ncm/applications/"
    url = ng1_host + uri

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
    uri = "/ng1api/ncm/applications/"
    url = ng1_host + uri + app_name

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

def get_messages(ng1_host, headers, cookies, app_name):
    uri = "/ng1api/ncm/applications/" + app_name + "/messages"
    url = ng1_host + uri

    # perform the HTTPS API call to get the App Messages information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_messages Successful')

        # return the json object that contains the Services information
        return get.json()

    else:
        print('[FAIL] get_messages Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

def get_message_detail(ng1_host, headers, cookies, app_name, message_name):
    uri = "/ng1api/ncm/applications/" + app_name + "/messages/" + message_name
    url = ng1_host + uri

    # perform the HTTPS API call to get the app message information
    get = requests.get(url, headers=headers, verify=False, cookies=cookies)

    if get.status_code == 200:
        # success
        print('[INFO] get_message_detail Successful')

        # return the json object that contains the Service information
        return get.json()

    else:
        print('[FAIL] get_message_detail Failed')
        print('URL:', url)
        print('Response Code:', get.status_code)
        print('Response Body:', get.text)

        return False

# ---------- Code Driver section below ----------------------------------------

now = datetime.now()
date_time = now.strftime("%Y_%m_%d_%H%M%S")

# Create the logging function.
# Use this option to log to stdout and stderr using systemd. You must also import os.
# logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
# Use this option to log to a file in the same directory as the .py python program is running
logging.basicConfig(filename="ng1_add_cisco_iot_customer.log", format='%(asctime)s %(message)s', filemode='a+')
# Creating a logger object.
logger = logging.getLogger()
# Set the logging level to the lowest setting so that all logging messages get logged.
logger.setLevel(logging.INFO) # Allowable options include DEBUG, INFO, WARNING, ERROR, and CRITICAL.
logger.info(f"*** Start of logs {date_time} ***")

# Hardcoding the filenames for encrypted credentials and the key file needed to decrypt the credentials.
cred_filename = 'CredFile.ini'
ng1key_file = 'ng1key.key'

# Retrieve the decrypted credentials that we will use to open a session to nG1.
try:
    with open(ng1key_file, 'r') as ng1key_in:
        ng1key = ng1key_in.read().encode()
        fng1 = Fernet(ng1key)
except:
    print(f'[CRITICAL] Unable to open ng1key_file: {ng1key_file}. Exiting...')
    exit()
try:
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
except:
    print(f'[CRITICAL] Unable to open cred_filename: {cred_filename}. Exiting...')
    exit()

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
if ng1destPort == '80' or ng1destPort == '8080':
    web_protocol = 'http://'
elif ng1destPort == '443' or ng1destPort == '8443':
    web_protocol = 'https://'
else:
    print(f'[CRITICAL] nG1 destination port {ng1destPort} is not equal to 80, 8080, 443 or 8443')
    print('Exiting...')
    exit()
ng1_host = web_protocol + ng1destination + ':' + ng1destPort

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

# Hardcoding the name of the master datacenter to gateways mapping json file.
current_datacenters_filename = 'CiscoIOT-DataCenters.json'
# Hardcoding the name of the master customer applications list json file.
app_list_filename = 'CiscoIOT-AppList.json'

# Build a device list for active Infinistreams/vStreams in the system.
# For each, include a list of active interfaces.
# For each interface, include a list of APNs associated to that interface
device_list, datacenter_list = build_device_list(current_datacenters_filename)

customers_filename = 'CiscoIOT-Customers' # Hardcoding the stem of the customer definition filename
current_customers_filename = customers_filename + '_current.json' # The name of the master customer definition json file.
new_customers_filename = customers_filename + '_new.json' # The name of the new customer definition json file we will create.
old_customers_filename = customers_filename + '_old.json' # The name of the backup customer definition json file we will create.

# Get info on all existing customers
customer_configs, customer_list = get_existing_customers_from_file(current_customers_filename)

# Fetch the existing domain tree data so that we know what domains already exist.
domain_tree_data = get_domains(ng1_host, headers, cookies)
# Search the existing domain tree to see if all the customers listed in the current_customers_filename match...
# what is currently configured in the dashboard domain tree. Print out any domains that are missing.
# Also search the customers listed in the current_customers_filename to see if there is a match in the...
# currently configured domain tree. Print out any customer names that are missing from the domain tree.
customer_domains_missing = validate_cust_domains_exist(customer_configs, domain_tree_data)
if customer_domains_missing != []: # There are missing customer domains.
    print(f'[Warning] There are customers in the {current_customers_filename} that are not in the current domain tree')
    print(f'[Warning] Customers in {current_customers_filename} with no domains are: {customer_domains_missing}')
    while True:
        user_input = input('Continue? y or n: ')
        if user_input.lower() == 'n':
            exit()
        elif user_input.lower() == 'y':
            break
        else:
            print("Invalid input. Please enter 'y' or 'n'")
            continue
else:
    print(f'[INFO] Customers in {current_customers_filename} all have verified domains in the system')
# Initialize an empty apn list that we will use later to verify user input.
apn_list = []
# Get info on all APN locations system-wide.
apn_configs = get_apns(ng1_host, headers, cookies)

if apn_configs != False:
    #print(f'apn_configs["apns"] are: {apn_configs["apns"]}')
    if apn_configs["apns"] == []: # get_apns was successful, but there were no apns in the system.
        print('[CRITICAL] There are no APNs configured in this system. Exiting...')
        exit()
    else:
        for apn in apn_configs["apns"]:
            apn_name = apn["name"]
            apn_list.append(apn_name)
else:
    print('[CRITICAL] Unable to fetch APNs. Exiting....')
    exit()

# Get the new customer profile from the user by presenting a menu.
# Note that customer profiles do not actually include the list of datacenters the user selected.
# So we need to return that as separate list called dc_entry_list.
while True:
    profile, dc_entry_list = customer_menu(ng1_host, headers, cookies, apn_list, datacenter_list, customer_list, device_list)
    if profile != False: # We made it through the menu Successfully.
        # print(f"Profile is : {profile}") # Display the customer attributes that the user entered.
        break
    # If the user does not confirm the new customer profile, let them start over
    else:
        print('New customer profile discarded, starting over...')
        print('')
        continue

# Fetch the APN id number that matches with each APN in the customer profile.
apn_ids = build_apn_ids_dict(profile)

# Initialize an empty dictionary to hold the name:id key, value pairs for each network service we create.
# We will use this later to add members to the dashboard domains that we create.
net_service_ids = {}
# Create a network service for each interface (gateway) that the user specified.
# Add the network service ids for each network service created to our net_service_ids dictionary.
net_service_ids = create_gateway_net_services(ng1_host, headers, cookies, apn_ids, apn_name, device_list, profile, net_service_ids, dc_entry_list)

# Create network services that include all GGSNs (interfaces) for each APN on every valid datacenter.
# Add the network service ids for each network service created to our net_service_ids dictionary.
net_service_ids = create_all_ggsns_net_service(ng1_host, headers, cookies, apn_ids, device_list, profile, net_service_ids, dc_entry_list)

# Get info on all customer applications from a json file and put it into the app_data dictionary.
app_data = get_customer_apps_from_file(app_list_filename)

# Now create create the application services for all apps defined in the app_data for each APN the user entered.
# The app_service_ids list that is returned will become members of domains as we create them.
# Therefore we need the id numbers to do that assignment.
# Use the network services we already created as members for the app service definitions.
app_service_ids = create_app_services(ng1_host, headers, cookies, apn_ids, app_data, net_service_ids, dc_entry_list)

domain_name = 'Cisco IOT'
# This is a domain layer that is common to all customers. If it exists, don't overwrite it.
skip, existing_parent_domain_id = domain_exists(domain_name, domain_tree_data)

if skip == False: # The domain does not yet exist, create it
    # Create the domain.
    # Initialize an empty list of domain member ids for use when we add domains that have members.
    domain_member_ids = {}
    parent_domain_id = 1 # This is the parentID of the default 'Enterprise' domain at the top.
    parent_domain_id = build_domain_tree(ng1_host, headers, cookies, domain_name, parent_domain_id, domain_member_ids)

domain_name = 'APNs'
# This is a domain layer that is common to all customers. If it exists, don't overwrite it.
skip, existing_parent_domain_id = domain_exists(domain_name, domain_tree_data)
if skip == False: # The domain does not yet exist, create it
    # Create the APN domain.
    # Initialize an empty list of domain member ids for use when we add domains that have members.
    domain_member_ids = {}
    parent_domain_id = build_domain_tree(ng1_host, headers, cookies, domain_name, parent_domain_id, domain_member_ids)
else:
    # The domain already exists, set the parent_domain_id to the existing domain.
    parent_domain_id = existing_parent_domain_id

if profile['type'] == 'Connected Cars':
    domain_name = 'Connected Car APNs'
else:
    domain_name = 'IOT APNs'
# This is a domain layer that is common to all customers. If it exists, don't overwrite it
skip, existing_parent_domain_id = domain_exists(domain_name, domain_tree_data)
if skip == False: # The domain does not yet exist, create it
    # Create the customer type domain.
    # Initialize an empty list of domain member ids for use when we add domains that have members.
    domain_member_ids = {}
    parent_domain_id = build_domain_tree(ng1_host, headers, cookies, domain_name, parent_domain_id, domain_member_ids)
else:
    # The domain already eists, set the parent_domain_id to the existing domain.
    parent_domain_id = existing_parent_domain_id

domain_name = profile['name'] # Set the domain name to be the customer name as entered in the menu

# Create the customer named domain. Note it is allowed that the customer named domain can be...
# the same as APN named domains below it. We have already checked in customer menu for duplicate...
# entries of the customer name. So this should create a unique customer name at this domain level.
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
    for datacenter in dc_entry_list:
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
    for datacenter in dc_entry_list:
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
    for datacenter in dc_entry_list:
        dc_acronym = translate_dc_name_to_acronym(datacenter)
        # Add the DNS domain as a child to the customer domain if only one APN.
        # If more than one APN, the User domain is a child to each APN named domain.

        # Look for any application service name that includes both the DNS app name, the APN name and the datacenter acronym.
        for application_service_name in app_service_ids:
            if 'DNS' in application_service_name and dc_acronym in application_service_name and apn_name in application_service_name:
                domain_member_ids[application_service_name] = app_service_ids[application_service_name]

    domain_name = 'DNS' # Hardcoding the domain name based on the same list of Control, User and DNS for all customers.
    dns_parent_domain_id = build_domain_tree(ng1_host, headers, cookies, domain_name, apn_parent_domain_id, domain_member_ids)

# Add the new customer profile to the current customer config profile dictionary.
customer_configs['Customers'].append(profile)
# Name the file that we want to write the new customer config profile dictionary to.
config_filename = new_customers_filename
# Save the new customer config profile dictionary to the new customer new_customers_filename file
save_cust_config_to_file(customer_configs, new_customers_filename, current_customers_filename, old_customers_filename)

#FOR TESTING: Delete everything
#domain_name = 'Cisco IOT'
#delete_domain(ng1_host, domain_name, headers, cookies)

close_session(ng1_host, headers, cookies)
