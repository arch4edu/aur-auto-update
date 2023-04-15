#!/bin/bash
echo "$@" | openssl pkeyutl -encrypt -pubin -inkey auto-update-bot.pem | base64
