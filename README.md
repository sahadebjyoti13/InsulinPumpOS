# InsulinPump OS

A clinical web dashboard for real-time monitoring and control of a closed-loop insulin infusion pump.

Built for doctors and clinical staff — no programming knowledge required to install or use.

**[⬇ Download for Windows](https://github.com/YOUR_USERNAME/InsulinPumpOS/releases/latest/download/InsulinPumpOS.zip)** · **[🌐 Open Landing Page](https://YOUR_USERNAME.github.io/InsulinPumpOS)**

---

## What it does

- **Live telemetry** — streams pump RPM, position, mode, and status in real time
- **CGM monitoring** — continuous glucose values on a rolling chart
- **Meal detection** — S** destabilisation index algorithm detects meal events from glucose dynamics and triggers an auto-bolus prompt
- **Remote device control** — send power, reset, basal rate, and bolus commands from the browser
- **Patient registry** — register and manage multiple pump devices
- **Historical data** — query any time range, plot any signal, export raw data

---

## For doctors and clinical staff

### What you need
- A Windows 10 or 11 computer (64-bit)
- Internet connection for first-time setup (~600 MB download, once only)
- 4 GB free disk space
- The insulin pump device connected to the same network

### First-time setup (run once)

1. Click the **Download for Windows** button above
2. Open the zip file and move the `InsulinPumpOS` folder to your Desktop
3. Open the folder and double-click **`install.bat`**
4. The installer handles everything automatically:
   - Installs required system components
   - Downloads and sets up Docker Desktop
   - Starts all services (database, broker, web app)
   - Opens the dashboard in your browser
5. If your computer restarts during setup, the installer resumes on its own — you do not need to do anything

> **First run takes 5–10 minutes.** After that, the system starts in under 15 seconds.

### Every day

| Action | What to do |
|--------|-----------|
| Start the system | Double-click `start.bat` |
| Open the dashboard | Browser opens automatically, or go to `http://localhost:8501` |
| Stop the system | Double-click `stop.bat` |

Your data is always saved between sessions.

---

## Architecture

```
Insulin Pump + CGM Sensor
        │
        │  MQTT (port 1883)
        ▼
  Mosquitto Broker  ──────────────────────────────┐
        │                                          │
        ▼                                          ▼
   Backend (Python)                        Streamlit Web UI
        │                                  (localhost:8501)
        ├──▶ PostgreSQL  (patient registry)
        └──▶ InfluxDB    (telemetry history)
```

### Components

| Service | Role | Technology |
|---------|------|-----------|
| Web UI | Dashboard, charts, controls | Streamlit + Plotly |
| Message broker | Real-time device communication | Mosquitto MQTT |
| Patient registry | Device and patient records | PostgreSQL |
| Telemetry store | Time-series signal history | InfluxDB v2 |
| Meal detection | S** destabilisation index | Python (custom) |

All four services run as Docker containers — no manual database setup needed.

---

## MQTT Topics

| Topic | Direction | Purpose |
|-------|-----------|---------|
| `medical/pump/{device_id}/data` | Device → App | Pump telemetry (RPM, position, status) |
| `medical/pump/{device_id}/cgm` | Sensor → App | Glucose readings |
| `medical/pump/{device_id}/host` | App → Device | Commands (power, basal, bolus) |

### Example payloads

**Pump telemetry (`/data`):**
```json
{
  "device_id": "CIIP003",
  "actual_rpm": 12.4,
  "position_deg": 180.58,
  "status": "running",
  "mode": "BASAL"
}
```

**CGM (`/cgm`):**
```json
{
  "device_id": "CIIP003",
  "timestamp": "2026-06-15T10:02:52",
  "glucose": 94.2,
  "trend": 1.1,
  "status": "OK"
}
```

---

## Repository structure

```
InsulinPumpOS/
│   index.html              Landing page (GitHub Pages)
│   README.md
│   docker-compose.yml      Full stack definition
│   install.bat             Windows one-click installer
│   install.sh              Linux / macOS installer
│   start.bat               Daily start script
│   stop.bat                Daily stop script
│   SETUP_GUIDE.md          Detailed guide for IT administrators
│
├───config/
│       mosquitto.conf      MQTT broker configuration
│
└───WebApp/
        app.py              Streamlit frontend
        backend.py          Database + MQTT services
        setup_wizard.py     In-app configuration wizard
        mealdetection.py    Meal detection service layer
        meal_detection_algo.py  S** algorithm implementation
        Dockerfile
        requirements.txt
        streamlit_config.toml
```

---

## For developers and IT administrators

### Running without Docker (bare metal)

Install dependencies:
```bash
pip install streamlit pandas numpy plotly psycopg2-binary influxdb-client paho-mqtt
```

Start required services manually (PostgreSQL, InfluxDB, Mosquitto), then:
```bash
cd WebApp
streamlit run app.py
```

### Configuration

All connection settings are read from environment variables (set automatically by Docker Compose). For custom deployments, edit the variables in `docker-compose.yml` under the `webapp` service — no source code changes needed.

| Variable | Default | Description |
|----------|---------|-------------|
| `MQTT_BROKER` | `mosquitto` | MQTT broker hostname |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `PG_HOST` | `postgres` | PostgreSQL host |
| `PG_DB` | `med_db` | Database name |
| `INFLUX_URL` | `http://influxdb:8086` | InfluxDB endpoint |
| `INFLUX_ORG` | `InsulinPumpOS` | InfluxDB organisation |
| `INFLUX_BUCKET` | `telemetry` | InfluxDB bucket |

Settings can also be changed from within the app under **Settings → System Configuration**.

### Useful commands

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# View logs
docker compose logs -f

# Restart just the web app
docker compose restart webapp

# Check service health
docker compose ps
```

### Data backup

```bash
# Backup patient registry
docker run --rm \
  -v insulinpumpos_postgres_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/postgres_backup.tar.gz /data

# Backup telemetry
docker run --rm \
  -v insulinpumpos_influx_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/influx_backup.tar.gz /data
```

### Ports used

| Port | Service |
|------|---------|
| 8501 | Web dashboard |
| 1883 | MQTT broker |
| 5432 | PostgreSQL |
| 8086 | InfluxDB |

---

## Troubleshooting

**MQTT shows OFFLINE in the dashboard**
The broker container is running but the connection handshake is still completing. Click **Reset Backend (MQTT)** in the sidebar, or wait 10 seconds and refresh the page.

**App not loading after install**
Wait 60 seconds — services need time to initialise on first run. Then open `http://localhost:8501`.

**Docker Desktop won't start**
Make sure WSL2 is installed: open PowerShell as Administrator and run `wsl --install`, then restart your computer.

**History shows no data**
Check that your device is publishing to the correct MQTT topic and that the time range you selected matches when the device was actually running.

---

## Meal Detection Algorithm

Meal detection uses the **S\*\* (S-star-star) destabilisation index** — a signal-processing approach that detects structural changes in glucose dynamics rather than relying on simple threshold crossings. This makes it sensitive to meal events even when absolute glucose values are within normal range.

When a meal is detected:
1. A warning banner appears on the Live Monitor page
2. If a bolus dose has been saved previously, it is delivered automatically
3. If no saved dose exists, the Device Control page prompts the user to enter and approve one

---

## Disclaimer

This is a **research prototype** developed at IIEST Shibpur. It is not a certified medical device and is not approved for clinical use. Do not use for actual patient treatment without appropriate regulatory approval and clinical validation.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
