#!/bin/bash
# Query: Find log lines showing certificate validation or trust failures during remote Puppet communication.
grep "certificate verify failed" "$1"
