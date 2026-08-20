#!/bin/bash
# Query: Find all DHCP messages with transaction ID starting with 0x7
grep "xid=0x7" "$1"
