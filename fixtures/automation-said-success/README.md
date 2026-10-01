Packet-only sample. The captured body is the bytes `accepted`. It is not a live destination check.

`packet.integrity.v1` can ALLOW because the digest matches.
`artifact.text.exact.v1` DENYs because those bytes are not `ok`.
Neither result establishes that an external write occurred.
Public adjudication is unsupported. This sample does not produce PROVED.
