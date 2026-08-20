#!/bin/bash
# Query: Find log lines showing SSH session closings.
grep "session closed" "$1"
