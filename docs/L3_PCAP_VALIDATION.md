# IoT-Zoo L3 PCAP validation and merge tools

## 1. Validate the L3 run

After running:

```bash
./scripts/run_l3.sh --time 120 --output /tmp/iot_zoo_l3.pcap
```

run:

```bash
python3 scripts/validate_l3_pcaps.py --pcap-dir /tmp --prefix iot_zoo_l3 --out-dir ./validation_l3
```

The script generates:

- `validation_l3/pcap_summary.csv`
- `validation_l3/pcap_summary.json`
- `validation_l3/tcpdump_log_summary.csv`
- `validation_l3/mqtt_topics.csv`
- `validation_l3/VALIDATION_REPORT.md`

It checks:

- all expected PCAP files exist;
- PCAPs are non-empty;
- packet counts;
- MQTT and TCP/1883 visibility;
- RTSP and TCP/8554 visibility;
- source/destination IP diversity;
- domains visible in each capture;
- tcpdump logs for common errors.

## 2. Merge PCAPs when needed

Domain/access switch captures:

```bash
./scripts/merge_l3_pcaps.sh --pcap-dir /tmp --prefix iot_zoo_l3 --out-dir ./merged_l3 --mode domain
```

Router/interface captures:

```bash
./scripts/merge_l3_pcaps.sh --pcap-dir /tmp --prefix iot_zoo_l3 --out-dir ./merged_l3 --mode router
```

All capture points:

```bash
./scripts/merge_l3_pcaps.sh --pcap-dir /tmp --prefix iot_zoo_l3 --out-dir ./merged_l3 --mode all
```

## 3. ML recommendation

For ML experiments, do not blindly merge all PCAPs and treat the merged file as a single independent trace. Multi-point captures can include the same packet observed at multiple locations.

Recommended workflow:

1. Convert each PCAP separately to flows/features.
2. Add metadata columns such as `capture_point`, `domain`, `subnet`, and `vantage_type`.
3. Concatenate the resulting CSVs.
4. Use per-domain CSVs for non-IID/domain-aware experiments.
5. Use core/router CSVs for centralized visibility experiments.

A fully merged PCAP is useful for exploratory analysis or a global trace, but it should be accompanied by deduplication or explicit capture-point metadata.
