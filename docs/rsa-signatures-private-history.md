# RSA signatures and private history API

This contract targets Python 3.12 and `cryptography==50.0.2`. Standard signatures use
RSASSA-PSS from RFC 8017 with SHA-256, MGF1(SHA-256), and a 32-byte salt. Signatures are
transported as standard padded base64. This is a proof-of-possession check only: the API does
not certify a person, account, certificate, PKI identity, or legal validity.

Deploy these routes only through HTTPS. History ownership is an anonymous, server-issued browser credential in
the `cw_history_profile` cookie (`HttpOnly`, `Secure`, `SameSite=Lax`). FE requests must include
credentials. Tabs in one browser profile share the credential; another profile cannot list,
read, download, or delete those records. Sharing a browser profile also shares its history.
`HISTORY_PROFILE_SIGNING_KEY` must be a stable 64-character hexadecimal (256-bit) secret whenever
`DATABASE_URL` is configured. Rotating it invalidates existing browser credentials without assigning
their rows to another visitor. Empty profiles retain the same valid cookie; database lookup failures
do not rotate it, and a client cannot forge a different owner identifier without the signing key.
The reverse proxy/APM must not capture request bodies, multipart fields, cookies, or query/body
payloads for these routes; the application itself logs only safe exception type/path metadata.

## Routes

### Raw educational integer signature

`POST /api/rsa/sign/raw` (`application/json`):

```json
{"m":"65","d":"2753","e":"17","n":"3233"}
```

The response contains the actual `signature = m^d mod n`, the supplied public key `{e,n}`, and
the complete bounded square-and-multiply trace. The private exponent and trace are returned to
the caller for analysis but are never stored in history.

```json
{
  "success": true,
  "result": {
    "mode": "raw-integer",
    "warning": "Raw RSA integer arithmetic is educational only; ...",
    "m": "65",
    "signature": "588",
    "publicKey": {"e": "17", "n": "3233"},
    "trace": {"operation": "sign", "input": "65", "exponent": "2753", "modulus": "3233", "result": "588", "steps": []}
  },
  "history": {"saved": true, "id": 123, "reason": "saved"}
}
```

`trace.steps` is abbreviated above; the real response includes every bounded
square-and-multiply row.

`POST /api/rsa/verify/raw` (`application/json`):

```json
{"m":"65","signature":"588","e":"17","n":"3233"}
```

The response contains `recoveredMessage = signature^e mod n` and `valid`, which compares the
recovered integer to `m`. All cryptographic numbers are ASCII decimal strings, bounded by the
existing 128-bit educational domain. `n >= 2`, `d >= 1`, `e >= 1`, and
`0 <= m,signature < n`. Raw mode is textbook modular arithmetic, not a secure document-signing
scheme.

```json
{
  "success": true,
  "result": {
    "mode": "raw-integer",
    "warning": "Raw RSA integer arithmetic is educational only; ...",
    "valid": true,
    "m": "65",
    "recoveredMessage": "65",
    "signature": "588",
    "publicKey": {"e": "17", "n": "3233"},
    "trace": {"operation": "verify", "input": "588", "exponent": "17", "modulus": "3233", "result": "65", "steps": []}
  },
  "history": {"saved": true, "id": 124, "reason": "saved"}
}
```

### Standard content signature

`POST /api/rsa/sign` accepts JSON text:

```json
{
  "source": "text",
  "text": "exact text, including CR/LF and whitespace",
  "privateKeyPem": "-----BEGIN ENCRYPTED PRIVATE KEY-----\n...",
  "passphrase": "optional password"
}
```

or multipart file input with fields `file`, `privateKeyPem`, and optional `passphrase`. The file
name must end in `.txt` case-insensitively; MIME is not trusted. The result includes `signature`,
the derived `publicKeyPem`, `sha256`, `contentBytes`, the algorithm descriptor, and `history`.

```json
{
  "success": true,
  "result": {
    "mode": "standard",
    "source": "text",
    "signature": "base64...",
    "publicKeyPem": "-----BEGIN PUBLIC KEY-----\n...",
    "contentBytes": 41,
    "sha256": "hex...",
    "algorithm": {"scheme": "RSASSA-PSS", "hash": "SHA-256", "mgf": "MGF1-SHA-256", "saltLength": 32, "signatureEncoding": "base64"}
  },
  "history": {"saved": true, "id": 125, "reason": "saved"}
}
```

`POST /api/rsa/verify` accepts JSON text:

```json
{
  "source": "text",
  "text": "exact text, including CR/LF and whitespace",
  "signature": "base64 signature",
  "publicKeyPem": "-----BEGIN PUBLIC KEY-----\n..."
}
```

or multipart fields `file`, `signature`, and `publicKeyPem`. A well-formed request always returns
HTTP 200 with `valid: true|false`; a cryptographic mismatch is not an HTTP/service error.

```json
{
  "success": true,
  "result": {"mode": "standard", "source": "file", "valid": false, "contentBytes": 41, "sha256": "hex...", "algorithm": {"scheme": "RSASSA-PSS", "hash": "SHA-256", "mgf": "MGF1-SHA-256", "saltLength": 32, "signatureEncoding": "base64"}},
  "history": {"saved": true, "id": 126, "reason": "saved"}
}
```

