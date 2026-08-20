#!/bin/bash
# Query: Find the unique hosts reporting an XMT Renew message
grep "XMT" "$1" | grep -i "renew"
