#!/bin/bash
set -e

echo "--- 🔧 Step 0: Permissions ---"
find devices -name "*.py" -exec chmod +x {} +

echo "--- 🏗️  Step 1: Building the CA (Security) ---"
docker build -t iotsim/certificates:latest ./devices/certificates

echo "--- 🏗️  Step 2: Building Devices ---"

echo "[1/16] 📡 MQTT Broker..."
docker build -t myzoo/mqtt_broker ./devices/mqtt_broker

echo "[2/16] 🏙️ Urban Observatory (Air, Water, Weather, Mobility)..."
docker build -t myzoo/urban_sensor ./devices/urban_observatory

echo "[3/16] 📹 Video Server..."
docker build -t myzoo/server_video ./devices/stream_server

echo "[4/16] 📷 Camera..."
docker build -t myzoo/camera ./devices/ip_camera

echo "[5/16] 📺 Consumer Video..."
docker build -t myzoo/consumer_video ./devices/stream_consumer

echo "[6/16] 🏭 Cooler Motor (Now with TLS support)..."
docker build -t myzoo/cooler_motor ./devices/cooler_motor

echo "[7/16] ⚙️  Predictive Maintenance..."
docker build -t myzoo/predictive_maintenance ./devices/predictive_maintenance

echo "[8/16] 🏢 Smart Building..."
docker build -t myzoo/building_monitor ./devices/building_monitor

echo "[9/16] 🏠 Home Automation..."
docker build -t myzoo/domotic_monitor ./devices/domotic_monitor

echo "[10/16] 🌫️  Air Legacy..."
docker build -t myzoo/air_quality ./devices/air_quality

echo "[11/16] 🏥 mHealth..."
docker build -t myzoo/mhealth ./devices/mhealth-device

echo "[12/16] 💡 Smart Lighting..."
docker build -t myzoo/smart_lighting ./devices/smart_lighting

echo "[13/16] 💡 Environmental Sensors..."
docker build -t myzoo/environmental_sensors ./devices/environmental_sensors

echo "[14/16] 🐟 Aquaponics Fish Pond..."
docker build -t myzoo/aquaponics_fish_pond ./devices/aquaponics_fish_pond

echo "[15/16] 🛗 Traction Elevator Predictive Maintenance..."
docker build -t myzoo/traction_elevator ./devices/traction-elevator-predictive-maintenance

echo "[16/16] 🛗 Greenhouse sensors..."
docker build -t myzoo/greenhouse_sensor ./devices/greenhouse_sensor

echo "✅ SUCCESS! Environment built."
