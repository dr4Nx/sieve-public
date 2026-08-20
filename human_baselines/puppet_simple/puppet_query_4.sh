#!/bin/bash
# Query: Find log lines showing the agent could not retrieve its catalog from a remote source.
grep "Could not retrieve catalog from remote server" "$1"
