import pandas as pd
from scapy.all import PcapReader, IP, TCP, UDP

def run_scapy_extraction(input_pcap, output_csv):
    data = []
    with PcapReader(input_pcap) as pcap_reader:
        for i, pkt in enumerate(pcap_reader):
            if pkt.haslayer(IP):
                res = {
                    'pkt_index': i + 1,
                    'ip_ttl': pkt[IP].ttl,
                    'tcp_seq': pkt[TCP].seq if pkt.haslayer(TCP) else 0,
                    'tcp_flags_str': str(pkt[TCP].flags) if pkt.haslayer(TCP) else ""
                }
                data.append(res)
    pd.DataFrame(data).to_csv(output_csv, index=False)
