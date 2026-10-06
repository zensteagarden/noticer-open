# Listing line

Plugin id: `listing-status`

One app for four line kinds: `status`, `price`, `offer`, `disclosure`. The kind is a label. The trunk ignores it. Each check is still the whole disclosed before line and the whole disclosed after line.

Host: Node producer. It does not verdict. It does not log into an MLS. Chrome page capture can supply a page selection. A saved email can supply an offer line. This plugin does not collect either.

Observable proxy: `artifact.text.exact.v1`.

That proxy does not establish that the MLS accepted the change, that a buyer saw it, that the page still says this, that an offer was delivered, that a disclosure form is complete, who wrote the line, that an external write happened, or authorization to act. There is no absence policy. One ALLOW is one line, not all four.

## The sentence the realtor needs

```sh
node plugins/listing-status/check.mjs --expect "Price · $425,000" --public "Price · $450,000"
```

This builds the packet, asks the trunk, and prints one sentence. `Match. You can tell the seller.` or `Not yet. The page still says ...`. It does not show integrity, a line kind, or an exit code. The before line is not collected on this screen. The check is whether the copied public line equals the line they meant to announce.

```sh
node plugins/listing-status/guide.mjs --kind price --before "Price · $450,000" --after "Price · $425,000" --expect-before "Price · $450,000" --expect-after "Price · $425,000" --out ./price.bundle.json
node plugins/listing-status/unpack.mjs ./price.bundle.json ./listing-packet
node src/cli.mjs verify ./listing-packet --policy artifact.text.exact.v1
```

`guide.mjs` writes a bundle. It does not verdict.

Shipped false-greens:

- status: portal said Active, selection still Coming Soon
- price: portal said reduced, selection still the old price
- offer: sent toast said the new offer, line still the old price
- disclosure: upload toast said posted, line still says missing

Integrity ALLOW only means both lines arrived intact. Exact-text DENY means the after line is not the line they named.

## Check the producer

```sh
node --test plugins/listing-status/plugin.test.mjs
```

Apache-2.0. Same NOTICE as the trunk.
