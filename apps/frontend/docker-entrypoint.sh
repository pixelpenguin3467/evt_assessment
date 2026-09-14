#!/bin/sh
set -eu
# Demo TLS only: self-signed cert at start so no private key is in git or the image.
openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout /tmp/tls.key -out /tmp/tls.crt -days 365 \
  -subj "/CN=localhost" >/dev/null 2>&1
exec nginx -g "daemon off;"
