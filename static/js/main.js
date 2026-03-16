// ============================================================
//  main.js – all client-side logic
// ============================================================

const serverDataEl = document.getElementById('server-data');
const SERVER_DATA = {
    version:          Number(serverDataEl.dataset.version),
    countdownSeconds: Number(serverDataEl.dataset.countdown)
};

// ---- Client-side state ----
let currentIndex   = 0;
let currentMaptype = 'daily';
let currentGn      = '0';  
let currentMn      = '0';  


// ---- Helper: execute <script> tags inside injected HTML ----
function activateScripts(container) {
    container.querySelectorAll('script').forEach(oldScript => {
        const newScript = document.createElement('script');
        newScript.textContent = oldScript.textContent;
        oldScript.parentNode.replaceChild(newScript, oldScript);
    });
}


// ---- Table row clicks ----
const rows = document.querySelectorAll('.data-table tbody tr');

rows.forEach((row, index) => {
    row.classList.add('clickable');
    row.addEventListener('click', () => {
        rows.forEach(r => r.classList.remove('selected'));
        row.classList.add('selected');
        currentIndex = index;
        currentGn = row.dataset.gn;
        currentMn = row.dataset.mn;


        // Pull metadata from the data- attributes
        const rowMeta = {
            index:   currentIndex,
            maptype: currentMaptype,
            gn:      currentGn,
            mn:      currentMn
        };

        fetch('/row_clicked', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(rowMeta)
        })
        .then(res => res.json())
        .then(data => {
            ['fig1-content', 'fig2-content', 'fig3-content'].forEach(id => {
                const key = id.replace('-content', '_html').replace('-', '');
                // keys: fig1_html, fig2_html, fig3_html
                const container = document.getElementById(id);
                container.innerHTML = data[id.replace('-content', '_html')];
                activateScripts(container);
            });
        })
        .catch(err => console.error('Fetch error:', err));
    });
});


// ---- Auto-reload on new version ----
const loadedVersion = SERVER_DATA.version;

setInterval(async () => {
    const resp = await fetch('/check_update');
    const data = await resp.json();
    if (data.version > loadedVersion) {
        location.reload();
    }
}, 2000);


// ---- Countdown timer ----
let remaining = SERVER_DATA.countdownSeconds;
let updating  = false;

function updateCountdown() {
    const el = document.getElementById('countdown-value');
    if (updating) {
        el.textContent = 'Updating...';
    } else if (remaining > 0) {
        el.textContent = remaining.toFixed(0) + 's';
        remaining -= 1;
    } else {
        el.textContent = '0s';
    }
}

function refreshCountdown() {
    fetch('/next_update')
        .then(r => r.json())
        .then(data => {
            updating = data.updating;
            if (!updating) {
                remaining = Math.max(0, data.next_update - data.server_time);
            }
        });
}

updateCountdown();
setInterval(updateCountdown, 1000);
setInterval(refreshCountdown, 1000);


// ---- Map type toggle ----
const maptypeHeadings = {
    daily: 'Daily visits',
    total: 'Cumulative visits to date'
};

function updateFig1Heading() {
    document.getElementById('fig1-heading').textContent =
        maptypeHeadings[currentMaptype];
}

function sendMapType(maptype) {
    currentMaptype = maptype;
    updateFig1Heading();

    document.querySelectorAll('.maptype-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.maptype === maptype);
    });

    fetch('/maptype_clicked', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            maptype: currentMaptype,
            index:   currentIndex,
            gn:      currentGn,   
            mn:      currentMn    

        })
    })
    .then(res => res.json())
    .then(data => {
        ['fig1-content', 'fig2-content'].forEach(id => {
            const container = document.getElementById(id);
            container.innerHTML = data[id.replace('-content', '_html')];
            activateScripts(container);
        });
    })
    .catch(error => console.error('Error:', error));
}