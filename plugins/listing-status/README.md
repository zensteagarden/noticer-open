# Listing status

Plugin id: `listing-status`

Host: Node producer. It takes the status line a realtor named, plus the disclosed selection from before the change and after it, and writes a schema 0.1 directory packet. It does not verdict. It does not log into an MLS. Chrome page capture can supply the two selections. This plugin does not collect the page.

Observable proxy: `artifact.text.exact.v1` on the whole disclosed before selection and the whole disclosed after selection.

That proxy does not establish that the MLS accepted the change, that a buyer saw it, that the page still says this, who wrote the page, that an external write happened, or authorization to act. There is no absence policy. "Coming Soon is gone" is not a verdict unless the whole after selection equals the status line they named.

## Unpack, then let the trunk verdict

```sh
node plugins/listing-status/unpack.mjs plugins/listing-status/fixtures/after-says-active.bundle.json ./listing-packet
node src/cli.mjs verify ./listing-packet --policy packet.integrity.v1
node src/cli.mjs verify ./listing-packet --policy artifact.text.exact.v1
```

Integrity ALLOW only means both selections arrived intact. Exact-text ALLOW means the before selection equals the named before line and the after selection equals the named status line. A portal toast that says Active while the after selection still says Coming Soon is DENY on exact-text and can still ALLOW on integrity.

## Check the producer

```sh
node --test plugins/listing-status/plugin.test.mjs
```

Apache-2.0. Same NOTICE as the trunk.
