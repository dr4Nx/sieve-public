#!/bin/bash
# Query: Find audit log lines that show SELinux policy loads.
grep "policy loaded" "$1"
