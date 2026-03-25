#!/bin/bash
mkdir -p raspberry_pi/certs
cd raspberry_pi/certs

# CA
openssl genrsa -out ca.key 2048
openssl req -x509 -new -nodes -key ca.key -days 365 -out ca.crt

# Server
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key \
-CAcreateserial -out server.crt -days 365

echo "Certificates generated"
