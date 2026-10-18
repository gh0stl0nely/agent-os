# How the daily Threads post works

- `queue.json`: one post per date (text). Every post carries the files in `config.json` -> `default_media`.
- `config.json`: footer, default attachments, pause switch (`"paused": true` stops everything), Toronto time.
- `manifest.json`: alt text, keywords and expiry date for each file. Expired files are refused.
- `state.json`: what has been posted (written by the workflow).
- Workflow: `.github/workflows/daily-post.yml`; script: `scripts/post_threads.py`.
- Secret: `THREADS_ACCESS_TOKEN` (GitHub Actions secret). Never put it in a file.

## Writing posts
- Before writing or editing any post text, load the `caption-check` skill and run every draft through it. If it is not available, load `stop-slop` and follow the owner rules below by hand.
- Owner rules: plain and human, no prices, never the word "gone", no slogan hooks ("Fight me", "Let that sink in"), only facts from the current graphics or menu. Show the owner the draft before changing a day's post.

## Lessons learned
- Posting is started at 11:00 Toronto by a Claude scheduled task ("Daily Threads post at 11:00", fires 10:58) that calls workflow_dispatch with mode post. GitHub's own cron runs start 3 to 7 hours late (measured Oct 16 and 17), so they are only a backup; they stop when the day is already posted.
- The workflow commits `state.json` after posting. A push to `main` during a run once made that commit fail (Oct 15), so the post went out but was not recorded. The save step now rebases and retries; still avoid pushing while a run is in progress.
- GitHub's scheduler starts runs late (first live run: 11:00 job never started on time). The workflow now starts at 10:35 Toronto and the script waits until 11:00.
- A manual trigger (`gh api -X POST .../dispatches`) can silently not start a run; always confirm a new run appears.
- `gh` GraphQL is blocked from Claude sessions; use `gh api` REST calls. Job logs are not readable from Claude sessions; read step results instead.
- Carousel of 4 images plus 1 video is accepted by Threads (verified Oct 7).
- When the queue runs out, or any attached file has expired, the run fails and GitHub emails the owner. Ask Claude for the next batch.
