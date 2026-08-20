#!/bin/bash
# Query: Find log lines showing the SSH server starting and listening on a port.
grep "Server listening" "$1"
