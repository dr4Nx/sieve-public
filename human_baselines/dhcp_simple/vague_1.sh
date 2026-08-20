#!/bin/bash
# Query: Show me DHCP errors
grep -iE "error|fail|bad|reject|denied|refused" "$1"
