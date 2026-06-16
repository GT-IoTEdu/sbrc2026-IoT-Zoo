# Dataset organization

IoT-Zoo keeps datasets close to the device profiles that use them. Most datasets are compressed as `.csv.xz` to reduce repository size.

## General profile layout

Most profiles follow this structure:

```text
devices/<profile_name>/
├── Dockerfile
├── client.py
└── <dataset-folder-or-file>.csv.xz
```

Examples:

```text
devices/air_quality/air_quality/AirQualityUCI.csv.xz
devices/aquaponics_fish_pond/dataset/dataset.csv.xz
devices/building_monitor/appliances_energy/energydata_complete.csv.xz
devices/predictive_maintenance/ai4i2020/ai4i2020.csv.xz
```

During the Docker image build, each Dockerfile copies the dataset expected by its profile. If a dataset file is missing, the corresponding image build will fail with a Docker `COPY` error.

## Urban Observatory layout

The Urban Observatory profile is different because it contains several datasets organized by domain:

```text
devices/urban_observatory/
├── air_quality/
│   ├── 2025-CO.csv.xz
│   ├── 2025-NO.csv.xz
│   ├── 2025-NO2.csv.xz
│   └── ...
├── building/
│   └── ...
├── weather/
│   └── ...
├── water/
│   └── ...
└── urban_sensor.py
```

The full orchestrator mounts `devices/urban_observatory/` at runtime. Before starting the full topology, `run_experiment.py` checks this folder and uncompresses missing `.csv` files from `.csv.xz` sources when needed, while keeping the original `.csv.xz` files.

## Basic demo data

The basic demo uses only a small subset of the Urban Observatory data. To avoid duplicating datasets, demo files are generated from the full `.csv.xz` files:

```bash
./scripts/prepare_demo_data.sh --duration 120 --clean
```

This command creates small CSV files under:

```text
sample_data/urban_observatory/
```

The generated files are enough to validate the pipeline for a 60- or 120-second basic demo, with a small safety margin. The script samples the sources needed by `demo_experiment.py`:

```text
CO air-quality telemetry
NO2 air-quality telemetry
Internal Temperature building telemetry
```

The original compressed datasets are not modified.

## Full topology data

The full topology uses the complete profile catalog and the datasets stored under each device profile folder. The most relevant expected paths are:

```text
devices/air_quality/air_quality/AirQualityUCI.csv.xz
devices/aquaponics_fish_pond/dataset/dataset.csv.xz
devices/building_monitor/appliances_energy/energydata_complete.csv.xz
devices/domotic_monitor/sml2010/*.txt.xz
devices/elevator_predictive_maintenance/dataset/dataset.csv.xz
devices/environmental_sensors/dataset/dataset.csv.xz
devices/farming_sensor/dataset/dataset.csv.xz
devices/greenhouse_sensor/dataset/dataset.csv.xz
devices/ip_camera/museum_lebanon.mp4
devices/mhealth-device/mhealth/*
devices/nurse-stress-prediction/dataset/dataset.csv.xz
devices/predictive_maintenance/ai4i2020/ai4i2020.csv.xz
devices/smart_building_m5/dataset/dataset.csv.xz
devices/smart_lighting/dataset/dataset.csv.xz
devices/traction-elevator-predictive-maintenance/dataset/dataset.csv.xz
devices/urban_observatory/**/*.csv.xz
```

## Verifying dataset availability

Use:

```bash
./scripts/check_environment.sh
```

For a quick check of compressed files:

```bash
find devices -name "*.csv.xz" -o -name "*.txt.xz" -o -name "*.mp4"
```

For the basic demo specifically:

```bash
./scripts/prepare_demo_data.sh --duration 120 --clean
find sample_data/urban_observatory -name "*.csv"
```
