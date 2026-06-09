# Ferrari F12 Canada Scanner

Scans Canadian sources for used Ferrari F12 listings, verifies each listing
is actually live (not an out-of-date aggregator listing), and emails the
results every morning.

## Sources

- AutoTrader.ca
- AutoHebdo.net
- SR Auto Group (Vancouver)
- Toybox Auto (Vancouver)

## Setup

### 1. Gmail App Password

The scanner sends email from jeffrey.dyck@gmail.com. You need a Gmail App Password:

1. Enable 2-Step Verification: https://myaccount.google.com/security
2. Generate an App Password: https://myaccount.google.com/apppasswords
3. Create one for "F12 Scanner" and copy the 16-char password

### 2. Set the Gmail App Password

The password is already stored in `.env` (only accessible by you). To update it:

Edit `C:\Users\m3nbtp\Downloads\F12 scanner\.env` and change the password value.

### 3. Schedule daily run (optional)

To run every morning at 7:00 AM:
```
powershell -ExecutionPolicy Bypass -File schedule_task.ps1
```
Run this as Administrator.

To run manually anytime:
```
run_scanner.bat
```
or
```
py -3.13 scanner.py
```
