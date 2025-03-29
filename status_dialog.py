from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QLabel, QHeaderView  # type: ignore
from PyQt6.QtGui import QColor  # type: ignore
from PyQt6.QtCore import Qt  # type: ignore
import kea_api

class StatusDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Server Status & Scope Utilization")
        self.setMinimumSize(900, 800)

        layout = QVBoxLayout(self)

        self.status_label = QLabel("Checking server status...")
        layout.addWidget(self.status_label)

        self.table = QTableWidget()
        layout.addWidget(self.table)

        self.update_status()

    def update_status(self):
        # Check if Kea server is reachable
        try:
            leases = kea_api.get_active_leases()
            server_up = True
        except:
            server_up = False

        if not server_up or leases is None:
            self.status_label.setText("❌ Kea DHCP Server is not responding.")
            return

        self.status_label.setText("✅ Kea DHCP Server is running.")

        subnets = kea_api.get_subnets()
        reservations = kea_api.get_reservations_from_db()

        self.table.setRowCount(len(subnets))
        headers = ["Subnet", "Subnet ID", "% Free", "# Free", "Total", "Leases", "Reservations"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        for row, subnet in enumerate(subnets):
            subnet_id = str(subnet["subnet_id"])
            cidr = subnet["subnet"]
            pool_ranges = subnet.get("pools", [])

            # Parse pool start/end
            total_ips = 0
            pool_start = pool_end = None
            for pool in pool_ranges:
                start, end = pool.split("-")
                start_int = int.from_bytes(map(int, start.split(".")), byteorder="big")
                end_int = int.from_bytes(map(int, end.split(".")), byteorder="big")
                total_ips += end_int - start_int + 1

            lease_count = sum(1 for l in leases if str(l.get("subnet-id")) == subnet_id)
            res_count = sum(1 for r in reservations if str(r.get("subnet_id", "")) == subnet_id)
            used = lease_count + res_count
            free = max(0, total_ips - used)
            percent_free = (free / total_ips) * 100 if total_ips else 0

            values = [cidr, subnet_id, f"{percent_free:.1f}%", str(free), str(total_ips), str(lease_count), str(res_count)]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                # Color code row based on % free
                if col == 2:
                    if percent_free < 10:
                        item.setBackground(QColor("#ffcccc"))  # Red
                    elif percent_free < 25:
                        item.setBackground(QColor("#fff3cd"))  # Yellow
                    else:
                        item.setBackground(QColor("#d4edda"))  # Green

                self.table.setItem(row, col, item)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