Typed content is measured after strict UTF-8 encoding. File content is UTF-8 validated but the
original bytes are signed and stored unchanged: BOM, LF/CRLF/CR, trailing whitespace, and Unicode
normalization form are not transformed. Empty content is rejected; whitespace-only content is
accepted. Exactly 5,242,880 bytes is accepted and byte 5,242,881 is rejected.

### History

- `GET /api/history` lists only the current profile's unexpired summaries.
- `GET /api/history/{id}` returns an owned record and its RSA payload/result.
- `GET /api/history/{id}/content` downloads the original RSA signed/verified bytes.
- `DELETE /api/history/{id}` deletes one owned record.
- `DELETE /api/history` deletes all records owned by the current profile.

Representative detail response (original bytes are deliberately retrieved only from the
`/content` endpoint):

```json
{
  "success": true,
  "result": {
    "id": 125,
    "createdAt": "2026-10-11T10:00:00Z",
    "cipher": "rsa",
    "operation": "sign",
    "source": "file",
    "responseMode": "content",
    "inputLength": 41,
    "outputLength": 344,
    "httpStatus": 200,
    "succeeded": true,
    "durationMs": 3,
    "valid": null,
    "processingState": "completed",
    "contentAvailable": true,
    "logicalSize": 912,
    "payload": {"signature": "base64...", "public_key": "-----BEGIN PUBLIC KEY-----\n...", "result": {"mode": "standard", "sha256": "hex..."}, "processing_state": "completed"}
  }
}
```

Every successful sign and every completed verify (`valid=true` and `valid=false`) attempts a
synchronous history write. Its response reports one of:

```json
{"history":{"saved":true,"id":123,"reason":"saved"}}
```

```json
{"history":{"saved":false,"id":null,"reason":"disabled|unavailable|capacity"}}
```

The cryptographic result remains successful if history cannot be written. Malformed requests,
invalid keys, media/size failures, and unexpected processing failures do not persist RSA content.
Private PEM, private `d`, passphrases, and secret-bearing traces are never history fields.

Records expire five hours after original creation; reads and downloads never extend that time.
The logical history budget is 50 MiB per browser profile and 500 MiB system-wide. Writes evict
the oldest creation time first within the profile, then globally. Therefore records can disappear
before five hours. User deletion and expiry cover live operational rows and payloads, not backups
or forensic removal of old disk bytes. Expired restored rows remain inaccessible and are purged
using their original creation time.

Operational deletion is driven by the oldest row's original-creation deadline, not by a periodic
five-minute grace. The API process and the independent Compose `retention` service both purge on
startup and schedule the next live deadline; a transient write failure is retried after one second.
Stopping only the API leaves the independent worker running. This mechanism has no finite deletion
bound while every retention process is stopped, the host is down, or SQLite cannot write: rows and
payloads remain physically present, although every API read/download rejects them at the five-hour
cutoff, and overdue rows are deleted when a worker can write again. SQLite has no autonomous TTL.
The owner approved the operating assumption that at least one retention worker, its host/container
runtime, and writable SQLite remain available. An outage crossing a record deadline is a contract
breach that must be alerted and remediated, not an authorized grace period or renewal; deletion
resumes immediately on recovery. This approval is not overall acceptance or deployment authority.

## Error envelope

Malformed requests, invalid key/domain inputs, unsupported media/encoding, size failures, and
unexpected failures use the existing RSA envelope:

```json
{"success":false,"code":"INVALID_PUBLIC_KEY","message":"...","field":"publicKeyPem"}
```

- `413`: request/content size (`CONTENT_TOO_LARGE`, `REQUEST_TOO_LARGE`)
- `415`: media, extension, or file encoding (`UNSUPPORTED_MEDIA_TYPE`,
  `UNSUPPORTED_FILE_TYPE`, `INVALID_TEXT_ENCODING`)
- `422`: malformed fields, decimal bounds, PEM/key/passphrase parsing, or signature base64
- `500`: unexpected service failure; messages and logs exclude submitted secrets

## OpenSSL interoperability

Decode the API's base64 signature to `signature.bin`, then verify exact `content.txt` bytes:

```sh
openssl dgst -sha256 -verify public.pem -signature signature.bin \
  -sigopt rsa_padding_mode:pss -sigopt rsa_pss_saltlen:32 \
  -sigopt rsa_mgf1_md:sha256 content.txt
```

An external signature for API verification can be produced with:

```sh
openssl dgst -sha256 -sign private.pem -out signature.bin \
  -sigopt rsa_padding_mode:pss -sigopt rsa_pss_saltlen:32 \
  -sigopt rsa_mgf1_md:sha256 content.txt
```

The private-key command's passphrase source should be supplied using the deployment's secure
OpenSSL mechanism; do not place a real passphrase directly in shell history.

Primary references: [cryptography RSA 50.0.2](https://cryptography.io/en/50.0.2/hazmat/primitives/asymmetric/rsa/),
[RFC 8017](https://www.rfc-editor.org/rfc/rfc8017), and
[OpenSSL RSA signature parameters](https://docs.openssl.org/3.6/man7/EVP_SIGNATURE-RSA/).
