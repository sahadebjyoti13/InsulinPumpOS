# InsulinPump OS — Clinical Setup Guide

**For clinical staff and IT administrators. No programming knowledge required.**

---

## What You Need

- A computer running **Windows 10/11**, **macOS**, or **Linux**
- **Docker Desktop** (free) — this is the only software you need to install manually
- An internet connection for the first-time setup (to download components)

---

## Step 1 — Install Docker Desktop

Docker is a tool that runs all the system components automatically, without you needing to install databases or configure servers.

| Your Computer | Download Link |
|---|---|
| Windows | https://www.docker.com/products/docker-desktop |
| macOS | https://www.docker.com/products/docker-desktop |
| Linux (Ubuntu) | https://docs.docker.com/desktop/linux/install/ |

**After installing:** Open Docker Desktop and wait until you see the green "Docker Desktop is running" message in the bottom left.

---

## Step 2 — Start the System

### Windows
1. Open the `InsulinPumpOS` folder
2. Double-click **`install.bat`**
3. A window will open — wait for it to say "System is ready"
4. Your browser will open automatically to the application

### macOS / Linux
1. Open Terminal
2. Navigate to the `InsulinPumpOS` folder:
   ```bash
   cd /path/to/InsulinPumpOS
   ```
3. Run:
   ```bash
   bash install.sh
   ```
4. Open your browser to **http://localhost:8501**

> **First-time start takes 2–5 minutes** as Docker downloads the required components. Subsequent starts take about 10 seconds.

---

## Step 3 — Open the Application

Open any web browser and go to:

```
http://localhost:8501
```

The application will open. On first use, go to **Settings → System Status** to confirm all services are connected (you should see three green checkmarks).

---

## Daily Use

### Starting the system each day
```bash
docker compose up -d
```
Then open http://localhost:8501

### Stopping the system
```bash
docker compose down
```

### Checking if everything is running
Open the app and go to **Settings → System Status**

---

## Accessing from Another Computer (e.g. Nurses' Station)

If the application is running on a dedicated server/PC, other computers on the same network can access it by opening a browser to:

```
http://<server-ip-address>:8501
```

To find the server's IP address:
- **Windows:** Open Command Prompt → type `ipconfig` → look for "IPv4 Address"
- **macOS/Linux:** Open Terminal → type `ifconfig` or `ip addr`

---

## Troubleshooting

### The app won't open / shows an error
1. Make sure Docker Desktop is running (green icon in taskbar)
2. Run: `docker compose logs webapp` — share this output with IT support

### "Service not connected" in System Status
1. Wait 60 seconds and click **Refresh Status** — services need time to start
2. If still failing, run: `docker compose restart`

### Application is slow or freezes
- Restart the app: `docker compose restart webapp`

### I accidentally closed the terminal — is the system still running?
Yes. The system runs in the background. You can close all terminal windows safely.

### How do I update to a new version?
```bash
docker compose pull
docker compose up -d
```

---

## For IT Administrators

### Changing passwords / connecting to your own databases
Edit `docker-compose.yml` and update the environment variables under the `webapp` service.
All settings can also be changed from within the app at **Settings → Connection Settings**.

### Data storage
- Patient registry: PostgreSQL data volume (`postgres_data`)
- Telemetry: InfluxDB data volume (`influx_data`)
- App config and saved formulas: `webapp_storage` volume

### Backup
```bash
# Backup all data volumes
docker run --rm -v insulinpumpOS_postgres_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/postgres_backup.tar.gz /data

docker run --rm -v insulinpumpOS_influx_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/influx_backup.tar.gz /data
```

### Network ports used
| Port | Service |
|---|---|
| 8501 | Web Application |
| 1883 | MQTT Broker |
| 5432 | PostgreSQL |
| 8086 | InfluxDB |

### Running on a server (no GUI Docker Desktop)
```bash
# Install Docker Engine (not Desktop) and Docker Compose plugin
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Then start normally
docker compose up -d
```

---

*InsulinPump OS — WebApp Component*  
*For support, contact your system administrator.*
