# Jayshree Analytics Hub

Upload any Excel workbook (protected or not) and get an automatic business dashboard:
cleaned data, master-sheet detection, business-area detection (Sales, Finance, Production,
HR, Store & Purchase, Attendance, or general), KPIs named from the workbook itself, and
bar / line / combo / pie / doughnut / radar / polar charts.

Runs on any computer, serves everyone on your WiFi/LAN, and needs **no internet** after install.

## Quick start (Windows / Linux / macOS, needs Python)

**Windows:** install Python 3.9+ from python.org (tick "Add Python to PATH"), then double-click `run.bat`.
**Linux / macOS:** `./run.sh`

The first run creates a virtual environment and installs three small packages (Flask, Waitress, msoffcrypto-tool).
The console then prints two addresses:

    On this computer : http://localhost:8085
    On your network  : http://192.168.1.25:8085   <- open this on other PCs / phones

**First time:** the first screen is "Create the administrator account". Only the owner (the email / mobile written in `config.ini`) can create it: verify with Google and/or a mobile OTP, then choose a username and password. Before that, do the one-time Firebase setup below.

## If another project already uses the port

The app now starts at port 8085 and, if that is busy, moves to the next free one and prints the
exact address. Always open the address shown in the console window. To choose a port yourself
(Windows): `set JP_PORT=9000` then `python app.py`. To see what is using a port:
`netstat -ano | findstr :5000`, then close that window or `taskkill /PID <number> /F`.

## Daily use

1. Log in and drop the latest `.xlsx / .xlsm / .xls / .csv` onto the upload box.
2. The dashboard is built from that file right away. **Nothing is stored**: the server never keeps your workbook.
3. Next day, upload the updated file again and the dashboard is rebuilt from it. After a refresh or log out you simply upload again.
   The admin panel shows an activity log (who analyzed which file name, and when). The file itself is never saved.
4. Password-protected workbooks (open-password) ask for the password when opened. The server uses it only to
   unlock the file for you; it is not saved. The file stays encrypted on disk. Older Excel encryption also works.
   Sheet-protected workbooks open without any password.

## Set up Google sign-in and mobile OTP (once, about 10 minutes)

Google verifies emails (the "Continue with Google" button) and Firebase, a free Google service, sends the SMS OTP to mobile numbers.
Nobody has to run an SMS gateway, and no email password is stored on this server.

1. Open https://console.firebase.google.com and create a project (any name; you can switch Analytics off).
2. **Build -> Authentication -> Get started -> Sign-in method:** turn **Google** ON (choose a support email) and turn **Phone** ON.
3. Click the gear icon -> **Project settings -> General -> Your apps -> Add app -> Web (</>)**. Register it (no hosting needed).
   Firebase now shows `apiKey`, `authDomain`, `projectId` and `appId`.
4. Open `config.ini` in this folder (created automatically on first start). Paste those four values into the `[firebase]` lines, and write
   the owner's Google email and mobile number (with country code) into `admin_email` / `admin_phone`. Save the file and refresh the website.
   No restart is needed.

Good to know
- **Open the website as `http://localhost:8085`** (on the computer that runs the server). Google and Firebase do not accept a raw IP address
  such as `192.168.1.5`. To use it from other devices you need a domain name with HTTPS; add that domain under
  *Authentication -> Settings -> Authorized domains*. `localhost` is allowed by default.
- Sign-in with the username / email / mobile **and password** still works from any device on your network; only the Google button and mobile OTP need `localhost` or your domain.
- The internet must be available on the server computer and in the browser (Google and reCAPTCHA are loaded from Google).
- To try mobile OTP for free, add **test phone numbers** in Firebase (*Authentication -> Sign-in method -> Phone -> Phone numbers for testing*):
  you choose a fake number and its 6-digit code. For real numbers Firebase has monthly SMS limits and may ask you to enable billing
  (see *Usage and billing* in the console); check its current rules.
- The 5-attempt limit for a mobile OTP is enforced in the page; Firebase also limits wrong codes and SMS requests on its side.
- No OTP is sent to an email address. Google confirms the email instead (the person must log in to that Google account), which is stronger.
  Only addresses that have a Google account can use the button.

## Sign in, register and forgot password

- **Sign in:** email, mobile number or username plus password, or **Continue with Google**, or **Sign in with mobile OTP**. One form for
  everyone; the account decides whether you are an admin or a user.
