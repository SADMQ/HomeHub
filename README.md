# Home Hub – Raspberry Pi Zero / MQTT / SQLite / TLS

This is the Raspberry Pi Zero part of the **Home Hub** project.  
It handles **data storage** from **MQTT** messages, saving them locally to **SQLite**, and supports **TLS encryption**.

---

## Project Overview

1. Arduino sends sensor data to the Raspberry Pi Zero via MQTT.  
2. Python program receives the data.  
3. The Python program:
   - Saves the data locally in `sensor_data.db` (backup in case of internet loss)  
   - Sends data to ThingsBoard over the internet

---
## Project Structure

```bash
HomeHub/
├── venv/                                # not in GitHub
├── raspberry_pi/
│   ├── app/
│   │   └── telemetry_logger.py          # tracked
│   ├── certs/
│   │   ├── ca.crt                       # not in GitHub
│   │   ├── ca.key                       # not in GitHub (private key!)
│   │   ├── ca.srl                       # not in GitHub
│   │   ├── generate_certs.sh            # tracked
│   │   ├── README.md                    # tracked
│   │   ├── server.crt                   # not in GitHub
│   │   ├── server.key                   # not in GitHub (private key!)
│   │   └──server.csr                    # not in GitHub
│   ├── cleanup.sh                       # tracked
│   ├── init_db.sh                       # tracked
│   ├── mqtt_setup/
│   │   └── mosquitto_conf_example.conf  # tracked
│   └── sensor_data.db                   # not in GitHub
├── scripts/
│   ├── publish_test.sh                  # tracked
│   └── subscribe_test.sh                # tracked
│── README.md                            # tracked
├── requirements.txt                     # tracked
└── .env.example                         # tracked (your .env should not be committed)
```
---
## Installation

On Raspberry Pi Zero:
```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients sqlite3 python3-pip
```
---
### Python Virtual Environment (venv)

The project uses a Python virtual environment to isolate dependencies.

1. Create and activate the virtual environment (first-time setup)
```bash
cd ~/HomeHub
python3 -m venv venv
source venv/bin/activate
```
- This only needs to be done once during setup.
- Your prompt should now show `(venv)` to indicate the environment is active.

2. Install the required Python packages:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```
- Packages installed here are isolated to this project.

Using the virtual environment:
- Whenever you want to run Python scripts manually, you need to activate the venv first:
```bash
source venv/bin/activate
```
- When done, you can deactivate it:
```bash
deactivate
```
## Configuration (.env)

1. Copy the example environment file:
```bash
cp .env.example .env
```
2. Fill in your own MQTT credentials and paths in `.env`:
```bash
MQTT_BROKER=localhost
MQTT_PORT=8883
MQTT_USER=your_user
MQTT_PW=your_password
MQTT_TOPIC=sensors/#
CA_CERT_PATH=your_path
DB_PATH=raspberry_pi/sensor_data.db
THINGSBOARD_TOKEN=your_token
```
---
## TLS Certificate Generation

Generate TLS certificates using the provided script `generate_certs.sh`.

### 1. Make the script executable (if not already):
```bash
chmod +x raspberry_pi/certs/generate_certs.sh
```
### 2. Run it:
```bash
./raspberry_pi/certs/generate_certs.sh
```
### 3. Copy the certificates to Mosquitto and set permissions:
```bash
sudo mkdir -p /etc/mosquitto/certs
sudo cp raspberry_pi/certs/*.crt /etc/mosquitto/certs/
sudo cp raspberry_pi/certs/*.key /etc/mosquitto/certs/
sudo chown mosquitto:mosquitto /etc/mosquitto/certs/*
sudo chmod 600 /etc/mosquitto/certs/*
```
---
## MQTT Configuration

### 1. Copy config file
```bash
sudo cp raspberry_pi/mqtt_setup/mosquitto_conf_example.conf /etc/mosquitto/conf.d/external.conf
```
### 2. Configure Mosquitto
```bash
vim /etc/mosquitto/conf.d/external.conf
```
Paste:
```bash
listener 8883
allow_anonymous false
password_file /etc/mosquitto/passwd

certfile /etc/mosquitto/certs/server.crt
keyfile /etc/mosquitto/certs/server.key
```
### 3. Create user/password
```bash
sudo mosquitto_passwd -c /etc/mosquitto/passwd your_user
```
You will be prompted to enter a password.
Choose any password, but make sure to use the same password in your .env file (MQTT_PW), otherwise authentication will fail.

### 4. Set permissions
```bash
sudo chown mosquitto:mosquitto /etc/mosquitto/passwd
sudo chmod 600 /etc/mosquitto/passwd
```
### 5. Restart Mosquitto
```bash
sudo systemctl restart mosquitto
```
**Note:**  
- Replace TLS certificate paths in the config if needed
---
## Initialize SQLite Database
```bash
cd raspberry_pi
./init_db.sh
```
This creates `sensor_data.db` with a `telemetry` table containing:

- `id` – unique identifier  
- `timestamp` – automatically recorded datetime  
- `topic` – sensor name (e.g. `sensors/temperature`)  
- `value` – numeric sensor reading  
---
## Run the Python Logger

You have two ways to run the logger:

### 1. Manual (for testing or development)

```bash
source venv/bin/activate
python3 raspberry_pi/app/telemetry_logger.py
```
This script will:

- Connect to the local MQTT broker  
- Subscribe to `sensors/#` topics  
- Save incoming messages to the database  
- Print received values to the terminal
- Forward saved messages to thingsboard

Keep this terminal open while the logger runs.

Deactivate the virtual environment when done:
```bash
deactivate
```
### 2. Automatic (recommended) - Systemd Auto-Start

A systemd service runs the logger automatically:

1. Create a service file:
```bash
sudo vim /etc/systemd/system/homehub.service
```
2. Paste the following:
```bash
[Unit]
Description=HomeHub Telemetry Logger
After=network.target

[Service]
Type=simple
User=dev
WorkingDirectory=/home/dev/HomeHub
ExecStart=/home/dev/HomeHub/venv/bin/python3 /home/dev/HomeHub/raspberry_pi/app/telemetry_logger.py
Restart=always

[Install]
WantedBy=multi-user.target
```
3. Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable homehub.service
sudo systemctl start homehub.service
```
4. Check status:
```bash
sudo systemctl status homehub.service
```   
---
## Testing

### Publish Example Data
```bash
./scripts/publish_test.sh
```
### Subscribe and View Data
```bash
./scripts/subscribe_test.sh
```
### View database contents
```bash
sqlite3 ./raspberry_pi/sensor_data.db "SELECT * FROM telemetry;"
```
---
## Cleanup Script

To keep the SQLite database from growing indefinitely, a cleanup script is included in the repository.

### 1. Make it executable:
```bash
chmod +x cleanup.sh
```
### 2. Schedule with cron (runs daily at 3 AM):
```bash
crontab -e
```
### 3. Add the following line at the end:
```bash
0 3 * * * /home/dev/HomeHub/cleanup.sh
```
---
## Notes

- Data Format
   - Topic: `sensors/temperature`  
   - Payload: `22.2`
- Keep TLS private keys out of GitHub (`.gitignore` handles this)  
- Use `tmux` or multiple terminals to run scripts simultaneously  
- This project is for educational purposes
