#!/bin/bash
# Query: Find log lines indicating Puppet runs were disabled by an administrative action.
grep -i "administratively disabled\|disabling puppet" "$1"
