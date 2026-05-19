const loginView = document.querySelector('#loginView');
const dashboardView = document.querySelector('#dashboardView');
const loginForm = document.querySelector('#loginForm');
const usernameInput = document.querySelector('#usernameInput');
const passwordInput = document.querySelector('#passwordInput');
const loginButton = document.querySelector('#loginButton');
const loginStatus = document.querySelector('#loginStatus');
const logoutButton = document.querySelector('#logoutButton');
const sessionUser = document.querySelector('#sessionUser');
const statusStrip = document.querySelector('#statusStrip');
const metricsNode = document.querySelector('#metrics');
const exportReport = document.querySelector('#exportReport');
let loansChart;
let statusChart;

const TOKEN_KEY = 'dashboardAccessToken';
const USER_KEY = 'dashboardUser';

loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    await login();
});

logoutButton.addEventListener('click', () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    showLogin();
});

document.querySelectorAll('[data-format]').forEach((button) => {
    button.addEventListener('click', async () => {
        const report = exportReport.value;
        const format = button.dataset.format;
        const token = currentToken();
        if (!token) {
            setStatus('Ingresa un token JWT de bibliotecario para exportar.', 'error');
            return;
        }
        try {
            const response = await fetch(`/api/reports/export/${format}/?report=${report}`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (!response.ok) {
                throw new Error('No se pudo generar la exportacion.');
            }
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `${report}.${format}`;
            link.click();
            URL.revokeObjectURL(url);
            setStatus(`Exportacion ${format.toUpperCase()} generada.`, 'ok');
        } catch (error) {
            setStatus(error.message, 'error');
        }
    });
});

function currentToken() {
    return localStorage.getItem(TOKEN_KEY) || '';
}

async function login() {
    const username = usernameInput.value.trim();
    const password = passwordInput.value;

    if (!username || !password) {
        setLoginStatus('Ingresa usuario y contrasena.');
        return;
    }

    loginButton.disabled = true;
    setLoginStatus('Validando credenciales...', true);

    try {
        const response = await fetch('/api/auth/token/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });

        if (!response.ok) {
            throw new Error('Usuario o contrasena invalidos.');
        }

        const data = await response.json();
        if (data.role !== 'librarian') {
            throw new Error('Esta vista requiere una cuenta bibliotecaria.');
        }

        localStorage.setItem(TOKEN_KEY, data.access);
        localStorage.setItem(USER_KEY, JSON.stringify({
            username: data.username,
            role: data.role,
        }));
        passwordInput.value = '';
        setLoginStatus('Acceso concedido.', true);
        showDashboard();
        await loadDashboard();
    } catch (error) {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
        setLoginStatus(error.message);
    } finally {
        loginButton.disabled = false;
    }
}

function setLoginStatus(message, ok = false) {
    loginStatus.textContent = message;
    loginStatus.className = ok ? 'login-status ok' : 'login-status';
}

function showLogin() {
    dashboardView.hidden = true;
    loginView.hidden = false;
    usernameInput.focus();
}

function showDashboard() {
    const user = storedUser();
    sessionUser.textContent = user?.username ? `Sesion: ${user.username}` : 'Sesion administrativa';
    loginView.hidden = true;
    dashboardView.hidden = false;
}

function storedUser() {
    try {
        return JSON.parse(localStorage.getItem(USER_KEY));
    } catch (error) {
        return null;
    }
}

async function apiGet(path) {
    const token = currentToken();
    const response = await fetch(path, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) {
        if (response.status === 401) {
            localStorage.removeItem(TOKEN_KEY);
            localStorage.removeItem(USER_KEY);
            showLogin();
            throw new Error('La sesion vencio. Inicia sesion nuevamente.');
        }
        throw new Error(response.status === 403 ? 'Acceso restringido a bibliotecarios.' : 'No se pudo cargar la informacion.');
    }
    return response.json();
}

async function loadDashboard() {
    try {
        setStatus('Cargando datos administrativos...', '');
        const [summary, reports] = await Promise.all([
            apiGet('/api/dashboard/'),
            apiGet('/api/reports/'),
        ]);
        renderMetrics(summary);
        renderTables(reports);
        renderCharts(summary, reports);
        setStatus(`Datos actualizados: ${formatDate(summary.generated_at)}`, 'ok');
    } catch (error) {
        setStatus(error.message, 'error');
    }
}

function setStatus(message, state) {
    statusStrip.className = `status-strip ${state}`;
    statusStrip.textContent = message;
}

function renderMetrics(summary) {
    const cards = [
        ['Libros', summary.totals.books],
        ['Usuarios', summary.totals.users],
        ['Prestamos activos', summary.totals.active_loans],
        ['Reservas activas', summary.totals.active_reservations],
        ['Sanciones activas', summary.totals.active_sanctions, 'warning'],
        ['Prestamos vencidos', summary.alerts.overdue_loans, summary.alerts.overdue_loans ? 'danger' : ''],
        ['Copias disponibles', summary.book_inventory.available_copies],
        ['Libros no disponibles', summary.book_inventory.unavailable_books, 'warning'],
    ];

    metricsNode.innerHTML = cards.map(([label, value, tone = '']) => `
        <article class="metric ${tone}">
            <span>${label}</span>
            <strong>${value}</strong>
        </article>
    `).join('');
}

function renderTables(reports) {
    fillTable('#reservedBooks', reports.most_reserved_books, ['title', 'isbn', 'reservations_count']);
    fillTable('#readAuthors', reports.most_read_authors, ['name', 'loans_count']);
    fillTable('#topUsers', reports.top_users_by_loans, ['username', 'email', 'loans_count']);
}

function fillTable(selector, rows, fields) {
    const tbody = document.querySelector(selector);
    if (!rows.length) {
        tbody.innerHTML = `<tr><td class="empty" colspan="${fields.length}">Sin datos para mostrar</td></tr>`;
        return;
    }
    tbody.innerHTML = rows.map((row) => `
        <tr>${fields.map((field) => `<td>${escapeHtml(row[field] ?? '')}</td>`).join('')}</tr>
    `).join('');
}

function renderCharts(summary, reports) {
    const loansData = reports.loans_by_month;
    loansChart?.destroy();
    loansChart = new Chart(document.querySelector('#loansChart'), {
        type: 'bar',
        data: {
            labels: loansData.map((row) => row.month),
            datasets: [{
                label: 'Prestamos',
                data: loansData.map((row) => row.total),
                backgroundColor: '#176b68',
            }],
        },
        options: chartOptions(),
    });

    const statuses = summary.loan_statuses;
    statusChart?.destroy();
    statusChart = new Chart(document.querySelector('#statusChart'), {
        type: 'doughnut',
        data: {
            labels: statuses.map((row) => row.status),
            datasets: [{
                data: statuses.map((row) => row.total),
                backgroundColor: ['#176b68', '#2563eb', '#b7791f', '#b42318'],
            }],
        },
        options: chartOptions(),
    });
}

function chartOptions() {
    return {
        responsive: true,
        plugins: {
            legend: { position: 'bottom' },
        },
        scales: {
            y: {
                beginAtZero: true,
                ticks: { precision: 0 },
            },
        },
    };
}

function formatDate(value) {
    return new Intl.DateTimeFormat('es-CO', {
        dateStyle: 'medium',
        timeStyle: 'short',
    }).format(new Date(value));
}

function escapeHtml(value) {
    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

if (currentToken()) {
    showDashboard();
    loadDashboard();
} else {
    showLogin();
}
