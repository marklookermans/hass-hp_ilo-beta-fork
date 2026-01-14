HP Integrated Lights-Out (iLO) for Home Assistant 🚀
This integration is an optimized fork designed to bring modern Home Assistant features to HP ProLiant servers. It supports iLO 3, 4, and 5 via a combination of the Redfish API and the legacy HP-iLO protocol.

✨ Key Features
Smart Polling: Uses a DataUpdateCoordinator to fetch all server metrics in a single batch, preventing iLO CPU exhaustion.

30s Update Interval: High-resolution monitoring for temperatures and fan speeds.

Full Power Control: Manage server power states directly from the UI or via automations.

Modern Config Flow: Easy setup via the integrations menu—no YAML configuration required.

Auto-Discovery: Detects servers automatically on your network using SSDP and Redfish.

🛠 Installation
Open HACS in your Home Assistant instance.

Click the three dots in the top right corner and select Custom repositories.

Add the URL of this repository and select Integration as the category.

Search for HP Integrated Lights-Out (iLO) and click install.

Restart Home Assistant.

Navigate to Settings > Devices & Services and click Add Integration to configure your server.

📊 Supported Entities
Sensors
Temperature: Real-time data for CPU, Memory, Ambient, and I/O zones.

Fans: Speed percentage for all installed system fans.

Power Status: Reports the current host power state (ON/OFF).

Power On Time: Cumulative server uptime in minutes.

Buttons (Physical Actions)
Power On: Boots the server if it is powered off.

Reboot (Warm): Sends a reset signal (simulates Ctrl+Alt+Del).

Shutdown (Graceful): "Presses" the power button (signals the OS to shut down cleanly).

Shutdown (Hard): Press & Hold action (simulates holding the button for 4 seconds) to force power-off.

⚡ Services
This integration registers services for use in scripts and automations:

hp_ilo.power_on

hp_ilo.reboot_server

hp_ilo.shutdown_graceful

hp_ilo.shutdown_hard (Press & Hold)

⚙️ Technical Details
This integration relies on two core Python libraries to communicate with your hardware:

python-hpilo: Used for legacy RIBCL communication. This handles the specific "Press & Hold" power actions and health data on older iLO versions.

python-redfish-library: Used during the discovery and configuration phase to identify modern iLO 5+ capabilities.

Polling Architecture
To protect the often-limited resources of the iLO management chip, this integration uses a centralized coordinator. Instead of each sensor (Temp, Fan, Power) asking the iLO for data independently, the coordinator performs one request every 30 seconds and distributes the data to all entities simultaneously.

🔍 Discovery Setup
To enable Auto-Discovery, ensure that SSDP/Discovery is enabled in your iLO Web Interface:

🚧 Roadmap
[x] Redfish-based Discovery.

[x] Power Button Entity (with Press & Hold fix).

[x] Centralized Data Caching.

[ ] Binary Sensor for Global Health (Healthy/Critical).

[ ] Firmware Update available notification.

Credits
Based on the original work by chkuendig/hass-hp_ilo-beta and the Home Assistant core contributors.
