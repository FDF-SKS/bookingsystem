(function(){
    // Theme toggle controller
    var STORAGE_KEY = 'site-theme'; // values: 'light' | 'dark' | 'system'
    var mq = null;

    function safeGetStorage(){
        try { return localStorage.getItem(STORAGE_KEY); } catch(e) { return null; }
    }
    function safeSetStorage(v){
        try { localStorage.setItem(STORAGE_KEY, v); } catch(e) {}
    }

    function detectSystem(){
        try { return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'; } catch(e) { return 'light'; }
    }

    function applyTheme(mode){
        var applied = mode;
        if(!mode || mode === 'system') applied = detectSystem();
        try {
            document.documentElement.setAttribute('data-bs-theme', applied);
            document.documentElement.dataset.siteTheme = mode || 'system';
        } catch(e) {}
    }

    function onSystemChange(e){
        // Only react if current stored preference is 'system'
        var stored = safeGetStorage();
        if(stored === 'system' || !stored) {
            var applied = e.matches ? 'dark' : 'light';
            try { document.documentElement.setAttribute('data-bs-theme', applied); } catch(e){}
            updateToggleUI();
        }
    }

    function enableSystemListener(){
        if(!mq) {
            try {
                mq = window.matchMedia('(prefers-color-scheme: dark)');
                if(mq.addEventListener) mq.addEventListener('change', onSystemChange);
                else if(mq.addListener) mq.addListener(onSystemChange);
            } catch(e) { mq = null; }
        }
    }
    function disableSystemListener(){
        if(mq) {
            try { if(mq.removeEventListener) mq.removeEventListener('change', onSystemChange); else if(mq.removeListener) mq.removeListener(onSystemChange); } catch(e){}
            mq = null;
        }
    }

    function setTheme(mode){
        mode = mode === 'light' || mode === 'dark' || mode === 'system' ? mode : 'system';
        safeSetStorage(mode);
        applyTheme(mode);
        if(mode === 'system') enableSystemListener(); else disableSystemListener();
        updateToggleUI();
        document.dispatchEvent(new CustomEvent('site:themeChanged', { detail: { theme: mode } }));
    }

    function init(){
        var stored = safeGetStorage() || 'system';
        applyTheme(stored);
        if(stored === 'system') enableSystemListener();
        // Attach click handlers for dropdown items
        document.addEventListener('DOMContentLoaded', function(){
            document.querySelectorAll('[data-theme-option]').forEach(function(el){
                el.addEventListener('click', function(ev){ ev.preventDefault(); var t = el.dataset.themeOption; setTheme(t); });
            });
            updateToggleUI();
        });
    }

    function updateToggleUI(){
        try {
            var stored = safeGetStorage() || 'system';
            document.querySelectorAll('[data-theme-option]').forEach(function(el){
                if(el.dataset.themeOption === stored){
                    el.classList.add('active');
                    el.setAttribute('aria-pressed','true');
                    // add check icon if not present
                    if(!el.querySelector('.theme-check')){
                        var span = document.createElement('span');
                        span.className = 'theme-check ms-2 text-primary';
                        span.innerHTML = '✓';
                        el.appendChild(span);
                    }
                } else {
                    el.classList.remove('active');
                    el.setAttribute('aria-pressed','false');
                    var existing = el.querySelector('.theme-check'); if(existing) existing.remove();
                }
            });
        } catch(e) {}
    }

    // Expose API
    window.themeToggle = {
        init: init,
        setTheme: setTheme,
        getStored: safeGetStorage,
        applyTheme: applyTheme
    };

    // Auto-init (will be a no-op if DOM not ready yet)
    if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
