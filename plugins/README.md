# Plugins

Noticer stays the trunk. A use case is a plugin that emits a disclosed packet. The trunk verdicts.

| Plugin | Host | Produces | Verdicts |
| --- | --- | --- | --- |
| `chrome-page-capture` | Chrome extension, Manifest V3 | page-text bundle, unpacked to a directory packet | no |
| `app-update` | Node producer | before and after text snapshots, unpacked to a directory packet | no |

MCP and API adapters are the same contract when you need them. Do not fork `src/verify.mjs` into those hosts.

Read [CONTRACT.md](CONTRACT.md) before adding a plugin.
