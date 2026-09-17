/**
 * Main Single Page Application Controller
 * Real-time SSE synchronization, tab management, modals, and API actions.
 */

const AppState = {
    currentView: 'dashboard',
    currentSemesterTab: 'all', // 'all', 'BCA 1st', 'BCA 3rd'
    admin: null, // {id, name, email, role}
    sessionToken: localStorage.getItem('event_admin_token') || null,
    eventSource: null,
    config: {}
};

// Toast notification helper
window.showToast = function(message, type = 'info') {
    const toast = document.createElement('div');
    const colors = {
        success: 'bg-emerald-600 text-white',
        error: 'bg-rose-600 text-white',
        warning: 'bg-amber-600 text-white',
        info: 'bg-blue-600 text-white'
    };
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-times-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };

    toast.className = `fixed bottom-5 right-5 z-50 px-4 py-3 rounded-xl shadow-xl flex items-center space-x-3 text-sm font-semibold transition-all transform duration-300 translate-y-2 opacity-0 ${colors[type] || colors.info}`;
    toast.innerHTML = `<i class="fas ${icons[type] || icons.info}"></i> <span>${message}</span>`;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.classList.remove('translate-y-2', 'opacity-0');
    }, 10);

    setTimeout(() => {
        toast.classList.add('translate-y-2', 'opacity-0');
        setTimeout(() => toast.remove(), 300);
    }, 3500);
};

// View Switcher
window.switchView = function(viewName) {
    AppState.currentView = viewName;

    // Toggle view containers
    document.querySelectorAll('.app-view').forEach(el => el.classList.add('hidden'));
    const target = document.getElementById(`view-${viewName}`);
    if (target) target.classList.remove('hidden');

    // Update nav tab highlights
    document.querySelectorAll('.nav-tab-btn').forEach(btn => {
        if (btn.dataset.view === viewName) {
            btn.classList.add('bg-blue-600', 'text-white', 'shadow-sm');
            btn.classList.remove('text-slate-600', 'hover:bg-slate-100');
        } else {
            btn.classList.remove('bg-blue-600', 'text-white', 'shadow-sm');
            btn.classList.add('text-slate-600', 'hover:bg-slate-100');
        }
    });

    // Camera control when switching to/from scanner view
    if (viewName === 'scanner') {
        if (window.ScannerController) {
            window.ScannerController.startCamera();
        }
    } else {
        if (window.ScannerController) {
            window.ScannerController.stopCamera();
        }
    }

    // Refresh view specific data
    if (viewName === 'dashboard') loadDashboardStats();
    if (viewName === 'students') loadStudents();
    if (viewName === 'admins') loadAdmins();
    if (viewName === 'audit') loadAuditLogs();
    if (viewName === 'settings') loadSettings();
};

// ==================== Real-time Server-Sent Events ====================

function initRealtimeSync() {
    if (AppState.eventSource) {
        AppState.eventSource.close();
    }

    const es = new EventSource('/api/events');
    AppState.eventSource = es;

    const statusBadge = document.getElementById('cloud-sync-status');

    es.onopen = () => {
        if (statusBadge) {
            statusBadge.innerHTML = '<span class="w-2 h-2 rounded-full bg-emerald-400 live-pulse mr-1.5 inline-block"></span><span class="text-xs font-semibold text-emerald-700">Cloud Sync Active</span>';
            statusBadge.className = 'px-3 py-1 bg-emerald-50 border border-emerald-200 rounded-full flex items-center shadow-xs';
        }
    };

    es.onerror = () => {
        if (statusBadge) {
            statusBadge.innerHTML = '<span class="w-2 h-2 rounded-full bg-amber-400 mr-1.5 inline-block"></span><span class="text-xs font-semibold text-amber-700">Reconnecting...</span>';
            statusBadge.className = 'px-3 py-1 bg-amber-50 border border-amber-200 rounded-full flex items-center shadow-xs';
        }
    };

    es.onmessage = (e) => {
        try {
            const msg = JSON.parse(e.data);
            handleRealtimeEvent(msg.event, msg.data);
        } catch (err) {}
    };
}

