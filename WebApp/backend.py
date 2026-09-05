"""
backend.py  –  InsulinPump OS
Reads all connection settings from:
  1. Environment variables  (set automatically by Docker Compose)
  2. /app/storage/config.json  (written by the first-run setup wizard)
  3. Hard-coded localhost defaults  (for bare-metal dev)

Doctors / clinical users never need to touch this file.
"""

import os
import json
import time
import queue
import threading
from collections import deque
from pathlib import Path

import psycopg2
import pandas as pd
from psycopg2.extras import RealDictCursor
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import paho.mqtt.client as mqtt
from datetime import datetime, timezone, timedelta

# ── Config loader ────────────────────────────────────────────────────────────

STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", "/app/storage"))
CONFIG_FILE = STORAGE_DIR / "config.json"


def _load_config() -> dict:
    """
    Priority: env vars > config.json > localhost defaults.
    Returns a flat dict of all connection settings.
    """
    # Start with localhost defaults (bare-metal / dev)
    cfg = {
        "MQTT_BROKER": "localhost",
        "MQTT_PORT": 1883,
        "PG_HOST": "localhost",
        "PG_PORT": 5432,
        "PG_DB": "med_db",
        "PG_USER": "postgres",
        "PG_PASSWORD": "password",
        "INFLUX_URL": "http://localhost:8086",
        "INFLUX_TOKEN": "",
        "INFLUX_ORG": "IIEST, Shibpur",
        "INFLUX_BUCKET": "NewHW",
    }

    # Layer 2: config.json written by setup wizard
    if CONFIG_FILE.exists():
        try:
            saved = json.loads(CONFIG_FILE.read_text())
            cfg.update({k: v for k, v in saved.items() if v not in (None, "")})
        except Exception:
            pass

    # Layer 3: environment variables (highest priority — Docker Compose)
    env_map = {
        "MQTT_BROKER": "MQTT_BROKER",
        "MQTT_PORT": "MQTT_PORT",
        "PG_HOST": "PG_HOST",
        "PG_PORT": "PG_PORT",
        "PG_DB": "PG_DB",
        "PG_USER": "PG_USER",
        "PG_PASSWORD": "PG_PASSWORD",
        "INFLUX_URL": "INFLUX_URL",
        "INFLUX_TOKEN": "INFLUX_TOKEN",
        "INFLUX_ORG": "INFLUX_ORG",
        "INFLUX_BUCKET": "INFLUX_BUCKET",
    }
    for key, env_var in env_map.items():
        val = os.environ.get(env_var)
        if val is not None:
            cfg[key] = val

    # Type coercion
    cfg["MQTT_PORT"] = int(cfg["MQTT_PORT"])
    cfg["PG_PORT"] = int(cfg["PG_PORT"])

    return cfg


