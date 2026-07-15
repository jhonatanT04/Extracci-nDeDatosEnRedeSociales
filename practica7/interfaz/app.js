// Estado global de la aplicación
const state = {
    dataset: null,
    records: [],
    filteredRecords: [],
    activeSentimentFilter: 'ALL',
    activeSourceFilter: 'ALL',
    activeSearch: '',
    activeSort: 'relevance',
    currentView: 'cards' // 'cards' o 'table'
};

// Colores e iconos de sentimientos
const SENTIMENT_META = {
    positivo: { icon: '😄', label: 'Positivo', class: 'sent-positivo' },
    negativo: { icon: '😡', label: 'Negativo', class: 'sent-negativo' },
    neutral:  { icon: '😐', label: 'Neutral',  class: 'sent-neutral' },
    mixto:    { icon: '⚖️', label: 'Mixto',    class: 'sent-mixto' },
    no_clasificable: { icon: '❓', label: 'No Clasificable', class: 'sent-no_clasificable' }
};

// Referencias del DOM
const dom = {
    fileInput: document.getElementById('fileInput'),
    dropOverlay: document.getElementById('dropOverlay'),
    serverSelectorContainer: document.getElementById('serverSelectorContainer'),
    datasetSelect: document.getElementById('datasetSelect'),
    
    metaDate: document.getElementById('metaDate'),
    metaProblematica: document.getElementById('metaProblematica'),
    totalRecords: document.getElementById('totalRecords'),
    totalSources: document.getElementById('totalSources'),
    modelUsed: document.getElementById('modelUsed'),
    
    sourcesGrid: document.getElementById('sourcesGrid'),
    recordsContainer: document.getElementById('recordsContainer'),
    tableContainer: document.getElementById('tableContainer'),
    tableBody: document.getElementById('tableBody'),
    
    searchInput: document.getElementById('searchInput'),
    sourceFilter: document.getElementById('sourceFilter'),
    sentimentFilter: document.getElementById('sentimentFilter'),
    sortFilter: document.getElementById('sortFilter'),
    
    viewCardsBtn: document.getElementById('viewCardsBtn'),
    viewTableBtn: document.getElementById('viewTableBtn'),
    
    displayedCount: document.getElementById('displayedCount'),
    totalCount: document.getElementById('totalCount'),
    clearFiltersBtn: document.getElementById('clearFiltersBtn')
};

// Inicialización en carga
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    setupDragAndDrop();
    tryLoadFromServer();
});

// Event Listeners generales
function setupEventListeners() {
    dom.fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            readJsonFile(e.target.files[0]);
        }
    });

    dom.searchInput.addEventListener('input', (e) => {
        state.activeSearch = e.target.value.toLowerCase().trim();
        applyFilters();
    });

    dom.sourceFilter.addEventListener('change', (e) => {
        state.activeSourceFilter = e.target.value;
        applyFilters();
    });

    dom.sentimentFilter.addEventListener('change', (e) => {
        state.activeSentimentFilter = e.target.value;
        updateKpiActiveStates();
        applyFilters();
    });

    dom.sortFilter.addEventListener('change', (e) => {
        state.activeSort = e.target.value;
        applyFilters();
    });

    // Clic en tarjetas KPI para filtrar rápido
    document.querySelectorAll('.kpi-card').forEach(card => {
        card.addEventListener('click', () => {
            const filter = card.getAttribute('data-filter');
            if (state.activeSentimentFilter === filter) {
                state.activeSentimentFilter = 'ALL';
                dom.sentimentFilter.value = 'ALL';
            } else {
                state.activeSentimentFilter = filter;
                dom.sentimentFilter.value = filter;
            }
            updateKpiActiveStates();
            applyFilters();
        });
    });

    // Toggles de vista
    dom.viewCardsBtn.addEventListener('click', () => {
        state.currentView = 'cards';
        dom.viewCardsBtn.classList.add('active');
        dom.viewTableBtn.classList.remove('active');
        dom.recordsContainer.style.display = 'grid';
        dom.tableContainer.style.display = 'none';
    });

    dom.viewTableBtn.addEventListener('click', () => {
        state.currentView = 'table';
        dom.viewTableBtn.classList.add('active');
        dom.viewCardsBtn.classList.remove('active');
        dom.recordsContainer.style.display = 'none';
        dom.tableContainer.style.display = 'block';
    });

    dom.clearFiltersBtn.addEventListener('click', () => {
        state.activeSearch = '';
        state.activeSentimentFilter = 'ALL';
        state.activeSourceFilter = 'ALL';
        dom.searchInput.value = '';
        dom.sentimentFilter.value = 'ALL';
        dom.sourceFilter.value = 'ALL';
        updateKpiActiveStates();
        applyFilters();
    });

    dom.datasetSelect.addEventListener('change', (e) => {
        if (e.target.value) {
            fetchDatasetFromServer(e.target.value);
        }
    });
}

