from PyQt6.QtWidgets import ( # type: ignore
    QMainWindow, QVBoxLayout, QWidget,
    QTreeWidget, QTreeWidgetItem, QSplitter, QMenu, QInputDialog
)
from PyQt6.QtGui import QAction # type: ignore
from PyQt6.QtCore import Qt # type: ignore
from show_leases_dialog import ShowLeasesDialog  # New leases window
from add_reservation_dialog import AddReservationDialog  # New reservation dialog
from config_loader import WINDOW_SIZES, SPLITTER_SIZES, debug_print
import sys
import kea_api

class DHCPManager(QMainWindow):
    def __init__(self):
        super().__init__()

        debug_print("DEBUG: Initializing DHCPManager...")

        # Use TreeViewDialog as the main UI
        self.tree_window = TreeViewDialog(self)
        self.setCentralWidget(self.tree_window)  # Make sure this is set!

        self.setWindowTitle("KEA DHCP Manager")
        #self.setGeometry(100, 100, 1000, 600)
        main_window_settings = WINDOW_SIZES.get("main_window", {})
        x = main_window_settings.get("x", 100)
        y = main_window_settings.get("y", 100)
        width = main_window_settings.get("width", 1000)
        height = main_window_settings.get("height", 600)

        self.setGeometry(x, y, width, height)

        # Make sure the window actually appears!
        self.tree_window.show()
        debug_print("DEBUG: TreeViewDialog should now be visible.")

    def closeEvent(self, event):
        """Ensures proper cleanup on exit."""
        debug_print("DEBUG: DHCPManager closing...")
        event.accept()

