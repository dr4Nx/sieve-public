#!/bin/bash
# Query: Find audit log lines that show SELinux enforcing mode changes.
grep "enforcing=" "$1"
