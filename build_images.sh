#!/bin/bash
set -e

echo "--- 🔧 Passo 0: Permissões ---"
find devices -name "*.py" -exec chmod +x {} +

echo "--- 🏗️  Passo 1: Construindo a CA (Segurança) ---"
docker build -t iotsim/certificates:latest ./devices/certificates

echo "--- 🏗️  Passo 2: Construindo Dispositivos ---"

echo "[1/11] 📡 Broker MQTT..."
docker build -t myzoo/mqtt_broker ./devices/mqtt_broker

echo "[2/11] 🏙️  Urban Observatory..."
docker build -t myzoo/urban_sensor ./devices/urban_observatory

echo "[3/11] 📹 Servidor Vídeo..."
docker build -t myzoo/server_video ./devices/stream_server

echo "[4/11] 📷 Camera..."
docker build -t myzoo/camera ./devices/ip_camera

echo "[5/11] 📺 Consumer Video..."
docker build -t myzoo/consumer_video ./devices/stream_consumer

echo "[6/11] 🏭 Cooler Motor (Agora com suporte a TLS)..."
docker build -t myzoo/cooler_motor ./devices/cooler_motor

echo "[7/11] ⚙️  Preditiva..."
docker build -t myzoo/predictive_maintenance ./devices/predictive_maintenance

echo "[8/11] 🏢 Smart Building..."
docker build -t myzoo/building_monitor ./devices/building_monitor

echo "[9/11] 🏠 Domótica..."
docker build -t myzoo/domotic_monitor ./devices/domotic_monitor

echo "[10/11] 🌫️  Air Legacy..."
docker build -t myzoo/air_quality ./devices/air_quality

echo "[11/11] 🏥 mHealth..."
docker build -t myzoo/mhealth ./devices/mhealth-device

echo "✅ SUCESSO! Ambiente construído."
