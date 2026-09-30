# Persistent YouTube channel live — Social Stream

## Problem
A normal YouTube *video* live URL stops when that broadcast ends.

## Solution
Paste the **channel live** URL instead:

```
https://www.youtube.com/channel/UCEXGDNclvmg6RW0vipJYsTQ/live
```

The engine converts it to:

```
https://www.youtube.com/embed/live_stream?channel=UCEXGDNclvmg6RW0vipJYsTQ
```

That embed always docks the **current** live on that channel. When one stream ends, the next live on the same channel can start without changing the saved link.

## Admin rules
| Paste | Result |
|-------|--------|
| `/channel/UC…/live` | Persistent channel live |
| `/channel/UC…` | Same |
| `ytchan:UC…` | Same |
| `@Handle/live` | Works if handle resolves to UC… |
| `/watch?v=…` live video | Ends when that broadcast ends |

## Install
1. Copy `app/routers/social_stream.py` over the repo file (or merge helpers).
2. Copy `templates/members/social_watch.html` (and `app/templates/members/…` if used).
3. Redeploy.
4. Re-add or toggle channel links so embed_url is rebuilt.

Member player also soft-reloads channel-live embeds every 4 minutes and when the tab is shown again.
