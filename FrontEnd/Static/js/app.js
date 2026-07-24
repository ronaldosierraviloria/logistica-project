document.addEventListener('DOMContentLoaded', function() {

    // --- Sync config from backend to localStorage ---
    async function syncConfig() {
        try {
            const res = await fetch('/api/configuracion');
            if (!res.ok) return;
            const config = await res.json();
            if (config.tema) localStorage.setItem('theme', config.tema);
            if (config.sidebar_colapsado) localStorage.setItem('sidebar_collapsed', config.sidebar_colapsado);
            if (config.animaciones) localStorage.setItem('animaciones', config.animaciones);
            if (config.filas_tabla) localStorage.setItem('filas_tabla', config.filas_tabla);
            if (config.notif_upload) localStorage.setItem('notif_upload', config.notif_upload);
            if (config.notif_eliminar) localStorage.setItem('notif_eliminar', config.notif_eliminar);
            if (config.notif_registro) localStorage.setItem('notif_registro', config.notif_registro);
        } catch (e) {
            // Silent fail - use defaults
        }
    }
    syncConfig();

    // --- Theme Toggle ---
    const themeToggleBtn = document.getElementById('theme-toggle');
    const themeToggleIcon = document.getElementById('theme-toggle-icon');
    const html = document.documentElement;

    function getPreferredTheme() {
        const stored = localStorage.getItem('theme');
        if (stored) return stored;
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    function applyTheme(theme) {
        if (theme === 'dark') {
            html.classList.add('dark');
            if (themeToggleIcon) themeToggleIcon.setAttribute('data-lucide', 'moon');
        } else {
            html.classList.remove('dark');
            if (themeToggleIcon) themeToggleIcon.setAttribute('data-lucide', 'sun');
        }
        localStorage.setItem('theme', theme);
        if (window.lucide) lucide.createIcons();
    }

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const current = html.classList.contains('dark') ? 'dark' : 'light';
            applyTheme(current === 'dark' ? 'light' : 'dark');
        });
    }
    applyTheme(getPreferredTheme());

    // --- Sidebar Mobile Toggle ---
    const sidebarToggleBtn = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebar-overlay');

    function toggleSidebar() {
        sidebar.classList.toggle('-translate-x-full');
        sidebarOverlay.classList.toggle('hidden');
        document.body.classList.toggle('overflow-hidden', !sidebar.classList.contains('-translate-x-full'));
    }

    if (sidebarToggleBtn) sidebarToggleBtn.addEventListener('click', toggleSidebar);
    if (sidebarOverlay) sidebarOverlay.addEventListener('click', toggleSidebar);

    // --- Sidebar Desktop Collapse ---
    const sidebarCollapseBtn = document.getElementById('sidebar-collapse-btn');

    function toggleSidebarCollapse() {
        const isCollapsed = html.classList.toggle('sidebar-collapsed');
        localStorage.setItem('sidebar_collapsed', isCollapsed);

        const newTitle = isCollapsed ? 'Mostrar sidebar' : 'Ocultar sidebar';
        const newIcon = isCollapsed ? 'panel-left-open' : 'panel-left-close';

        if (sidebarCollapseBtn) {
            const icon = sidebarCollapseBtn.querySelector('i');
            if (icon) icon.setAttribute('data-lucide', newIcon);
            sidebarCollapseBtn.title = newTitle;
            sidebarCollapseBtn.setAttribute('aria-label', newTitle);
            sidebarCollapseBtn.setAttribute('data-tooltip', newTitle);
        }

        setTimeout(() => {
            window.dispatchEvent(new Event('resize'));
        }, 350);

        if (window.lucide) lucide.createIcons();
    }

    function initCollapseBtn() {
        const isCollapsed = html.classList.contains('sidebar-collapsed');
        const titleText = isCollapsed ? 'Mostrar sidebar' : 'Ocultar sidebar';
        const iconName = isCollapsed ? 'panel-left-open' : 'panel-left-close';

        if (sidebarCollapseBtn) {
            const icon = sidebarCollapseBtn.querySelector('i');
            if (icon) icon.setAttribute('data-lucide', iconName);
            sidebarCollapseBtn.title = titleText;
            sidebarCollapseBtn.setAttribute('aria-label', titleText);
            sidebarCollapseBtn.setAttribute('data-tooltip', titleText);
        }

        if (window.lucide) lucide.createIcons();
    }

    initCollapseBtn();

    if (sidebarCollapseBtn) {
        sidebarCollapseBtn.addEventListener('click', toggleSidebarCollapse);
    }

    // --- Profile Dropdown ---
    const profileBtn = document.getElementById('profile-btn');
    const profileDropdown = document.getElementById('profile-dropdown');

    if (profileBtn && profileDropdown) {
        profileBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const wasOpen = !profileDropdown.classList.contains('hidden');
            profileDropdown.classList.toggle('hidden');
            if (!wasOpen && notifPanel && !notifPanel.classList.contains('hidden')) {
                notifPanel.classList.add('closing');
                setTimeout(() => {
                    notifPanel.classList.add('hidden');
                    notifPanel.classList.remove('closing');
                }, 150);
                notifOpen = false;
            }
        });
        document.addEventListener('click', () => {
            if (profileDropdown && !profileDropdown.classList.contains('hidden')) {
                profileDropdown.classList.add('hidden');
            }
        });
    }

    // --- Page Transitions ---
    const mainContent = document.querySelector('main');
    if (mainContent) {
        mainContent.classList.add('page-animate-in');
        document.querySelectorAll('a[href]').forEach(link => {
            link.addEventListener('click', function(e) {
                const href = this.getAttribute('href');
                if (href && href.startsWith('/') && !href.includes('#') && !this.hasAttribute('download') && !this.getAttribute('onclick')) {
                    e.preventDefault();
                    mainContent.classList.remove('page-animate-in');
                    mainContent.classList.add('page-animate-out');
                    setTimeout(() => { window.location.href = href; }, 250);
                }
            });
        });
    }

    // --- Table Search ---
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const val = this.value.toLowerCase();
            document.querySelectorAll('.data-row').forEach(row => {
                const matches = row.innerText.toLowerCase().includes(val);
                row.style.display = matches ? '' : 'none';
            });
        });
    }

    // --- Toast Auto-dismiss ---
    document.querySelectorAll('.toast-item').forEach(toast => {
        setTimeout(() => {
            toast.style.transition = 'opacity 0.3s, transform 0.3s';
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    });

    // --- Progress Bar Animation ---
    document.querySelectorAll('.progress-animate').forEach(bar => {
        const target = bar.getAttribute('data-progress');
        if (target) {
            setTimeout(() => { bar.style.width = target + '%'; }, 100);
        }
    });

    // --- Chart.js default color sync with theme ---
    if (window.Chart) {
        const isDark = html.classList.contains('dark');
        Chart.defaults.color = isDark ? '#94a3b8' : '#64748b';
        Chart.defaults.font.family = "'Inter', sans-serif";
    }

    // --- Notification Panel ---
    const notifBtn = document.getElementById('notification-btn');
    const notifPanel = document.getElementById('notification-panel');
    const notifBadge = document.getElementById('notification-badge');
    const notifCountBadge = document.getElementById('notification-count-badge');
    const notifList = document.getElementById('notification-list');
    const notifEmpty = document.getElementById('notification-empty');
    const notifLoading = document.getElementById('notification-loading');
    const notifMarkAll = document.getElementById('notification-mark-all');
    const notifClear = document.getElementById('notification-clear');

    let notifOpen = false;
    let notifPolling = null;
    let lastNotifCount = 0;

    const NOTIF_ICON_MAP = {
        'upload': 'upload',
        'eliminar': 'trash-2',
        'registro': 'user-plus',
        'acceso': 'log-in',
        'bell': 'bell',
        'info': 'info',
        'alerta': 'alert-triangle',
        'exito': 'check-circle',
        'error': 'x-circle'
    };

    const NOTIF_COLOR_MAP = {
        'upload': 'bg-blue-100 dark:bg-blue-500/20 text-blue-600 dark:text-blue-400',
        'eliminar': 'bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400',
        'registro': 'bg-green-100 dark:bg-green-500/20 text-green-600 dark:text-green-400',
        'acceso': 'bg-amber-100 dark:bg-amber-500/20 text-amber-600 dark:text-amber-400',
        'bell': 'bg-slate-100 dark:bg-slate-600 text-slate-500 dark:text-slate-400',
        'info': 'bg-blue-100 dark:bg-blue-500/20 text-blue-600 dark:text-blue-400',
        'alerta': 'bg-orange-100 dark:bg-orange-500/20 text-orange-600 dark:text-orange-400',
        'exito': 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400',
        'error': 'bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400'
    };

    function timeAgo(dateStr) {
        if (!dateStr) return '';
        const now = new Date();
        const date = new Date(dateStr.replace(' ', 'T'));
        const diff = Math.floor((now - date) / 1000);
        if (diff < 60) return 'Ahora mismo';
        if (diff < 3600) return `Hace ${Math.floor(diff / 60)}m`;
        if (diff < 86400) return `Hace ${Math.floor(diff / 3600)}h`;
        if (diff < 604800) return `Hace ${Math.floor(diff / 86400)}d`;
        return dateStr.split(' ')[0];
    }

    function renderNotifItem(n) {
        const icon = NOTIF_ICON_MAP[n.Icono] || 'bell';
        const colorClass = NOTIF_COLOR_MAP[n.Tipo] || NOTIF_COLOR_MAP['bell'];
        const unread = !n.Leida;
        return `
            <div class="notif-item-enter flex items-start gap-3 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors cursor-pointer ${unread ? 'bg-primary-50/50 dark:bg-primary-500/5' : ''}" 
                 data-notif-id="${n.ID_Notificacion}" onclick="window.NotifPanel.markRead(${n.ID_Notificacion})">
                <div class="flex-shrink-0 mt-0.5">
                    <div class="w-8 h-8 rounded-lg ${colorClass} flex items-center justify-center">
                        <i data-lucide="${icon}" class="w-4 h-4"></i>
                    </div>
                </div>
                <div class="flex-1 min-w-0">
                    <div class="flex items-start justify-between gap-2">
                        <p class="text-sm font-semibold ${unread ? 'text-slate-900 dark:text-white' : 'text-slate-600 dark:text-slate-300'} leading-tight">${n.Titulo}</p>
                        ${unread ? '<span class="flex-shrink-0 w-2 h-2 bg-primary-500 rounded-full notif-unread-pulse mt-1.5"></span>' : ''}
                    </div>
                    <p class="text-xs ${unread ? 'text-slate-600 dark:text-slate-400' : 'text-slate-400 dark:text-slate-500'} mt-0.5 leading-relaxed">${n.Mensaje}</p>
                    <p class="text-[10px] text-slate-300 dark:text-slate-600 mt-1 font-medium">${timeAgo(n.Fecha_Creacion)}</p>
                </div>
            </div>
        `;
    }

    function updateBadge(count) {
        lastNotifCount = count;
        if (count > 0) {
            notifBadge.textContent = count > 99 ? '99+' : count;
            notifBadge.classList.remove('hidden');
            notifBadge.classList.add('flex');
            notifCountBadge.textContent = count;
            notifCountBadge.classList.remove('hidden');
        } else {
            notifBadge.classList.add('hidden');
            notifBadge.classList.remove('flex');
            notifCountBadge.classList.add('hidden');
        }
    }

    async function fetchNotificaciones() {
        try {
            const res = await fetch('/api/notificaciones');
            if (!res.ok) return;
            const data = await res.json();
            const notifs = data.notificaciones;

            notifLoading.classList.add('hidden');

            if (notifs.length === 0) {
                notifEmpty.classList.remove('hidden');
                notifList.querySelectorAll('.notif-item-enter').forEach(el => el.remove());
            } else {
                notifEmpty.classList.add('hidden');
                notifList.querySelectorAll('.notif-item-enter').forEach(el => el.remove());
                notifList.insertAdjacentHTML('beforeend', notifs.map(renderNotifItem).join(''));
                if (window.lucide) lucide.createIcons();
            }

            const prevCount = lastNotifCount;
            updateBadge(data.no_leidas);

            if (data.no_leidas > prevCount && prevCount > 0) {
                const bellIcon = notifBtn.querySelector('i');
                if (bellIcon) {
                    bellIcon.classList.add('bell-shake');
                    setTimeout(() => bellIcon.classList.remove('bell-shake'), 700);
                }
            }
        } catch (e) {
            notifLoading.classList.add('hidden');
        }
    }

    window.NotifPanel = {
        markRead: async function(id) {
            try {
                await fetch(`/api/notificaciones/${id}/leer`, { method: 'POST' });
                const item = notifList.querySelector(`[data-notif-id="${id}"]`);
                if (item) {
                    item.classList.remove('bg-primary-50/50', 'dark:bg-primary-500/5');
                    const dot = item.querySelector('.notif-unread-pulse');
                    if (dot) dot.remove();
                }
                const currentCount = parseInt(notifBadge.textContent) || 0;
                updateBadge(Math.max(0, currentCount - 1));
            } catch (e) { /* silent */ }
        }
    };

    if (notifBtn && notifPanel) {
        notifBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            notifOpen = !notifPanel.classList.contains('hidden');

            if (profileDropdown && !profileDropdown.classList.contains('hidden')) {
                profileDropdown.classList.add('hidden');
            }
            
            if (notifOpen) {
                notifPanel.classList.add('hidden');
                if (notifPolling) { clearInterval(notifPolling); notifPolling = null; }
            } else {
                notifPanel.classList.remove('hidden');
                notifPanel.classList.remove('closing');
                notifList.querySelectorAll('.notif-item-enter').forEach(el => el.remove());
                notifEmpty.classList.add('hidden');
                notifLoading.classList.remove('hidden');
                fetchNotificaciones();
                notifPolling = setInterval(fetchNotificaciones, 15000);
            }
        });

        document.addEventListener('click', (e) => {
            if (!notifPanel.classList.contains('hidden') && !notifPanel.contains(e.target) && e.target !== notifBtn && !notifBtn.contains(e.target)) {
                notifPanel.classList.add('closing');
                setTimeout(() => {
                    notifPanel.classList.add('hidden');
                    notifPanel.classList.remove('closing');
                }, 150);
                if (notifPolling) { clearInterval(notifPolling); notifPolling = null; }
                notifOpen = false;
            }
        });

        notifMarkAll.addEventListener('click', async (e) => {
            e.stopPropagation();
            try {
                await fetch('/api/notificaciones/leer-todas', { method: 'POST' });
                notifList.querySelectorAll('.notif-item-enter').forEach(item => {
                    item.classList.remove('bg-primary-50/50', 'dark:bg-primary-500/5');
                    const dot = item.querySelector('.notif-unread-pulse');
                    if (dot) dot.remove();
                });
                updateBadge(0);
            } catch (e) { /* silent */ }
        });

        notifClear.addEventListener('click', async (e) => {
            e.stopPropagation();
            try {
                await fetch('/api/notificaciones/limpiar', { method: 'POST' });
                fetchNotificaciones();
            } catch (e) { /* silent */ }
        });
    }

    // Initial fetch for badge count
    if (notifBtn) {
        fetch('/api/notificaciones')
            .then(r => r.ok ? r.json() : null)
            .then(data => { if (data) updateBadge(data.no_leidas); })
            .catch(() => {});
    }

});
