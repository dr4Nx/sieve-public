#!/bin/bash
# Query: Find DHCPREQUEST messages on interface eth0 from host localhost with port 67
grep "DHCPREQUEST" "$1" | grep "eth0" | grep "localhost" | grep "port 67"
