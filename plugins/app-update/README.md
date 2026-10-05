# App update

Plugin id: `app-update`

Host: Node producer. It takes two disclosed text snapshots, before and after, and writes a schema 0.1 directory packet. It does not verdict. A Chrome capture can feed it later. This plugin does not collect the page.

Observable proxy: `artifact.text.exact.v1` on the disclosed before bytes and the disclosed after bytes.

That proxy does not establish that a release shipped, that a substring was removed from a larger page, who wrote either snapshot, that the page still says this, that an external write happened, or authorization to act. There is no public absence policy. "Gone" is not a verdict here. The before blob is bound only by an exact-text claim on those before bytes.

## Unpack, then let the trunk verdict

```sh
node plugins/app-update/unpack.mjs plugins/app-update/fixtures/after-is-ready.bundle.json ./update-packet
node src/cli.mjs verify ./update-packet --policy packet.integrity.v1
node src/cli.mjs verify ./update-packet --policy artifact.text.exact.v1
```

Integrity ALLOW only means both snapshots arrived intact. Exact-text ALLOW means the before bytes equal the named before text and the after bytes equal the named after text. A release note that says ready while the after bytes are still loading is DENY on exact-text and can still ALLOW on integrity.

## Check the producer

```sh
node --test plugins/app-update/plugin.test.mjs
```

Apache-2.0. Same NOTICE as the trunk.
