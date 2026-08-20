#!/bin/bash
# Query: Find log lines indicating Puppet execution was re-enabled after being disabled.
grep "Enabling Puppet" "$1"
