# Host Rangebook on Google Cloud (VM)

Use this on a **Debian/Ubuntu** GCP VM after you upload `Agent.zip` (same project as `stock_signal_ml.py`).

**Security first:** Rangebook has **no login screen**. If port 5000 is open to the whole internet, anyone can use your desk and your Kite session on the server is at risk. Before going live, read [Secure access](#secure-access-recommended) and restrict who can reach the VM.

---

## 1. Install `unzip`, then extract the archive

SSH into the VM (browser SSH in GCP console is fine). In your home directory you should see `Agent.zip`.

Fresh Debian images often do not include `unzip`. Install it first (you can install Python in the same step):

```bash
sudo apt-get update
sudo apt-get install -y unzip python3 python3-venv python3-pip
```

Extract:

```bash
cd ~
unzip -o Agent.zip
ls
```

**No `sudo`?** Extract with Python instead:

```bash
cd ~
python3 -m zipfile -e Agent.zip .
ls
```

You need a folder that contains `stock_signal_ml.py`, `requirements.txt`, and `dashboard/`. Common layouts:

- `~/Agent/stock_signal_ml.py`
- or `~/Agent/Agent/stock_signal_ml.py` if the zip had an extra top folder

Set a variable (adjust the path if `ls` shows something different):

```bash
export APP=~/Agent
# example if nested: export APP=~/Agent/Agent

test -f "$APP/stock_signal_ml.py" && echo "OK: $APP" || echo "Fix APP path"
```

Optional: keep code in `~/my-private-app`:

```bash
mkdir -p ~/my-private-app
rsync -a --delete "$APP/" ~/my-private-app/
export APP=~/my-private-app
```

---

## 2. Python virtual environment and dependencies

(Skip the apt block above if you already ran it in step 1.)

---

```bash
cd "$APP"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Quick check:

```bash
python stock_signal_ml.py --news-stats
```

(Should print JSON and exit; confirms imports work.)

---

## 3. Kite `.env` (secrets)

Create **`$APP/.env`** on the VM only — never commit it, never put it in the zip for public sharing.

```bash
cd "$APP"
nano .env
```

Minimum (copy from your local machine’s working `.env`):

```env
KITE_API_KEY=your_key
KITE_API_SECRET=your_secret
KITE_ACCESS_TOKEN=
```

Optional **auto login** (best on a server with no browser):

```env
KITE_USER_ID=your_zerodha_id
KITE_PASSWORD=your_password
KITE_TOTP_SECRET=your_totp_secret
```

If you use **browser login** on the server, set redirect URL in [Kite developer console](https://developers.kite.trade/) to match:

```env
KITE_REDIRECT_URL=http://127.0.0.1:8765/
```

Lock the file:

```bash
chmod 600 .env
```

Refresh token (on the VM, with venv active):

```bash
cd "$APP"
source .venv/bin/activate
python kite_login.py
# or: python kite_login.py --paste   (paste redirect URL from your PC if needed)
```

---

## 4. Run manually (first test)

```bash
cd "$APP"
source .venv/bin/activate
python stock_signal_ml.py
```

You should see:

```text
API SERVER RUNNING on http://localhost:5000
```

Leave this terminal open for the test.

---

## 5. Open firewall (GCP) — restrict by IP

In **Google Cloud Console → VPC network → Firewall**, create a rule:

| Field | Value |
|--------|--------|
| Direction | Ingress |
| Target | Your VM (network tag or default) |
| Source | **Your home/mobile public IP**/32 (Google “what is my ip” on the device you use) |
| Protocol | tcp:5000 |

Do **not** use `0.0.0.0/0` unless you add nginx + password (see below).

Find the VM **External IP** (Compute Engine → VM instances).

On your **phone or laptop** (same allowed IP):

```text
http://EXTERNAL_IP:5000/dashboard
http://EXTERNAL_IP:5000/health
```

If `/health` returns JSON with `"status": "ok"`, the app is hosted correctly.

---

## 6. Keep it running after logout (systemd)

Create a service (replace `narawadesachin255` if your username differs):

```bash
sudo tee /etc/systemd/system/rangebook.service << 'EOF'
[Unit]
Description=Rangebook API and dashboard
After=network.target

[Service]
Type=simple
User=narawadesachin255
WorkingDirectory=/home/narawadesachin255/Agent
Environment=PATH=/home/narawadesachin255/Agent/.venv/bin
ExecStart=/home/narawadesachin255/Agent/.venv/bin/python stock_signal_ml.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

Edit paths if you used `~/my-private-app` or a nested `Agent/Agent`:

```bash
sudo nano /etc/systemd/system/rangebook.service
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable rangebook
sudo systemctl start rangebook
sudo systemctl status rangebook
```

Logs:

```bash
journalctl -u rangebook -f
```

After code updates:

```bash
cd "$APP"
source .venv/bin/activate
pip install -r requirements.txt   # if dependencies changed
sudo systemctl restart rangebook
```

---

## 7. Secure access (recommended)

### Option A — IP allowlist only (simplest)

Keep firewall source = **your IP/32**. When your ISP changes IP, update the rule. Phone on mobile data has a **different IP** — add a second rule or use Option B.

### Option B — Tailscale (phone + laptop, no public port)

Install [Tailscale](https://tailscale.com/) on the VM and on your phone/PC. Do **not** open 5000 to the public internet. Open:

```text
http://100.x.x.x:5000/dashboard
```

(Tailscale IP of the VM.)

### Option C — HTTPS + password (nginx)

Use a domain, Let’s Encrypt, and HTTP basic auth in front of Flask. Flask stays on `127.0.0.1:5000`; only nginx listens on 443. Example outline:

```bash
sudo apt-get install -y nginx apache2-utils
sudo htpasswd -c /etc/nginx/.rangebook_htpasswd your_username
```

Configure nginx `proxy_pass http://127.0.0.1:5000` for `/` and `/dashboard`, with `auth_basic`. Point DNS to the VM and use Certbot for TLS.

Change systemd `ExecStart` is unchanged; bind remains `0.0.0.0:5000` or switch to `127.0.0.1` only if **only** nginx is public.

---

## 8. Daily operations on the cloud VM

| Task | Command |
|------|---------|
| Kite token (daily if no TOTP auto) | `cd $APP && source .venv/bin/activate && python kite_login.py` |
| Restart app | `sudo systemctl restart rangebook` |
| View logs | `journalctl -u rangebook -n 100` |
| Morning brief (CLI) | `python stock_signal_ml.py --morning-report` |
| Instrument search cache | `curl -X POST "http://127.0.0.1:5000/kite/instruments/refresh?force=1"` |

Data lives on the VM disk:

- `stock_signal_data/knowledge.db`
- `stock_signal_data/watchlists.json`
- `.env`

Back up `stock_signal_data/` and `.env` to a **private** GCS bucket or download periodically.

---

## 9. Troubleshooting

| Problem | What to check |
|---------|----------------|
| Browser cannot connect | GCP firewall, VM external IP, `sudo systemctl status rangebook` |
| Symbol search 404 | Old code — restart after unzip; `curl http://127.0.0.1:5000/instruments/search?q=n` |
| Kite / live data missing | `python kite_login.py`, `.env` permissions, token not expired |
| Phone works, laptop does not | Different public IPs — firewall allowlist |
| `ModuleNotFoundError` | `source .venv/bin/activate` and `pip install -r requirements.txt` |
| `Permission denied` on `Agent/.git/...` when unzipping | Folder already exists — if `test -f ~/Agent/stock_signal_ml.py` prints OK, **skip unzip** and use `~/Agent`. To replace from zip: `rm -rf ~/Agent && unzip -o Agent.zip` |

---

## Quick copy-paste checklist

```bash
cd ~ && export APP=~/Agent && test -f "$APP/stock_signal_ml.py" || { unzip -o Agent.zip; export APP=~/Agent; }
cd "$APP" && sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip unzip
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
nano .env   # paste Kite secrets, chmod 600 .env
python kite_login.py
python stock_signal_ml.py   # test, then Ctrl+C
# configure systemd + firewall, then open http://EXTERNAL_IP:5000/dashboard
```

For all local commands and tests, see the main [README.md](../README.md).
