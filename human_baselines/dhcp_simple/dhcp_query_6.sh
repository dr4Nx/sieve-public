#!/bin/bash
# Query: Find the unique DHCP destination IPs used with non-standard ports
grep "port" "$1" | grep -v "port 67" | grep -v "port 68"
