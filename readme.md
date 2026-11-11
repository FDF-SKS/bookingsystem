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
| `staging`     | Postgres i container | Amazon SES | påkrævet | gunicorn | Test af Docker-opsætning / staging-server |
| `production`  | Postgres i container | Amazon SES | påkrævet | gunicorn | Den rigtige server |

Der findes to skabeloner i repoet. Begge indeholder **kun dummy-værdier** og må gerne ligge offentligt på GitHub:

| Fil | Kopiér til | Indhold |
|-----|------------|---------|
| `.env.example` | `.env` | Lokal udvikling (`ENVIRONMENT=dev`) |
| `.env.staging.example` | `.env.staging` | Docker-staging (`ENVIRONMENT=staging`) |

> ⚠️ `.env` og `.env.staging` er listet i `.gitignore`. De må aldrig committes, og de må ikke genbruge produktionens nøgler eller database-adgangskode.

Skal du bruge en anden værdi end dummy-værdierne, f.eks. en rigtig `DJANGO_SECRET_KEY`, kan du generere en med (samme kommando på alle platforme):
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
Django kører på Python, så for at sikre at vi har de rigtige pakker installeret, laver vi et virtual environment. Her er kommandoerne **ikke** ens på de tre platforme.

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

**Windows (cmd / Kommandoprompt):**
```bat
python -m venv venv
venv\Scripts\activate.bat
```

> Får du i PowerShell fejlen *"running scripts is disabled on this system"*, kør da én gang:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

Når det virker, står der `(venv)` foran din prompt. Så skal alle `python`- og `pip`-kommandoer herunder køres i det aktiverede environment.

### 3. Installer afhængigheder
Køres fra repository-roden – samme kommando på alle platforme:
```bash
pip install -r src/requirements.txt
```

### 4. Opret din `.env`-fil
Selve kommandoen til at kopiere filen er forskellig fra Windows til macOS/Linux.

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
Gå ind i `src`-mappen og kør migreringerne – samme kommando på alle platforme:
```bash
cd src
python manage.py migrate
```

Hvis det er første gang der migreres, skal du oprette en superbruger for at få adgang til Django admin. Email og password kan bagefter bruges til at logge ind på booking-siden:
```bash
python manage.py createsuperuser
```

### 6. Start udviklingsserveren
Samme kommando på alle platforme (husk at du stadig står i `src`-mappen):
```bash
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
Kør fra `src`-mappen – samme kommando på alle platforme:
```bash
python manage.py test
```

GitHub Actions-workflowet **Django Tests** (`.github/workflows/django.yml`) kører automatisk `manage.py check`, `makemigrations --check` og hele testsuiten ved hvert push og hver pull request. En PR kan ikke merges hvis testene fejler.


## 🚀 Sådan kører du projektet

### 1. Lokal Udvikling
Bedst til hurtige UI/UX ændringer og test af logik. Følg opsætningen ovenfor (punkt 1-6) – den ender med, at serveren kører.

Applikationen er nu tilgængelig på `http://localhost:8000`.

---

