#!/bin/bash
# Query: Find log lines showing successful SSH logins using public key authentication.
grep "Accepted publickey" "$1"