- **Register (new users):** verify your email with Google and/or your mobile number with an SMS OTP (5 attempts), then choose a username and
  a password, then sign in with them. No account exists until at least one contact is verified. If someone presses Continue with Google
  on the sign-in page and has no account yet, they land on the same "choose a username and password" step.
- **First account:** only the owner's email / mobile from `config.ini` can create it; it becomes the administrator. Later registrations are
  normal users. Registration can be closed with `registration = off` in `config.ini`.
- **Forgot password:** verify with Google or a mobile OTP, then choose a new username (you may keep the old one) and a new password.
  Only a verified email / mobile on the account works.
- **My profile:** change your username or password, add or change a verified email / mobile, or remove them. Contacts typed in by an admin for
  someone else stay "not verified" until that person confirms them here.
- **Admin -> Users:** add or remove users and reset a password. **Admin -> Activity log:** who analyzed which file name.
- Passwords need 8+ characters with a letter and a number. Changing a password signs that account out of every other browser.
- If Google / Firebase is unavailable, **Forgot password -> I have the recovery key** is the emergency backup (key in `data/recovery_key.txt`; keep it private).

## "Not Found" page

The server is running but cannot find the dashboard page. Make sure the folder looks like this (`index.html` inside `static`):

    jayshree-hub/
      app.py   run.bat   requirements.txt
      static/  index.html   vendor/(xlsx.full.min.js, chart.umd.js)

Open the main address only (for example `http://localhost:8085`). Mistyped addresses now redirect there.

## "This site can't be reached" / "Server not reached"

Check in this order:
1. **Is the server window still open?** The black cmd window must say "Jayshree Analytics Hub is running". If it was closed, the
   server is off. Double-click `run.bat` again and leave the window open.
2. **Use the address printed in that window.** The IP changes when you switch WiFi/hotspot, and the port becomes 8086, 8087...
   if 8085 is busy. The current addresses are also saved in `data/server_address.txt`.
3. **Try `http://localhost:8085` on the same PC.** If that works but a phone or another PC cannot connect, Windows Firewall is blocking it:
   right-click `allow_network.bat` -> Run as administrator. Both devices must be on the same WiFi (some hotspots and college/office
   WiFi block device-to-device traffic).
4. **If the window shows an error,** take a screenshot of it. To see which program uses a port: `netstat -ano | findstr :8085`.

## Let other devices connect (Windows)

- When Windows asks "Allow Python to communicate on networks?", choose **Private networks -> Allow**.
- Or run once in an Administrator terminal:
  `netsh advfirewall firewall add rule name="Analytics Hub" dir=in action=allow protocol=TCP localport=8085`
- Give the host PC a fixed IP (router "DHCP reservation") so the address never changes.
- To start automatically at boot: Task Scheduler -> create task -> trigger "At startup" -> action: run `run.bat`.
  (Linux: a systemd service running `run.sh`.)

## Public hosting (Render)

`render.yaml` prepares a Render web service with a persistent data disk. It keeps the SQLite database,
Flask signing key, and recovery key across deploys. The disk requires a paid service; check Render's
current pricing before creating it.

1. Put the project source in a private GitHub repository and connect that repository to Render as a Blueprint.
   Do **not** upload `data/`, `.venv/`, or `config.ini`; these are local/private and are excluded by `.gitignore`.
2. During Blueprint setup, provide a unique, strong value for the `JP_ADMIN_PASSWORD` secret. It creates the
   first `admin` account. Remove that environment variable after the first successful deploy; the account is
   then stored in the persistent database.
3. Use the `onrender.com` HTTPS address initially. The app binds to Render's assigned `PORT` and marks session
   cookies Secure. Add a custom domain later in Render if desired.
4. Registration is disabled until Firebase is configured. To enable Google/SMS sign-in, add
   `JP_FIREBASE_API_KEY`, `JP_FIREBASE_AUTH_DOMAIN`, `JP_FIREBASE_PROJECT_ID`, and `JP_FIREBASE_APP_ID`
   as Render environment variables; set `JP_REGISTRATION=on` and add the Render HTTPS domain to Firebase's
   Authorized domains. Optionally set `JP_ADMIN_EMAIL`, `JP_ADMIN_PHONE`, and `JP_COUNTRY_CODE`.

