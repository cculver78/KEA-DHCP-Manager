from PyQt6.QtWidgets import QApplication  # type: ignore
from dhcp_manager import DHCPManager
import sys
from config_loader import CONFIG, DEBUG, KEA_SERVER, MYSQL_CONFIG, WINDOW_SIZES, apply_dynamic_window_sizes  # Import global config


if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_dynamic_window_sizes()
    window = DHCPManager()
    
    window.show()

    sys.exit(app.exec())