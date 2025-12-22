# Ubuntu Service Setup Guide for Gluco-Watch

This guide will help you set up the Gluco-Watch service to run automatically on Ubuntu startup and keep it running in the background.

## Prerequisites

- Ubuntu 18.04 or later (systemd required)
- Python 3.6 or later
- User account with sudo privileges

## Step 1: Install Dependencies

1. Update your system:
```bash
sudo apt update
sudo apt upgrade -y
```

2. Install Python 3 and pip if not already installed:
```bash
sudo apt install python3 python3-pip python3-venv -y
```

3. Navigate to the ingestor directory:
```bash
cd ~/gluco-watch/ingestor
```

4. Create a virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate
```

5. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Step 2: Configure Environment

1. Create or edit the `.env` file in the `ingestor` directory:
```bash
nano .env
```

2. Add your configuration (replace with your actual values):
```env
# EasyView API Credentials
EASYVIEW_USERNAME=your_email@example.com
EASYVIEW_PASSWORD=your_password
EASYVIEW_USER_TYPE=P

# Timezone settings
TZ_OFFSET_HOURS=1
WINDOW_HOURS=24

# Firebase Realtime Database URL
FIREBASE_DATABASE_URL=https://gluco-watch-default-rtdb.europe-west1.firebasedatabase.app/
```

3. Ensure the Firebase credentials file is present:
```bash
ls -la gluco-watch-firebase-adminsdk-fbsvc-cd567c4e05.json
```

4. Set proper permissions for sensitive files:
```bash
chmod 600 .env
chmod 600 gluco-watch-firebase-adminsdk-fbsvc-cd567c4e05.json
```

## Step 3: Test the Script Manually

Before setting up as a service, test that the script works:

```bash
# If using virtual environment, activate it first
source venv/bin/activate

# Run the script
python3 test.py
```

Press `Ctrl+C` to stop it. If it works correctly, proceed to the next step.

## Step 4: Install Systemd Service

1. Copy the service file to systemd directory:
```bash
sudo cp gluco-watch.service /etc/systemd/system/
```

2. Edit the service file to match your user and paths:
```bash
sudo nano /etc/systemd/system/gluco-watch.service
```

**Important:** Replace `%i` with your actual username in the service file, or use the template below:

```ini
[Unit]
Description=Gluco-Watch Service - Monitors glucose levels via EasyView API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=YOUR_USERNAME
Group=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/gluco-watch/ingestor
Environment="PATH=/home/YOUR_USERNAME/.local/bin:/usr/local/bin:/usr/bin:/bin"
# If using virtual environment, use the venv python:
ExecStart=/home/YOUR_USERNAME/gluco-watch/ingestor/venv/bin/python3 /home/YOUR_USERNAME/gluco-watch/ingestor/test.py
# Or if using system Python:
# ExecStart=/usr/bin/python3 /home/YOUR_USERNAME/gluco-watch/ingestor/test.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=gluco-watch

# Security settings
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

**Replace `YOUR_USERNAME` with your actual Ubuntu username.**

3. If using a virtual environment, make sure the venv path is correct in `ExecStart`.

4. Reload systemd to recognize the new service:
```bash
sudo systemctl daemon-reload
```

## Step 5: Enable and Start the Service

1. Enable the service to start on boot:
```bash
sudo systemctl enable gluco-watch.service
```

2. Start the service:
```bash
sudo systemctl start gluco-watch.service
```

3. Check the service status:
```bash
sudo systemctl status gluco-watch.service
```

You should see "active (running)" in green.

## Step 6: Monitor Logs

### View Service Logs (systemd journal)

View recent logs:
```bash
sudo journalctl -u gluco-watch.service -f
```

View last 100 lines:
```bash
sudo journalctl -u gluco-watch.service -n 100
```

View logs from today:
```bash
sudo journalctl -u gluco-watch.service --since today
```

### View Application Logs (file-based)

The application also writes logs to a file:
```bash
tail -f ~/gluco-watch/ingestor/logs/gluco-watch.log
```

