from PyQt6.QtWidgets import ( # type: ignore
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout
)
import kea_api
import re
import ipaddress
from notification_window import NotificationWindow
from config_loader import debug_print

class AddReservationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Reservation")
        self.setMinimumSize(300, 200)

        layout = QVBoxLayout(self)

        # Input fields
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("IP Address")
        self.mac_input = QLineEdit()
        self.mac_input.setPlaceholderText("MAC Address")
        self.hostname_input = QLineEdit()
        self.hostname_input.setPlaceholderText("Hostname (Optional)")
        self.subnet_input = QLineEdit()
        self.subnet_input.setPlaceholderText("Subnet ID")

        layout.addWidget(QLabel("IP Address:"))
        layout.addWidget(self.ip_input)
        layout.addWidget(QLabel("MAC Address:"))
        layout.addWidget(self.mac_input)
        layout.addWidget(QLabel("Hostname:"))
        layout.addWidget(self.hostname_input)
        layout.addWidget(QLabel("Subnet ID:"))
        layout.addWidget(self.subnet_input)

        # Buttons
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.add_reservation)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def add_reservation(self):
        """
        Calls `add_reservation_to_db` with user inputs.
        """
        ip_address = self.ip_input.text().strip()
        mac_address = self.mac_input.text().strip()
        hostname = self.hostname_input.text().strip()
        subnet_id = self.subnet_input.text().strip()

        debug_print(f"[DEBUG] Add Reservation clicked -> IP: {ip_address}, MAC: {mac_address}, Hostname: {hostname}, Subnet: {subnet_id}")

        if not ip_address or not mac_address or not subnet_id:
            debug_print(f"[DEBUG] ERROR: Missing required fields.")
            NotificationWindow("IP, MAC, and Subnet are required fields.", "Error", parent=self).exec()
            return  # Prevent function from continuing

        # Validate IP address format
        try:
            ipaddress.IPv4Address(ip_address)
        except ipaddress.AddressValueError:
            debug_print(f"[DEBUG] ERROR: Invalid IP address -> {ip_address}")
            NotificationWindow("Invalid IP address. Enter a valid IPv4 address (e.g., 192.168.1.100)", "Error", parent=self).exec()
            return

        # Ensure MAC address format is valid (XX:XX:XX:XX:XX:XX or XX-XX-XX-XX-XX-XX)
        if not re.match(r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$", mac_address):
            debug_print(f"[DEBUG] ERROR: Invalid MAC address format -> {mac_address}")
            NotificationWindow("Invalid MAC address format. Expected format: XX:XX:XX:XX:XX:XX or XX-XX-XX-XX-XX-XX", "Error", parent=self).exec()
            return

        # Convert MAC address to HEX format (normalize to colons `:` for consistency)
        mac_binary = mac_address.replace("-", ":").replace(":", "").upper().strip()

        success = kea_api.add_reservation_to_db(ip_address, mac_binary, hostname, subnet_id)

        debug_print(f"[DEBUG] add_reservation_to_db() returned: {success}")

        if success:
            debug_print(f"[DEBUG] SUCCESS: Reservation added.")
            NotificationWindow(f"Reservation added successfully for {ip_address}", "Success", parent=self).exec()
            self.accept()  # Close dialog on success
        else:
            debug_print(f"[DEBUG] ERROR: Failed to add reservation.")
            NotificationWindow(f"Failed to add reservation for {ip_address}", "Error", parent=self).exec()