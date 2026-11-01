# Nyt bookingsystem til kurserne i FDF
Dette er et forsøg på at lave et nyt booking system til kurserne indenfor FDF. Det er work-in-progress, så bær over med os!


## Framework
Web appen er bygget som en Django web app. Det er et framework hvor du som udvikler primært arbejder i python, og bruger python scripts server side til at håndtere databasen og servere html. Det gør at det programmeringssprog du skal sætte dig ind i primært er python, hvilket er meget udbredt inden for en række grene af programmering, og ikke blot web-udvikling. Dette skulle gøre "bar of entry" lavere for flere.

Vil du læse mere om Django?:
https://docs.djangoproject.com/en/5.2/


Skal du bare have installeret Django og komme igang?:
https://docs.djangoproject.com/en/5.2/intro/install/


## 🧩 Miljøvariabler (.env-filer)

Projektet bruger tre forskellige opsætninger, og de styres af variablen `ENVIRONMENT`:

| `ENVIRONMENT` | Database | Email | Redis | Webserver | Bruges til |
|---------------|----------|-------|-------|-----------|------------|
| `dev`         | SQLite (`src/db.sqlite3`) | printes i terminalen | ikke nødvendig (Celery kører inline) | `runserver` | Lokal udvikling på din egen maskine |
| `staging`     | Postgres i container | Amazon SES | påkrævet | gunicorn (den lokale `docker-compose.staging.yaml` kører dog `runserver`) | Test af Docker-opsætning / staging-server |
| `production`  | Postgres i container | Amazon SES | påkrævet | gunicorn | Den rigtige server |

Der findes to skabeloner i repoet. Begge indeholder **kun dummy-værdier** og må gerne ligge offentligt på GitHub:

| Fil | Kopiér til | Indhold |
|-----|------------|---------|
| `.env.example` | `.env` | Lokal udvikling (`ENVIRONMENT=dev`) |
| `.env.staging.example` | `.env.staging` | Docker-staging (`ENVIRONMENT=staging`) |

> ⚠️ `.env` og `.env.staging` er listet i `.gitignore`. De må aldrig committes, og de må ikke indeholde de samme nøgler som produktionen.

Skal du bruge en anden værdi end dummy-værdierne, f.eks. en rigtig `DJANGO_SECRET_KEY`, kan du generere en med:
```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```


## Opsætning (lokal udvikling)
> OBS! Det antages at du allerede har Python samt Git kørende på din maskine.

### 1. Klon repository
```bash
git clone https://github.com/FDF-SKS/bookingsystem
cd bookingsystem
```

### 2. Opret virtual environment

**macOS / Linux:**
```bash
cd bookingsystem
```
Django kører på Python, så for at sikre at vi har de rigtige pakker installeret, så laver vi et virtual environment. 
```bash 
python -m venv venv
venv\Scripts\activate.bat
```

> Får du i PowerShell fejlen *"running scripts is disabled on this system"*, kør da én gang:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

Når det virker, står der `(venv)` foran din prompt. Så skal alle `python`- og `pip`-kommandoer herunder køres i det aktiverede environment.

### 3. Installer afhængigheder

**macOS / Linux:**
```bash
pip install -r src/requirements.txt
```

**Windows (PowerShell eller cmd):**
```powershell
pip install -r src/requirements.txt
```

### 4. Opret din `.env`-fil

**macOS / Linux:**
```bash
cp .env.example .env
nano .env          # eller brug din foretrukne editor
```

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
notepad .env       # eller åbn i VS Code med: code .env
```

**Windows (cmd / Kommandoprompt):**
```bat
copy .env.example .env
notepad .env
```

Filen skal have `ENVIRONMENT=dev`, når du kører Django direkte på din maskine. Så bruges SQLite, emails printes i terminalen, og du behøver hverken Postgres eller Redis.

### 5. Kør database-migreringer

Gå ind i `src`-mappen (samme kommando på alle platforme):
```bash
cd src
```

**macOS / Linux:**
```bash
python manage.py migrate
```

**Windows (PowerShell eller cmd):**
```powershell
python manage.py migrate
```

Hvis det er første gang der migreres, skal du oprette en superbruger for at få adgang til Django admin. Email og password kan bagefter bruges til at logge ind på booking-siden:
```bash
python manage.py createsuperuser
```

### 6. Start udviklingsserveren

**macOS / Linux:**
```bash
python manage.py runserver
```

**Windows (PowerShell eller cmd):**
```powershell
python manage.py runserver
```

Du skulle gerne få en meddelelse i terminalen der ligner den her:
```bash
Watching for file changes with StatReloader
Performing system checks...

