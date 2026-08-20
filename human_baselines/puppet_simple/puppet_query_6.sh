#!/bin/bash
# Query: Find log lines showing Puppet could not deliver its report back to a remote service.
grep "Could not send report" "$1"
