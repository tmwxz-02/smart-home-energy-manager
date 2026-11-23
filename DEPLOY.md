# Putting the app online

`start.bat` runs the app **only on your computer** (`127.0.0.1`). To let other people open it **at any time**, even when your laptop is off, it must run on a server. This guide uses **PythonAnywhere**: it has a free plan, runs Python, keeps SQLite files between restarts, and needs no credit card.

Result: a permanent address like `https://yourname.pythonanywhere.com`.

> Free plans and their conditions can change. Check pythonanywhere.com/pricing before you rely on them.

## Before you upload: decide who may change data

The online copy has **one shared database**. Everything one visitor adds, every other visitor sees. Choose one option:

| Option | Setting | Good for |
| --- | --- | --- |
| Read-only (recommended for showing the project) | `SHEM_READ_ONLY = 1` | Instructor and classmates can open every page, the demo, analytics and calculators, but cannot change or delete anything |
| Password | `SHEM_PASSWORD = <your password>` | Only people you give the password to can open the site. Combine it with read-only if you like |
| Open | neither | Anyone with the link can add or change data |

The **Demo** workspace (synthetic data) is generated automatically on first visit, so a read-only copy still has plenty to show.

## Step-by-step: PythonAnywhere

1. **Build the upload file.** On your computer, in the project folder, run:
   ```bash
   python make_zip.py
   ```
   This creates `dist\fai.zip` (code only, without your `data` folder).

2. **Create an account.** Go to <https://www.pythonanywhere.com>, choose the free *Beginner* account and sign up. You do this yourself; the user name becomes part of the address.

3. **Upload the zip.** Open **Files** → go to `/home/<username>/` → **Upload a file** → choose `dist\fai.zip`.

4. **Unpack it.** Open **Consoles** → **Bash**, and run:
   ```bash
   unzip fai.zip
   ls fai
   ```
   You should see `app.py`, `wsgi.py`, `backend`, `frontend` and the other files.

   Live copy of this project: **https://tmwxz.pythonanywhere.com** (editable by anyone with the link; to make it read-only again, uncomment the `SHEM_READ_ONLY` line in the WSGI file and click Reload).

5. **Create the web app.** Open **Web** → **Add a new web app** → **Next** → **Manual configuration** (not Flask or Django) → choose **Python 3.10** or newer → **Next**.

6. **Connect the code.** On the **Web** page, click the link to the **WSGI configuration file** (`/var/www/<username>_pythonanywhere_com_wsgi.py`). Delete everything in it, paste this, and replace `USERNAME` with your user name:
   ```python
   import os
   import sys

   project = "/home/USERNAME/fai"
   if project not in sys.path:
       sys.path.insert(0, project)

   os.environ["SHEM_DATA_DIR"] = project + "/data"
   os.environ["SHEM_READ_ONLY"] = "1"          # remove this line to allow changes
   # os.environ["SHEM_PASSWORD"] = "choose-a-password"   # optional

   from wsgi import application  # noqa: E402
   ```
   Click **Save**.

7. **Start it.** Back on the **Web** tab, click the green **Reload** button. Open `https://<username>.pythonanywhere.com`. The page should load with the "Read-only copy" banner. Click **Demo** to see the synthetic data.

8. **Keep it alive.** On the free plan the web app stops after **one month** unless you log in and click **"Run until 1 month from today"** on the **Web** tab (PythonAnywhere emails a reminder a week before). Do this shortly before the defense.

### Updating after you change the code

1. Run `python make_zip.py` again and upload the new `fai.zip` (overwrite it).
2. In the Bash console:
   ```bash
   unzip -o fai.zip
   ```
3. Click **Reload** on the **Web** tab. Your online `data` folder is not in the zip, so online data is kept.

### If something goes wrong

- **"Something went wrong" page:** on the **Web** tab, open the **Error log**. The most common cause is a wrong user name in the WSGI file path.
- **The page loads but buttons do nothing:** reload with Ctrl+F5 to clear the cache.
- **Want to start the online data from zero:** in the Bash console run `rm fai/data/*.db`, then click **Reload**.

## Alternative: share from your own laptop (temporary)

For a quick showing (for example, to your teammate tonight) you can expose the copy running on your laptop through a free tunnel such as Cloudflare Tunnel (`cloudflared tunnel --url http://localhost:8000`). It works **only while your laptop is on and `start.bat` is running**, and the address changes each time. You have to download `cloudflared` from Cloudflare yourself. If you do this, start the app with a password:

```bash
set SHEM_PASSWORD=choose-a-password
python app.py
```

On the same Wi-Fi, `start_network.bat` is enough and needs no tunnel.

## Other hosts

Any host that can run Python works:
- with a WSGI server: use `wsgi:application`;
- or with a start command: `python app.py --host 0.0.0.0 --no-browser` (the port is taken from the `PORT` environment variable).

Many free plans (for example Render's free web services) **delete local files on restart**, so the SQLite data would be lost. Use them only together with read-only mode, where the data that matters is the auto-generated demo.
