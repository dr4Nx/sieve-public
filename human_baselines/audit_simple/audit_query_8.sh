#!/bin/bash
# Query: Find audit log lines for PAM session open events.
grep -i "pam.*session.*open\|session_open" "$1"
