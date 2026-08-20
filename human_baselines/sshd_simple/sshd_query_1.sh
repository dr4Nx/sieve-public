#!/bin/bash
# Query: Find log lines recording SSH authentication failures.
grep -E "authentication failure|Failed password|Invalid user" "$1"
