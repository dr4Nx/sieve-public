#!/bin/bash
# Query: Find audit log lines that record the audit daemon process ID being set or changed.
grep "audit_pid=" "$1"
