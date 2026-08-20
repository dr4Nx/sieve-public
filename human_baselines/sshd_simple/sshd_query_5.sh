#!/bin/bash
# Query: Find log lines showing SSH session openings.
grep "session opened" "$1"
