#!/bin/bash
# Query: Find audit log lines for systemd unit start events that name a service unit.
grep "unit=" "$1" | grep "type=1130"
