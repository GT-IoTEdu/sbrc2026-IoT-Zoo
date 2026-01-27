#!/bin/bash

# Script de Construção Automática do IoT-Zoo
# Deve ser executado da raiz do projeto: sudo ./build_images.sh

set -e # Para o script se houver erro em qualquer build

echo "=============================================="
echo "🏗️  INICIANDO CONSTRUÇÃO DO IOT-ZOO IMAGES"
echo "=============================================="

# 1. Infraestrutura
echo "[1/11] 📡 Construindo Broker MQTT..."
docker build -t myzoo/mqtt_broker ./devices/mqtt_broker_mosquitto

# 2. Sensores Urbanos (O Núcleo do Experimento)
echo "[2/11] 🏙️  Construindo Urban Sensor (Gateway Universal)..."
# Atenção: Certifique-se que a pasta air_quality_urban_repository existe
docker build -t myzoo/urban_sensor ./devices/air_quality_urban_repository

# 3. Sistema de Vídeo (CCTV)
echo "[3/11] 📹 Construindo Servidor de Vídeo (RTSP)..."
docker build -t myzoo/server_video ./devices/server_video_rtsp

echo "[4/11] 📷 Construindo Câmera IP..."
docker build -t myzoo/camera ./devices/camera_ip

echo "[5/11] 📺 Construindo Consumidor de Vídeo..."
docker build -t myzoo/consumer_video ./devices/consumer_video

# 4. Indústria 4.0
echo "[6/11] 🏭 Construindo Cooler Motor (Vibração/Binário)..."
docker build -t myzoo/cooler_motor ./devices/cooler_motor_industrial

echo "[7/11] ⚙️  Construindo Manutenção Preditiva..."
docker build -t myzoo/predictive_maintenance ./devices/predictive_maintenance

# 5. Smart Building / Home
echo "[8/11] 🏢 Construindo Smart Building..."
docker build -t myzoo/building_monitor ./devices/building_energy_monitor

echo "[9/11] 🏠 Construindo Domótica (Legado)..."
docker build -t myzoo/domotic_monitor ./devices/domotic_monitor

echo "[10/11] 🌫️  Construindo Air Quality (Legado)..."
docker build -t myzoo/air_quality ./devices/air_quality_legacy

# 6. Saúde
echo "[11/11] 🏥 Construindo mHealth (Paciente)..."
docker build -t myzoo/mhealth ./devices/mhealth_monitor

echo "=============================================="
echo "✅ SUCESSO! Todas as 11 imagens foram criadas."
echo "   Agora você pode rodar: sudo python3 run_experiment.py"
echo "=============================================="
