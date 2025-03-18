# KEA DHCP Manager

## Overview

KEA DHCP Manager is a PyQt6-based GUI for managing [ISC Kea DHCP](https://kea.isc.org/) servers. It allows administrators to view active leases, add reservations, modify lease parameters, and interact with the Kea API and MySQL database.

⚠️ **This is an early version**—it works but is not fully featured yet. Feel free to contribute!

## Features

- View active DHCP leases in a table format
- Add, modify, and delete DHCP reservations
- Fetch leases and reservations from MySQL
- Interact with Kea API for subnet and lease modifications
- Dynamically adjust UI based on screen resolution

## Installation

### Prerequisites

- Python 3.8+
- Kea DHCP Server with API enabled
- MySQL database storing DHCP reservations

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configuration

Edit `config.json` to set up your Kea server and MySQL connection:

```json
{
    "WINDOW_SIZES": {
        "use_screen_resolution": true,
        "comment": "If use_screen_resolution is true, the below values will be ignored.",
        "main_window": { "x": 100, "y": 100, "width": 1500, "height": 800 },
        "leases_dialog": { "x": 200, "y": 150, "width": 100, "height": 800 }
    },

    "SPLITTER_SIZES": {
        "main_window": [350, 900]
    },

    "server_address": "http://dhcpservername.yourdomain",
    "server_port": 8000,

    "mysql": {
        "host": "192.168.0.2",
        "user": "kea",
        "password": "yourpassword",
        "database": "kea"
    },

    "debug": "YES"
}
```

## Usage

Run the application with:

```bash
python main.py
```

## License

This project is licensed under the MIT License—see [LICENSE](LICENSE) for details.

### Contributing

You are free to modify and improve this project, but please provide credit as per the MIT License.
