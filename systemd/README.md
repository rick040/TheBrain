# Nightly vault auto-commit

`scripts/vault-autocommit.sh` commits + pushes whatever changed under
`vault/` since the last run. Two ways to schedule it — pick whichever
matches the machine it runs on (doesn't need to be the eventual NAS, see
`docs/00-PLAN.md`).

## systemd (Linux, user timer — no root needed)

```bash
mkdir -p ~/.config/systemd/user
cp systemd/vault-autocommit.service systemd/vault-autocommit.timer ~/.config/systemd/user/
# edit the WorkingDirectory/ExecStart paths in the .service file if your
# clone isn't at ~/TheBrain
systemctl --user daemon-reload
systemctl --user enable --now vault-autocommit.timer
systemctl --user list-timers vault-autocommit.timer   # confirm it's scheduled
```

## cron (macOS, or any Linux without systemd --user)

```bash
crontab -e
# add:
45 23 * * * cd $HOME/TheBrain && ./scripts/vault-autocommit.sh >> /tmp/vault-autocommit.log 2>&1
```

Both run the same script; the only difference is what triggers it.