View last 100 lines:
```bash
tail -n 100 ~/gluco-watch/ingestor/logs/gluco-watch.log
```

## Common Service Management Commands

### Start the service:
```bash
sudo systemctl start gluco-watch.service
```

### Stop the service:
```bash
sudo systemctl stop gluco-watch.service
```

### Restart the service:
```bash
sudo systemctl restart gluco-watch.service
```

### Check service status:
```bash
sudo systemctl status gluco-watch.service
```

### Disable auto-start on boot:
```bash
sudo systemctl disable gluco-watch.service
```

### Enable auto-start on boot:
```bash
sudo systemctl enable gluco-watch.service
```

## Troubleshooting

### Service won't start

1. Check service status for errors:
```bash
sudo systemctl status gluco-watch.service
```

2. Check journal logs for detailed errors:
```bash
sudo journalctl -u gluco-watch.service -n 50 --no-pager
```

3. Verify paths in the service file:
```bash
sudo cat /etc/systemd/system/gluco-watch.service
```

4. Check file permissions:
```bash
ls -la ~/gluco-watch/ingestor/
```

5. Test the script manually:
```bash
cd ~/gluco-watch/ingestor
source venv/bin/activate  # if using venv
python3 test.py
```

### Service keeps restarting

1. Check logs for the error:
```bash
sudo journalctl -u gluco-watch.service -n 100 --no-pager
```

2. Check application log file:
```bash
tail -n 100 ~/gluco-watch/ingestor/logs/gluco-watch.log
```

3. Common issues:
   - Missing `.env` file or incorrect credentials
   - Missing Firebase credentials file
   - Network connectivity issues
   - Python dependencies not installed

### Permission Issues

If you see permission errors:

1. Ensure the service file has the correct user:
```bash
sudo nano /etc/systemd/system/gluco-watch.service
# Check User= and Group= lines
```

2. Ensure the user owns the files:
```bash
sudo chown -R $USER:$USER ~/gluco-watch/
```

3. Check log directory permissions:
```bash
chmod 755 ~/gluco-watch/ingestor/logs
```

### Network Issues

If the service can't connect to the API:

1. Check network connectivity:
```bash
ping easyview.medtrum.eu
```

2. Check if the service starts after network is ready:
```bash
# The service file should have:
# After=network-online.target
# Wants=network-online.target
```

## Log Rotation

The application automatically rotates log files:
- Maximum log file size: 10 MB
- Number of backup files: 5
- Location: `~/gluco-watch/ingestor/logs/gluco-watch.log`

Old logs are automatically archived as:
- `gluco-watch.log.1`
- `gluco-watch.log.2`
- etc.

## Updating the Service

After making changes to the code:

1. Stop the service:
```bash
sudo systemctl stop gluco-watch.service
```

2. Pull/update your code

3. Restart the service:
```bash
sudo systemctl start gluco-watch.service
```

Or simply restart:
```bash
sudo systemctl restart gluco-watch.service
```

## Security Notes

1. **Never commit sensitive files:**
   - `.env` file
   - Firebase credentials JSON file
   - Log files (may contain sensitive data)

2. **File permissions:**
   - `.env`: 600 (read/write for owner only)
   - Firebase credentials: 600
   - Service file: 644

3. **Firewall:**
   - The service only makes outbound connections
   - No inbound ports need to be opened

## Verification

To verify everything is working:

1. Check service is running:
```bash
sudo systemctl is-active gluco-watch.service
# Should output: active
```

2. Check recent logs show successful operations:
```bash
sudo journalctl -u gluco-watch.service --since "5 minutes ago" | grep -i "success\|completed\|glucose"
```

3. Check application log file:
```bash
tail -n 20 ~/gluco-watch/ingestor/logs/gluco-watch.log
```

4. Verify data is being saved to Firebase (check your Firebase console)

## Additional Resources

- Systemd documentation: `man systemd.service`
- Journalctl documentation: `man journalctl`
- Service logs: `~/gluco-watch/ingestor/logs/gluco-watch.log`