def save_config(updates: dict):
    """Called by the setup wizard to persist user-supplied values."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    existing = {}
    if CONFIG_FILE.exists():
        try:
            existing = json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    existing.update(updates)
    CONFIG_FILE.write_text(json.dumps(existing, indent=2))


def get_config() -> dict:
    return _load_config()


# ── Connectivity probe (used by system status page) ──────────────────────────


def probe_services() -> dict:
    """
    Returns a dict with keys: mqtt, postgres, influxdb.
    Each value is {"ok": bool, "message": str}.
    """
    cfg = _load_config()
    results = {}

    # MQTT
    try:
        import socket

        s = socket.create_connection((cfg["MQTT_BROKER"], cfg["MQTT_PORT"]), timeout=3)
        s.close()
        results["mqtt"] = {
            "ok": True,
            "message": f"Reachable at {cfg['MQTT_BROKER']}:{cfg['MQTT_PORT']}",
        }
    except Exception as e:
        results["mqtt"] = {"ok": False, "message": str(e)}

    # PostgreSQL
    try:
        conn = psycopg2.connect(
            host=cfg["PG_HOST"],
            port=cfg["PG_PORT"],
            dbname=cfg["PG_DB"],
            user=cfg["PG_USER"],
            password=cfg["PG_PASSWORD"],
            connect_timeout=3,
        )
        conn.close()
        results["postgres"] = {
            "ok": True,
            "message": f"Connected to {cfg['PG_HOST']}:{cfg['PG_PORT']}/{cfg['PG_DB']}",
        }
    except Exception as e:
        results["postgres"] = {"ok": False, "message": str(e)}

    # InfluxDB
    try:
        client = InfluxDBClient(
            url=cfg["INFLUX_URL"], token=cfg["INFLUX_TOKEN"], org=cfg["INFLUX_ORG"]
        )
        health = client.health()
        client.close()
        results["influxdb"] = {
            "ok": health.status == "pass",
            "message": f"Status: {health.status}",
        }
    except Exception as e:
        results["influxdb"] = {"ok": False, "message": str(e)}

    return results


# ── DatabaseService ───────────────────────────────────────────────────────────


class DatabaseService:
    def __init__(self):
        self.pg_conn = None
        self.influx_client = None
        self.influx_write = None
        self.influx_query = None
        self._cfg = _load_config()

    def connect(self):
        cfg = self._cfg

        # PostgreSQL
        try:
            self.pg_conn = psycopg2.connect(
                host=cfg["PG_HOST"],
                port=cfg["PG_PORT"],
                dbname=cfg["PG_DB"],
                user=cfg["PG_USER"],
                password=cfg["PG_PASSWORD"],
            )
            self._init_pg_table()
            print("✅ PostgreSQL Connected")
        except Exception as e:
            print(f"❌ PostgreSQL Error: {e}")

        # InfluxDB
        try:
            self.influx_client = InfluxDBClient(
                url=cfg["INFLUX_URL"], token=cfg["INFLUX_TOKEN"], org=cfg["INFLUX_ORG"]
            )
            self._init_influx_bucket()
            self.influx_write = self.influx_client.write_api(write_options=SYNCHRONOUS)
            self.influx_query = self.influx_client.query_api()
            print("✅ InfluxDB Connected")
        except Exception as e:
            print(f"❌ InfluxDB Error: {e}")

    def _init_pg_table(self):
        if not self.pg_conn:
            return
        with self.pg_conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS patients (
                    device_id TEXT PRIMARY KEY,
                    patient_name TEXT,
                    device_name TEXT,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            self.pg_conn.commit()

    def _init_influx_bucket(self):
        cfg = self._cfg
        try:
            buckets_api = self.influx_client.buckets_api()
            bucket = buckets_api.find_bucket_by_name(cfg["INFLUX_BUCKET"])
            if bucket is None:
                org_api = self.influx_client.organizations_api()
                orgs = org_api.find_organizations(org=cfg["INFLUX_ORG"])
                if orgs:
                    buckets_api.create_bucket(
                        bucket_name=cfg["INFLUX_BUCKET"], org_id=orgs[0].id
                    )
        except Exception as e:
            print(f"⚠️  Influx bucket init failed: {e}")

    def add_patient(self, device_id, name, device_name):
        if not self.pg_conn:
            return False, "Database not connected"
        try:
            with self.pg_conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO patients (device_id, patient_name, device_name)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (device_id) DO UPDATE
                    SET patient_name = EXCLUDED.patient_name;
                """,
                    (device_id, name, device_name),
                )
                self.pg_conn.commit()
            return True, "Registered Successfully"
        except Exception as e:
            return False, str(e)

    def get_patients(self):
        if not self.pg_conn:
            return []
        try:
            with self.pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM patients")
                return cur.fetchall()
        except Exception:
            return []

    def save_telemetry(self, data):
        if not self.influx_write:
            return
        cfg = self._cfg
        try:
            p = (
                Point("telemetry")
                .tag("device_id", data.get("device_id"))
                .tag("patient_name", data.get("patient_name", "Unknown"))
            )
            for key, value in data.items():
                if key in [
                    "device_id",
                    "patient_name",
                    "timestamp",
                    "device_name",
                    "patient_id",
                ]:
                    continue
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    p = p.field(key, float(value))
                else:
                    p = p.field(key, str(value))
            self.influx_write.write(
                bucket=cfg["INFLUX_BUCKET"], org=cfg["INFLUX_ORG"], record=p
            )
        except Exception as e:
            print(f"Influx Write Error: {e}")

    def get_history(self, device_id, start_dt, end_dt):
        if not self.influx_query:
            return pd.DataFrame()
        cfg = self._cfg
        try:
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=datetime.now().astimezone().tzinfo)

            end_dt = end_dt + timedelta(minutes=5)
            start_str = start_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            end_str = end_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            query = (
                f'from(bucket: "{cfg["INFLUX_BUCKET"]}")'
                f" |> range(start: {start_str}, stop: {end_str})"
                f' |> filter(fn: (r) => r["_measurement"] == "telemetry")'
                f' |> filter(fn: (r) => r["device_id"] == "{device_id}")'
                f' |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")'
            )

            df_result = self.influx_query.query_data_frame(query)

            if isinstance(df_result, list):
                if not df_result:
                    return pd.DataFrame()
                merged_df = df_result[0]
                for i in range(1, len(df_result)):
                    drop_cols = [
                        c
                        for c in [
                            "result",
                            "table",
                            "_start",
                            "_stop",
                            "_measurement",
                            "device_id",
                            "patient_name",
                        ]
                        if c in df_result[i].columns
                    ]
                    temp_df = df_result[i].drop(columns=drop_cols)
                    merged_df = pd.merge(merged_df, temp_df, on="_time", how="outer")
                return merged_df

            return df_result if df_result is not None else pd.DataFrame()
        except Exception as e:
            print(f"Influx Query Error: {e}")
            return pd.DataFrame()