// Drag & Drop en toda la ventana
function setupDragAndDrop() {
    let dragCounter = 0;

    window.addEventListener('dragenter', (e) => {
        e.preventDefault();
        dragCounter++;
        dom.dropOverlay.classList.add('active');
    });

    window.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dragCounter--;
        if (dragCounter === 0) {
            dom.dropOverlay.classList.remove('active');
        }
    });

    window.addEventListener('dragover', (e) => {
        e.preventDefault();
    });

    window.addEventListener('drop', (e) => {
        e.preventDefault();
        dragCounter = 0;
        dom.dropOverlay.classList.remove('active');
        if (e.dataTransfer.files.length > 0) {
            readJsonFile(e.dataTransfer.files[0]);
        }
    });
}

// Cargar desde archivo local (FileReader)
function readJsonFile(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
        try {
            const data = JSON.parse(e.target.result);
            loadDataset(data, file.name);
        } catch (err) {
            alert('Error al leer el archivo JSON: ' + err.message);
        }
    };
    reader.readAsText(file);
}

// Conectar con servidor local Python si está activo
async function tryLoadFromServer() {
    try {
        const res = await fetch('/api/datasets');
        if (res.ok) {
            const data = await res.json();
            if (data.datasets && data.datasets.length > 0) {
                dom.serverSelectorContainer.style.display = 'block';
                dom.datasetSelect.innerHTML = data.datasets.map(d => 
                    `<option value="${d.nombre}" ${d.nombre === data.latest ? 'selected' : ''}>${d.nombre} (${d.fecha})</option>`
                ).join('');
                
                fetchDatasetFromServer(data.latest);
                return;
            }
        }
    } catch (e) {
        // No está corriendo con servidor python, se espera carga manual via archivo local
        console.log('Modo estático detectado. Usa "Cargar JSON local" para abrir un archivo.');
    }
}

async function fetchDatasetFromServer(filename) {
    try {
        const res = await fetch(`/api/dataset?file=${encodeURIComponent(filename)}`);
        if (res.ok) {
            const data = await res.json();
            loadDataset(data, filename);
        }
    } catch (e) {
        console.error('Error al cargar dataset del servidor:', e);
    }
}

// Cargar dataset en estado y actualizar UI
function loadDataset(data, sourceName = '') {
    state.dataset = data;
    state.records = data.registros || [];
    
    // Si no está el campo modelo a nivel raíz, intentamos sacar el de los registros
    let modelo = data.modelo || '--';
    if (modelo === '--' && state.records.length > 0) {
        modelo = state.records[0].modelo || 'GPT/Llama';
    }
    
    dom.metaDate.textContent = `Archivo: ${sourceName} (${data.generado_en ? new Date(data.generado_en).toLocaleString() : 'Fecha no especificada'})`;
    dom.metaProblematica.textContent = data.problematica || 'Análisis de Sentimientos sobre Redes Sociales (Práctica 07)';
    dom.totalRecords.textContent = state.records.length.toLocaleString();
    dom.modelUsed.textContent = modelo.toUpperCase();
    
    // Obtener fuentes únicas y poblar select
    const sources = [...new Set(state.records.map(r => r.fuente).filter(Boolean))].sort();
    dom.totalSources.textContent = sources.length;
    
    dom.sourceFilter.innerHTML = '<option value="ALL">Todas las redes</option>' + 
        sources.map(s => `<option value="${s}">${s}</option>`).join('');

    renderKpis();
    renderSourcesBreakdown(sources);
    applyFilters();
}

