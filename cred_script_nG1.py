from cryptography.fernet import Fernet
import ctypes
import time
import os
import sys

class Credentials():

    def __init__(self):
        self.__ng1destination = ""
        self.__ng1port = ""
        self.__ng1token = ""
        self.__ng1username = ""
        self.__ng1key = ""
        self.__ng1password = ""
        self.__ng1key_file = 'ng1key.key'
        self.__time_of_exp = -1

    @property
    def ng1destination(self):
        return self.__ng1destination
    @ng1destination.setter
    def ng1destination(self, ng1destination):
        self.__ng1destination = ng1destination

    @property
    def ng1port(self):
        return self.__ng1port
    @ng1port.setter
    def ng1port(self, ng1port):
        self.__ng1port = ng1port

    @property
    def ng1token(self):
        return self.__ng1token
    @ng1token.setter
    def ng1token(self, ng1token):
        self.__ng1key = Fernet.generate_key()
        fng1 = Fernet(self.__ng1key)
        self.__ng1token = fng1.encrypt(ng1token.encode()).decode()
        del fng1

    @property
    def ng1username(self):
        return self.__ng1username
    @ng1username.setter
    def ng1username(self, ng1username):
        self.__ng1username = ng1username

    @property
    def ng1password(self):
        return self.__ng1password
    @ng1password.setter
    def ng1password(self, ng1password):
        self.__ng1key = Fernet.generate_key()
        fng1 = Fernet(self.__ng1key)
        self.__ng1password = fng1.encrypt(ng1password.encode()).decode()
        del fng1

    @property
    def expiry_time(self):
        return self.__time_of_exp
    @expiry_time.setter
    def expiry_time(self, exp_time):
        if (exp_time >= 2):
            self.__time_of_exp = exp_time

    def create_cred(self):
                #This function encrypts the password then stores key in a key file, it stores encrypted pw in cred file, with all other target information.
        cred_filename = 'CredFile.ini'
        with open(cred_filename, 'w') as file_in:
            file_in.write("#Credential file:\nExpiry={}\nng1token={}\nng1username={}\nng1password={}\nng1destination={}\nng1port={}\n"
                        .format(self.__time_of_exp, self.__ng1token, self.__ng1username, self.__ng1password, self.__ng1destination, self.__ng1port))
            # If there exists an older key file, This will remove it.
            if os.path.exists(self.__ng1key_file):
                os.remove(self.__ng1key_file)

                # Open the key.key file and place the key in it.
        try:
            os_type = sys.platform
            if os_type == 'linux':
                self.__ng1key_file = '.' + self.__ng1key_file
            else:
                pass

            with open(self.__ng1key_file, 'w') as key_in:
                    key_in.write(self.__ng1key.decode())
                    # Hiding the key file. The below code learns OS and tries to hide key file accordingly.
                    #if os_type == 'win32' or os_type == 'win64':
                        #ctypes.windll.kernel32.SetFileAttributesW(self.__ng1key_file, 2)
                    #else:
                        #pass

        except PermissionError:
            os.remove(self.__key_file)
            print("A Permission error occurred.")
            sys.exit()

        self.__ng1key = ""
        self.__ng1destination = ""
        self.__ng1port = ""
        self.__ng1token = ""
        self.__ng1username = ""
        self.__ng1password = ""

def yes_or_no(question):
    reply = ""
    while reply != 'y' or reply != 'n':
        reply = str(input(question+' (y/n): ')).lower().strip()
        if reply[:1] == 'y':
            return True
        if reply[:1] == 'n':
            return False
        else:
            print("The answer is invalid, please enter y or n")
            continue

def main():
    # Creating an object for Credentials class
    creds = Credentials()
    token_or_password = ""

    # Accepting credentials
    creds.ng1destination = input("Enter nG1 hostname/IP: ")
    creds.ng1port = input("Enter nG1 port: ")
    # Give the user the option to use an API Token or a username:password pair
    if yes_or_no("Use Token instead of Username:Password?"):
        creds.ng1token = input("Enter nG1 User Token: ")
    else:
        creds.ng1username = input("Enter nG1 Username: ")
        creds.ng1password = input("Enter nG1 Password: ")
    print("Enter the expiry time for key file in minutes, [default:Will never expire]: ")
    creds.expiry_time = int(input("Enter time: ") or '-1')

    # calling the Credit
    creds.create_cred()
    print("Cred file created successfully at {}"
          .format(time.ctime()))

if __name__ == "__main__":
    main()
