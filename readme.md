# Nyt bookingsystem til kurserne i FDF
Dette er et forsøg på at lave et nyt booking system til kurserne indenfor FDF. Det er work-in-progress, så bær over med os!


## Framework
Web appen er bygget som en Django web app. Det er et framework hvor du som udvikler primært arbejder i python, og bruger python scripts server side til at håndtere databasen og servere html. Det gør at det programmeringssprog du skal sætte dig ind i primært er python, hvilket er meget udbredt inden for en række grene af programmering, og ikke blot web-udvikling. Dette skulle gøre "bar of entry" lavere for flere. 

Vil du læse mere om Django?: 
https://docs.djangoproject.com/en/5.2/


Skal du bare have installeret Django og komme igang?: 
https://docs.djangoproject.com/en/5.2/intro/install/


## Opsætning
> OBS! Det antages at du allerede har Python samt Git gørende på din maskine

Først kloner du git repository
```bash 
git clone https://github.com/FDF-SKS/bookingsystem
```
Så hopper vi ind i det ny hentede repository
```bash
cd booking-system
```
Django kører på Python, så for at sikre at vi har de rigtige pakker installeret, så laver vi et virtual environment. 
```bash 
python -m venv venv
```

herefter skal der laves et virtuelt enviroment som vi kan køre python med diverse pakker afgrænset i
**Mac/Linux:**
```bash 
source venv/bin/activate
```
**Windows (PowerShell):**
```powershell
venv\Scripts\activate
```
herefter skal vi have sat enviroment variabler op. lav derfor en `.env` fil baseret på `.env.example` og tilpas værdierne:

**Mac/Linux:**
```bash
cp .env.example .env
nano .env  # eller brug din foretrukne editor
```

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
notepad .env  # eller åbn i VS Code med: code .env
```

**Vigtige .env variable:**

| Variable              | Log level  | Database | Beskrivelse |
|-----------------------|------------|----------|----------|
| `ENVIRONMENT=dev`     | Debug      | sqlite3    | Til Django direkte - giver fuld log output og kører uden Redis |
| `ENVIRONMENT=staging` | Warning    | postgres13 | Til Django pakket ind i en Docker container|



Der er gjort klar til at der kan ligges en frontend på, derfor skal vi navigere ind i mappen "src"

```bash 
cd src
```

Herefter installerer vi alle afhængigheder
```bash 
pip install -r requirements.txt
```


Nu er vores virtual enviroment klar til at køre vores Django side. Næste skridt er at få django til at køre de seneste database migreringer, så databasen er ajour.

```bash 
python manage.py migrate
```
Hvis det er første gang der migreres, skal vi oprætte en superbruger for at få adgang til Django admin delen. Brugernavn og password kan derefer bruges til at logge ind på booking siden
```bash 
python manage.py createsuperuser
```
Herefter er der kun tilbage at starte serveren
```bash 
python manage.py runserver
```
Du skulle gerne få en meddelelse i terminalen der ligner den her:
```bash 
(venv) \Sti\til\dit\repository\booking-docker\src python manage.py runserver
Watching for file changes with StatReloader
Performing system checks...

System check identified no issues (0 silenced).
February 12, 2026 - 20:38:09
Django version 5.2.10, using settings 'core.settings'
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.

WARNING: This is a development server. Do not use it in a production setting. Use a production WSGI or ASGI server instead.
For more information on production servers see: https://docs.djangoproject.com/en/5.2/howto/deployment/

```
Nu skulle gerne være oppe og køre, og kunne logge ind med din superbruger på booking siden - den er desværre helt tom, så nu kan du gå igang med at fylde den med dummy data.


## 🚀 Sådan kører du projektet

### 1. Lokal Udvikling
Bedst til hurtige UI/UX ændringer og test af logik.

**Naviger til src mappen:**
```bash
cd src
```

**Installer dependencies:**
```bash
pip install -r requirements.txt
```

**Kør database migrationer:**
```bash
python manage.py migrate
```

**Start udviklingsserveren:**
```bash
python manage.py runserver
```

Applikationen er nu tilgængelig på `http://localhost:8000`

---

### 2. Staging (Docker)
At teste på din maskine er fint nok. Vi bruger docker til at teste hvordan det virker på noget der er sat op som produktions serveren, og minder mere om den.
> OBS: for at komme videre, skal du have sat Docker op. [Kom igang med Docker](https://www.docker.com/get-started/)

**Start staging miljøet:**
```bash
docker compose -f docker-compose.yaml -f docker-compose.staging.yaml --env-file .env.staging up -d --build
```

**Kør database migrationer:**
```bash
docker compose exec web python manage.py createsuperuser
```

---

## 🚢 Deployment til Produktion (Hetzner)

### Trin A: Fra din lokale maskine
Byg og push det nyeste Docker image til Docker Hub.

**Byg Docker image:**
```bash
docker build -t mglavind/booking-app:latest .
```

**Push til Docker Hub:**
```bash
docker push mglavind/booking-app:latest
```

---

### Trin B: På Hetzner serveren
Kør automatiseringsskriptet for at hente det nye image og opdatere det live site.

**Kør deployment script:**
```bash
./deploy.sh
```

---

## 📝 deploy.sh Scriptet

`deploy.sh` scriptet på Hetzner serveren automatiserer følgende:

1. **Henter** det nyeste Docker image fra Docker Hub
2. **Genstarter** containers uden manuel konfiguration
3. **Migrerer** database schema automatisk
4. **Indsamler** statiske filer (essentielt for **Unfold** admin temaet)
5. **Håndterer** tilladelser for `./static` og `./media` mapperne
6. **Genindlæser** Nginx for at sikre nye assets serveres med det samme

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

**Opret backup af databasen:**
```bash
docker compose exec db pg_dump -U mglavind production_db > backups/db_backup_$(date +%F).sql
```

Dette opretter en backup fil med dagens dato i filnavnet (f.eks. `db_backup_2026-02-12.sql`)

---