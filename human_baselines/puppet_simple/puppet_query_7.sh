#!/bin/bash
# Query: Find log lines showing resources were skipped because a dependency chain had already failed.
grep "Skipping because of failed dependencies" "$1"
