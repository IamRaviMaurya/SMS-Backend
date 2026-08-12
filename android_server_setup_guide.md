# 📱 Android Termux Python Backend Server — Setup Guide

Yeh documentation batati hai ki ek purane Android phone (8GB RAM, 128GB Storage) ko Termux, Python, Uvicorn, aur Cloudflare Tunnel ka upayog karke ek high-performance personal web server me kaise badla jaye.

---

## 🛠️ Architecture Overview

```text
[ Internet Client / Frontend ]
               │
               ▼ (Public HTTPS Request)
    [ Cloudflare Edge Network ]
               │
               ▼ (Secure Tunnel)
  [ Android Phone — Termux CLI Environment ]
               │
     ┌─────────┴─────────┐
     │                   │
  [ Cloudflared ] ──► [ Uvicorn ASGI Server ]
                         │
                         ▼
                  [ FastAPI / Python App ]
```

---

## ⚙️ Key Specifications & Requirements

* **Hardware:** Android Phone (Minimum 4GB+ RAM recommended)
* **OS:** Android 10+
* **Environment:** Termux (F-Droid Build)
* **Runtime:** Python 3.11+
* **ASGI Server:** Uvicorn
* **Tunneling Tool:** Cloudflared CLI

---

## 🚀 Step-by-Step Installation & Deployment

### 1. Base Environment Setup (Termux)
> **Note:** Play Store version of Termux is deprecated. Use F-Droid or GitHub release.

```bash
# Update core package repositories
pkg update && pkg upgrade -y

# Install core build dependencies & version control
pkg install python git rust clang binutils make libffi openssl -y

# Enable Wakelock to prevent Android OS from killing background tasks
termux-wake-lock
```

### 2. Android OS Optimization
To ensure **24/7 uptime**, disable OS-level process killing:
1. Go to **Settings → Apps → Termux → Battery**.
2. Select **"Unrestricted"** or **"Don't Optimize"**.
3. Verify Termux notification shows **`WakeLock held`**.

---

### 3. Repository & Virtual Environment Setup

```bash
# Clone backend project repository
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd <YOUR_REPOSITORY_FOLDER>

# Create & activate Python Virtual Environment
python -m venv venv
source venv/bin/activate

# Fix Android API Level for Rust-based packages (pydantic-core, maturin)
export ANDROID_API_LEVEL=24

# Upgrade pip build tools
pip install --upgrade pip setuptools wheel maturin

# Install dependencies using pre-compiled binaries where possible
pip install --prefer-binary -r requirements.txt
```

---

### 4. Running the Local Application Server

Execute the ASGI server binding to all network interfaces (`0.0.0.0`):

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

* **Local Verification:** Access `http://localhost:8000` or `http://<PHONE_LOCAL_IP>:8000` from any device connected to the same Wi-Fi.

---

### 5. Exposing Server to Global Internet (Public HTTPS)

Open a **New Termux Session** (Swipe left → New Session) while keeping Uvicorn active:

```bash
# Install Cloudflare CLI
pkg install cloudflared -y

# Launch Quick Tunnel (Generates free HTTPS URL)
cloudflared tunnel --url http://localhost:8000
```

* **Output:** Copy the generated URL ending with `.trycloudflare.com` (e.g., `https://surgery-london-convertible-excited.trycloudflare.com`).

---

## 📌 Server Management Cheat Sheet

| Task | Command |
| :--- | :--- |
| **Start Wakelock** | `termux-wake-lock` |
| **Stop Wakelock** | `termux-wake-unlock` |
| **Activate Virtual Env** | `source venv/bin/activate` |
| **Check Active IP** | `ifconfig` or `ip a` |
| **Stop Server / Tunnel** | `Ctrl + C` |

---

## ⚠️ Hardware & Maintenance Guidelines

1. **Battery Health:** Continuous charging causes heat and battery swelling. Use a smart plug or charge cycle limiter app if rooted.
2. **Thermal Management:** Keep the phone in a well-ventilated area (near a fan or on a cool surface).
3. **Session Persistence:** Quick Cloudflare tunnels change URLs when restarted. For production, configure a permanent custom domain with Cloudflare Named Tunnels.
