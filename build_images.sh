#!/bin/bash
set -e

echo "--- 🔧 Step 0: Permissions ---"
find devices -name "*.py" -exec chmod +x {} +

echo "--- 🏗️  Step 1: Building the CA (Security) ---"
docker build -t iotsim/certificates:latest ./devices/certificates

echo "--- 🏗️  Step 2: Building Devices ---"

echo "[1/17] 📡 MQTT Broker..."
docker build -t myzoo/mqtt_broker ./devices/mqtt_broker

echo "[2/17] 🏙️ Urban Observatory (Air, Water, Weather, Mobility)..."
docker build -t myzoo/urban_sensor ./devices/urban_observatory

echo "[3/17] 📹 Video Server..."
docker build -t myzoo/server_video ./devices/stream_server

echo "[4/17] 📷 Camera..."
docker build -t myzoo/camera ./devices/ip_camera

echo "[5/17] 📺 Consumer Video..."
docker build -t myzoo/consumer_video ./devices/stream_consumer

echo "[6/17] 🏭 Cooler Motor (Now with TLS support)..."
docker build -t myzoo/cooler_motor ./devices/cooler_motor

echo "[7/17] 🏢 Smart Building..."
docker build -t myzoo/building_monitor ./devices/building_monitor

echo "[8/17] 🏠 Home Automation..."
docker build -t myzoo/domotic_monitor ./devices/domotic_monitor

echo "[9/17] 🌫️  Air Legacy..."
docker build -t myzoo/air_quality ./devices/air_quality

echo "[10/17] 🏥 mHealth..."
docker build -t myzoo/mhealth ./devices/mhealth-device

echo "[11/17] 💡 Smart Lighting..."
docker build -t myzoo/smart_lighting ./devices/smart_lighting

echo "[12/17] 💡 Environmental Sensors..."
docker build -t myzoo/environmental_sensors ./devices/environmental_sensors

echo "[13/17] 🐟 Aquaponics Fish Pond..."
docker build -t myzoo/aquaponics_fish_pond ./devices/aquaponics_fish_pond

echo "[14/17] ⚙️  Predictive Maintenance..."
docker build -t myzoo/predictive_maintenance ./devices/predictive_maintenance

echo "[15/17] ⚙️  Elevator Predictive Maintenance..."
docker build -t myzoo/elevator_predictive_maintenance ./devices/elevator_predictive_maintenance

echo "[16/17] 🛗 Traction Elevator Predictive Maintenance..."
docker build -t myzoo/traction_elevator ./devices/traction-elevator-predictive-maintenance

echo "[17/17] 🛗 Greenhouse sensors..."
docker build -t myzoo/greenhouse_sensor ./devices/greenhouse_sensor

echo "[17/17] 🌾 farming sensors..."
docker build -t myzoo/farming_sensor ./devices/farming_sensor

echo "✅ SUCCESS! Environment built."
