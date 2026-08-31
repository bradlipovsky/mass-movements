# NIST Beacon execution record

The public GitHub frame anchor was rechecked before contacting the beacon. At
`2026-08-31T19:04:31Z`, issue 17 contained exactly one comment beginning
`Frame freeze:`. Comment 5482406481 retained the complete body
`Frame freeze: 0ff1c327468b5fb874ef2f87b1d64107838418e5`, and its
`created_at` and `updated_at` fields both remained
`2026-08-31T18:03:26Z`. The frame extracted from that commit and the working
frame were byte-identical, with SHA-256
`482c9d585777317ab69363481db3df1011e2d4e8ce84c3826b151406cace9879`.
The remote branch resolved to verification commit
`0e3019c28aea803926e0ac35aea1842f89651613`.

The exact registered request was

```text
https://beacon.nist.gov/beacon/2.0/pulse/time/next/1788203005999
```

It began at `2026-08-31T19:04:43Z` and completed at
`2026-08-31T19:04:44Z`. The HTTP response date was
`2026-08-31T19:04:44Z`. Raw headers and JSON are retained. The returned pulse
was chain 2, index 1921300, signed at `2026-08-31T19:04:00.000Z`, 34 seconds
after the registered target. Its version is 2.0, cipher suite is 0, period is
60,000 milliseconds, and status is zero.

## Cryptographic checks

The pulse-identified certificate and pulse 1921299 were retrieved at
`2026-08-31T19:04:57Z`. The leaf certificate DER has SHA-512
`528943a555f5f8ca54423be6dfb95925a35c7b552046420e7d7cd072058a14d6536ad3a8e9754b6582f164a90b0cd86a65d659f5426a2659a947595d1c816c8c`,
exactly the signed certificate identifier. Its validity interval is
2025-08-28 through 2026-09-04 UTC. The DigiCert intermediate named by its AIA
was retained, and OpenSSL 1.1.1k verified the leaf at Unix time 1788203040
against the system DigiCert Global Root G2 trust anchor:

```text
openssl verify -attime 1788203040 -purpose any \
  -CAfile /etc/pki/tls/certs/ca-bundle.crt \
  -untrusted verification/issuer_certificate.pem certificate.pem
certificate.pem: OK
```

The live NIST schema's four-byte length encoding produced 807 signed bytes for
each pulse. RSA PKCS#1 v1.5 SHA-512 verification returned `Verified OK` for
both. SHA-512 of signed bytes followed by the 512-byte signature independently
reproduced each published output. The current pulse's `previous` value equals
the preceding output; both use chain 2, their indices differ by one, their
timestamps differ by 60,000 milliseconds, and SHA-512 of the current local
random value equals the preceding precommitment. The draft eight-byte encoding
produced 863 signed bytes and returned `Verification Failure` for both pulses,
as expected; it was not used as a fallback.

## Selection

Only after all checks above succeeded, the pulse output was passed to the
frozen selector. All 1,826 frame rows received unique HMAC-SHA256 digests.
Exactly 96 rows were selected, with the frozen allocations of 4--12 cells in
each of 19 nonempty RGI strata and zero in empty region 20. Every selected
count, first-order inclusion probability, and same-stratum pair probability
reproduces the protocol. The full randomized frame has SHA-256
`14db0fffd4d46c52b5cea7cba29c783d958aa94fefca8dd67e210df1a8134022`;
the selected sample has SHA-256
`1e9164813893e285aeeeaa1a7833e16c87172cbe4d3357e245854ab13966613b`.
No DEM, PZI, case, climate, or terrain-outcome value entered the draw.
