#!/bin/bash
# Query: List all hosts which sent a DHCPDISCOVER messages
grep "DHCPDISCOVER" "$1"
