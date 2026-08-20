#!/bin/bash
# Query: Find audit log lines that show SELinux boolean changes.
grep "bool=" "$1"