class TreeViewDialog(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        debug_print("DEBUG: Initializing TreeViewDialog...")

        self.setWindowTitle("DHCP Manager - Tree View")

        # Splitter: Left = Tree View, Right = Leases Table
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Panel: Tree Widget
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["DHCP Scopes"])
        self.tree_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_widget.itemClicked.connect(self.handle_tree_click)  # Detect clicks
        self.splitter.addWidget(self.tree_widget)
        # Connect custom context menu
        self.tree_widget.customContextMenuRequested.connect(self.create_context_menu)

        # Right Panel: Lease Table (Embedded)
        self.leases_dialog = ShowLeasesDialog(self)
        self.leases_dialog.setWindowFlags(Qt.WindowType.Widget)  # Make it an embedded widget
        self.splitter.addWidget(self.leases_dialog)

        # Set initial splitter sizes
        splitter_sizes = SPLITTER_SIZES.get("main_window", [400, 700])

        # Apply splitter sizes
        self.splitter.setSizes(splitter_sizes)


        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.splitter)

        # Ensure `load_subnets()` runs AFTER layout is set up
        self.show()  # Ensure widget is visible
        debug_print("DEBUG: Calling load_subnets()...")
        self.load_subnets()  # Load subnets immediately

    
    def force_close(self):
        """Ensures both the tree view and the leases dialog close together."""
        debug_print("DEBUG: Close button clicked, forcing full shutdown")
        
        if self.leases_dialog:
            debug_print("DEBUG: Closing leases dialog from force_close()")
            self.leases_dialog.setParent(None)  
            self.leases_dialog.close()
            self.leases_dialog.deleteLater()
            self.leases_dialog = None  

        self.close()

    def quit_app(self):
        """Closes the entire application."""
        debug_print("DEBUG: Quit button clicked. Exiting application...")
        self.close()  # Close TreeViewDialog
        sys.exit(0)  # Fully exit the program

        
    def closeEvent(self, event):
        """Ensures TreeViewDialog and leases dialog close cleanly without leaving an orphan window."""
        debug_print("DEBUG: closeEvent() triggered")

        if self.leases_dialog:
            debug_print("DEBUG: Closing leases dialog...")
            self.leases_dialog.setParent(None)  # Detach from parent first
            self.leases_dialog.close()  
            self.leases_dialog.deleteLater()  # Ensure it gets destroyed
            self.leases_dialog = None  

        if self.parent():
            if hasattr(self.parent(), "tree_window"):
                debug_print("DEBUG: Clearing parent reference to tree_window")
                setattr(self.parent(), "tree_window", None)  

        debug_print("DEBUG: TreeViewDialog has fully closed.")
        event.accept()

    def load_subnets(self):
        """Loads subnets and their details into the tree view."""
        debug_print("DEBUG: Calling load_subnets()...")
        
        subnets = kea_api.get_subnets()
        leases = kea_api.get_active_leases()
        reservations = kea_api.get_reservations_from_db()

        self.tree_widget.clear()

        for subnet in subnets:
            subnet_id = str(subnet.get("subnet_id", "Unknown ID"))
            subnet_cidr = subnet.get("subnet", "Unknown Subnet")
            formatted_text = f"{subnet_cidr} (ID: {subnet_id})"

            subnet_item = QTreeWidgetItem([formatted_text])
            subnet_item.setData(0, Qt.ItemDataRole.UserRole, subnet_id)
            self.tree_widget.addTopLevelItem(subnet_item)

            # Add Leases Node (Shows Leases + Reservations)
            leases_item = QTreeWidgetItem(["Leases"])
            leases_item.setData(0, Qt.ItemDataRole.UserRole, f"leases_{subnet_id}")
            subnet_item.addChild(leases_item)

            for lease in leases:
                if str(lease.get("subnet_id")) == subnet_id:
                    lease_text = f"{lease.get('ip-address', 'Unknown')} → {lease.get('hw-address', 'Unknown')}"
                    lease_item = QTreeWidgetItem([lease_text])
                    lease_item.setData(0, Qt.ItemDataRole.UserRole, "lease")
                    leases_item.addChild(lease_item)

            for res in reservations:
                if str(res.get("subnet_id")) == subnet_id:
                    res_text = f"{res.get('ip-address', 'Unknown')} → {res.get('dhcp_identifier', 'Unknown')} (Res.)"
                    res_item = QTreeWidgetItem([res_text])
                    res_item.setData(0, Qt.ItemDataRole.UserRole, "reservation")
                    leases_item.addChild(res_item)

            # Add Pool Information (Prevent crash)
            pool_text = f"Pool: {', '.join(subnet.get('pools', []))}"
            pool_item = QTreeWidgetItem([pool_text])
            pool_item.setData(0, Qt.ItemDataRole.UserRole, None)  # Prevent crash
            subnet_item.addChild(pool_item)

            # Add Lease Time (Prevent crash)
            lease_time_text = f"Lease Time: {subnet.get('valid_lifetime', 'N/A')} sec"
            lease_time_item = QTreeWidgetItem([lease_time_text])
            lease_time_item.setData(0, Qt.ItemDataRole.UserRole, None)  # Prevent crash
            subnet_item.addChild(lease_time_item)

        self.tree_widget.repaint()  # Ensure UI refresh


    def handle_tree_click(self, item):
        """Handles clicks on tree nodes, including 'Add Reservation'."""
        selected_type = item.data(0, Qt.ItemDataRole.UserRole)

        if selected_type is None:
            return  # Prevent crashes on non-interactive items (e.g., Lease Time, Pool)

        if selected_type.isdigit():  # Clicked a subnet (scope)
            subnet_id = selected_type
            self.leases_dialog.load_leases(subnet_id)
            self.leases_dialog.show()

        elif selected_type.startswith("leases_"):  # Clicked "Leases"
            subnet_id = selected_type.split("_")[1]
            self.leases_dialog.load_leases(subnet_id)
            self.leases_dialog.show()


    def show_reservations(self, subnet_id):
        """Displays only reservations for the selected subnet in the table view."""
        all_reservations = kea_api.get_reservations_from_db()
        filtered_reservations = [res for res in all_reservations if str(res.get("subnet_id")) == str(subnet_id)]
        self.leases_dialog.load_reservations(filtered_reservations)

    def show_leases(self, subnet_id):
        """Displays only leases for the selected subnet in the table view."""
        all_leases = kea_api.get_active_leases()
        filtered_leases = [lease for lease in all_leases if str(lease.get("subnet_id")) == str(subnet_id)]
        self.leases_dialog.load_leases(filtered_leases)

    def create_context_menu(self, pos):
        item = self.tree_widget.itemAt(pos)
        if not item:
            return

        menu = QMenu(self.tree_widget)

        # Add "Add Reservation" option if clicked on a subnet
        if item.data(0, Qt.ItemDataRole.UserRole) and item.data(0, Qt.ItemDataRole.UserRole).isdigit():
            add_reservation_action = QAction("Add Reservation", self)
            add_reservation_action.triggered.connect(lambda: self.open_add_reservation_dialog(item.data(0, Qt.ItemDataRole.UserRole)))
            menu.addAction(add_reservation_action)

        item_text = item.text(0)
        # If the item is a subnet (contains "ID:")
        if "ID:" in item_text:
            change_lifetime_action = QAction("Change Lease Time", self.tree_widget)
            change_pool_action = QAction("Change Pool Range", self.tree_widget)

            change_lifetime_action.triggered.connect(lambda: self.change_lease_time(item))
            change_pool_action.triggered.connect(lambda: self.change_pool_range(item))

            menu.addAction(change_lifetime_action)
            menu.addAction(change_pool_action)

        # If the item is a lease time entry
        elif "Lease Time:" in item_text:
            change_lifetime_action = QAction("Change Lease Time", self.tree_widget)
            change_lifetime_action.triggered.connect(lambda: self.change_lease_time(item))
            menu.addAction(change_lifetime_action)

        # If the item is a pool entry
        elif "Pool:" in item_text:
            change_pool_action = QAction("Change Pool Range", self.tree_widget)
            change_pool_action.triggered.connect(lambda: self.change_pool_range(item))
            menu.addAction(change_pool_action)

        if not menu.isEmpty():
            menu.exec(self.tree_widget.viewport().mapToGlobal(pos))

    def open_add_reservation_dialog(self, subnet_id):
        """Opens the Add Reservation dialog and prefills the subnet ID."""
        dialog = AddReservationDialog(self)
        dialog.subnet_input.setText(str(subnet_id))  # Pre-fill subnet
        dialog.subnet_input.setReadOnly(True)
        if dialog.exec():
          self.load_subnets()
          self.leases_dialog.refresh_leases()

    def change_lease_time(self, item):
        subnet_id = item.parent().data(0, Qt.ItemDataRole.UserRole)  # Get the parent subnet ID
        new_lifetime_hours, ok = QInputDialog.getInt(self, "Change Lease Time", "Enter new lease time (hours):", 1, 1, 9999)
        if ok:
            kea_api.update_subnet_lifetime(subnet_id, new_lifetime_hours * 3600)  # Convert to seconds
            self.load_subnets()  # **Manually reload the subnets**
    
    def change_pool_range(self, item):
        subnet_text = item.parent().text(0)  # Get subnet text (e.g., "192.168.1.0/24 (ID: 1)")
        subnet_id = item.parent().data(0, Qt.ItemDataRole.UserRole)  # Get the subnet ID

        # Extract the first three octets from the subnet
        base_ip = subnet_text.split(" ")[0].rsplit(".", 1)[0]  # Get "192.168.1"

        # Get user input (allowing only the last octet)
        start_octet, ok1 = QInputDialog.getInt(self, "Change Pool Range", f"Enter the starting octet (e.g., 20) for {base_ip}.XX:", 20, 1, 254)
        if not ok1:
            return

        end_octet, ok2 = QInputDialog.getInt(self, "Change Pool Range", f"Enter the ending octet (e.g., 240) for {base_ip}.XX:", 240, start_octet + 1, 254)
        if not ok2:
            return

        new_pool_range = f"{base_ip}.{start_octet}-{base_ip}.{end_octet}"

        #(f"Updating pool range for subnet {subnet_id} to {new_pool_range}")
        kea_api.update_subnet_pool(subnet_id, new_pool_range)
        debug_print("Finished updating, now refreshing the tree view...")

        self.load_subnets()  # Reload tree
        self.tree_widget.repaint()


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication # type: ignore
    app = QApplication(sys.argv)
    window = DHCPManager()
    window.show()    
    sys.exit(app.exec())