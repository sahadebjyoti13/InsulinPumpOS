"""
setup_wizard.py  –  InsulinPump OS
First-run configuration wizard for clinical staff.
Imported and called by app.py when config is incomplete or the user
navigates to Settings > System Configuration.
"""

import streamlit as st
import time
from backend import save_config, get_config, probe_services


def render_status_badge(ok: bool, message: str):
    color = "#00cc96" if ok else "#ef553b"
    icon = "✅" if ok else "❌"
    label = "Connected" if ok else "Not reachable"
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:12px;
                    background:rgba(30,33,48,0.6); border:1px solid {'#00cc96' if ok else '#ef553b'};
                    border-radius:10px; padding:12px 18px; margin-bottom:8px;">
            <span style="font-size:22px;">{icon}</span>
            <div>
                <div style="font-weight:700; color:{color};">{label}</div>
                <div style="font-size:12px; color:#888; margin-top:2px;">{message}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def view_system_status():
    """
    Renders the live service-status panel.
    Can be embedded in the Settings page sidebar.
    """
    st.markdown("### System Status")
    st.caption("Live connectivity check — click Refresh to re-test.")

    if st.button("🔄 Refresh Status", key="status_refresh"):
        st.session_state.pop("_probe_results", None)

    if "_probe_results" not in st.session_state:
        with st.spinner("Checking services…"):
            st.session_state["_probe_results"] = probe_services()

    results = st.session_state["_probe_results"]

    service_labels = {
        "mqtt":     "MQTT Broker",
        "postgres": "Patient Registry (PostgreSQL)",
        "influxdb": "Telemetry Store (InfluxDB)",
    }

    all_ok = True
    for key, label in service_labels.items():
        r = results.get(key, {"ok": False, "message": "Not checked"})
        st.markdown(f"**{label}**")
        render_status_badge(r["ok"], r["message"])
        if not r["ok"]:
            all_ok = False

    if all_ok:
        st.success("All services are online. The system is ready.")
    else:
        st.warning(
            "One or more services are not reachable. "
            "If you just started the system, wait 30 seconds and refresh. "
            "Otherwise, see the Troubleshooting section below."
        )

    return all_ok


