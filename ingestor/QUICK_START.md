# Quick Start Guide - Gluco-Watch Service

## Quick Setup (5 minutes)

### 1. Install dependencies
```bash
cd ~/gluco-watch/ingestor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure `.env` file
```bash
nano .env
```
Add your credentials (see UBUNTU_SETUP.md for details)

### 3. Test manually
```bash
python3 test.py
```
Press Ctrl+C after verifying it works.

### 4. Install as service
```bash
# Edit service file with your username
sudo nano /etc/systemd/system/gluco-watch.service
# Copy from gluco-watch.service and replace %i with your username

# Install and start
sudo systemctl daemon-reload
sudo systemctl enable gluco-watch.service
sudo systemctl start gluco-watch.service
```

### 5. Check status
```bash
sudo systemctl status gluco-watch.service
sudo journalctl -u gluco-watch.service -f
```

## Common Commands

```bash
# Service management
sudo systemctl start gluco-watch.service
sudo systemctl stop gluco-watch.service
sudo systemctl restart gluco-watch.service
sudo systemctl status gluco-watch.service

# View logs
sudo journalctl -u gluco-watch.service -f          # Follow logs
tail -f ~/gluco-watch/ingestor/logs/gluco-watch.log  # Application logs
```

## Log Locations

- **Systemd logs**: `sudo journalctl -u gluco-watch.service`
- **Application logs**: `~/gluco-watch/ingestor/logs/gluco-watch.log`
- **Log rotation**: Automatic (10MB max, 5 backups)

## Troubleshooting

1. **Service won't start**: Check `sudo journalctl -u gluco-watch.service -n 50`
2. **Permission errors**: Check file ownership and `.env` permissions
3. **Network issues**: Verify internet connectivity and API endpoints

For detailed setup, see `UBUNTU_SETUP.md`.
