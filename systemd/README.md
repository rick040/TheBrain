# Scheduled jobs + the always-on bot

Everything here assumes the repo is cloned to `~/TheBrain` with a venv at
`~/TheBrain/.venv` (`python3 -m venv .venv && pip install -r requirements-dev.txt`).
Adjust paths in the `.service` files if yours differs. None of this needs
to run on the eventual NAS specifically — a VPS or your laptop while it's
on both work (see `docs/00-PLAN.md`).

## One always-running process: the Telegram bot

Not a timer — it needs to stay up to receive messages. A user-level
systemd *service* (not timer) restarts it if it crashes:

```ini
# ~/.config/systemd/user/thebrain-bot.service
[Unit]
Description=TheBrain Telegram bot

[Service]
WorkingDirectory=%h/TheBrain
ExecStart=%h/TheBrain/.venv/bin/python3 -m app.bot.telegram_bot
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now thebrain-bot.service
systemctl --user status thebrain-bot.service
```

## Scheduled (timer) jobs

| Timer | Runs | What |
|---|---|---|
| `vault-autocommit` | 23:45 daily | commits + pushes anything changed under `vault/` |
| `thebrain-morning-brief` | 07:30 daily | `app.brain.coach --morning-brief` — sends via Telegram (needs `TELEGRAM_CHAT_ID`, see below) |
| `thebrain-nudges` | every 2h, 08:00-20:00 | `app.brain.coach --nudges` — stale leads, unbilled hours, missed habits |
| `thebrain-metabolism` | 03:30 daily | `app.brain.metabolism` — freshness flags + tag-merge proposals |
| `thebrain-gap-review` | Sunday 18:00 | `app.brain.gap_review` — needs Phase 2's self-model to produce anything meaningful; harmless no-op until then |

Install any of them the same way:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/<name>.service systemd/<name>.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now <name>.timer
systemctl --user list-timers   # confirm they're all scheduled
```

**Before enabling `thebrain-morning-brief` or `thebrain-nudges`**: message
the bot `/start` once and copy the chat id it replies with into
`TELEGRAM_CHAT_ID` in `.env` — these jobs push proactively (not in
response to a message), so the bot needs to know where to send to; there
is no other way for it to find out.

## cron equivalents (macOS, or Linux without systemd --user)

```bash
crontab -e
# add:
45 23 * * *        cd $HOME/TheBrain && ./scripts/vault-autocommit.sh >> /tmp/thebrain.log 2>&1
30 7  * * *        cd $HOME/TheBrain && .venv/bin/python3 -m app.brain.coach --morning-brief >> /tmp/thebrain.log 2>&1
0  8,10,12,14,16,18,20 * * *  cd $HOME/TheBrain && .venv/bin/python3 -m app.brain.coach --nudges >> /tmp/thebrain.log 2>&1
30 3  * * *        cd $HOME/TheBrain && .venv/bin/python3 -m app.brain.metabolism >> /tmp/thebrain.log 2>&1
0  18 * * 0        cd $HOME/TheBrain && .venv/bin/python3 -m app.brain.gap_review >> /tmp/thebrain.log 2>&1
```

The bot itself (`app.bot.telegram_bot`) still needs *something* to keep
it running under cron-only setups — e.g. a `@reboot` crontab entry plus a
process supervisor, or just run it in a `screen`/`tmux` session. systemd
handles this more cleanly, which is the main reason to prefer it if you
have the choice.