# ── MQTTService ───────────────────────────────────────────────────────────────


class MQTTService:
    def __init__(self, db_service):
        try:
            from paho.mqtt.enums import CallbackAPIVersion

            self.client = mqtt.Client(CallbackAPIVersion.VERSION1)
        except ImportError:
            self.client = mqtt.Client()

        self._cfg = _load_config()
        self.data_queue = queue.Queue()
        self.db = db_service
        self.device_heartbeats = {}
        self.latest_data = {}
        self.cgm_latest_data = {}
        self.cgm_history = {}
        self.cgm_msg_count = {}
        self.cgm_last_seen = {}
        self.last_valid_rpm = {}

    def start(self):
        cfg = self._cfg
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        try:
            self.client.connect(cfg["MQTT_BROKER"], cfg["MQTT_PORT"], 60)
            self.client.loop_start()
            print(f"✅ MQTT Service Started on {cfg['MQTT_BROKER']}:{cfg['MQTT_PORT']}")
        except Exception as e:
            print(f"❌ MQTT Connection Error: {e}")

    def _on_connect(self, client, userdata, flags, rc, *args):
        if rc == 0:
            print("✅ MQTT Broker Connected!")
            client.subscribe("medical/pump/#")
        else:
            print(f"❌ MQTT Connection Failed (rc={rc})")

    def send_command(self, device_id, payload):
        topic = f"medical/pump/{device_id}/host"
        try:
            info = self.client.publish(topic, json.dumps(payload))
            return info.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            print(f"MQTT Publish Error: {e}")
            return False

    def _on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            topic_l = str(topic).lower()
            is_data = topic_l.endswith("/data")
            is_cgm = topic_l.endswith("/cgm") or topic_l.endswith("cgm")
            if not is_data and not is_cgm:
                return

            payload = json.loads(msg.payload.decode())
            dev_id = payload.get("device_id")

            if not dev_id:
                try:
                    parts = str(topic).split("/")
                    if len(parts) >= 4 and parts[0] == "medical" and parts[1] == "pump":
                        dev_id = parts[2]
                        payload["device_id"] = dev_id
                except Exception:
                    dev_id = None

            payload["timestamp"] = datetime.now().strftime("%H:%M:%S")

            if dev_id:
                if is_cgm:
                    self.device_heartbeats[dev_id] = time.time()
                    self.cgm_latest_data[dev_id] = payload
                    if dev_id not in self.cgm_history:
                        self.cgm_history[dev_id] = deque(maxlen=360)
                    self.cgm_history[dev_id].append(payload)

                    payload_db = dict(payload)
                    try:
                        if "glucose" in payload_db:
                            payload_db["cgm_glucose"] = float(payload_db["glucose"])
                    except Exception:
                        pass
                    try:
                        if "trend" in payload_db:
                            payload_db["cgm_trend"] = float(payload_db["trend"])
                    except Exception:
                        pass
                    self.db.save_telemetry(payload_db)
                    return

                # RPM spike filter
                if "actual_rpm" in payload:
                    try:
                        rpm_val = float(payload["actual_rpm"])
                        if abs(rpm_val) > 50:
                            if dev_id in self.last_valid_rpm:
                                payload["actual_rpm"] = self.last_valid_rpm[dev_id]
                            else:
                                del payload["actual_rpm"]
                        else:
                            self.last_valid_rpm[dev_id] = rpm_val
                            payload["actual_rpm"] = rpm_val
                    except (ValueError, TypeError):
                        if dev_id in self.last_valid_rpm:
                            payload["actual_rpm"] = self.last_valid_rpm[dev_id]
                        else:
                            payload.pop("actual_rpm", None)

                self.device_heartbeats[dev_id] = time.time()
                self.latest_data[dev_id] = payload

            self.db.save_telemetry(payload)
            self.data_queue.put(payload)
            if self.data_queue.qsize() > 500:
                self.data_queue.get()

        except Exception:
            pass
