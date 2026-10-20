# Deploying mlb-today on the Mac Mini

mlb-today runs as one container on a self-hosted Ubuntu box, with Watchtower beside it pulling new images from
GHCR. This walks from a fresh Ubuntu install to a running digest. Besides Docker and this GitHub repository, the
only outside accounts to set up are [Resend](https://resend.com) (email) and [healthchecks.io](https://healthchecks.io)
(alerting).

Images are published by `.github/workflows/image.yml`:

| Tag | Published on push to | Use |
|---|---|---|
| `edge` | `release/v2` | the Mini until cutover |
| `latest` | `main` | the Mini after cutover |
| `sha-<7>` | both | pinning or rolling back to one commit |

## 1. Install Docker

Install Docker Engine and the Compose plugin from Docker's apt repository (the Ubuntu `docker.io` package lags
behind and ships without Compose v2):

```sh
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Let your user run Docker without `sudo`, then log out and back in for the group to apply:

```sh
sudo usermod -aG docker "$USER"
```

Check it: `docker run --rm hello-world` and `docker compose version`. Docker starts on boot by default, and both
services use `restart: unless-stopped`, so the stack comes back after a reboot on its own.

## 2. Make sure the Mini can pull the image

The `ghcr.io/tomboone/mlb-today` package needs to be readable by the Mini. Pick one:

- **Public package (simplest).** On GitHub: your profile → Packages → `mlb-today` → Package settings → Change
  visibility → Public. Nothing else to do; skip to step 3.
- **Private package.** Create a classic personal access token with only the `read:packages` scope, then log in on
  the Mini:

  ```sh
  echo "<token>" | docker login ghcr.io -u tomboone --password-stdin
  ```

  Watchtower needs the same credentials. After step 3, create `deploy/docker-compose.override.yml` (Compose merges
  it automatically) containing:

  ```yaml
  services:
    watchtower:
      volumes:
        - ${HOME}/.docker/config.json:/config.json:ro
  ```

## 3. Fetch the deploy files

Only `deploy/` is needed on the Mini. A sparse clone fetches that directory (plus the handful of top-level files
git always includes) without the source tree:

```sh
git clone --filter=blob:none --sparse --branch main https://github.com/tomboone/mlb-today.git
cd mlb-today
git sparse-checkout set deploy
cd deploy
```

Every command from here on runs in `mlb-today/deploy/`. `git pull` picks up later changes to these files.

Create the data directory the container writes snapshots, state, and dry-run output to. The container runs as a
non-root user with UID/GID 999, so the directory must be owned by it, or Docker creates it root-owned and the app
cannot write:

```sh
mkdir -p data
sudo chown 999:999 data
```

## 4. Set up Resend

1. In the Resend dashboard, **Domains → Add Domain**, and add the sending domain (`tomboone.com`, or a subdomain
   such as `mail.tomboone.com` to keep it separate from other mail).
2. Add the DNS records Resend lists (the DKIM `TXT` record, and the `MX` and SPF `TXT` records on the `send`
   subdomain) at the DNS provider, then click **Verify DNS Records**. Verification usually takes minutes but can
   take longer while DNS propagates; wait until the domain shows **Verified**.
3. **API Keys → Create API Key** with **Sending access**, restricted to that domain. Copy the key; Resend shows it
   once.

`RESEND_FROM` must be an address on the verified domain, e.g. `MLB Today <mlb@tomboone.com>`.

## 5. Create the healthchecks.io check

1. In healthchecks.io, **Add Check**. Set **Period** to 1 day and **Grace** to 6 hours (a late first pitch can push a
   send hours past the previous day's).
2. Under **Integrations**, make sure at least one notification channel (email is the default) is enabled.
3. Copy the check's ping URL (`https://hc-ping.com/<uuid>`) for `HEALTHCHECKS_URL`.

The app pings after each successful send and pings `/fail` when a send fails even after its retry. Only send days
ping, so pause the check over the All-Star break and the off-season to avoid false alarms.

## 6. Configure `.env`

```sh
cp .env.example .env
chmod 600 .env
```

Edit `.env`. At minimum set `RECIPIENTS`, `RESEND_API_KEY`, `RESEND_FROM`, and `HEALTHCHECKS_URL`. The SMTP
variables enable the SMTP fallback transport (Fastmail); leave them blank to run Resend alone. Every variable and its
default is documented in `.env.example`.

For a first run, consider `DRY_RUN=true`: digests are rendered to `data/` instead of emailed, so you can compare a
few days' output before going live.

## 7. Start it

```sh
docker compose config -q   # validates the compose file and .env; prints nothing on success
docker compose up -d
docker compose ps
```

`docker compose ps` shows both services running. `mlb-today` reports `health: starting` until its first health
check, about 5 minutes after start, then `healthy` (the scheduler plans the day at boot).

## Day-to-day

**Logs.** The app logs structured JSON to stdout:

```sh
docker compose logs -f mlb-today
docker compose logs -f watchtower    # image updates
```

**Preview a digest** without sending it. Write into `/data` (the only directory the container can write), which is
`./data` on the host:

```sh
docker compose exec mlb-today mlb-today preview --out /data/digest.html
docker compose exec mlb-today mlb-today preview --date 2026-07-04 --out /data/digest.html
docker compose exec mlb-today mlb-today preview --from-snapshots --out /data/digest.html   # no network
```

Each writes `data/digest.html` and `data/digest.txt`; copy them off the Mini to view, e.g.
`scp mini:mlb-today/deploy/data/digest.html .`.

**Send one now:** `docker compose exec mlb-today mlb-today send` (add `--dry-run` to render to `data/` instead).
A manual send does not record the last-sent marker, so the scheduler still sends that day's digest at its usual
time; use `--dry-run` or `preview` when you only want to look.

**Health:** `docker compose exec mlb-today mlb-today health; echo $?` exits 0 when the scheduler has been active
in the last 26 hours.

**Updates** are automatic: Watchtower checks GHCR every 5 minutes and restarts `mlb-today` (the only container
labelled both `com.centurylinklabs.watchtower.enable=true` and `com.centurylinklabs.watchtower.scope=mlb-today`)
on the new image, removing the old one. Its `--scope mlb-today` keeps it away from other projects' containers and
Watchtowers on the same host, such as nba-today's; `docker compose logs watchtower` should show
`Only checking containers using enable label, in scope "mlb-today"`. To update by hand:
`docker compose pull && docker compose up -d`.

**Roll back** by pinning a commit: change the `image` tag in `docker-compose.yml` to `sha-<7>` and run
`docker compose up -d`. Watchtower keeps following that tag, which never moves, so updates stop until you switch
back.

## Moving a `release/v2` checkout to `main`

A Mini set up before cutover cloned `release/v2` and runs `edge`. Once `release/v2` has merged into `main` and
`latest` is published, switch it over:

```sh
git restore docker-compose.yml   # drop any local tag pin first
git fetch origin main
git switch main
docker compose up -d
```

`docker-compose.yml` on `main` reads `ghcr.io/tomboone/mlb-today:latest`, and Watchtower follows it from then on.
