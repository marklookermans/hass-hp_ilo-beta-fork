# HP Integrated Lights-Out (iLO) for Home Assistant 🚀

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
![Project Maintenance](https://img.shields.io/badge/maintainer-Mark%20Lookermans-blue.svg)
![Version](https://img.shields.io/badge/version-0.2.0-orange.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

An advanced, high-performance integration for monitoring and managing **HP ProLiant Servers** via iLO 3, 4, and 5. This fork is optimized for stability, speed, and deep Home Assistant integration.

---

## 🌟 Key Improvements

| Feature | Description |
| :--- | :--- |
| **High Frequency** | Real-time monitoring with a default **30-second polling interval**. |
| **Efficient** | Uses a `DataUpdateCoordinator` to fetch data in one batch, reducing iLO CPU load. |
| **Actionable** | Includes **Buttons** and **Services** for power management (Power On, Reboot, Shutdown). |
| **Modern** | Full support for **Config Flow** and **Auto-Discovery** (SSDP & Redfish). |

---

## 📦 Installation

### Option 1: HACS (Recommended)
1. Open **HACS** in Home Assistant.
2. Click the three dots (top right) → **Custom repositories**.
3. Paste this Repository URL and select **Integration** as the category.
4. Search for `HP Integrated Lights-Out` and click **Install**.
5. **Restart Home Assistant.**

### Option 2: Manual
1. Download the `hp_ilo` folder from `custom_components`.
2. Paste it into your `/config/custom_components/` directory.
3. **Restart Home Assistant.**

---

## 🚀 Setup & Discovery
Once installed, go to **Settings** → **Devices & Services** → **Add Integration** and search for **HP iLO**.

> [!TIP]
> **Auto-Discovery:** For the best experience, enable **SSDP/Discovery** in your iLO Web Interface. This allows Home Assistant to find your server automatically.



---

## 📊 Available Entities

### 🌡️ Monitoring (Sensors)
* **Environment:** Detailed temperature readings for CPU, Memory, I/O, and Ambient zones.
* **Cooling:** Fan speed percentages for all system fans.
* **Status:** Current Power State (ON/OFF) and Power-On time.

### ⚡ Control (Buttons)
The integration provides physical buttons on the device page for immediate action:
* **Power On:** Starts the server.
* **Reboot (Warm):** Triggers a warm restart (Soft Reset).
* **Shutdown (Graceful):** Signals the OS to shut down cleanly.
* **Shutdown (Hard):**
