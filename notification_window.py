from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton # type: ignore

class NotificationWindow(QDialog):
    def __init__(self, message, title="Notification", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(300, 150)

        layout = QVBoxLayout(self)

        # Message Label
        self.message_label = QLabel(message)
        layout.addWidget(self.message_label)

        # OK Button to Close
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)  # Close window when clicked
        layout.addWidget(self.ok_button)