function handleRealtimeEvent(eventName, data) {
    console.log('[Realtime Event]', eventName, data);

    if (eventName === 'checkin_event') {
        // Instant check-in across all 4-5 scanners & dashboard
        loadDashboardStats();
        if (AppState.currentView === 'students') loadStudents(false);
        if (AppState.currentView === 'audit') loadAuditLogs();

        // Refresh offline roster cache
        if (window.OfflineSyncManager) window.OfflineSyncManager.downloadRoster();
    } else if (eventName === 'duplicate_alert') {
        window.showToast(`ALERT: Duplicate Scan Attempt for ${data.student_name} (${data.roll_no})`, 'error');
        if (AppState.currentView === 'audit') loadAuditLogs();
    } else if (eventName === 'admin_approved' || eventName === 'admin_registered') {
        if (AppState.currentView === 'admins') loadAdmins();
    } else if (eventName === 'student_added' || eventName === 'sheet_imported' || eventName === 'student_updated' || eventName === 'student_deleted') {
        loadDashboardStats();
        if (AppState.currentView === 'students') loadStudents(false);
        if (window.OfflineSyncManager) window.OfflineSyncManager.downloadRoster();
    }
}

// ==================== Dashboard Metrics ====================

async function loadDashboardStats() {
    try {
        const res = await fetch('/api/stats');
        const json = await res.json();
        if (!json.success) return;
        const s = json.stats;

        // Top counter cards
        document.getElementById('stat-total-invited').innerText = s.total_invited;
        document.getElementById('stat-total-checkedin').innerText = s.total_checked_in;
        document.getElementById('stat-total-pending').innerText = s.total_pending;
        document.getElementById('stat-turnout-rate').innerText = s.turnout_rate + '%';

        // BCA 1st Sem
        document.getElementById('bca1-checkedin').innerText = s.bca1.checked_in;
        document.getElementById('bca1-total').innerText = s.bca1.invited;
        document.getElementById('bca1-progress-bar').style.width = `${s.bca1.rate}%`;
        document.getElementById('bca1-rate-badge').innerText = `${s.bca1.rate}%`;

        // BCA 3rd Sem
        document.getElementById('bca3-checkedin').innerText = s.bca3.checked_in;
        document.getElementById('bca3-total').innerText = s.bca3.invited;
        document.getElementById('bca3-progress-bar').style.width = `${s.bca3.rate}%`;
        document.getElementById('bca3-rate-badge').innerText = `${s.bca3.rate}%`;

        // Recent check-in feed
        const feed = document.getElementById('recent-checkins-feed');
        if (feed) {
            if (s.recent_checkins.length === 0) {
                feed.innerHTML = '<div class="text-xs text-slate-400 py-6 text-center">No check-ins yet. Live activity will appear here as passes are scanned.</div>';
            } else {
                feed.innerHTML = s.recent_checkins.map(item => `
                    <div class="flex items-center justify-between p-3 rounded-lg bg-slate-50 border border-slate-100 hover:bg-slate-100/80 transition">
                        <div class="flex items-center space-x-3">
                            <div class="w-8 h-8 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold text-xs">
                                <i class="fas fa-check"></i>
                            </div>
                            <div>
                                <strong class="text-sm text-slate-900 block leading-tight">${item.name}</strong>
                                <span class="text-xs text-slate-500 font-mono">${item.roll_no} &bull; ${item.semester}</span>
                            </div>
                        </div>
                        <div class="text-right">
                            <span class="text-xs font-semibold text-slate-700 block">${item.checked_in_at ? item.checked_in_at.substring(11, 19) : ''}</span>
                            <span class="text-2xs text-slate-400">By ${item.scanned_by_admin_name || 'Admin'} (${item.scan_method === 'QR_CAMERA' ? 'QR' : 'Manual'})</span>
                        </div>
                    </div>
                `).join('');
            }
        }
    } catch (e) {
        console.warn('Error loading stats:', e);
    }
}

// ==================== Students & Sheets ====================

window.filterSemester = function(sem) {
    AppState.currentSemesterTab = sem;
    document.querySelectorAll('.sem-tab-btn').forEach(b => {
        if (b.dataset.sem === sem) {
            b.classList.add('bg-blue-600', 'text-white', 'shadow-xs');
            b.classList.remove('bg-white', 'text-slate-600');
        } else {
            b.classList.remove('bg-blue-600', 'text-white', 'shadow-xs');
            b.classList.add('bg-white', 'text-slate-600');
        }
    });
    loadStudents();
};

