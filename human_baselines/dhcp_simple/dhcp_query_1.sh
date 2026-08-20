#!/bin/bash
# Query: Return lines assigning an IP to host laphroaig
grep "laphroaig" "$1" | grep -i "DHCPACK"
