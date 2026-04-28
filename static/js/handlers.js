/**
 * handlers.js – All event listener setup and user interaction handling
 * 
 * This module handles:
 * - Table row selection and data updates
 * - Table header sorting
 * - Map type toggle buttons (daily vs. cumulative)
 * - Observability plot click interactions
 */



/**
 * Initialize all event listeners for table rows.
 * 
 * When a row is clicked:
 * - Updates selected row styling
 * - Sends row metadata to server
 * - Updates all three plots with new data
 * - Reattaches plot click handlers
 */
function initTableRowClickHandlers() {
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
                // Before overwriting innerHTML, purge the old figures
                // to prevent memory leaks from Plotly.js
                ['fig1-content', 'fig2-content', 'fig3-content'].forEach(id => {
                    const container = document.getElementById(id);
                    const existingPlot = container.querySelector('.plotly-graph-div');
                    if (existingPlot) {
                        Plotly.purge(existingPlot);  // releases Plotly's internal references
                    }
                    container.innerHTML = data[id.replace('-content', '_html')];
                    activateScripts(container);
                });
                
                // Reattach observability plot click handler to new plot
                setTimeout(() => attachObsPlotClickHandler(), 100);
            })
            .catch(err => console.error('Fetch error:', err));
        });
    });
}


/**
 * Initialize table header sorting.
 * 
 * Features:
 * - Click header to sort by that column
 * - Toggles between ascending/descending
 * - Attempts numeric sort first, falls back to alphabetic
 * - Visual indicator on sorted header
 */
function initTableSortingHandlers() {
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
            
            // Re-render rows in new order
            rows.forEach(row => tbody.appendChild(row));
            
            // Add sort indicator to current header
            header.classList.add(isAscending ? 'sort-desc' : 'sort-asc');
        });
    });
}


/**
 * Handle map type toggle button clicks (Daily vs. Cumulative).
 * 
 * Updates:
 * - currentMaptype state
 * - Figure 1 heading
 * - Button active state
 * - Fetches new data from server and updates figures 1 and 2
 */
function sendMapType(maptype) {
    currentMaptype = maptype;
    updateFig1Heading();

    // Update button active states
    document.querySelectorAll('.maptype-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.maptype === maptype);
    });

    // Fetch updated figures from server
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
        // Update figures 1 and 2 (figure 3 doesn't change with maptype)
        ['fig1-content', 'fig2-content'].forEach(id => {
            const container = document.getElementById(id);
            container.innerHTML = data[id.replace('-content', '_html')];
            activateScripts(container);
        });
    })
    .catch(error => console.error('Error updating map type:', error));
}


/**
 * Attach click handler to observability plot (figure 3).
 * 
 * Only responds to clicks on the top panel (hours observable by date).
 * When clicked, fetches a 5-day observation window starting on that date
 * and updates the bottom panel.
 */
function attachObsPlotClickHandler() {
    const fig3Container = document.getElementById('fig3-content');
    const plotDiv = fig3Container?.querySelector('.plotly-graph-div');
    
    if (!plotDiv) {
        return;
    }
    
    plotDiv.on('plotly_click', (eventData) => {
        // Extract the clicked point's x-value (date)
        const point = eventData.points[0];
        if (!point) {
            return;
        }
        
        // Only respond to clicks on the top panel (row 1, col 1)
        // For a 2-row, 1-col subplot: 
        // row 1 = xaxis, yaxis  and 
        // row 2 = xaxis2,yaxis2
        const xaxisName = point.xaxis._name;
        const yaxisName = point.yaxis._name;
        
        if (xaxisName !== 'xaxis' || yaxisName !== 'yaxis') {
            return;
        }
        
        const selectedDate = point.x;  // ISO date string from Plotly
        
        // Send update request to server
        fetch('/obs_plot_update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                gn: currentGn,
                mn: currentMn,
                selected_date: selectedDate,
                window_days: 5
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'ok') {
                const container = document.getElementById('fig3-content');
                const existingPlot = container.querySelector('.plotly-graph-div');
                if (existingPlot) {
                    Plotly.purge(existingPlot);
                }
                container.innerHTML = data.fig3_html;
                activateScripts(container);
                
                // Reattach click handler to new plot
                setTimeout(() => attachObsPlotClickHandler(), 100);
            }
        })
        .catch(error => console.error('Error updating observability plot:', error));
    });
}


/**
 * Initialize all event handlers when Document Object Model (DOM) is ready.
 */
document.addEventListener('DOMContentLoaded', () => {
    initTableRowClickHandlers();
    initTableSortingHandlers();
    attachObsPlotClickHandler();
});
