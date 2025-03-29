from PyQt6.QtWidgets import (  # type: ignore
    QHBoxLayout, QLineEdit, QDialog, QVBoxLayout, QTableWidget, 
    QTableWidgetItem, QPushButton, QHeaderView, QMenu
)
from PyQt6.QtCore import Qt  # type: ignore
import datetime
import time
import sys
import kea_api
from PyQt6.QtGui import QGuiApplication  # type: ignore
from notification_window import NotificationWindow
from config_loader import WINDOW_SIZES, debug_print


class ShowLeasesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Active Leases")

        # Set the initial window size
        lease_window_settings = WINDOW_SIZES.get("leases_dialog", {})
        x = lease_window_settings.get("x", 200)
        y = lease_window_settings.get("y", 150)
        width = lease_window_settings.get("width", 1000)
        height = lease_window_settings.get("height", 900)
        self.setMinimumSize(800, 400)
        self.setGeometry(x, y, width, height)

        self.layout = QVBoxLayout(self)

        # Filter Layout
        self.filter_layout = QHBoxLayout()
        self.filters = []
        column_headers = ["IP Address", "MAC Address", "Hostname", "Lease Expiration", "Subnet ID"]

        for header in column_headers:
            filter_input = QLineEdit()
            filter_input.setPlaceholderText(f"Filter {header}...")
            filter_input.textChanged.connect(self.apply_filters)  # Apply filter when text changes
            self.filter_layout.addWidget(filter_input)
            self.filters.append(filter_input)

        self.layout.addLayout(self.filter_layout)

        # Table widget
        self.table = QTableWidget()
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.layout.addWidget(self.table)

        # Create the buttons first before adding them to the layout
        #self.reset_filters_button = QPushButton("Reset Filters")
        #self.reset_filters_button.clicked.connect(self.reset_filters)

        #self.refresh_button = QPushButton("Refresh View")
        #self.refresh_button.clicked.connect(self.refresh_leases)

        #self.quit_button = QPushButton("Quit")
        #self.quit_button.clicked.connect(self.quit_app)            MOVED THESE BUTTONS TO THE MAIN PORTION OF THE WINDOW

        # Create a horizontal layout for buttons
        #self.button_layout = QHBoxLayout()
        #self.button_layout.addWidget(self.reset_filters_button)
        #self.button_layout.addWidget(self.refresh_button)
        #self.button_layout.addWidget(self.quit_button)

        # Add the button layout at the bottom
        #self.layout.addLayout(self.button_layout)

        # Load data initially
        self.load_leases()

    def refresh_leases(self):
        """Refreshes the leases table without clearing data or filters."""

        # Keep the currently applied subnet filter (if any)
        if self.filters[4].text().strip():  # Assuming the Subnet ID filter is at index 4
            selected_subnet_id = self.filters[4].text().strip()
        else:
            selected_subnet_id = None  # No active filter

        # Reload the leases with the selected subnet filter
        self.load_leases(selected_subnet_id)

        # Ensure filters remain applied (avoid clearing them)
        self.apply_filters()

    
    def reset_filters(self):
        """Clears all filters and refreshes the table to show all data."""
        
        # Clear all input filters
        for filter_input in self.filters:
            filter_input.clear()

        # Reload leases with no subnet filter (show all data)
        self.load_leases(subnet_id=None)  

        # Ensure filters apply correctly (this is redundant but safe)
        self.apply_filters()


    def load_leases(self, subnet_id=None):
        leases = kea_api.get_active_leases()
        if subnet_id is not None:
            leases = [lease for lease in leases if str(lease.get("subnet-id")) == str(subnet_id)]

        reservations = kea_api.get_reservations_from_db()  # Fetch reservations separately

        # Convert reservations to a dictionary for quick lookup
        self.reserved_ips = {res["ip-address"]: res for res in reservations}

        # Ensure reservations without active leases are included
        all_ips = sorted(set(lease["ip-address"] for lease in leases) | 
                 {ip for ip, res in self.reserved_ips.items() if res.get("subnet-id") == str(subnet_id) or subnet_id is None})

        # Reset sorting to avoid mismatches
        self.table.setSortingEnabled(False)  # Disable sorting before reloading data

        if all_ips:
            headers = ["IP Address", "MAC Address", "Hostname", "Lease Expiration", "Subnet ID", "Reservation"]
            self.table.setColumnCount(len(headers))
            self.table.setRowCount(len(all_ips))
            self.table.setHorizontalHeaderLabels(headers)

            # Prevent event firing during load
            try:
                self.table.cellChanged.disconnect(self.handle_cell_edit)
            except TypeError:
                pass  # Ignore if the signal is not connected yet

            # Dictionary to track correct row placement
            row_map = {}  

            for row, ip_address in enumerate(all_ips):
                lease = next((lease for lease in leases if lease["ip-address"] == ip_address), {})
                reservation = self.reserved_ips.get(ip_address, {})

                # Ensure correct MAC address selection
                if reservation and "dhcp_identifier" in reservation:
                    hw_address = reservation["dhcp_identifier"]  # Use reserved MAC if available
                else:
                    hw_address = lease.get("hw-address", "")

                # Ensure correct hostname selection
                if reservation and "hostname" in reservation:
                    hostname = reservation["hostname"]
                else:
                    hostname = lease.get("hostname", "N/A")

                lease_subnet_id = str(lease.get("subnet-id", "N/A"))  # Avoid overwriting `subnet_id` argument

                # Calculate expiration time
                cltt = lease.get("cltt", 0)
                valid_lft = lease.get("valid-lft", 0)
                expire_time = cltt + valid_lft if cltt and valid_lft else 0
                expire_str = datetime.datetime.utcfromtimestamp(expire_time).strftime('%Y-%m-%d %H:%M:%S') if expire_time > 0 else "N/A"

                # Ensure MAC address is properly formatted
                if isinstance(hw_address, bytes):
                    hw_address = ":".join(f"{b:02X}" for b in hw_address)

                row_map[ip_address] = row  # Track correct row index

                # Check if this lease is a reservation
                is_reserved = ip_address in self.reserved_ips

                for col, value in enumerate([ip_address, hw_address, hostname, expire_str, lease_subnet_id]):
                    item = QTableWidgetItem(str(value))

                    # Allow editing on:
                    # - Hostname column (index 2)
                    # - MAC Address column (index 1) **only if it is a reservation**
                    if col == 2 or (col == 1 and is_reserved):
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)  # Enable editing
                    else:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Keep read-only

                    self.table.setItem(row, col, item)

                # Add checkmark for reservations
                reservation_checkbox = QTableWidgetItem("✅" if is_reserved else "")
                reservation_checkbox.setFlags(reservation_checkbox.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 5, reservation_checkbox)

            self.table.cellChanged.connect(self.handle_cell_edit)  # Reconnect after load

            # Enable sorting after reloading data
            self.table.setSortingEnabled(True)

            # Automatically resize columns dynamically
            header = self.table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        else:
            self.table.setRowCount(0)

    def filter_subnet(self, subnet_id):
        """Filters the table to only show leases or reservations for the selected subnet."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 4)  # Subnet ID column
            if item and item.text() == subnet_id:
                self.table.setRowHidden(row, False)  # Show matching rows
            else:
                self.table.setRowHidden(row, True)  # Hide non-matching rows


    def apply_filters(self):
        """
        Filters the table based on input fields above each column.
        """
        for row in range(self.table.rowCount()):
            self.table.setRowHidden(row, False)  # Reset row visibility

            for col, filter_input in enumerate(self.filters):
                filter_text = filter_input.text().strip().lower()
                cell_text = self.table.item(row, col).text().strip().lower() if self.table.item(row, col) else ""

                # Hide row if it doesn't match the filter
                if filter_text and filter_text not in cell_text:
                    self.table.setRowHidden(row, True)
                    break  # No need to check other columns if one fails

    def show_context_menu(self, position):
        """
        Displays a right-click context menu with Copy, Convert to Reservation, and Delete Reservation options.
        """
        menu = QMenu()
        copy_action = menu.addAction("Copy")
        convert_action = menu.addAction("Convert to Reservation")
        delete_action = menu.addAction("Delete Reservation")

        selected_item = self.table.itemAt(position)
        if not selected_item:
            return

        row = selected_item.row()
        ip_address = self.table.item(row, 0).text() if self.table.item(row, 0) else ""

        # Enable/Disable options based on reservation status
        is_reserved = ip_address in self.reserved_ips
        convert_action.setEnabled(not is_reserved)
        delete_action.setEnabled(is_reserved)

        action = menu.exec(self.table.viewport().mapToGlobal(position))

        if action == copy_action:
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(selected_item.text())

        elif action == convert_action:
            self.convert_to_reservation(ip_address)

        elif action == delete_action:
            self.delete_reservation(ip_address)


    def convert_to_reservation(self, ip_address):
        """
        Converts a lease to a reservation in the MySQL database.
        """
        if not ip_address:
            return

        # Prevent duplicate execution
        if ip_address in self.reserved_ips:
            NotificationWindow(f"{ip_address} is already a reservation.", "Info", parent=self).exec()
            return

        # Get lease details
        row = None
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0) and self.table.item(r, 0).text() == ip_address:
                row = r
                break

        if row is None:
            NotificationWindow(f"Failed to find lease for {ip_address}", "Error", parent=self).exec()
            return

        mac_address = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
        hostname = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
        subnet_id = self.table.item(row, 4).text() if self.table.item(row, 4) else ""

        # Call MySQL function to add reservation
        success = kea_api.add_reservation_to_db(ip_address, mac_address, hostname, subnet_id)

        if success:
            for attempt in range(5):  # Retry up to 5 times
                time.sleep(0.5)  # Wait before checking DB
                self.reserved_ips = {res["ip-address"]: res for res in kea_api.get_reservations_from_db()}

                if ip_address in self.reserved_ips:
                    break  # Exit loop if reservation is found

            if ip_address in self.reserved_ips:  # Double-check it was added
                # Temporarily disable `cellChanged` to prevent unwanted database updates
                self.table.cellChanged.disconnect(self.handle_cell_edit)

                # Update UI to reflect reservation
                self.reserved_ips[ip_address] = True
                reservation_checkbox = QTableWidgetItem("✅")
                reservation_checkbox.setFlags(reservation_checkbox.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 5, reservation_checkbox)

                # Reconnect the signal after UI updates are done
                self.table.cellChanged.connect(self.handle_cell_edit)

                NotificationWindow(f"Reservation successfully added for {ip_address}", "Success", parent=self).exec()
                return
            else:
                NotificationWindow(f"Failed to verify reservation for {ip_address}.", "Error", parent=self).exec()
                return

        NotificationWindow(f"Failed to add reservation for {ip_address}.", "Error", parent=self).exec()

    def delete_reservation(self, ip_address):
        """
        Deletes a reservation and updates the UI.
        """
        if not ip_address:
            return

        # Prevent duplicate deletions
        if ip_address not in self.reserved_ips:
            NotificationWindow(f"{ip_address} is not a reservation.", "Info", parent=self).exec()
            return

        success = kea_api.delete_reservation_from_db(ip_address, parent=self)

        if success:
            # Find the row in the table
            row = None
            for r in range(self.table.rowCount()):
                if self.table.item(r, 0) and self.table.item(r, 0).text() == ip_address:
                    row = r
                    break

            if row is not None:
                # Prevent the cellChanged event from triggering another DB update
                self.table.cellChanged.disconnect(self.handle_cell_edit)

                # Remove from reserved IPs BEFORE refreshing
                self.reserved_ips.pop(ip_address, None)

                # Remove checkmark from UI
                self.table.setItem(row, 5, QTableWidgetItem(""))

                # Reconnect the signal after UI changes are done
                self.table.cellChanged.connect(self.handle_cell_edit)

                # Show success notification ONLY here
                NotificationWindow(f"Reservation for {ip_address} successfully deleted.", "Success", parent=self).exec()

            return  # Ensure no additional processing occurs


    def handle_cell_edit(self, row, column):
        """
        Handles edits to the MAC address and hostname columns, updating the MySQL database.
        """
        ip_address = self.table.item(row, 0).text()
        new_value = self.table.item(row, column).text().strip()

        if not ip_address:
            return

        success = False  # Default to failure

        if column == 2:  # Hostname Column
            success = kea_api.update_hostname(ip_address, new_value)

        elif column == 1:  # MAC Address Column (only for reservations)
            if ip_address in self.reserved_ips:
                success = kea_api.update_mac_address(ip_address, new_value)
            else:
                return  # Ignore changes if it's not a reservation

        if success:
            NotificationWindow(f"Successfully updated {ip_address}", "Success", parent=self).exec()
        else:
            NotificationWindow(f"Failed to update database for {ip_address}", "Error", parent=self).exec()
    
    def quit_app(self):
        """Closes the entire application."""
        debug_print("DEBUG: Quit button clicked. Exiting application...")

        self.close()  # Close the dialog
        sys.exit(0)  # Fully exit