### 2. Staging (Docker)
At teste på din maskine er fint nok. Vi bruger Docker til at teste hvordan det virker på noget der er sat op som produktionsserveren, og som minder mere om den.
> OBS: For at komme videre skal du have Docker Desktop installeret og kørende. [Kom igang med Docker](https://www.docker.com/get-started/)

Staging bruger en **separat** env-fil, så den ikke overskriver din lokale `.env`. Kopiér skabelonen (kommandoen er forskellig på Windows og macOS/Linux):

**macOS / Linux:**
```bash
cp .env.staging.example .env.staging
chmod 600 .env.staging
```

**Windows (PowerShell eller cmd):**
```powershell
Copy-Item .env.staging.example .env.staging
```

Herefter er resten ens på alle platforme:
```bash
docker compose -f docker-compose.staging.yaml --env-file .env.staging up -d --build
```

Første gang du starter miljøet, skal du oprette en superbruger i containeren:
```bash
docker compose -f docker-compose.staging.yaml --env-file .env.staging exec web python manage.py createsuperuser
```

Staging-miljøet er tilgængeligt på `http://localhost:8001`. Email-nøglerne i `.env.staging.example` er bevidst ugyldige, så staging ikke kan sende rigtige emails.

> 🧯 **Fejlfinding:** Får du `Database is uninitialized and superuser password is not specified`, mangler der en database-adgangskode i `.env.staging`. Postgres læser `POSTGRES_PASSWORD`/`POSTGRES_USER`/`POSTGRES_DB`, og de sættes i `docker-compose.staging.yaml` ud fra `DATABASE_PASSWORD`/`DATABASE_USERNAME`/`DATABASE_NAME`. Kontrollér at `DATABASE_PASSWORD` er udfyldt, og start igen. Er containeren allerede startet halvt op, kan du rydde staging-volumet (sletter kun staging-data) med:
> ```bash
> docker compose -f docker-compose.staging.yaml --env-file .env.staging down -v
> ```

> 🧯 **Fejlfinding (403 ved login):** Et `POST` til `/accounts/login/` med status 403 betyder, at CSRF-kontrollen fejlede – ikke at passwordet er forkert. Årsagen skrives kun til serverloggen (brugeren ser fortsat Djangos standard-403-side):
> ```bash
> docker compose -f docker-compose.staging.yaml --env-file .env.staging logs web | grep CSRF
> ```
> De typiske årsager er:
> - Du åbner siden på én adresse og logger ind på en anden (`localhost` og `127.0.0.1` deler ikke cookies). Brug samme adresse hele vejen.
> - Siden blev indlæst før containeren blev genstartet – genindlæs login-siden og prøv igen.
> - Adressen mangler i `CSRF_TRUSTED_ORIGINS` i `.env.staging` (skabelonen har både staging-domænet og `http://localhost:8001`).
> - nginx skal sende `proxy_set_header Host $http_host` (ikke `$host`). Med `$host` mister Django porten, og så afvises samme-origin POSTs på ikke-standard-porte som `localhost:8001`.

> 🧯 **Fejlfinding (Windows):** Fejler `web` med `exec /app/entrypoint.sh: no such file or directory`, skyldes det næsten altid CRLF-linieskift i en Windows-checkout – shebang'en bliver `#!/bin/bash\r`. Repoet har en `.gitattributes`, der tvinger LF, og `dockerfile` fjerner desuden eventuelle `\r` ved build. Kør derfor en **rebuild** af imaget:
> ```bash
> docker compose -f docker-compose.staging.yaml --env-file .env.staging build --no-cache web
> docker compose -f docker-compose.staging.yaml --env-file .env.staging up -d
> ```

---

## 🚢 Deployment til Produktion (Hetzner)

### Trin A: Byg og push Docker-imaget fra din lokale maskine
Imaget skal bygges til serverens arkitektur. Serveren er en Hetzner ARM-maskine (`linux/arm64`). På en Apple Silicon-mac (M1/M2/M3) er `linux/arm64` default; på en Intel-mac skal `--platform linux/arm64` angives eksplicit. Kommandoen er:
```bash
docker login -u mglavind
docker buildx build --platform linux/arm64 -f dockerfile -t mglavind/booking-app:latest --push .
```

Vil du bygge ét image, der virker på både ARM og Intel, kan du bruge multi-arch (kræver buildx med emulation til amd64):
```bash
docker buildx build --platform linux/amd64,linux/arm64 -f dockerfile -t mglavind/booking-app:latest --push .
```

Har du ikke Docker Hub-adgang, kan du i stedet bygge lokalt uden `--push` og få imaget overført på anden vis.

### Trin B: Udrulning på serveren
Udrulningen sker automatisk: `.github/workflows/hetzner.yml` logger på serveren via SSH ved hvert push til `main` og kører

1. `docker compose pull web` – henter det nyeste image fra Docker Hub
2. `docker compose up -d` – genstarter containere uden nedetid
3. `python manage.py migrate --noinput` – opdaterer databaseskemaet
4. `python manage.py collectstatic --noinput` – indsamler statiske filer (essentielt for **Unfold** admin-temaet)
5. `docker image prune -f` – rydder op i gamle images

Vil du deploye manuelt, kan du gøre det samme på serveren (samme kommandoer uanset om du SSH'er fra Windows eller macOS/Linux):
```bash
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
Alle kommandoer er ens på alle platforme.

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
Selve kommandoen er ens – kun datoformatet i filnavnet er forskelligt.

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
