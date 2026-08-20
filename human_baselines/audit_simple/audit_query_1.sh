#!/bin/bash
# Query: Find audit log lines that report SELinux AVC denials.
grep "avc.*denied\|denied.*avc" "$1"