def view_setup_wizard():
    """
    Full first-run wizard. Call this from app.py Settings page.
    Saves connection details to /app/storage/config.json.
    """
    st.markdown(
        "<h1>⚙️ System Configuration</h1>"
        "<p style='color:#888;'>Complete this once. Your settings are saved automatically.</p>",
        unsafe_allow_html=True,
    )

    tab_status, tab_config, tab_help = st.tabs(
        ["📡 System Status", "🔧 Connection Settings", "❓ Help & Troubleshooting"]
    )

    # ── Tab 1: Status ────────────────────────────────────────────────────────
    with tab_status:
        view_system_status()

    # ── Tab 2: Config ────────────────────────────────────────────────────────
    with tab_config:
        cfg = get_config()

        st.markdown(
            """
            <div style="background:rgba(99,110,250,0.12); border:1px solid #636efa;
                        border-radius:10px; padding:14px 18px; margin-bottom:20px;">
                <b style="color:#636efa;">ℹ️ Note for Docker users</b><br>
                <span style="color:#aaa; font-size:13px;">
                If you launched the system with the provided installer, all settings are
                pre-configured. You only need this page if you are connecting to your own
                databases or a custom MQTT broker.
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("🔌 MQTT Broker", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                mqtt_host = st.text_input(
                    "Broker Address",
                    value=cfg.get("MQTT_BROKER", "localhost"),
                    placeholder="localhost or 192.168.1.x",
                    help="The IP address or hostname of your MQTT broker.",
                )
            with col2:
                mqtt_port = st.number_input(
                    "Port", value=int(cfg.get("MQTT_PORT", 1883)),
                    min_value=1, max_value=65535,
                    help="Default is 1883.",
                )

        with st.expander("🗄️ Patient Registry (PostgreSQL)", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                pg_host = st.text_input("Host", value=cfg.get("PG_HOST", "localhost"))
                pg_db   = st.text_input("Database Name", value=cfg.get("PG_DB", "med_db"))
                pg_user = st.text_input("Username", value=cfg.get("PG_USER", "postgres"))
            with col2:
                pg_port = st.number_input("Port", value=int(cfg.get("PG_PORT", 5432)),
                                          min_value=1, max_value=65535)
                pg_pass = st.text_input("Password", value=cfg.get("PG_PASSWORD", ""),
                                        type="password")

        with st.expander("📊 Telemetry Store (InfluxDB)", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                influx_url    = st.text_input("InfluxDB URL",
                                              value=cfg.get("INFLUX_URL", "http://localhost:8086"))
                influx_org    = st.text_input("Organisation",
                                              value=cfg.get("INFLUX_ORG", ""))
                influx_bucket = st.text_input("Bucket Name",
                                              value=cfg.get("INFLUX_BUCKET", "telemetry"))
            with col2:
                influx_token = st.text_input("API Token",
                                             value=cfg.get("INFLUX_TOKEN", ""),
                                             type="password",
                                             help="Create an All Access token in InfluxDB → Data → API Tokens.")

        st.markdown("<br>", unsafe_allow_html=True)
        col_save, col_test = st.columns([1, 1])

        with col_save:
            if st.button("💾 Save Settings", type="primary", use_container_width=True):
                save_config({
                    "MQTT_BROKER":    mqtt_host,
                    "MQTT_PORT":      int(mqtt_port),
                    "PG_HOST":        pg_host,
                    "PG_PORT":        int(pg_port),
                    "PG_DB":          pg_db,
                    "PG_USER":        pg_user,
                    "PG_PASSWORD":    pg_pass,
                    "INFLUX_URL":     influx_url,
                    "INFLUX_TOKEN":   influx_token,
                    "INFLUX_ORG":     influx_org,
                    "INFLUX_BUCKET":  influx_bucket,
                })
                st.success("Settings saved. Restart the app for changes to take effect.")

        with col_test:
            if st.button("🔍 Test Connection Now", use_container_width=True):
                st.session_state.pop("_probe_results", None)
                with st.spinner("Testing…"):
                    results = probe_services()
                    st.session_state["_probe_results"] = results
                all_ok = all(r["ok"] for r in results.values())
                if all_ok:
                    st.success("All services reachable!")
                else:
                    failed = [k for k, v in results.items() if not v["ok"]]
                    st.error(f"Cannot reach: {', '.join(failed)}. Check the Help tab.")

    # ── Tab 3: Help ──────────────────────────────────────────────────────────
    with tab_help:
        st.markdown("### 🚀 Quick Start (Docker — Recommended)")
        st.code(
            "# 1. Install Docker Desktop from https://www.docker.com\n"
            "# 2. Open a terminal in the InsulinPumpOS folder\n"
            "docker compose up -d\n"
            "# 3. Open your browser to http://localhost:8501",
            language="bash",
        )

        st.markdown("---")
        st.markdown("### ❓ Common Issues")

        with st.expander("MQTT — Cannot connect"):
            st.markdown(
                """
- Make sure the MQTT broker is running.  
  If using Docker: `docker compose up -d mosquitto`
- Check the broker address is correct (use the server's IP on a local network).
- Default port is **1883** — make sure no firewall is blocking it.
"""
            )

        with st.expander("PostgreSQL — Authentication failed"):
            st.markdown(
                """
- The password in Connection Settings must match what PostgreSQL was configured with.
- If using Docker, the default password is **insulinpump_secret**.
- If you changed the password, update it here and click Save.
"""
            )

        with st.expander("InfluxDB — Unauthorized / Token invalid"):
            st.markdown(
                """
- Log in to InfluxDB at **http://localhost:8086**.
- Go to **Data → API Tokens → Generate All Access Token**.
- Copy the token and paste it in the InfluxDB section above.
- If using Docker, the token is automatically set to `insulinpump-super-secret-token-change-me`.
"""
            )

        with st.expander("App not loading / white screen"):
            st.markdown(
                """
- Wait 30–60 seconds after running `docker compose up` — services need time to start.
- Run `docker compose logs webapp` to see error messages.
- Make sure ports 8501, 1883, 5432, 8086 are not already in use.
"""
            )

        st.markdown("---")
        st.markdown(
            "<div style='color:#888; font-size:12px;'>"
            "For technical support, share the output of <code>docker compose logs</code> "
            "with your IT administrator."
            "</div>",
            unsafe_allow_html=True,
        )
