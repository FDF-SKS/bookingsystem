"""The built-in guides for the booking system.

Each page lives as a plain HTML file in ``pages/`` and is registered here. The
``seed_wiki_guides`` management command turns this list into ``WikiPage`` rows,
so the guides are versioned in git and can be deployed with a single command
instead of being copied by hand.

The markup is deliberately limited to what the TipTap editor can hold (headings,
paragraphs, lists, quotes, links, images and inline formatting). Anything else
would be stripped the first time a page is opened and saved in the editor.
"""

from pathlib import Path

PAGES_DIR = Path(__file__).resolve().parent / 'pages'

# ``parent`` refers to another page's slug. The list is ordered so a parent is
# always defined before its children.
PAGES = [
    {
        'slug': 'guide-til-bookingsystemet',
        'title': 'Guide til bookingsystemet',
        'parent': None,
        'order': 10,
    },
    # --- Kom godt i gang ---------------------------------------------------
    {
        'slug': 'kom-godt-i-gang',
        'title': 'Kom godt i gang',
        'parent': 'guide-til-bookingsystemet',
        'order': 10,
    },
    {
        'slug': 'log-ind',
        'title': 'Log ind og første gang',
        'parent': 'kom-godt-i-gang',
        'order': 10,
    },
    {
        'slug': 'forside-og-navigation',
        'title': 'Forsiden og navigation',
        'parent': 'kom-godt-i-gang',
        'order': 20,
    },
    {
        'slug': 'min-profil-og-sikkerhed',
        'title': 'Min profil og sikkerhed',
        'parent': 'kom-godt-i-gang',
        'order': 30,
    },
    # --- Tjanser -----------------------------------------------------------
    {
        'slug': 'tjanser',
        'title': 'Tjanser i løbet af eventet',
        'parent': 'guide-til-bookingsystemet',
        'order': 20,
    },
    {
        'slug': 'tjanser-se-og-opdater',
        'title': 'Se og opdater dine tjanser',
        'parent': 'tjanser',
        'order': 10,
    },
    {
        'slug': 'tjanser-byt',
        'title': 'Byt en tjanse med et andet team',
        'parent': 'tjanser',
        'order': 20,
    },
    {
        'slug': 'tjanser-overblik',
        'title': 'Alle tjanser over flere dage',
        'parent': 'tjanser',
        'order': 30,
    },
    # --- Slutrengøring -----------------------------------------------------
    {
        'slug': 'slutrengoring',
        'title': 'Slutrengøring',
        'parent': 'guide-til-bookingsystemet',
        'order': 30,
    },
    {
        'slug': 'slutrengoring-for-teams',
        'title': 'Slutrengøring: sådan gør dit team',
        'parent': 'slutrengoring',
        'order': 10,
    },
    {
        'slug': 'slutrengoring-call-center',
        'title': 'Slutrengøring: status for call center',
        'parent': 'slutrengoring',
        'order': 20,
    },
    {
        'slug': 'slutrengoring-opsaetning',
        'title': 'Slutrengøring: opsætning for admin',
        'parent': 'slutrengoring',
        'order': 30,
    },
    # --- Bookinger ---------------------------------------------------------
    {
        'slug': 'bookinger',
        'title': 'Bookinger',
        'parent': 'guide-til-bookingsystemet',
        'order': 40,
    },
    {
        'slug': 'bookinger-saadan',
        'title': 'Sådan laver du en booking',
        'parent': 'bookinger',
        'order': 10,
    },
    {
        'slug': 'butikken',
        'title': 'Butikken',
        'parent': 'bookinger',
        'order': 20,
    },
    {
        'slug': 'aktivitetsteam',
        'title': 'AktivitetsTeam',
        'parent': 'bookinger',
        'order': 30,
    },
    {
        'slug': 'loeb',
        'title': 'Løb',
        'parent': 'bookinger',
        'order': 40,
    },
    {
        'slug': 'sos',
        'title': 'SOS',
        'parent': 'bookinger',
        'order': 50,
    },
    {
        'slug': 'foto',
        'title': 'Foto',
        'parent': 'bookinger',
        'order': 60,
    },
    {
        'slug': 'sjak',
        'title': 'Sjak',
        'parent': 'bookinger',
        'order': 70,
    },
    {
        'slug': 'teknik',
        'title': 'Teknik',
        'parent': 'bookinger',
        'order': 80,
    },
    {
        'slug': 'depot',
        'title': 'Depot',
        'parent': 'bookinger',
        'order': 90,
    },
    {
        'slug': 'legeaftaler',
        'title': 'Legeaftaler',
        'parent': 'bookinger',
        'order': 100,
    },
    # --- Administrator -----------------------------------------------------
    {
        'slug': 'administrator',
        'title': 'For administratorer',
        'parent': 'guide-til-bookingsystemet',
        'order': 50,
    },
    {
        'slug': 'admin-overblik',
        'title': 'Admin: overblik og opbygning',
        'parent': 'administrator',
        'order': 10,
    },
    {
        'slug': 'admin-events-og-teams',
        'title': 'Admin: events og teams',
        'parent': 'administrator',
        'order': 20,
    },
    {
        'slug': 'admin-medarbejdere-og-noegler',
        'title': 'Admin: medarbejdere og nøgler',
        'parent': 'administrator',
        'order': 30,
    },
    {
        'slug': 'admin-tjanser',
        'title': 'Admin: tjanser og tildeling',
        'parent': 'administrator',
        'order': 40,
    },
    {
        'slug': 'admin-godkend-bookinger',
        'title': 'Admin: godkend bookinger',
        'parent': 'administrator',
        'order': 50,
    },
    {
        'slug': 'admin-wiki',
        'title': 'Admin: rediger wikien',
        'parent': 'administrator',
        'order': 60,
    },
]

SLUGS = [page['slug'] for page in PAGES]


def content_path(slug: str) -> Path:
    """Return the HTML file that holds the body of ``slug``."""
    return PAGES_DIR / f'{slug}.html'


def content_for(page: dict) -> str:
    """Return the body HTML for a manifest entry."""
    return content_path(page['slug']).read_text(encoding='utf-8').strip()
