#!/bin/bash
# Query: Show DHCPOFFER or DHCPACK messages from server 192.168.1.1
grep -E "DHCPOFFER|DHCPACK" "$1" | grep "192.168.1.1"
