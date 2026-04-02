import os
import subprocess
import pandas as pd
import argparse

def main():
    parser = argparse.ArgumentParser(description='IoT-Zoo PCAP to CSV Converter')
    parser.add_argument('--input', required=True, help='Path to input PCAP file')
    parser.add_argument('--output', default='final_dataset.csv', help='Final CSV name')
    args = parser.parse_args()

    # 1. Tshark Extraction (Application Features)
    print("🚀 Step 1: Running Tshark extraction...")
    tshark_cmd = (
        f"tshark -r {args.input} -T fields "
        "-e frame.number -e frame.time_epoch -e frame.len -e ip.src -e ip.dst "
        "-e ip.proto -e tcp.srcport -e tcp.dstport -e tcp.flags "
        "-e _ws.col.Protocol -e mqtt.topic -e mqtt.msgtype -e mqtt.qos -e mqtt.len "
        "-E header=y -E separator=/t > tmp_tshark.csv"
    )
    subprocess.run(tshark_cmd, shell=True, check=True)

    # 2. Scapy Extraction (Network Features)
    print("🚀 Step 2: Running Scapy extraction...")
    from extract_scapy import run_scapy_extraction
    run_scapy_extraction(args.input, "tmp_scapy.csv")

    # 3. Merge via pkt_index
    print("🚀 Step 3: Merging features...")

    df_t = pd.read_csv("tmp_tshark.csv", sep='\t', on_bad_lines='skip', low_memory=False)
    df_s = pd.read_csv("tmp_scapy.csv")
    
    df_t.rename(columns={'frame.number': 'pkt_index'}, inplace=True)
    
    df_final = pd.merge(df_s, df_t, on='pkt_index', how='inner')
    
    df_final.to_csv(args.output, index=False)
    
    if os.path.exists("tmp_tshark.csv"): os.remove("tmp_tshark.csv")
    if os.path.exists("tmp_scapy.csv"): os.remove("tmp_scapy.csv")
    
    print(f"🎉 Success! Dataset generated: {args.output} ({len(df_final)} rows)")

if __name__ == "__main__":
    main()
