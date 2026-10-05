# Chrome page capture

Plugin id: `chrome-page-capture`

Host: Chrome extension, Manifest V3. It captures selected text, or the page text if nothing is selected, and downloads a bundle. It does not verdict.

Observable proxy: `artifact.text.exact.v1` on the disclosed UTF-8 bytes.

That proxy does not establish who wrote the page, that the page still says this, that an external write happened, or authorization to act.

## Load the extension

1. Chrome → Extensions → enable Developer mode.
2. Load unpacked → this directory.
3. Open a page, optionally select the text you want disclosed, then click the extension.
4. Name the intention and the exact text the trunk should require.
5. Export the bundle.

## Unpack, then let the trunk verdict

From this repository:

```sh
node plugins/chrome-page-capture/unpack.mjs noticer-page-capture.bundle.json ./page-packet
node src/cli.mjs verify ./page-packet --policy packet.integrity.v1
node src/cli.mjs verify ./page-packet --policy artifact.text.exact.v1
```

Integrity ALLOW only means the packet is intact. Exact-text ALLOW means the disclosed bytes equal the text you named. Neither is PROVED. Public PROVED stays disabled.

## Check the producer

```sh
node --test plugins/chrome-page-capture/plugin.test.mjs
```

Apache-2.0. Same NOTICE as the trunk.