// Actualizar visual de KPIs
function renderKpis() {
    const total = state.records.length || 1;
    const counts = { positivo: 0, negativo: 0, neutral: 0, mixto: 0, no_clasificable: 0 };
    
    state.records.forEach(r => {
        const sent = r.sentimiento || 'no_clasificable';
        if (counts[sent] !== undefined) counts[sent]++;
        else counts.no_clasificable++;
    });

    for (const [sent, count] of Object.entries(counts)) {
        const pct = Math.round((count / total) * 100);
        const elCount = document.getElementById(`count${capitalize(sent)}`);
        const elPct = document.getElementById(`pct${capitalize(sent)}`);
        if (elCount) elCount.textContent = count.toLocaleString();
        if (elPct) elPct.textContent = `${pct}%`;
    }
}

function updateKpiActiveStates() {
    document.querySelectorAll('.kpi-card').forEach(card => {
        if (card.getAttribute('data-filter') === state.activeSentimentFilter) {
            card.classList.add('active-filter');
        } else {
            card.classList.remove('active-filter');
        }
    });
}

// Barras por red social
function renderSourcesBreakdown(sources) {
    if (!sources || sources.length === 0) {
        dom.sourcesGrid.innerHTML = '<p class="text-secondary">No se detectaron fuentes en este dataset.</p>';
        return;
    }

    const sourceCounts = {};
    const sourceSentiments = {};

    sources.forEach(s => {
        sourceCounts[s] = 0;
        sourceSentiments[s] = { positivo: 0, negativo: 0, neutral: 0, mixto: 0, no_clasificable: 0 };
    });

    state.records.forEach(r => {
        const s = r.fuente;
        const sent = r.sentimiento || 'no_clasificable';
        if (sourceCounts[s] !== undefined) {
            sourceCounts[s]++;
            if (sourceSentiments[s][sent] !== undefined) sourceSentiments[s][sent]++;
            else sourceSentiments[s].no_clasificable++;
        }
    });

    dom.sourcesGrid.innerHTML = sources.map(s => {
        const totalSource = sourceCounts[s] || 1;
        const sents = sourceSentiments[s];
        
        const segmentsHtml = Object.entries(sents).map(([sent, count]) => {
            if (count === 0) return '';
            const pct = (count / totalSource) * 100;
            const color = getComputedStyle(document.documentElement).getPropertyValue(`--${getSentPrefix(sent)}-text`).trim() || '#ccc';
            return `<div class="bar-segment" style="width: ${pct}%; background-color: ${color};" title="${SENTIMENT_META[sent].label}: ${count} (${Math.round(pct)}%)"></div>`;
        }).join('');

        return `
            <div class="source-item">
                <div class="source-header">
                    <span class="source-name">${getSourceIcon(s)} ${s}</span>
                    <span class="source-count">${totalSource} opiniones</span>
                </div>
                <div class="source-bar-wrapper">
                    ${segmentsHtml}
                </div>
            </div>
        `;
    }).join('');
}

// Aplicar filtros, búsqueda y orden
function applyFilters() {
    state.filteredRecords = state.records.filter(r => {
        // Filtro por red social
        if (state.activeSourceFilter !== 'ALL' && r.fuente !== state.activeSourceFilter) {
            return false;
        }
        // Filtro por sentimiento
        if (state.activeSentimentFilter !== 'ALL' && r.sentimiento !== state.activeSentimentFilter) {
            return false;
        }
        // Búsqueda textual
        if (state.activeSearch) {
            const matchTexto = (r.texto || '').toLowerCase().includes(state.activeSearch);
            const matchJust = (r.justificacion || '').toLowerCase().includes(state.activeSearch);
            const matchAutor = (r.autor || '').toLowerCase().includes(state.activeSearch);
            if (!matchTexto && !matchJust && !matchAutor) return false;
        }
        return true;
    });

    // Ordenar
    if (state.activeSort === 'likes') {
        state.filteredRecords.sort((a, b) => {
            const likesA = (a.metricas && a.metricas.likes) ? Number(a.metricas.likes) : 0;
            const likesB = (b.metricas && b.metricas.likes) ? Number(b.metricas.likes) : 0;
            return likesB - likesA;
        });
    } else if (state.activeSort === 'source') {
        state.filteredRecords.sort((a, b) => (a.fuente || '').localeCompare(b.fuente || ''));
    }

    renderRecords();
}

