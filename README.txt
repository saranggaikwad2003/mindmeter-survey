MINDMETER — UPDATED STUDENT DIGITAL WELLBEING WEBSITE
=====================================================

WHAT IS INCLUDED
- Similar clean blue/white dashboard design to the screenshot
- 15-question student survey plus optional comment
- Consent confirmation and 18+ participation prompt
- Central server-side SQLite database (not browser localStorage)
- Admin login, dashboard, response table and CSV export
- Share survey / WhatsApp buttons on the dashboard
- Ready for local testing and deployment

RUN LOCALLY ON WINDOWS
1. Install Python 3.10 or newer from https://www.python.org/downloads/
   During setup, select "Add Python to PATH".
2. Extract this ZIP.
3. Open the extracted folder, click the File Explorer address bar, type cmd, press Enter.
4. Run:
   py -m venv .venv
   .venv\Scripts\activate
   py -m pip install -r requirements.txt
   py app.py
5. Open http://127.0.0.1:5000

ADMIN LOGIN (LOCAL DEMO)
URL: http://127.0.0.1:5000/admin/login
Username: admin
Password: ChangeMe123!

IMPORTANT SECURITY
- Change the default admin password before collecting real responses.
- For a fresh database, set MINDMETER_ADMIN_PASSWORD before first run:
  set MINDMETER_ADMIN_PASSWORD=YourStrongPassword
- The initial admin account is created once. Changing the environment variable later
  does not change an existing database password.
- Keep the database file data/responses.db private and back it up.
- Do not publish the database or share admin credentials.
- Before collecting actual responses, obtain supervisor/college approval and use voluntary consent.
- Do not collect names, student IDs, emails or phone numbers.
- This is not a medical diagnostic test; score bands are exploratory indicators only.

SHARE WITH STUDENTS
1. Run the website locally to test it.
2. To allow students outside your computer to access it, deploy the project to a hosting provider.
3. After deployment, open the public website URL and click "Share Survey" or "WhatsApp".
4. Do NOT send http://127.0.0.1:5000 to students; localhost works only on your computer.
5. Use persistent database storage for deployment. The SQLite file must not be stored on an ephemeral disk.

NOTE
The project includes an actual server-side database implementation, but this ZIP has not been
published online. You must deploy it to obtain a public link.
