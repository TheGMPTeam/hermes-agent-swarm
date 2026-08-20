# Verify a local Ollama vision model

The `visioner` profile uses a LOCAL Ollama vision model (e.g. `minicpm-v4.6:latest`
on `10.0.0.120:11434`). Confirm it actually SEES images before trusting a swarm
to "look at the UI" — a model that silently isn't multimodal will waste a whole run.

## 1. Download a REAL image (synthetic red squares are weak tests)
```bash
curl -sL --max-time 20 -o /tmp/real.jpg "https://picsum.photos/400/300"
file /tmp/real.jpg   # expect: JPEG image data ... 400x300
```
(If picsum is blocked, any direct-image URL works; avoid Wikipedia hotlinks — they
return HTML error pages, not images.)

## 2. Direct Ollama chat with the image (bypasses Hermes)
```bash
B64=$(base64 -i /tmp/real.jpg | tr -d '\n')
curl -s --max-time 40 http://10.0.0.120:11434/api/chat -d "{
  \"model\":\"minicpm-v4.6:latest\",
  \"messages\":[{\"role\":\"user\",\"content\":\"Describe this photograph in 2 sentences.\",\"images\":[\"$B64\"]}],
  \"stream\":false}" | python3 -c "import json,sys;print(json.load(sys.stdin).get('message',{}).get('content','NO CONTENT'))"
```
Expected: a real description (e.g. "a tranquil ocean scene with a small white boat...").
A correct description proves the model is genuinely vision-capable.

## 3. Via the Hermes profile (the actual swarm path)
```bash
hermes -p visioner --cli chat -q "Describe this photo." --image /tmp/real.jpg
```
Expect: `📎 attaching 1 image(s) natively (model supports vision): real.jpg` and an answer.
If Hermes does NOT attach the image, the profile's `model.provider` / `model.base_url`
(ollama @ 10.0.0.120:11434) is misconfigured — fix via
`hermes config set model.provider ollama --profile visioner` +
`hermes config set model.base_url http://10.0.0.120:11434 --profile visioner`.

## Notes
- `model_info` from `/api/show` may NOT advertise a "vision" flag even for vision
  models (MiniCPM-V keys differ) — the image round-trip above is the REAL test.
- If the Ollama host is down/unreachable, `launch_vision` workers fail; use
  `launch` / `vgctl swarm --no-vision run` instead.
- Vision is OFFLOADED to local Ollama on purpose: it costs nothing and avoids sending
  UI screenshots to the cloud.
