# Deployment — apiverify.aidcmo.com

These files deploy the FastAPI web service on the NY server. The CLI and library
parts of the repo are unaffected — they remain installable without the `[web]`
extra.

## Prerequisites on the box

- Ubuntu 24.04+ (or any systemd-managed distro)
- Python 3.10+
- nginx
- A redis reachable from the host (we re-use the existing `sub2api-redis`
  container at `172.17.0.1:6379` on db 3)
- DNS A record `apiverify.aidcmo.com → <server-ip>` (set in your DNS provider,
  not on the server)

## One-shot install

```bash
cd /opt
git clone https://github.com/study8677/api_verify.git api-verify
cd api-verify
bash deploy/install.sh
```

Re-running `install.sh` is idempotent. It will:

1. Create/refresh `/opt/api-verify/.venv` and install `pip install -e ".[web]"`.
2. Install / reload the `api-verify.service` systemd unit.
3. Install / reload the nginx site config at
   `/etc/nginx/sites-{available,enabled}/apiverify.aidcmo.com.conf`.
4. Curl `http://127.0.0.1:8083/api/health` to verify the service answers.

## Getting HTTPS

Once DNS is propagated and the HTTP site is responding:

```bash
certbot --nginx -d apiverify.aidcmo.com
```

certbot will inject the HTTPS server block into the same nginx site file and
set up auto-renewal.

## Configuration

The systemd unit sets these environment variables. Override in
`/etc/systemd/system/api-verify.service.d/override.conf` if you need to:

| Var | Default | Meaning |
| --- | --- | --- |
| `APIVERIFY_RATE_LIMIT_PER_HOUR` | `5` | Per-IP hourly verification cap. |
| `APIVERIFY_REDIS_URL` | `redis://172.17.0.1:6379/3` | Optional; falls back to in-process counter. |
| `LOG_LEVEL` | `INFO` | uvicorn / app log level. |

## Operating

```bash
systemctl status api-verify
journalctl -u api-verify -n 100 --no-pager
systemctl restart api-verify
```

The service does not log API keys, request bodies, or response bodies — only
protocol/model/IP/timing.
