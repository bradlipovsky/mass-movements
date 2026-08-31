# NIST Beacon verification record

This directory freezes the authority and procedure used for the issue #17
sample before a pulse is requested. The public frame comment was created at
`2026-08-31T18:03:26Z`. The registered target is therefore
`2026-08-31T19:03:26Z`, or `1788203006000` Unix milliseconds, and the exact
argument to the strictly-later endpoint is `1788203005999`.

No pulse, certificate, randomized frame, or selected-cell value had been
retrieved when this record was written. The canonical frame remains the LF
byte sequence with SHA-256
`482c9d585777317ab69363481db3df1011e2d4e8ce84c3826b151406cace9879`.

## Authority

`beacon-2.0.xsd` is the live NIST schema retrieved from the URL linked by the
NIST Beacon 2.0 service page. `NIST.IR.8213-draft.pdf` is the May 2019 draft
reference linked by the same page. Their HTTP responses and byte hashes are
retained here.

The deployed schema and draft disagree about serialization. The live schema
uses four-byte big-endian length prefixes and a four-byte external status. The
draft uses eight-byte prefixes and an eight-byte external status. Verification
will use the deployed schema. The draft encoding will be retained as a
negative comparison, not as a fallback.

## Signed message

For the deployed schema, UTF-8 strings and hex-decoded values receive a
four-byte big-endian byte-length prefix. Cipher suite, period, external status,
and pulse status are four-byte big-endian integers. Chain and pulse indices are
eight-byte big-endian integers. Fields enter the message in this order:

1. URI, version, cipher suite, period, and certificate identifier;
2. chain index, pulse index, timestamp, and local random value;
3. external source identifier, status, and value;
4. the received previous, hour, day, month, and year values, without their
   type labels or URIs;
5. precommitment value and pulse status.

The RSA PKCS#1 v1.5 signature must verify the SHA-512 hash of these serialized
bytes under the public key in the identified certificate. The executable
check is

```text
openssl dgst -sha512 -verify public_key.pem \
  -signature signature.bin signed_fields.bin
```

The pulse output is checked independently as
`SHA512(signed_fields.bin || signature.bin)`. The same calculations are
required for the preceding pulse.

## Acceptance gates

Before `scripts/geographic_select.py` may run, all of the following must pass:

- the GitHub comment remains unique, exact, and unedited, and the named commit
  remains on the remote branch with the registered frame bytes;
- the returned pulse is version 2.0, cipher suite 0, period 60,000, status zero,
  and falls from the target through target plus 24 hours;
- the response URI, indices, certificate identifier, signature, output, and
  five ordered link values are present;
- SHA-512 of the leaf certificate DER equals the certificate identifier, the
  certificate verifies and is valid at the pulse epoch, and the pulse
  signature and recomputed output both agree;
- the preceding pulse independently verifies, has the same chain and the
  immediately preceding index, and is separated by 60,000 milliseconds;
- the preceding output equals the current `previous` value, and SHA-512 of the
  current local random bytes equals the preceding precommitment; and
- the exact request, response headers and bytes, certificates, signed bytes,
  signatures, OpenSSL output, retrieval times, and hashes are retained.

Any failed or unavailable gate stops the draw. There is no alternate beacon,
local seed, changed frame, delayed target, or draft-serialization fallback.
