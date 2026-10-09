# secrets-hygiene reference

## What the scanner looks for

| Rule id | What it matches | Severity |
|---|---|---|
| private-key-block | A PEM private key header | high |
| aws-access-key-id, github-token, github-fine-grained-token, slack-token, stripe-key, anthropic-key, openai-style-key, google-api-key, square-token, meta-or-threads-token, url-with-password | Documented token prefixes with the length each provider uses, and a URL with a password in it | high |
| jwt | Three dot-separated segments that start the way a JSON web token does | medium |
| generic-secret-assignment | A name containing key, secret, token, password and so on, set to a long high-randomness value. Skips placeholders, environment-variable names, references such as `${{ secrets.X }}`, and low-randomness values | medium |
| plan-handles-secret | (plans only) A step that says paste, store, type, commit or share together with a key, token, password or credential | medium |
| risky-filename | A `.env` file (not `.env.example`), key and certificate files, SSH private keys, credential files | medium |

Not covered: secrets in images or binaries, secrets split across lines, values encoded or encrypted by the writer, short passwords. A clean report means "none of these patterns", never "no secrets".

## Owner instructions: storing a secret safely

These are what the scanner returns. Agents never do them.

**Where a secret may live**
1. A password manager, for anything a person types or approves.
2. For a value a GitHub Action needs: the repository's Actions secrets. Path (checked against GitHub's documentation, K-sec-0008): repository Settings, then Secrets and variables, then Actions, the Secrets tab, New repository secret. The workflow refers to it as `${{ secrets.NAME }}` and never contains the value.
3. Nowhere else: not in a file in the repository, not in a chat, not in a commit message, not in a pull request, not in a screenshot.

**If a secret may have leaked**
1. Do not paste it anywhere to "check" it.
2. Revoke or rotate it on the provider's own site first. Rotating is what makes a leaked value safe; deleting it from the repository does not.
3. Store the new value as above.
4. Replace the value in the file with a reference.
5. If the value was committed or pushed, removing it from history is a separate destructive step (class R3) with its own Preflight Brief. Do not rewrite history to hide a leak you have not rotated.

**GitHub's own layer** (see `agents/03-guardian/OWNER-SETUP-CHECKLIST.md`): secret scanning and push protection for this public repository. This scanner and the proposed hooks sit behind that layer, they do not replace it.

## Suppression
A line containing `secrets-hygiene:ignore` is reported under `suppressed`, not hidden. Use it only for a deliberate synthetic example, and say why in the same comment. A reviewer should look at every suppressed item.
