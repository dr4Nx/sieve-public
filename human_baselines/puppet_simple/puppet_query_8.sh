#!/bin/bash
# Query: Find log lines where Puppet reports that a needed command could not be found.
grep "command not found" "$1"