System check identified no issues (0 silenced).
Django version 5.2.10, using settings 'core.settings'
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-C.
```

Nu skulle siden gerne være oppe på `http://127.0.0.1:8000`, og du kan logge ind med din superbruger. Den er desværre helt tom, så nu kan du gå igang med at fylde den med dummy data.

> 🔑 Login foregår med **email** – ikke brugernavn. Passkeys og engangskoder via email er også understøttet, og kan sættes op under kontoindstillingerne.


## ✅ Tests

Testene kører fra `src`-mappen:

**macOS / Linux:**
```bash
cd src
python manage.py test
```

**Windows (PowerShell eller cmd):**
```powershell
cd src
python manage.py test
```

GitHub Actions-workflowet **Django Tests** (`.github/workflows/django.yml`) kører automatisk `manage.py check`, `makemigrations --check` og hele testsuiten ved hvert push og hver pull request. En PR kan ikke merges hvis testene fejler.


## 🚀 Sådan kører du projektet

### 1. Lokal Udvikling
Bedst til hurtige UI/UX ændringer og test af logik. Følg opsætningen ovenfor, og kør derefter:

**macOS / Linux:**
```bash
cd src
python manage.py runserver
```

**Windows (PowerShell eller cmd):**
```powershell
cd src
python manage.py runserver
```

Applikationen er nu tilgængelig på `http://localhost:8000`.

---

