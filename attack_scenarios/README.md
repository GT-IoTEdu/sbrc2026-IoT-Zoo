# IoT-Zoo attack scenarios

A scenario YAML enables one or more attack containers on top of the benign L3 topology.
The topology itself remains in `topology_l3_segmented_institutional.yaml`.

Run example:

```bash
sudo python3 run_experiment.py \
  --topology topology_l3_segmented_institutional.yaml \
  --attack-scenario attack_scenarios/mqtt_publisher_flood.yaml \
  --time 180 \
  --output /tmp/iot_zoo_l3.pcap
```

Validate example:

```bash
python3 scripts/validate_l3_pcaps.py \
  --pcap-dir /tmp \
  --prefix iot_zoo_l3 \
  --out-dir ./validation_mqtt_publisher_flood \
  --expect-ip 10.10.0.60 \
  --expect-ip 10.20.0.100 \
  --expect-port 1883
```

Recommended campaign order:

1. benign-only baseline;
2. one isolated attack scenario at a time;
3. multi-attack scenarios only after isolated runs are validated.
