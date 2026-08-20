#!/bin/bash
# Query: Find audit log lines for failed SSH authentication attempts handled by sshd.
grep "sshd" "$1" | grep "failed"
