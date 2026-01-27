#!/bin/bash

# Execute na raiz: sudo ./build_images.sh

set -e

echo "=============================================="
echo "🏗️  INICIANDO CONSTRUÇÃO  "
echo "=============================================="

# 1. Infraestrutura
echo "[1/11] 📡 Construindo Broker MQTT..."
docker build -t myzoo/mqtt_broker ./devices/mqtt_broker

# 2. Sensores Urbanos
echo "[2/11] 🏙️  Construindo Urban Sensor (Gateway)..."
docker build -t myzoo/urban_sensor ./devices/air_quality_urban_repository

# 3. Sistema de Vídeo
echo "[3/11] 📹 Construindo Servidor de Vídeo..."
docker build -t myzoo/server_video ./devices/stream_server

echo "[4/11] 📷 Construindo Câmera IP..."
docker build -t myzoo/camera ./devices/ip_camera

echo "[5/11] 📺 Construindo Consumidor de Vídeo..."
docker build -t myzoo/consumer_video ./devices/stream_consumer

# 4. Indústria
echo "[6/11] 🏭 Construindo Cooler Motor..."
docker build -t myzoo/cooler_motor ./devices/cooler_motor

echo "[7/11] ⚙️  Construindo Manutenção Preditiva..."
docker build -t myzoo/predictive_maintenance ./devices/predictive_maintenance

# 5. Smart Building / Home
echo "[8/11] 🏢 Construindo Smart Building..."
docker build -t myzoo/building_monitor ./devices/building_monitor

echo "[9/11] 🏠 Construindo Domótica..."
docker build -t myzoo/domotic_monitor ./devices/domotic_monitor

echo "[10/11] 🌫️  Construindo Air Quality (Legado)..."
docker build -t myzoo/air_quality ./devices/air_quality

# 6. Saúde
echo "[11/11] 🏥 Construindo mHealth (Paciente)..."
docker build -t myzoo/mhealth ./devices/mhealth-device

echo "=============================================="
echo "✅ SUCESSO! Todas as imagens foram criadas."
echo "=============================================="
