#!/bin/bash
# Query: Find audit log lines showing kernel audit initialization events.
grep "initialized" "$1" | grep "type=2000"
