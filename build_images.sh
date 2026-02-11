#!/bin/bash
set -e

echo "--- 🔧 Step 0: Permissions ---"
find devices -name "*.py" -exec chmod +x {} +

echo "--- 🏗️  Step 1: Building the CA (Security) ---"
docker build -t iotsim/certificates:latest ./devices/certificates

echo "--- 🏗️  Step 2: Building Devices ---"

echo "[1/15] 📡 MQTT Broker..."
docker build -t myzoo/mqtt_broker ./devices/mqtt_broker

echo "[2/15] 🏙️ Urban Observatory (Air, Water, Weather, Mobility)..."
docker build -t myzoo/urban_sensor ./devices/urban_observatory

echo "[3/15] 📹 Video Server..."
docker build -t myzoo/server_video ./devices/stream_server

echo "[4/15] 📷 Camera..."
docker build -t myzoo/camera ./devices/ip_camera

echo "[5/15] 📺 Consumer Video..."
docker build -t myzoo/consumer_video ./devices/stream_consumer

echo "[6/15] 🏭 Cooler Motor (Now with TLS support)..."
docker build -t myzoo/cooler_motor ./devices/cooler_motor

echo "[7/15] ⚙️  Predictive Maintenance..."
docker build -t myzoo/predictive_maintenance ./devices/predictive_maintenance

echo "[8/15] ⚙️  Elevator Predictive Maintenance..."
docker build -t myzoo/elevator_predictive_maintenance ./devices/elevator_predictive_maintenance

echo "[9/15] 🏢 Smart Building..."
docker build -t myzoo/building_monitor ./devices/building_monitor

echo "[10/15] 🏠 Home Automation..."
docker build -t myzoo/domotic_monitor ./devices/domotic_monitor

echo "[11/15] 🌫️  Air Legacy..."
docker build -t myzoo/air_quality ./devices/air_quality

echo "[12/15] 🏥 mHealth..."
docker build -t myzoo/mhealth ./devices/mhealth-device

echo "[13/15] 💡 Smart Lighting..."
docker build -t myzoo/smart_lighting ./devices/smart_lighting

echo "[14/15] 💡 Environmental Sensors..."
docker build -t myzoo/environmental_sensors ./devices/environmental_sensors

echo "[15/15] 🐟 Aquaponics Fish Pond..."
docker build -t myzoo/aquaponics_fish_pond ./devices/aquaponics_fish_pond

echo "✅ SUCCESS! Environment built."
