#!/bin/bash
# Query: Return DHCP server IP addresses that are not broadcast addresses
grep -v "255.255.255.255" "$1" | grep -iE "DHCP(OFFER|ACK)"
