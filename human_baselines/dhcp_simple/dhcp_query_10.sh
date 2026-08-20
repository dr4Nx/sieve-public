#!/bin/bash
# Query: Return logs reporting bad IP checksums
grep -i "bad.*checksum\|checksum.*bad" "$1"
