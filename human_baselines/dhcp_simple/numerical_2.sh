#!/bin/bash
# Query: Show logs with retry interval less than 5
grep -E "interval [1-4]$" "$1"
