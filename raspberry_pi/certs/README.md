# TLS Certificates

Place your TLS certificates here:

- ca.crt        # CA certificate
- server.crt    # Server certificate
- ca.key        # CA private key
- server.key    # Server private key
- ca.srl        # OpenSSL metadata
- server.csr    # Certificate signing request

You can generate all certificates locally with:

```bash
./generate_certs.sh
```
