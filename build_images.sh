#!/bin/bash
set -e

echo "--- 🔧 Step 0: Permissions ---"
find devices -name "*.py" -exec chmod +x {} +

echo "--- 🔁 Step 0.1: Sync Zenoh shim into device dirs ---"
# Fonte única de verdade do shim em devices/_zenoh_common; copia para cada device
# que tenha uma variante *_zenoh.py (o contexto de build é a própria pasta do device).
for zfile in devices/*/iotzoo_zenoh.py; do
    cp -f devices/_zenoh_common/iotzoo_zenoh.py "$zfile"
done

echo "--- 🏗️  Step 1: Building the CA (Security) ---"
docker build -t iotsim/certificates:latest ./devices/certificates

echo "--- 🏗️  Step 2: Building Protocol Infrastructure (Brokers/Routers/Agents) ---"

echo "[infra] 📡 MQTT Broker (Mosquitto)..."
docker build -t myzoo/mqtt_broker ./devices/mqtt_broker

echo "[infra] 🌐 Zenoh Router..."
docker build -t myzoo/zenoh_router ./devices/zenoh_router

echo "[infra] 🛰️  DDS-XRCE Agent (eProsima Micro-XRCE-DDS-Agent)..."
docker build -t myzoo/xrce_dds_agent ./devices/xrce_dds_agent

echo "[infra] 🧩 DDS-XRCE generic client base (Micro-XRCE-DDS-Client)..."
docker build -t myzoo/xrce_client_base -f devices/_xrce_common/Dockerfile .

echo "--- 🏗️  Step 3: Building Devices ---"

echo "[2/20] 🏙️ Urban Observatory (Air, Water, Weather, Mobility)..."
docker build -t myzoo/urban_sensor ./devices/urban_observatory

echo "[3/20] 📹 Video Server..."
docker build -t myzoo/server_video ./devices/stream_server

echo "[4/20] 📷 Camera..."
docker build -t myzoo/camera ./devices/ip_camera

echo "[5/20] 📺 Consumer Video..."
docker build -t myzoo/consumer_video ./devices/stream_consumer

echo "[6/20] 🏭 Cooler Motor (Now with TLS support)..."
docker build -t myzoo/cooler_motor ./devices/cooler_motor

echo "[7/20] 🏢 Smart Building..."
docker build -t myzoo/building_monitor ./devices/building_monitor

echo "[8/20] 🏠 Home Automation..."
docker build -t myzoo/domotic_monitor ./devices/domotic_monitor

echo "[9/20] 🌫️  Air Legacy..."
docker build -t myzoo/air_quality ./devices/air_quality

echo "[10/20] 🏥 mHealth..."
docker build -t myzoo/mhealth ./devices/mhealth-device

echo "[11/20] 💡 Smart Lighting..."
docker build -t myzoo/smart_lighting ./devices/smart_lighting

echo "[12/20] 💡 Environmental Sensors..."
docker build -t myzoo/environmental_sensors ./devices/environmental_sensors

echo "[13/20] 🐟 Aquaponics Fish Pond..."
docker build -t myzoo/aquaponics_fish_pond ./devices/aquaponics_fish_pond

echo "[14/20] ⚙️  Predictive Maintenance..."
docker build -t myzoo/predictive_maintenance ./devices/predictive_maintenance

echo "[15/20] ⚙️  Elevator Predictive Maintenance..."
docker build -t myzoo/elevator_predictive_maintenance ./devices/elevator_predictive_maintenance

echo "[16/20] 🛗 Traction Elevator Predictive Maintenance..."
docker build -t myzoo/traction_elevator ./devices/traction-elevator-predictive-maintenance

echo "[17/20] 🛗 Greenhouse sensors..."
docker build -t myzoo/greenhouse_sensor ./devices/greenhouse_sensor

echo "[18/20] 🌾 Farming sensors..."
docker build -t myzoo/farming_sensor ./devices/farming_sensor

echo "[19/20] 🏢 Smart Building M5 (Energy & Environment)..."

echo "[20/20] 👩‍⚕️ Nurse Stress Prediction..."
docker build -t myzoo/nurse_stress ./devices/nurse-stress-prediction
docker build -t myzoo/smart_building_m5 ./devices/smart_building_m5

echo "✅ SUCCESS! Environment built."
