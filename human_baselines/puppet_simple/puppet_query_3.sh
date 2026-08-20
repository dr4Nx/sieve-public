#!/bin/bash
# Query: Find log lines where Puppet says it could not fetch the node definition it needed.
grep "Unable to fetch my node definition" "$1"