// Renderizado final de tarjetas o tabla
function renderRecords() {
    const total = state.records.length;
    const displayed = state.filteredRecords.length;
    
    dom.displayedCount.textContent = displayed.toLocaleString();
    dom.totalCount.textContent = total.toLocaleString();
    
    // Mostrar botón de limpiar si hay filtros activos
    const hasFilters = state.activeSearch || state.activeSentimentFilter !== 'ALL' || state.activeSourceFilter !== 'ALL';
    dom.clearFiltersBtn.style.display = hasFilters ? 'inline-block' : 'none';

    if (displayed === 0) {
        dom.recordsContainer.innerHTML = `
            <div style="grid-column: 1 / -1; text-align: center; padding: 4rem 1rem;" class="glass-card">
                <p style="font-size: 1.2rem; color: var(--text-secondary);">No se encontraron opiniones que coincidan con los filtros seleccionados.</p>
            </div>
        `;
        dom.tableBody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 3rem;">No se encontraron registros coincidentes.</td></tr>`;
        return;
    }

    // Renderizar Tarjetas
    if (state.currentView === 'cards') {
        dom.recordsContainer.innerHTML = state.filteredRecords.map(r => {
            const sentMeta = SENTIMENT_META[r.sentimiento] || SENTIMENT_META.no_clasificable;
            const metricsHtml = formatMetrics(r.metricas);

            return `
                <article class="record-card">
                    <div>
                        <div class="record-header">
                            <span class="source-badge">${getSourceIcon(r.fuente)} ${r.fuente || 'Desconocido'}</span>
                            <span class="sentiment-badge ${sentMeta.class}">${sentMeta.icon} ${sentMeta.label}</span>
                        </div>
                        <div class="record-body" style="margin-top: 1rem;">
                            <div class="record-text">${escapeHtml(r.texto || '(Sin contenido textual)')}</div>
                            ${r.justificacion ? `
                                <div class="record-justification">
                                    <strong>¿Por qué clasificó así el LLM?</strong>
                                    ${escapeHtml(r.justificacion)}
                                </div>
                            ` : ''}
                        </div>
                    </div>
                    <div class="record-footer">
                        <span title="Autor">${escapeHtml(r.autor || 'Anónimo')}</span>
                        <div class="metrics-pills">
                            ${metricsHtml}
                        </div>
                    </div>
                </article>
            `;
        }).join('');
    }

    // Renderizar Tabla
    dom.tableBody.innerHTML = state.filteredRecords.map(r => {
        const sentMeta = SENTIMENT_META[r.sentimiento] || SENTIMENT_META.no_clasificable;
        return `
            <tr>
                <td><strong>${r.fuente || '--'}</strong></td>
                <td><span class="sentiment-badge ${sentMeta.class}">${sentMeta.icon} ${sentMeta.label}</span></td>
                <td style="max-width: 400px;">${escapeHtml(r.texto || '')}</td>
                <td style="max-width: 350px; font-size: 0.85rem; color: var(--text-secondary);">${escapeHtml(r.justificacion || '--')}</td>
                <td><div class="metrics-pills" style="flex-direction: column; gap: 0.2rem;">${formatMetrics(r.metricas)}</div></td>
            </tr>
        `;
    }).join('');
}

// Utilidades de apoyo
function formatMetrics(metricas = {}) {
    let pills = [];
    if (metricas.likes) pills.push(`<span class="metric-pill">❤️ ${metricas.likes}</span>`);
    if (metricas.comentarios) pills.push(`<span class="metric-pill">💬 ${metricas.comentarios}</span>`);
    if (metricas.vistas) pills.push(`<span class="metric-pill">👁️ ${metricas.vistas}</span>`);
    if (metricas.compartidos) pills.push(`<span class="metric-pill">🔄 ${metricas.compartidos}</span>`);
    return pills.length > 0 ? pills.join('') : '<span>--</span>';
}

function getSourceIcon(fuente = '') {
    const f = fuente.toLowerCase();
    if (f.includes('facebook')) return '📘';
    if (f.includes('tiktok')) return '🎵';
    if (f.includes('youtube')) return '▶️';
    if (f.includes('twitter') || f.includes('x-twitter')) return '🐦';
    return '🌐';
}

function getSentPrefix(sent) {
    if (sent === 'positivo') return 'pos';
    if (sent === 'negativo') return 'neg';
    if (sent === 'neutral') return 'neu';
    if (sent === 'mixto') return 'mix';
    return 'na';
}

function capitalize(str) {
    if (str === 'no_clasificable') return 'NoClasificable';
    return str.charAt(0).toUpperCase() + str.slice(1);
}

function escapeHtml(text) {
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}
