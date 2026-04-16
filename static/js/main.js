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
let currentGn      = '1';  
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
            // Before overwriting innerHTML, purge the old figure:
            ['fig1-content', 'fig2-content', 'fig3-content'].forEach(id => {
                const container = document.getElementById(id);
                const existingPlot = container.querySelector('.plotly-graph-div');
                if (existingPlot) {
                    Plotly.purge(existingPlot);  // ← releases Plotly's internal references
                }
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


// ---- Countdown + progress bar ----
let remaining = SERVER_DATA.countdownSeconds;
let updating  = false;
let progress  = 0;
let progressMsg = '';

const T_REFRESH = SERVER_DATA.countdownSeconds;

function updateCountdown() {
    const el    = document.getElementById('countdown-value');
    const fill  = document.getElementById('progress-fill');
    const track = document.querySelector('.progress-track');

    if (updating) {
        track.style.display  = 'block';
        el.textContent       = progressMsg || 'Processing...';
        fill.style.width     = Math.round(progress * 100) + '%';
    } else {
        track.style.display  = 'none';
        if (remaining > 0) {
            el.textContent = 'Next update in ' + Math.ceil(remaining) + 's';
            remaining -= 1;
        } else {
            el.textContent = 'Next update in 0s';
        }
    }
}

function refreshCountdown() {
    fetch('/next_update')
        .then(r => r.json())
        .then(data => {
            updating    = data.updating;
            progress    = data.progress    || 0;
            progressMsg = data.progress_msg || '';
            if (!updating) {
                remaining = Math.max(0, data.next_update - data.server_time);
            }
        });
}

updateCountdown();
setInterval(() => {
    updateCountdown();
    refreshCountdown();
}, 1000);


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

// ---- Table sorting (vanilla JS, no jQuery) ----
document.querySelectorAll('.sortable-table thead th').forEach((header, index) => {
    header.style.cursor = 'pointer';
    header.addEventListener('click', () => {
        const table = header.closest('table');
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        
        // Determine sort direction (ascending or descending)
        const isAscending = header.classList.contains('sort-asc');
        
        // Remove sort classes from all headers
        table.querySelectorAll('thead th').forEach(th => {
            th.classList.remove('sort-asc', 'sort-desc');
        });
        
        // Sort rows
        rows.sort((a, b) => {
            const aCell = a.children[index].textContent.trim();
            const bCell = b.children[index].textContent.trim();
            
            // Try numeric sort first
            const aNum = parseFloat(aCell);
            const bNum = parseFloat(bCell);
            
            if (!isNaN(aNum) && !isNaN(bNum)) {
                return isAscending ? bNum - aNum : aNum - bNum;
            }
            
            // Fall back to alphabetic sort
            return isAscending ? bCell.localeCompare(aCell) : aCell.localeCompare(bCell);
        });
        
        // Re-render rows
        rows.forEach(row => tbody.appendChild(row));
        
        // Add sort indicator to current header
        header.classList.add(isAscending ? 'sort-desc' : 'sort-asc');
    });
});