### 2. Staging (Docker)
At teste på din maskine er fint nok. Vi bruger Docker til at teste hvordan det virker på noget der er sat op som produktionsserveren, og som minder mere om den.
> OBS: For at komme videre skal du have Docker Desktop installeret og kørende. [Kom igang med Docker](https://www.docker.com/get-started/)

Staging bruger en **separat** env-fil, så den ikke overskriver din lokale `.env`.

**macOS / Linux:**
```bash
cp .env.staging.example .env.staging
chmod 600 .env.staging
docker compose -f docker-compose.staging.yaml --env-file .env.staging up -d --build
```

**Windows (PowerShell):**
```powershell
Copy-Item .env.staging.example .env.staging
docker compose -f docker-compose.staging.yaml --env-file .env.staging up -d --build
```

**Windows (cmd / Kommandoprompt):**
```bat
copy .env.staging.example .env.staging
docker compose -f docker-compose.staging.yaml --env-file .env.staging up -d --build
```

Første gang du starter miljøet, skal du oprette en superbruger i containeren:

**macOS / Linux:**
```bash
docker compose -f docker-compose.staging.yaml --env-file .env.staging exec web python manage.py createsuperuser
```

**Windows (PowerShell eller cmd):**
```powershell
docker compose -f docker-compose.staging.yaml --env-file .env.staging exec web python manage.py createsuperuser
```

Staging-miljøet er tilgængeligt på `http://localhost:8001`. Email-nøglerne i `.env.staging.example` er bevidst ugyldige, så staging kan ikke sende rigtige emails.

---

## 🚢 Deployment til Produktion (Hetzner)

### Trin A: Byg og push Docker-imaget fra din lokale maskine

Imaget skal bygges til serverens arkitektur (`linux/amd64`). På en Apple Silicon-mac (M1/M2/M3) er dette ekstra vigtigt, ellers crasher containeren med `exec format error`.

**macOS / Linux:**
```bash
docker login -u mglavind
docker buildx build --platform linux/amd64 -f dockerfile -t mglavind/booking-app:latest --push .
```

**Windows (PowerShell eller cmd):**
```powershell
docker login -u mglavind
docker buildx build --platform linux/amd64 -f dockerfile -t mglavind/booking-app:latest --push .
```

Har du ikke Docker Hub-adgang, kan du i stedet bygge lokalt uden `--push` og få imaget overført på anden vis.

### Trin B: Udrulning på serveren

Udrulningen sker automatisk: `.github/workflows/hetzner.yml` logger på serveren via SSH ved hvert push til `main` og kører

1. `docker compose pull web` – henter det nyeste image fra Docker Hub
2. `docker compose up -d` – genstarter containere uden nedetid
3. `python manage.py migrate --noinput` – opdaterer databaseskemaet
4. `python manage.py collectstatic --noinput` – indsamler statiske filer (essentielt for **Unfold** admin-temaet)
5. `docker image prune -f` – rydder op i gamle images

Vil du deploye manuelt, kan du gøre det samme på serveren:

**macOS / Linux (via SSH):**
```bash
ssh root@<server-ip>
cd /root/booking-system
docker compose pull web
docker compose up -d
docker compose exec -T web python manage.py migrate --noinput
docker compose exec -T web python manage.py collectstatic --noinput
```

**Windows (PowerShell):**
```powershell
ssh root@<server-ip>
cd /root/booking-system
docker compose pull web
docker compose up -d
docker compose exec -T web python manage.py migrate --noinput
docker compose exec -T web python manage.py collectstatic --noinput
```

> 🔐 Huskeseddel: produktionens `.env` ligger **kun** på serveren. Den er ikke i repoet og må ikke kopieres til din lokale maskine eller til staging.

---

## 🛠️ Almindelige Vedligeholdelseskommandoer

### Logs & Fejlfinding

**Følg live logs:**
```bash
docker compose logs -f web
```

**Åbn Django shell:**
```bash
docker compose exec web python manage.py shell
```

**Genstart services:**
```bash
docker compose restart
```

---

### Database Backup

**macOS / Linux:**
```bash
docker compose exec -T db sh -c 'pg_dump -U "$DATABASE_USERNAME" "$DATABASE_NAME"' > db_backup_$(date +%F).sql
```

**Windows (PowerShell):**
```powershell
docker compose exec -T db sh -c 'pg_dump -U "$DATABASE_USERNAME" "$DATABASE_NAME"' > db_backup_$(Get-Date -Format yyyy-MM-dd).sql
```

Dette opretter en backup-fil med dagens dato i filnavnet (f.eks. `db_backup_2026-02-12.sql`).

---

### Email (Amazon SES)

Emails sendes via Celery (`worker`-servicen) og Amazon SES (`django-ses`). Status følges under Admin > Emails.

**Miljøvariabler (`.env.staging.example` viser formatet):**
```
SITE_URL=https://booking.markusglavind.dk
DEFAULT_FROM_EMAIL=<verificeret afsender i SES>
AWS_SES_REGION_NAME=eu-north-1
AWS_SES_ACCESS_KEY_ID=...
AWS_SES_SECRET_ACCESS_KEY=...
AWS_SES_CONFIGURATION_SET=<navn på configuration set>
```

**AWS-opsætning:**
1. Verificér domænet i SES (DKIM, SPF, DMARC) og ansøg om production access.
2. Opret et SNS-topic og en configuration set med event destination (Delivery, Bounce, Complaint) til topicet.
3. Tilføj en HTTPS-subscription på `https://<domæne>/ses/notifications/` (bekræftes automatisk af Django).
4. IAM-bruger med kun `ses:SendRawEmail` (og `ses:SendEmail`) til afsender-identiteten.

**Test på staging:** send til `success@`, `bounce@` og `complaint@simulator.amazonses.com` og kontrollér status i Email-log.

**Oprydning af email-log:** bodies slettes straks efter afsendelse. Kør dagligt via cron for at rydde fejlede emails (>7 dage) og slette log-rækker (>90 dage):
```bash
30 3 * * * docker compose exec -T web python manage.py cleanup_email_logs
```
