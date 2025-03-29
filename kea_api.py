import requests  # type: ignore
import pymysql  # type: ignore
from notification_window import NotificationWindow
from config_loader import KEA_SERVER, MYSQL_CONFIG, DUMMY_DATA, debug_print
import time


def get_subnets():
    """
    Fetches the list of subnets from the Kea API.
    """
    if DUMMY_DATA:
        return [
            {
                "subnet_id": 1,
                "subnet": "10.1.1.0/24",
                "valid_lifetime": 3600,
                "pools": ["10.1.1.20-10.1.1.21"]
            },
            {
                "subnet_id": 2,
                "subnet": "10.2.2.0/24",
                "valid_lifetime": 7200,
                "pools": ["10.2.2.50-10.2.2.52"]
            },
            {
                "subnet_id": 3,
                "subnet": "10.3.3.0/24",
                "valid_lifetime": 1800,
                "pools": ["10.3.3.30-10.3.3.210"]
            },
            {
                "subnet_id": 4,
                "subnet": "10.4.4.0/24",
                "valid_lifetime": 5400,
                "pools": ["10.4.4.40-10.4.4.220"]
            },
            {
                "subnet_id": 5,
                "subnet": "10.5.5.0/24",
                "valid_lifetime": 3600,
                "pools": ["10.5.5.10-10.5.5.230"]
            },
            {
                "subnet_id": 6,
                "subnet": "10.6.6.0/24",
                "valid_lifetime": 9000,
                "pools": ["10.6.6.60-10.6.6.250"]
            }
        ]
    
    url = f"{KEA_SERVER}/"
    headers = {"Content-Type": "application/json"}
    payload = {
        "command": "config-get",
        "service": ["dhcp4"]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        debug_print(f"Response: {data}")
        if not data or "arguments" not in data[0] or "Dhcp4" not in data[0]["arguments"]:
            raise ValueError("Invalid response from Kea API")
        
        subnets = data[0]["arguments"]["Dhcp4"].get("subnet4", [])
        
        return [
            {
                "subnet_id": subnet["id"],
                "subnet": subnet["subnet"],
                "valid_lifetime": subnet["valid-lifetime"],
                "pools": [pool["pool"] for pool in subnet.get("pools", [])]
            }
            for subnet in subnets
        ]
    except (requests.RequestException, ValueError) as e:
        NotificationWindow(f"Error fetching subnets from Kea API:\n{str(e)}", "API Error").exec()
        return []
    
def update_subnet_lifetime(subnet_id, new_lifetime):
    """
    Updates the lease time for a given subnet and adjusts renew-timer and rebind-timer accordingly.
    Only writes to config if config-set is successful.
    """
    if DUMMY_DATA:
        debug_print(f"[DUMMY] Skipping update_subnet_lifetime for subnet {subnet_id} with lifetime {new_lifetime}")
        NotificationWindow(f"[DUMMY MODE] Lease time change skipped for subnet {subnet_id}.", "Info").exec()
        return

    url = f"{KEA_SERVER}/"
    headers = {"Content-Type": "application/json"}

    try:
        # Step 1: Fetch the current configuration
        config_get_payload = {
            "command": "config-get",
            "service": ["dhcp4"]
        }

        response = requests.post(url, headers=headers, json=config_get_payload)
        response.raise_for_status()
        config_data = response.json()

        if config_data[0]["result"] != 0:
            debug_print(f"Error fetching config: {config_data[0]['text']}")
            NotificationWindow(f"Error fetching config: {config_data[0]['text']}").exec()
            return  # Stop execution if config-get fails

        # Step 2: Find and update the subnet in the configuration
        dhcp4_config = config_data[0]["arguments"]["Dhcp4"]

        debug_print(f"[DEBUG] Checking for subnet ID: {subnet_id}")

        found = False
        for subnet in dhcp4_config.get("subnet4", []):
            debug_print(f"[DEBUG] Checking subnet ID: {subnet['id']}")
            if int(subnet["id"]) == int(subnet_id):
                subnet["valid-lifetime"] = new_lifetime
                subnet["renew-timer"] = int(new_lifetime * 0.5)  # Set renew-time (T1) to 50% of lifetime
                subnet["rebind-timer"] = int(new_lifetime * 0.875)  # Set rebind-time (T2) to 87.5% of lifetime
                
                # Adjust min/max valid-lifetime
                subnet["min-valid-lifetime"] = new_lifetime
                subnet["max-valid-lifetime"] = new_lifetime
                
                found = True
                break

        if not found:
            debug_print(f"Subnet ID {subnet_id} not found in configuration.")
            NotificationWindow(f"Subnet ID {subnet_id} not found in configuration.").exec()
            return  # Stop execution if subnet is not found

        # Step 3: Apply the updated configuration
        config_set_payload = {
            "command": "config-set",
            "service": ["dhcp4"],
            "arguments": {"Dhcp4": dhcp4_config}
        }

        response = requests.post(url, headers=headers, json=config_set_payload)
        response.raise_for_status()
        result = response.json()

        if result[0]["result"] != 0:
            debug_print(f"Error updating lease time: {result[0]['text']}")
            NotificationWindow(f"Error updating lease time: {result[0]['text']}").exec()
            return  # Stop execution if config-set fails

        debug_print(f"Successfully updated lease time for subnet {subnet_id} to {new_lifetime} seconds.")
        debug_print(f"Renew Timer: {subnet['renew-timer']} sec, Rebind Timer: {subnet['rebind-timer']} sec.")
        debug_print(f"Min/Max Lifetime: {subnet['min-valid-lifetime']} sec")
        NotificationWindow(f"Successfully updated lease time for subnet {subnet_id} to {new_lifetime} seconds.\nRenew Timer: {subnet['renew-timer']} sec, Rebind Timer: {subnet['rebind-timer']} sec.\nMin/Max Lifetime: {subnet['min-valid-lifetime']} sec").exec()

        # Step 4: Persist the change **only if config-set was successful**
        config_write_payload = {
            "command": "config-write",
            "service": ["dhcp4"]
        }

        response = requests.post(url, headers=headers, json=config_write_payload)
        response.raise_for_status()
        result = response.json()

        if result[0]["result"] != 0:
            debug_print(f"Error writing config: {result[0]['text']}")
            NotificationWindow(f"Error writing config: {result[0]['text']}").exec()
        else:
            debug_print("Configuration successfully written to file.")
            NotificationWindow(f"Configuration successfully written to file.").exec()


    except requests.RequestException as e:
        debug_print(f"Request failed: {e}")
        NotificationWindow(f"Request failed: {e}").exec()

def update_subnet_pool(subnet_id, new_pool_range):
    """
    Workaround to update pool range: Get current config, modify pools, and reapply config.
    """
    if DUMMY_DATA:
        debug_print(f"[DUMMY] Skipping update_subnet_pool for subnet {subnet_id} with pool {new_pool_range}")
        NotificationWindow(f"[DUMMY MODE] Pool update skipped for subnet {subnet_id}.", "Info").exec()
        return
    
    url = f"{KEA_SERVER}/"
    headers = {"Content-Type": "application/json"}

    try:
        # Step 1: Fetch current configuration
        config_get_payload = {
            "command": "config-get",
            "service": ["dhcp4"]
        }

        response = requests.post(url, headers=headers, json=config_get_payload)
        response.raise_for_status()
        config_data = response.json()

        if config_data[0]["result"] != 0:
            NotificationWindow(f"Error fetching config: {config_data[0]['text']}", "API Error").exec()
            return  # Stop execution if config-get fails

        # Step 2: Locate the correct subnet and update its pool
        dhcp4_config = config_data[0]["arguments"]["Dhcp4"]

        found = False
        for subnet in dhcp4_config.get("subnet4", []):
            if int(subnet["id"]) == int(subnet_id):
                subnet["pools"] = [{"pool": new_pool_range}]
                found = True
                break

        if not found:
            NotificationWindow(f"Subnet ID {subnet_id} not found in configuration.", "Error").exec()
            return  # Stop execution if subnet is not found

        # Step 3: Apply the updated configuration
        config_set_payload = {
            "command": "config-set",
            "service": ["dhcp4"],
            "arguments": {"Dhcp4": dhcp4_config}
        }

        response = requests.post(url, headers=headers, json=config_set_payload)
        response.raise_for_status()
        set_result = response.json()

        if set_result[0]["result"] != 0:
            NotificationWindow(f"Error applying new pool range: {set_result[0]['text']}", "API Error").exec()
            return  # Stop execution if config-set fails

        debug_print(f"Successfully updated pool range for subnet {subnet_id} to {new_pool_range}.")
        NotificationWindow(f"Successfully updated pool range for subnet {subnet_id} to {new_pool_range}.").exec()

        # Step 4: Persist the change only if config-set was successful
        config_write_payload = {
            "command": "config-write",
            "service": ["dhcp4"]
        }

        response = requests.post(url, headers=headers, json=config_write_payload)
        response.raise_for_status()
        write_result = response.json()

        if write_result[0]["result"] != 0:
            NotificationWindow(f"Error writing config: {write_result[0]['text']}", "API Error").exec()
        else:
            debug_print("Configuration successfully written to file.")
            NotificationWindow(f"Configuration successfully written to file.").exec()

    except requests.RequestException as e:
        NotificationWindow(f"Request failed: {e}", "API Error").exec()


def get_active_leases():
    if DUMMY_DATA:
        now = int(time.time())
        return [
            {
                "ip-address": "10.1.1.25",
                "hw-address": "AA:BB:CC:DD:EE:01",
                "hostname": "alpha",
                "subnet-id": 1,
                "cltt": now - 100,
                "valid-lft": 1800
            },
            {
                "ip-address": "10.2.2.66",
                "hw-address": "AA:BB:CC:DD:EE:02",
                "hostname": "beta",
                "subnet-id": 2,
                "cltt": now - 300,
                "valid-lft": 3600
            },
            {
                "ip-address": "10.3.3.77",
                "hw-address": "AA:BB:CC:DD:EE:03",
                "hostname": "gamma",
                "subnet-id": 3,
                "cltt": now - 400,
                "valid-lft": 1200
            },
            {
                "ip-address": "10.4.4.88",
                "hw-address": "AA:BB:CC:DD:EE:04",
                "hostname": "delta",
                "subnet-id": 4,
                "cltt": now - 200,
                "valid-lft": 3600
            },
            {
                "ip-address": "10.5.5.99",
                "hw-address": "AA:BB:CC:DD:EE:05",
                "hostname": "epsilon",
                "subnet-id": 5,
                "cltt": now - 500,
                "valid-lft": 2400
            },
            {
                "ip-address": "10.6.6.111",
                "hw-address": "AA:BB:CC:DD:EE:06",
                "hostname": "zeta",
                "subnet-id": 6,
                "cltt": now - 600,
                "valid-lft": 9000
            }
        ]
    
    url = f"{KEA_SERVER}/"
    headers = {"Content-Type": "application/json"}

    payload = {
        "command": "lease4-get-all",
        "service": ["dhcp4"]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raise an error for HTTP failures
        
        data = response.json()

        # Ensure the response contains lease data
        if isinstance(data, list) and len(data) > 0 and "arguments" in data[0]:
            return data[0]["arguments"].get("leases", [])
        
        return []
    
    except requests.RequestException as e:
        NotificationWindow(f"Error fetching leases:\n{str(e)}", "Error").exec()
        return []

def get_reservations_from_db():
    if DUMMY_DATA:
        return [
            {
                "ip-address": "10.1.1.240",
                "dhcp_identifier": "AABBCCDDEEF0",
                "hostname": "reserved-alpha",
                "subnet_id": 1
            },
            {
                "ip-address": "10.2.2.200",
                "dhcp_identifier": "AABBCCDDEEF1",
                "hostname": "reserved-beta",
                "subnet_id": 2
            },
            {
                "ip-address": "10.3.3.210",
                "dhcp_identifier": "AABBCCDDEEF2",
                "hostname": "reserved-gamma",
                "subnet_id": 3
            },
            {
                "ip-address": "10.4.4.220",
                "dhcp_identifier": "AABBCCDDEEF3",
                "hostname": "reserved-delta",
                "subnet_id": 4
            },
            {
                "ip-address": "10.5.5.230",
                "dhcp_identifier": "AABBCCDDEEF4",
                "hostname": "reserved-epsilon",
                "subnet_id": 5
            },
            {
                "ip-address": "10.6.6.250",
                "dhcp_identifier": "AABBCCDDEEF5",
                "hostname": "reserved-zeta",
                "subnet_id": 6
            }
        ]
    
    try:
        conn = pymysql.connect(
            host=MYSQL_CONFIG.get("host", "127.0.0.1"),
            user=MYSQL_CONFIG.get("user", "kea"),
            password=MYSQL_CONFIG.get("password", ""),
            database=MYSQL_CONFIG.get("database", "kea"),
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = conn.cursor()

        query = "SELECT dhcp_identifier, dhcp_identifier_type, INET_NTOA(ipv4_address) as ip_address FROM hosts"
        cursor.execute(query)
        reservations = cursor.fetchall()

        # Convert 'ip_address' to 'ip-address' to match lease API output
        formatted_reservations = [
            {"ip-address": res["ip_address"], "dhcp_identifier": res["dhcp_identifier"]}
            for res in reservations
        ]

        cursor.close()
        conn.close()
        return formatted_reservations

    except pymysql.connect.Error as e:
        debug_print(f"Error fetching leases from DB:\n{str(e)}")
        NotificationWindow(f"Error fetching leases from DB:\n{str(e)}", "Error").exec()
        return []
    
def add_reservation_to_db(ip_address, mac_address, hostname, subnet_id, parent=None):
    """
    Inserts a reservation into the Kea MySQL database.
    """
    if DUMMY_DATA:
        debug_print(f"[DUMMY] Skipping real DB insert for reservation {ip_address} → {mac_address}")
        NotificationWindow(f"[DUMMY MODE] Reservation added for {ip_address} (not really).", "Success", parent).exec()
        return True
    
    try:
        if not mac_address or mac_address.strip() == "":
            error_msg = f"[DEBUG] ERROR: MAC address is empty for {ip_address}"
            NotificationWindow(error_msg, "Error", parent).exec()
            return False

        # Convert MAC address to HEX format
        mac_binary = mac_address.replace(":", "").replace("-", "").upper().strip()

        if len(mac_binary) != 12 or not all(c in "0123456789ABCDEF" for c in mac_binary):
            error_msg = f"[DEBUG] ERROR: Invalid MAC address format -> {mac_binary}"
            NotificationWindow(error_msg, "Error", parent).exec()
            return False

        conn = pymysql.connect(
            host=MYSQL_CONFIG.get("host", "127.0.0.1"),
            user=MYSQL_CONFIG.get("user", "kea"),
            password=MYSQL_CONFIG.get("password", ""),
            database=MYSQL_CONFIG.get("database", "kea"),
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = conn.cursor()

        query = """
            INSERT INTO hosts (dhcp_identifier, dhcp_identifier_type, dhcp4_subnet_id, ipv4_address, hostname)
            VALUES (UNHEX(%s), 0, %s, INET_ATON(%s), %s)
            ON DUPLICATE KEY UPDATE hostname = VALUES(hostname), dhcp4_subnet_id = VALUES(dhcp4_subnet_id);
        """

        cursor.execute(query, (mac_binary, subnet_id, ip_address, hostname))
        conn.commit()

        rows_affected = cursor.rowcount

        cursor.close()
        conn.close()

        if rows_affected > 0:
            return True  # Success

        error_msg = f"[DEBUG] WARNING: No rows inserted for {ip_address}. Possible duplicate or invalid input."
        NotificationWindow(error_msg, "Warning", parent).exec()
        return False

    except pymysql.connector.Error as e:
        error_msg = f"[DEBUG] ERROR: MySQL Exception: {e}"
        NotificationWindow(error_msg, "Database Error", parent).exec()
        return False


def delete_reservation_from_db(ip_address, parent=None):
    """
    Deletes a reservation from the Kea database.
    """
    if DUMMY_DATA:
        debug_print(f"[DUMMY] Skipping real DB delete for {ip_address}")
        NotificationWindow(f"[DUMMY MODE] Reservation for {ip_address} deleted (not really).", "Success", parent).exec()
        return True
    
    try:
        conn = pymysql.connect(
            host=MYSQL_CONFIG.get("host", "127.0.0.1"),
            user=MYSQL_CONFIG.get("user", "kea"),
            password=MYSQL_CONFIG.get("password", ""),
            database=MYSQL_CONFIG.get("database", "kea"),
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = conn.cursor()

        query = "DELETE FROM hosts WHERE ipv4_address = INET_ATON(%s)"

        cursor.execute(query, (ip_address,))
        conn.commit()

        rows_deleted = cursor.rowcount

        cursor.close()
        conn.close()

        if rows_deleted > 0:
            return True
        else:
            NotificationWindow(f"No reservation found for {ip_address}.", "Warning", parent).exec()
            return False

    except pymysql.connector.Error as e:
        NotificationWindow(f"Error deleting reservation from DB: {e}", "Database Error", parent).exec()
        return False



def update_hostname(ip_address, hostname):
    """
    Updates the hostname for a reservation in the Kea database.
    """
    if DUMMY_DATA:
        debug_print(f"[DUMMY] Skipping real DB hostname update for {ip_address} → {hostname}")
        return True
    
    try:
        conn = pymysql.connect(
            host=MYSQL_CONFIG.get("host", "127.0.0.1"),
            user=MYSQL_CONFIG.get("user", "kea"),
            password=MYSQL_CONFIG.get("password", ""),
            database=MYSQL_CONFIG.get("database", "kea"),
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = conn.cursor()

        query = "UPDATE hosts SET hostname = %s WHERE ipv4_address = INET_ATON(%s)"
        cursor.execute(query, (hostname, ip_address))
        conn.commit()

        cursor.close()
        conn.close()
        return True

    except pymysql.connector.Error as e:
        NotificationWindow(f"Error updating hostname in DB:\n{str(e)}", "Error").exec()
        return False

def update_mac_address(ip_address, mac_address, parent=None):
    """
    Updates the MAC address for a reservation in the Kea database.
    The MAC address is stored in binary format using UNHEX().
    """
    if DUMMY_DATA:
        debug_print(f"[DUMMY] Skipping real MAC update for {ip_address} → {mac_address}")
        NotificationWindow(f"[DUMMY MODE] MAC address updated for {ip_address} (not really).", "Success", parent).exec()
        return True
    
    try:
        if not mac_address or mac_address.strip() == "":
            NotificationWindow(f"Error: MAC address is empty for {ip_address}", "Error", parent).exec()
            return False  # Prevent empty MAC addresses

        # Convert MAC address (format "00:1A:2B:3C:4D:5E") to "001A2B3C4D5E" for UNHEX
        mac_binary = mac_address.replace(":", "").replace("-", "").upper().strip()

        # Ensure MAC address is valid (must be 12 hex characters)
        if len(mac_binary) != 12 or not all(c in "0123456789ABCDEF" for c in mac_binary):
            NotificationWindow(f"Error: Invalid MAC address format for {ip_address} -> {mac_address}", "Error", parent).exec()
            return False

        conn = pymysql.connect(
            host=MYSQL_CONFIG.get("host", "127.0.0.1"),
            user=MYSQL_CONFIG.get("user", "kea"),
            password=MYSQL_CONFIG.get("password", ""),
            database=MYSQL_CONFIG.get("database", "kea"),
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = conn.cursor()

        query = "UPDATE hosts SET dhcp_identifier = UNHEX(%s) WHERE ipv4_address = INET_ATON(%s)"

        cursor.execute(query, (mac_binary, ip_address))
        conn.commit()

        rows_affected = cursor.rowcount

        cursor.close()
        conn.close()

        if rows_affected > 0:
            NotificationWindow(f"MAC address successfully updated for {ip_address}", "Success", parent).exec()
            return True
        else:
            NotificationWindow(f"No rows updated. Possible issue with IP {ip_address}", "Warning", parent).exec()
            return False

    except pymysql.connector.Error as e:
        NotificationWindow(f"Error updating MAC address in DB: {e}", "Database Error", parent).exec()
        return False