async function loadStudents(showLoading = true) {
    const tbody = document.getElementById('students-table-body');
    if (!tbody) return;

    if (showLoading) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center py-8 text-xs text-slate-400"><i class="fas fa-spinner fa-spin mr-1"></i> Loading students...</td></tr>';
    }

    const sem = AppState.currentSemesterTab;
    const status = document.getElementById('student-status-filter')?.value || 'all';
    const search = document.getElementById('student-search-input')?.value || '';

    try {
        const url = `/api/students?semester=${encodeURIComponent(sem)}&status=${encodeURIComponent(status)}&search=${encodeURIComponent(search)}`;
        const res = await fetch(url);
        const json = await res.json();
        if (!json.success) return;

        const students = json.students;
        document.getElementById('students-count-badge').innerText = `${students.length} Students`;

        if (students.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center py-10 text-xs text-slate-400">No student records found matching filter.</td></tr>';
            return;
        }

        tbody.innerHTML = students.map((s, idx) => {
            const isChecked = s.status === 'checked_in';
            const statusBadge = isChecked
                ? `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-2xs font-bold bg-emerald-100 text-emerald-800">
                    <i class="fas fa-check-circle mr-1"></i> Checked In
                   </span>`
                : `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-2xs font-bold bg-amber-100 text-amber-800">
                    <i class="fas fa-clock mr-1"></i> Pending
                   </span>`;

            const checkinDetails = isChecked
                ? `<div class="text-2xs text-slate-500">${s.checked_in_at ? s.checked_in_at.substring(11, 16) : ''} &bull; ${s.scanned_by_admin_name || 'Admin'}</div>`
                : `<div class="text-2xs text-slate-400">Not verified yet</div>`;

            return `
                <tr class="hover:bg-slate-50/80 border-b border-slate-100 transition">
                    <td class="px-4 py-3 text-xs font-mono font-bold text-blue-600">${s.roll_no}</td>
                    <td class="px-4 py-3">
                        <strong class="text-xs font-bold text-slate-900 block">${s.name}</strong>
                        <span class="text-2xs text-slate-500">${s.email}</span>
                    </td>
                    <td class="px-4 py-3">
                        <span class="px-2 py-0.5 rounded text-2xs font-bold ${s.semester.includes('1st') ? 'bg-indigo-50 text-indigo-700' : 'bg-purple-50 text-purple-700'}">
                            ${s.semester}
                        </span>
                    </td>
                    <td class="px-4 py-3 font-mono text-2xs text-slate-600">${s.phone}</td>
                    <td class="px-4 py-3">${statusBadge}${checkinDetails}</td>
                    <td class="px-4 py-3">
                        <span class="font-mono text-3xs bg-slate-100 px-1.5 py-0.5 rounded text-slate-600" title="${s.pass_token}">${s.pass_token.substring(0, 14)}...</span>
                    </td>
                    <td class="px-4 py-3 text-right space-x-1">
                        <button onclick="viewPassModal('${s.pass_token}')" class="p-1.5 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded transition" title="View Pass Card & QR">
                            <i class="fas fa-qrcode"></i>
                        </button>
                        <button onclick="sendSingleEmail(${s.id})" class="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 rounded transition" title="Send Invitation Email">
                            <i class="fas fa-envelope"></i>
                        </button>
                        <button onclick="openWhatsAppUrl(${s.id})" class="p-1.5 text-slate-500 hover:text-emerald-600 hover:bg-emerald-50 rounded transition" title="Send via WhatsApp">
                            <i class="fab fa-whatsapp"></i>
                        </button>
                        <button onclick="resendLostPass(${s.id})" class="p-1.5 text-slate-500 hover:text-amber-600 hover:bg-amber-50 rounded transition" title="Resend Lost Pass">
                            <i class="fas fa-share-square"></i>
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (e) {
        console.warn('Error loading students:', e);
    }
}

// Pass Preview & Actions Modal
window.viewPassModal = async function(token) {
    const modal = document.getElementById('pass-preview-modal');
    if (!modal) return;

    try {
        const res = await fetch(`/api/pass-details/${token}`);
        const data = await res.json();
        if (!data.success) return;

        const s = data.student;
        const cfg = data.config;

        document.getElementById('modal-pass-qr').src = data.qr_b64;
        document.getElementById('modal-pass-name').innerText = s.name;
        document.getElementById('modal-pass-roll').innerText = s.roll_no;
        document.getElementById('modal-pass-sem').innerText = s.semester;
        document.getElementById('modal-pass-token').innerText = s.pass_token;
        document.getElementById('modal-pass-link').href = `/pass/${s.pass_token}`;

        // Hook up resend buttons in modal
        document.getElementById('modal-resend-email-btn').onclick = () => sendSingleEmail(s.id);
        document.getElementById('modal-resend-wa-btn').onclick = () => openWhatsAppUrl(s.id);
        document.getElementById('modal-resend-all-btn').onclick = () => resendLostPass(s.id);

        modal.classList.remove('hidden');
    } catch (e) {
        window.showToast('Could not load pass details', 'error');
    }
};

window.sendSingleEmail = async function(studentId) {
    window.showToast('Dispatching email invitation...', 'info');
    try {
        const res = await fetch(`/api/send-email/${studentId}`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            window.showToast(data.message, 'success');
        } else {
            window.showToast(data.message || 'Failed to send email', 'error');
        }
    } catch (e) {
        window.showToast('Network error sending email', 'error');
    }
};

window.openWhatsAppUrl = async function(studentId) {
    try {
        const res = await fetch(`/api/whatsapp-url/${studentId}`);
        const data = await res.json();
        if (data.success && data.wa_url) {
            window.open(data.wa_url, '_blank');
            window.showToast(`WhatsApp invitation opened for ${data.phone}`, 'success');
        }
    } catch (e) {
        window.showToast('Error generating WhatsApp link', 'error');
    }
};

window.resendLostPass = async function(studentId) {
    window.showToast('Resending pass to guest...', 'info');
    try {
        const res = await fetch(`/api/resend-pass/${studentId}`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            window.showToast(data.message, 'success');
            if (data.whatsapp_url) {
                // Also give option to open WhatsApp immediately
                window.open(data.whatsapp_url, '_blank');
            }
        } else {
            window.showToast(data.message || 'Resend failed', 'error');
        }
    } catch (e) {
        window.showToast('Error resending pass', 'error');
    }
};

window.triggerBulkEmail = async function() {
    const sem = AppState.currentSemesterTab;
    const confirmMsg = sem === 'all' 
        ? 'Send official invitation emails to ALL BCA 1st & 3rd Sem students?' 
        : `Send official invitation emails to all ${sem} students?`;

    if (!confirm(confirmMsg)) return;

    window.showToast('Sending bulk invitations in progress...', 'info');
    try {
        const res = await fetch('/api/send-bulk-email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ semester: sem })
        });
        const data = await res.json();
        if (data.success) {
            window.showToast(data.message, 'success');
            loadStudents();
        } else {
            window.showToast(data.message || 'Bulk dispatch failed', 'error');
        }
    } catch (e) {
        window.showToast('Error during bulk email dispatch', 'error');
    }
};

// ==================== Admin & OTP Management ====================

async function loadAdmins() {
    const tbody = document.getElementById('admins-table-body');
    if (!tbody) return;

    try {
        const res = await fetch('/api/auth/admins');
        const data = await res.json();
        if (!data.success) return;

        tbody.innerHTML = data.admins.map(a => {
            const isCreator = a.role === 'creator';
            const statusClass = {
                approved: 'bg-emerald-100 text-emerald-800',
                pending: 'bg-amber-100 text-amber-800',
                rejected: 'bg-rose-100 text-rose-800'
            }[a.status] || 'bg-slate-100 text-slate-800';

            const actions = isCreator 
                ? '<span class="text-xs text-slate-400 font-semibold">Master Admin</span>'
                : `
                    <div class="space-x-1">
                        ${a.status !== 'approved' ? `<button onclick="approveAdminAction(${a.id})" class="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-2xs font-bold transition">Approve & OTP</button>` : ''}
                        ${a.status === 'approved' ? `<button onclick="regenOtpAction(${a.id})" class="px-2 py-1 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded text-2xs font-bold transition" title="Generate New 6-Digit OTP">New OTP</button>` : ''}
                        ${a.status !== 'rejected' ? `<button onclick="rejectAdminAction(${a.id})" class="px-2 py-1 bg-rose-50 hover:bg-rose-100 text-rose-700 rounded text-2xs font-bold transition">Revoke</button>` : ''}
                    </div>
                `;

            return `
                <tr class="hover:bg-slate-50 border-b border-slate-100 transition">
                    <td class="px-4 py-3">
                        <strong class="text-xs font-bold text-slate-900 block">${a.name}</strong>
                        <span class="text-2xs text-slate-500">${a.email}</span>
                    </td>
                    <td class="px-4 py-3 text-xs text-slate-600 font-mono">${a.phone || '-'}</td>
                    <td class="px-4 py-3">
                        <span class="px-2 py-0.5 rounded text-2xs font-black uppercase ${isCreator ? 'bg-purple-100 text-purple-800' : 'bg-slate-100 text-slate-800'}">
                            ${a.role}
                        </span>
                    </td>
                    <td class="px-4 py-3">
                        <span class="px-2 py-0.5 rounded text-2xs font-bold uppercase ${statusClass}">
                            ${a.status}
                        </span>
                    </td>
                    <td class="px-4 py-3 font-mono font-bold text-xs text-blue-700 bg-blue-50/40">
                        ${a.status === 'approved' ? (a.otp || '-') : '<span class="text-slate-400">Locked</span>'}
                    </td>
                    <td class="px-4 py-3 text-right">${actions}</td>
                </tr>
            `;
        }).join('');
    } catch (e) {
        console.warn('Error loading admins:', e);
    }
}

window.approveAdminAction = async function(id) {
    try {
        const res = await fetch('/api/auth/approve-admin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ admin_id: id })
        });
        const d = await res.json();
        if (d.success) {
            window.showToast(`Admin Approved! OTP: ${d.otp}`, 'success');
            loadAdmins();
        }
    } catch (e) {
        window.showToast('Error approving admin', 'error');
    }
};

window.regenOtpAction = async function(id) {
    try {
        const res = await fetch('/api/auth/regenerate-otp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ admin_id: id })
        });
        const d = await res.json();
        if (d.success) {
            window.showToast(`New 6-digit OTP Generated: ${d.otp}`, 'success');
            loadAdmins();
        }
    } catch (e) {
        window.showToast('Error regenerating OTP', 'error');
    }
};

window.rejectAdminAction = async function(id) {
    try {
        const res = await fetch('/api/auth/reject-admin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ admin_id: id })
        });
        const d = await res.json();
        if (d.success) {
            window.showToast('Admin permissions revoked', 'warning');
            loadAdmins();
        }
    } catch (e) {
        window.showToast('Error revoking admin', 'error');
    }
};

// ==================== Audit Logs ====================

async function loadAuditLogs() {
    const tbody = document.getElementById('audit-table-body');
    if (!tbody) return;

    const search = document.getElementById('audit-search-input')?.value || '';
    try {
        const res = await fetch(`/api/audit-logs?search=${encodeURIComponent(search)}`);
        const d = await res.json();
        if (!d.success) return;

        if (d.logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center py-8 text-xs text-slate-400">No audit events recorded yet.</td></tr>';
            return;
        }

        tbody.innerHTML = d.logs.map(l => {
            const isDup = l.action === 'DUPLICATE_ATTEMPT';
            const actionBadge = isDup
                ? '<span class="px-2 py-0.5 bg-rose-100 text-rose-800 text-2xs font-bold rounded">DUPLICATE REJECTED</span>'
                : '<span class="px-2 py-0.5 bg-emerald-100 text-emerald-800 text-2xs font-bold rounded">CHECKED IN</span>';

            return `
                <tr class="hover:bg-slate-50 border-b border-slate-100 text-xs transition">
                    <td class="px-4 py-3 font-mono text-slate-500 text-2xs">${l.timestamp}</td>
                    <td class="px-4 py-3">
                        <strong class="text-slate-900 block font-bold">${l.student_name}</strong>
                        <span class="font-mono text-blue-600 text-2xs">${l.roll_no} &bull; ${l.semester}</span>
                    </td>
                    <td class="px-4 py-3 font-semibold text-slate-700">${l.admin_name}</td>
                    <td class="px-4 py-3 font-mono text-2xs text-slate-500">${l.method}</td>
                    <td class="px-4 py-3">${actionBadge}</td>
                    <td class="px-4 py-3 text-slate-500 text-2xs">${l.details || '-'}</td>
                </tr>
            `;
        }).join('');
    } catch (e) {
        console.warn('Error loading audit logs:', e);
    }
}

// ==================== Event Settings & Configuration ====================

async function loadSettings() {
    try {
        const res = await fetch('/api/config');
        const d = await res.json();
        if (d.success && d.config) {
            AppState.config = d.config;
            document.getElementById('cfg-event-name').value = d.config.event_name || '';
            document.getElementById('cfg-event-date').value = d.config.event_date || '';
            document.getElementById('cfg-venue').value = d.config.venue || '';
            document.getElementById('cfg-creator-email').value = d.config.creator_email || '';
            document.getElementById('cfg-smtp-server').value = d.config.smtp_server || 'smtp.gmail.com';
            document.getElementById('cfg-smtp-port').value = d.config.smtp_port || 587;
            document.getElementById('cfg-smtp-user').value = d.config.smtp_user || '';
            document.getElementById('cfg-smtp-password').value = d.config.smtp_password || '';
        }
    } catch (e) {}

    // Load recent notifications log into outbox
    loadOutbox();
}

window.saveSettings = async function(e) {
    if (e) e.preventDefault();
    const payload = {
        event_name: document.getElementById('cfg-event-name').value.trim(),
        event_date: document.getElementById('cfg-event-date').value.trim(),
        venue: document.getElementById('cfg-venue').value.trim(),
        creator_email: document.getElementById('cfg-creator-email').value.trim(),
        smtp_server: document.getElementById('cfg-smtp-server').value.trim(),
        smtp_port: document.getElementById('cfg-smtp-port').value.trim(),
        smtp_user: document.getElementById('cfg-smtp-user').value.trim(),
        smtp_password: document.getElementById('cfg-smtp-password').value.trim(),
    };

    try {
        const res = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const d = await res.json();
        if (d.success) {
            window.showToast('Event settings saved successfully!', 'success');
        }
    } catch (err) {
        window.showToast('Error saving configuration', 'error');
    }
};

async function loadOutbox() {
    const box = document.getElementById('outbox-logs-container');
    if (!box) return;

    try {
        const res = await fetch('/api/notifications');
        const d = await res.json();
        if (d.success && d.notifications) {
            if (d.notifications.length === 0) {
                box.innerHTML = '<div class="text-xs text-slate-400 py-4 text-center">Outbox is empty. Send invitations to view logs here.</div>';
                return;
            }

            box.innerHTML = d.notifications.map(n => `
                <div class="p-3 bg-slate-50 border border-slate-100 rounded-lg text-xs flex items-center justify-between">
                    <div>
                        <div class="flex items-center space-x-2">
                            <span class="font-bold text-slate-900">${n.recipient}</span>
                            <span class="px-2 py-0.2 rounded text-3xs font-bold uppercase ${n.channel === 'email' ? 'bg-indigo-100 text-indigo-800' : 'bg-emerald-100 text-emerald-800'}">${n.channel}</span>
                            <span class="px-2 py-0.2 rounded text-3xs font-bold uppercase ${n.status === 'sent' ? 'bg-emerald-100 text-emerald-800' : (n.status === 'simulated' ? 'bg-sky-100 text-sky-800' : 'bg-slate-100 text-slate-800')}">${n.status}</span>
                        </div>
                        <div class="text-slate-500 text-2xs mt-0.5">${n.student_name || 'Student'} (${n.roll_no || '-'}) &bull; ${n.created_at}</div>
                    </div>
                </div>
            `).join('');
        }
    } catch (e) {}
}

// ==================== Excel Upload Handler ====================

window.uploadExcelFile = async function(inputElement) {
    const file = inputElement.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    window.showToast('Uploading & parsing Excel spreadsheet...', 'info');
    try {
        const res = await fetch('/api/upload-excel', {
            method: 'POST',
            body: formData
        });
        const d = await res.json();
        if (d.success) {
            window.showToast(d.message, 'success');
            loadStudents();
            loadDashboardStats();
        } else {
            window.showToast(d.message || 'Excel upload failed', 'error');
        }
    } catch (e) {
        window.showToast('Error uploading Excel file', 'error');
    }
    inputElement.value = '';
};

// ==================== App Startup ====================

document.addEventListener('DOMContentLoaded', () => {
    initRealtimeSync();
    loadDashboardStats();

    // Check if admin is currently authenticated
    const currentToken = localStorage.getItem('event_admin_token');
    const adminName = localStorage.getItem('event_admin_name') || 'Gate 1 - Rahul Sharma (Demo Admin)';
    if (!currentToken) {
        // Set default demo scanner session so user can test scanning right out of the box!
        localStorage.setItem('event_admin_token', 'TOKEN-SCANNER-DEMO-GATE1');
        localStorage.setItem('event_admin_name', 'Gate 1 - Rahul Sharma');
    }

    const scannerNameEl = document.getElementById('current-scanner-name');
    if (scannerNameEl) {
        scannerNameEl.innerText = localStorage.getItem('event_admin_name') || 'Gate Scanner';
    }

    if (window.ScannerController) {
        window.ScannerController.init();
    }
});
