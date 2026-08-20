#!/bin/bash
# Query: Find log lines reporting deprecated SSH configuration options.
grep "Deprecated" "$1"
