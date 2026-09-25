# Churchgate Default Hero (with voice note)

Full-screen professional animation **synced to the marketing voice note** (~3:08).

## Files to deploy

```
static/churchgate-default-hero.html
static/Churchgate_Marketing_VoiceNote.mp3
```

Both must sit in the **same folder** (or update the `<source src="...">` path).

## Homepage embed

```html
{% if not home_video_url %}
<iframe
  src="/static/churchgate-default-hero.html"
  title="Churchgate introduction"
  style="width:100%;height:min(70vh,560px);border:0;border-radius:16px;background:#020617;"
  allow="autoplay"
></iframe>
{% else %}
<video src="{{ home_video_url }}" controls playsinline style="width:100%;border-radius:16px;"></video>
{% endif %}
```

For a **full-bleed hero**, use height closer to `80vh` or open the HTML as its own page.

## Behaviour

- Voice note plays automatically when the browser allows
- Scenes change in time with the narration
- Progress bar, play/pause, mute
- Soft loop after the voice ends
- Does **not** touch uploads, books, or database — static files only

## Note on autoplay

Some mobile browsers block autoplay with sound until the user taps once. The UI shows “Tap ▶ to begin” in that case.
