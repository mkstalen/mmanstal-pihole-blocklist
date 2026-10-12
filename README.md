# Pi-hole merged blocklist

A single, de-duplicated blocklist built daily from the lists in [`sources.txt`](sources.txt).

**Pi-hole URL:**

```
https://raw.githubusercontent.com/mkstalen/mmanstal-pihole-blocklist/main/blocklist.txt
```

## How it works

A GitHub Actions workflow runs every day at about 3am Sydney time. It:

1. Downloads every list in `sources.txt` (hosts-file, plain-domain and Adblock `||domain^` formats).
2. Merges them, removes duplicates and invalid entries.
3. Adds anything in `extra-blocks.txt` and removes anything in `allowlist.txt`.
4. Commits `blocklist.txt` only if something changed.

If any source fails to download, or the merged list suddenly shrinks by more than half,
the run fails and the previous list stays live. GitHub emails you when a run fails.

## Making changes

- **Add or remove a source:** edit `sources.txt`.
- **Never block a domain:** add it to `allowlist.txt`.
- **Always block a domain:** add it to `extra-blocks.txt`.

Any of these edits triggers a rebuild straight away. You can also run it manually from
**Actions → Update blocklist → Run workflow**.
