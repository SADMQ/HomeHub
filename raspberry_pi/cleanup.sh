#!/bin/bash

sqlite3 /home/dev/HomeHub/raspberry_pi/sensor_data.db <<EOF
DELETE FROM telemetry
WHERE timestamp < datetime('now', '-1 day');
EOF
