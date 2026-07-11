# BD API Deployment Guide (Local -> GitHub -> VM)

This documents how to deploy the BD API FastAPI app from your local Windows machine to the Ubuntu VM and run it as a managed service.

## 1. Local setup and GitHub

1. Edit code locally in:

   `C:\Users\GrahamEather\projects\bd-api`

2. Ensure `.gitignore` ignores local artifacts:

   ```gitignore
   __pycache__/
   *.pyc
   .venv/
   .env
   ```

3. Commit and push:

   ```powershell
   git status
   git add .
   git commit -m "Describe your change here"
   git pull --rebase origin main   # if remote has new commits
   git push origin main
   ```

This keeps GitHub as the source of truth for the app code.

## 2. VM prep (Ubuntu)

SSH into the VM:

```bash
ssh ubuntu@<PUBLIC-IP>
```

Clone or update the repo:

```bash
cd /home/ubuntu

# First time
git clone https://github.com/FuguFishy/bd-api.git

# Later updates
cd bd-api
git pull origin main
```

Create/update the Python venv:

```bash
cd /home/ubuntu/bd-api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

# If templates are used
pip install jinja2
```

This venv isolates dependencies on the VM and matches what you use locally.

## 3. Systemd service (`bd-api`)

Create the service file:

```bash
sudo nano /etc/systemd/system/bd-api.service
```

Contents:

```ini
[Unit]
Description=BD API FastAPI application
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/bd-api
Environment="PATH=/home/ubuntu/bd-api/.venv/bin"
ExecStart=/home/ubuntu/bd-api/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable bd-api.service
sudo systemctl start bd-api.service
sudo systemctl status bd-api.service
```

Check port 8000 is owned by the service:

```bash
sudo lsof -i :8000
```

You should see a `uvicorn` process using `/home/ubuntu/bd-api/.venv/bin/uvicorn` and working from `/home/ubuntu/bd-api`.

## 4. Testing from VM

From the VM:

```bash
curl -I http://127.0.0.1:8000/docs
```

Expect `200 OK` or similar, which confirms the app is responding locally.

## 5. Testing from Windows

In PowerShell, using the VM public IP:

```powershell
$jsonResolve = @{
  action            = "create_organisation_and_contact"
  resolved_by       = "Graham"
  organisation_name = "Test Organisation"
  contact_name      = "Test Contact"
} | ConvertTo-Json

Invoke-RestMethod -Method POST `
  -Uri "http://<PUBLIC-IP>:8000/review-queue/17/resolve" `
  -ContentType "application/json" `
  -Body $jsonResolve
```

Expected success response:

```text
ok                     : True
review_queue_id        : 17
review_status          : resolved
review_action          : create_organisation_and_contact
linked_organisation_id : <id>
linked_contact_id      : <id>
```

This proves the end-to-end path from local -> VM -> database is working.

## 6. Everyday operations on the VM

```bash
# Check service status
sudo systemctl status bd-api.service

# Restart after code changes
sudo systemctl restart bd-api.service

# View recent logs
journalctl -u bd-api.service -n 100 --no-pager

# Stop service
sudo systemctl stop bd-api.service
```

## 7. Normal deployment workflow

1. Make changes locally.
2. Commit and push to GitHub.
3. On the VM, run:

   ```bash
   cd /home/ubuntu/bd-api
   git pull origin main
   source .venv/bin/activate
   pip install -r requirements.txt   # only if dependencies changed
   sudo systemctl restart bd-api.service
   ```

4. Confirm the service is healthy:

   ```bash
   sudo systemctl status bd-api.service
   ```

This keeps deployment simple, low-cost, and repeatable without relying on a manually started terminal session.