The deployment uses a **new, empty database**; it does not migrate local users or activity history. Keep
the Render recovery key private and arrange a secure backup of the persistent disk. Do not put credentials
or the recovery key in GitHub.

## Settings (environment variables, all optional)

| Variable | Default | Meaning |
|---|---|---|
| `JP_PORT` | 8085 | Port to start from. If busy, the next free port is used automatically |
| `JP_HOST` | 0.0.0.0 | `127.0.0.1` = this computer only |
| `JP_MAX_MB` | 200 | Largest upload accepted |
| `JP_CONFIG` | `./config.ini` | Where the settings file lives |
| `JP_ADMIN_PASSWORD` | (empty) | Optional: create the first admin `admin` from this password instead of the Google / mobile setup |
| `JP_DATA_DIR` | ./data | Where the database and uploads live |
| `PORT` | (platform-provided) | Used when `JP_PORT` is not set, for public hosting platforms |
| `JP_COOKIE_SECURE` | false | Set `true` when serving over HTTPS |
| `JP_FIREBASE_API_KEY` etc. | (empty) | Optional hosting overrides: `JP_FIREBASE_AUTH_DOMAIN`, `JP_FIREBASE_PROJECT_ID`, `JP_FIREBASE_APP_ID` |
| `JP_REGISTRATION` | from `config.ini` | Override registration (`on` / `off`) |
| `JP_ADMIN_EMAIL`, `JP_ADMIN_PHONE`, `JP_COUNTRY_CODE` | from `config.ini` | Optional owner/contact settings for hosted Firebase flows |

## Backup

Copy the `data/` folder (`hub.db` = users and activity log, `recovery_key.txt`, `secret.key`). It contains no workbooks.

## Project layout

    app.py             Flask API: login, sessions, users, Firebase token check, activity log, unlock protected files (SQLite)
    config.ini         Your Firebase details and a few switches (created automatically; you fill it once)
    static/index.html  The whole app (analysis engine + screens)
    static/vendor/     SheetJS, Chart.js and the Firebase browser files
    run.bat / run.sh   One-click start
    data/              Created on first run (database, secret key, recovery_key.txt)

API: `POST /api/login|logout|password`, `POST /api/firebase/login`, `POST /api/signup/verify|create`, `POST /api/forgot/verify|reset`,
`GET /api/profile`, `POST /api/profile/contact|username`, `GET|POST /api/users`, `POST|GET /api/activity`, `POST /api/decrypt`, `POST /api/forgot` (recovery key), `GET /healthz`.
How it is checked: the browser gets a signed ID token from Firebase; the server verifies its signature with Google's public keys, the project id,
the expiry and a sign-in time of at most 10 minutes, and only then trusts the email / mobile number inside.

## How the analysis works

1. Every sheet is read; title rows, multi-row headers and "one column per day" layouts are normalized.
2. Cleaning: blank rows/columns, duplicates, total/footer rows, N/A placeholders, text-to-number and date conversion. Excel error cells and empty placeholder rows are reported.
3. The master sheet is the largest, most complete data table (sheet names such as "master"/"data" score higher).
4. Business area is scored from sheet names and headers.
5. Figures the workbook itself states are read first: label/value blocks above the table (for example "Schedule value" with
   its number underneath), "Total" rows below or above the table, and label: value pairs at the top or bottom of a sheet.
   They are used exactly as written and listed in the card "Figures found in sheet headers and totals". If a stated total
   differs from the sum of its rows, a note tells you.
   KPIs come from the workbook: plan-vs-actual ratios, rejection rate, totals named by their real headers with units
   (Rs Cr/L, pcs, kg, hrs, %), and one KPI per row on summary/MIS sheets.
6. Charts are chosen from the date, category and numeric columns found; each chart has a type switcher.

## Security notes

- Passwords are stored hashed (PBKDF2 via Werkzeug); sessions use signed HttpOnly cookies; 5 failed logins lock an IP for 5 minutes.
- The server speaks plain HTTP, which is fine on a trusted office network.
- Workbooks are processed in the browser and never saved on the server.

## Limits

- Analysis runs in the browser, so very large workbooks (tens of MB) take longer on slow devices.
- KPIs are inferred from headers. Company-specific formulas (for example "Utilised capacity") appear only if the workbook has the needed columns.
