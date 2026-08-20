# GitHub SSH deploy keys (no-PAT publishing)

## Symptom
`git push` fails with:
```
ERROR: Permission to TheGMPTeam/<repo>.git denied to deploy key
fatal: Could not read from remote repository.
```

## Why
The SSH key offered (`~/.ssh/id_ed25519`, comment `hermes-virusgpt-push`) is a
**deploy key** tied to a SINGLE repo. `ssh -T git@github.com` returns
`Hi TheGMPTeam/VirusGPT! ... authenticated` — the identity is the repo the key
belongs to, NOT a personal account. A deploy key only grants access to its own
repo, and by default is **read-only**. Pushing to any OTHER repo is denied.

## Confirm which key/identity is in play
```bash
ssh -T -o StrictHostKeyChecking=no -o BatchMode=yes git@github.com
# -> Hi TheGMPTeam/<REPO>! You've successfully authenticated...
```

## Convert an HTTPS remote to SSH
`https://github.com/TheGMPTeam/<repo>`  ->  `git@github.com:TheGMPTeam/<repo>.git`
(The user's setup is SSH / no PAT — use the SSH form, not https://.)

## Fix (either)
1. **Reuse the key:** target repo → Settings → Deploy keys → Add deploy key,
   paste `~/.ssh/id_ed25519.pub`, check **Allow write access**, Add key. Retry push.
2. **Per-repo key:** `ssh-keygen -t ed25519 -C "hermes-<repo>-push" -f ~/.ssh/id_ed25519_<repo>`,
   add the new `.pub` to the target repo with write access. If multiple keys collide,
   add a `~/.ssh/config` block:
   ```
   Host github.com
     IdentityFile ~/.ssh/id_ed25519_<repo>
   ```

## Note
This is a per-project publishing concern, not agent-swarm-specific. If you publish
many repos this way, consider a generic git/SSH-publish skill — but it bit us while
shipping THIS skill, so the lesson lives here too.
