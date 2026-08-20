#!/bin/bash
# Query: Find log lines showing successful SSH logins using password authentication.
grep "Accepted password" "$1"
