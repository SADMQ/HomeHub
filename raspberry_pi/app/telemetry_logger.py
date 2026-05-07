import os
import ssl
import sqlite3
import requests
import json
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from paho.mqtt.enums import CallbackAPIVersion

# Load .env
load_dotenv()

# --- Config ---
MQTT_BROKER = os.getenv("MQTT_BROKER", "10.42.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", 8883))
MQTT_USER = os.getenv("MQTT_USER", "sensoruser")
MQTT_PW = os.getenv("MQTT_PW", "Secret123")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "sensors/#")
CA_CERT = os.path.abspath(os.getenv("CA_CERT_PATH"))
DB_PATH = os.getenv("DB_PATH")
TB_TOKEN = os.getenv("THINGSBOARD_TOKEN")

TB_URL = f"https://thingsboard.cloud/api/v1/{TB_TOKEN}/telemetry"
ARDUINO_CMND_TOPIC = "cmnd/alarm/state"


# SQLite Setup
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

#----------------Local-link------------------------

# Callbackfunction for when recieving compressed alarm JSON 
def on_alarmPackage(client, userdata, msg):
    try:
        payload_str = msg.payload.decode("utf-8").strip()        
        payload_JSON = json.loads(payload_str)
        print(f"!!! ALARM EVENT: {payload_JSON}")     

        # Save locally to SQlite
        cursor.execute("INSERT INTO telemetry (topic, value) VALUES (?, ?)", (msg.topic, payload_str))
        conn.commit()

        # # Push as parsed JSON to cloud via HTTPs
        cloud_key = msg.topic.replace("/", "_")

        response = requests.post(TB_URL, json=payload_JSON, timeout=5)

        if response.status_code == 200:
            print("Saved to cloud")
        else:
            print(f"Cloud Sync failed: {response.status_code}")

    except Exception as e:
        print(f"Alarm Callback Error: {e}")


# When local MQTT connects:
def on_local_connect(client, userdata, flags, rc):
    print(f"Local Link Connected (Result: {rc})")

    # Route specific topic to specific callback functions
    client.message_callback_add("alarmInfo", on_alarmPackage)  

    # Subscribe to sensors and the separate topic alarmInfo     
    client.subscribe([("sensors/#", 0), ("alarmInfo", 0)])


def on_local_disconnect(client, userdata, rc):
    print(f"!!! Local Link Disconnected: {rc}")


# Parse sensordata and save to local DB + push to TB
def on_local_message(client, userdata, msg):
    print("MQTT RECEIVED:", msg.topic, msg.payload)
    try:
        payload_str = msg.payload.decode("utf-8").strip() 

        try:
            value = float(payload_str)
        except ValueError:
            print(f"Invalid payload: {payload_str}")
            return 

        if value == -127.0 or value == 127.0:
            print("Ignored sensor error value")
            return           
        # Save locally to SQlite
        cursor.execute("INSERT INTO telemetry (topic, value) VALUES (?, ?)", (msg.topic, value))
        conn.commit()
        print(f"Saved {msg.topic} -> {value}")

        # Push to cloud via HTTPs
        cloud_key = msg.topic.replace("/", "_")    
        
        response = requests.post(TB_URL, json={cloud_key: value}, timeout=5)

        if response.status_code == 200:
            print("Saved to cloud")
        else:
            print(f"Cloud Sync failed: {response.status_code}")

    except Exception as e:
        print(f"Local Msg Error: {e}")



#----------------Cloud-link------------------------

# When cloud mqtt connects:
def on_cloud_connect(client, userdata, flags, rc):
    print(f"Cloud Link Connected: {rc}")
    # Subscribe to command topic
    client.subscribe("v1/devices/me/attributes")


def on_cloud_disconnect(client, userdata, rc):
    print(f"!!! Cloud Link Disconnected: {rc}")


# Handles command messages from Thingsboard
def on_cloud_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        print(f"Cloud Attribute Update: {data}")

        # Receive remote command via cloud_client
        if data.get("remoteActivate") is True:
            payload = "2"

            # Send remote command via local_client
            local_client.publish(ARDUINO_CMND_TOPIC, payload, qos=1)
            print(f">>> CLOUD COMMAND: remoteActivate relayed as '{payload}' to Arduino")

    except Exception as e:
        print(f"Cloud Attribute Error: {e}")

#-----------------------Setup-clients--------------------------

# Initialize clients for local and cloud
local_client = mqtt.Client(CallbackAPIVersion.VERSION1, "Telemetry_Local")
cloud_client = mqtt.Client(CallbackAPIVersion.VERSION1, "Telemetry_Cloud")

# Local client wiring and config
local_client.on_connect = on_local_connect
local_client.on_message = on_local_message
local_client.username_pw_set(MQTT_USER, MQTT_PW)
local_client.tls_set(ca_certs=CA_CERT, tls_version=ssl.PROTOCOL_TLS_CLIENT)
local_client.tls_insecure_set(True)

# Cloud client wiring and config
cloud_client.on_connect = on_cloud_connect
cloud_client.on_message = on_cloud_message
cloud_client.username_pw_set(TB_TOKEN)
cloud_client.tls_set(ca_certs=None, tls_version=ssl.PROTOCOL_TLS_CLIENT)

#---------------------main-loop------------------------

# Start connections to TB and local broker
try:
    print("Starting Dual-Link Relay...")
    local_client.connect(MQTT_BROKER, MQTT_PORT, 60)   
    cloud_client.connect("mqtt.thingsboard.cloud", 8883, 60)     

    local_client.loop_start()
    cloud_client.loop_forever()
except KeyboardInterrupt:
    print("Exiting...")
    conn.close()
except Exception as e:
    print(f"Error starting relay: {e}")
    conn.close()