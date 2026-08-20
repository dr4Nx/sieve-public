#!/bin/bash
# Query: Find log lines where an SSH login was attempted with an invalid or unknown username.
grep -E "Invalid user|check pass; user unknown" "$1"
