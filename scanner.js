/**
 * QR Scanner Controller with Web Audio feedback & Manual Search Fallback
 */

const SoundEffects = {
    audioCtx: null,

    getAudioContext() {
        if (!this.audioCtx) {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            this.audioCtx = new AudioContext();
        }
        if (this.audioCtx.state === 'suspended') {
            this.audioCtx.resume();
        }
        return this.audioCtx;
    },

    playSuccess() {
        try {
            const ctx = this.getAudioContext();
            const now = ctx.currentTime;
            
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(587.33, now); // D5
            osc.frequency.exponentialRampToValueAtTime(880.00, now + 0.12); // A5

            gain.gain.setValueAtTime(0.3, now);
            gain.gain.exponentialRampToValueAtTime(0.01, now + 0.35);

            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(now);
            osc.stop(now + 0.35);
        } catch (e) {
            console.log('Audio feedback not available', e);
        }
    },

    playDuplicate() {
        try {
            const ctx = this.getAudioContext();
            const now = ctx.currentTime;

            // Two quick alert buzzes
            [0, 0.16].forEach(offset => {
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = 'sawtooth';
                osc.frequency.setValueAtTime(220, now + offset);
                osc.frequency.linearRampToValueAtTime(140, now + offset + 0.12);

                gain.gain.setValueAtTime(0.4, now + offset);
                gain.gain.exponentialRampToValueAtTime(0.01, now + offset + 0.12);

                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start(now + offset);
                osc.stop(now + offset + 0.12);
            });
        } catch (e) {
            console.log('Audio feedback error', e);
        }
    },

    playError() {
        try {
            const ctx = this.getAudioContext();
            const now = ctx.currentTime;
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'square';
            osc.frequency.setValueAtTime(160, now);
            gain.gain.setValueAtTime(0.35, now);
            gain.gain.exponentialRampToValueAtTime(0.01, now + 0.3);

            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(now);
            osc.stop(now + 0.3);
        } catch (e) {
            console.log('Audio feedback error', e);
        }
    }
};

const ScannerController = {
    html5QrCode: null,
    isScanning: false,
    facingMode: 'environment',
    isCooldown: false,
    lastScannedText: '',

    init() {
        // Setup manual search listener
        const searchInput = document.getElementById('manual-search-input');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => this.handleManualSearchInput(e.target.value));
        }
    },

    async startCamera() {
        const readerElement = document.getElementById('qr-reader');
        if (!readerElement) return;

        if (this.html5QrCode) {
            try {
                await this.html5QrCode.stop();
            } catch (e) {}
        }

        this.html5QrCode = new Html5Qrcode('qr-reader');
        const config = {
            fps: 15,
            qrbox: { width: 250, height: 250 },
            aspectRatio: 1.0
        };

        try {
            await this.html5QrCode.start(
                { facingMode: this.facingMode },
                config,
                (decodedText) => this.onScanSuccess(decodedText),
                (errorMessage) => { /* ignore per-frame failures */ }
            );
            this.isScanning = true;
            document.getElementById('camera-status-text').innerText = 'Camera Active - Align QR Code';
            document.getElementById('camera-status-text').className = 'text-xs text-emerald-400 font-medium';
        } catch (err) {
            console.error('Failed to start camera:', err);
            document.getElementById('camera-status-text').innerText = 'Camera Error: ' + (err.message || 'Check permissions');
            document.getElementById('camera-status-text').className = 'text-xs text-rose-400 font-medium';
        }
    },

    async stopCamera() {
        if (this.html5QrCode && this.isScanning) {
            try {
                await this.html5QrCode.stop();
                this.isScanning = false;
            } catch (e) {}
        }
    },

    async switchCamera() {
        this.facingMode = this.facingMode === 'environment' ? 'user' : 'environment';
        await this.startCamera();
    },

    extractPassToken(rawText) {
        if (!rawText) return '';
        rawText = rawText.trim();
        // If scanned URL like http://.../pass/PASS-BCA1ST-...
        if (rawText.includes('/pass/')) {
            const parts = rawText.split('/pass/');
            return parts[parts.length - 1].trim();
        }
        return rawText;
    },

    async onScanSuccess(decodedText) {
        if (this.isCooldown) return;
        const token = this.extractPassToken(decodedText);
        if (!token) return;

        this.isCooldown = true;
        this.lastScannedText = token;

        // Perform check-in
        await this.executeCheckIn(token, null, 'QR_CAMERA');

        // Cooldown timer to prevent accidental double firing
        setTimeout(() => {
            this.isCooldown = false;
        }, 1800);
    },

    async executeCheckIn(passToken, studentId, method = 'QR_CAMERA') {
        const token = localStorage.getItem('event_admin_token');
        if (!token) {
            window.showToast('Please login with approved Admin OTP first!', 'error');
            window.switchView('admins');
            return;
        }

        const isOnline = navigator.onLine;

        if (!isOnline) {
            // Offline Verification Flow
            this.handleOfflineVerification(passToken, studentId, method);
            return;
        }

        try {
            const res = await fetch('/api/scan-checkin', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    pass_token: passToken,
                    student_id: studentId,
                    method: method
                })
            });

            const data = await res.json();

            if (res.status === 200 && data.success) {
                // VERIFIED
                SoundEffects.playSuccess();
                this.displayResultCard('VERIFIED', data.student, data.message);
                if (window.showToast) window.showToast(`Verified: ${data.student.name}`, 'success');
            } else if (res.status === 409) {
                // DUPLICATE ATTEMPT
                SoundEffects.playDuplicate();
                this.displayResultCard('DUPLICATE', data.student, data.message, data.checked_in_at, data.scanned_by_admin_name);
                if (window.showToast) window.showToast('Warning: Duplicate Scan Rejected!', 'error');
            } else {
                // INVALID PASS / UNAUTHORIZED
                SoundEffects.playError();
                this.displayResultCard('INVALID', null, data.message || 'Pass Token Not Found');
                if (window.showToast) window.showToast(data.message || 'Invalid Pass', 'error');
            }
        } catch (err) {
            console.warn('Network error during scan, switching to offline fallback:', err);
            this.handleOfflineVerification(passToken, studentId, method);
        }
    },

    handleOfflineVerification(passToken, studentId, method) {
        const roster = window.OfflineSyncManager.getCachedRoster();
        let student = null;
        if (passToken) {
            student = roster.find(s => s.pass_token === passToken || s.roll_no.toLowerCase() === passToken.toLowerCase());
        } else if (studentId) {
            student = roster.find(s => s.id === studentId);
        }

        if (!student) {
            SoundEffects.playError();
            this.displayResultCard('INVALID', null, 'OFFLINE: Pass token not found in local cache');
            return;
        }

        if (student.status === 'checked_in') {
            SoundEffects.playDuplicate();
            this.displayResultCard('DUPLICATE', student, 'OFFLINE ALERT: Already Checked In!', student.checked_in_at, student.scanned_by_admin_name);
        } else {
            // Queue offline scan
            window.OfflineSyncManager.enqueueScan(student.pass_token, method);
            SoundEffects.playSuccess();
            this.displayResultCard('OFFLINE_VERIFIED', student, 'ENTRY APPROVED (Offline Queued)');
            if (window.showToast) window.showToast(`Offline Verified: ${student.name} (Queued)`, 'warning');
        }
    },

    displayResultCard(status, student, message, prevTime = null, prevAdmin = null) {
        const container = document.getElementById('scan-result-card');
        if (!container) return;

        container.classList.remove('hidden');

        let bgClass = 'bg-emerald-50 border-emerald-500 text-emerald-950';
        let badgeClass = 'bg-emerald-600 text-white';
        let iconHtml = '<i class="fas fa-check-circle text-4xl text-emerald-600"></i>';
        let statusTitle = 'ENTRY VERIFIED';

        if (status === 'DUPLICATE') {
            bgClass = 'bg-rose-50 border-rose-500 text-rose-950';
            badgeClass = 'bg-rose-600 text-white';
            iconHtml = '<i class="fas fa-exclamation-triangle text-4xl text-rose-600 animate-pulse"></i>';
            statusTitle = 'ALREADY CHECKED IN!';
        } else if (status === 'INVALID') {
            bgClass = 'bg-amber-50 border-amber-500 text-amber-950';
            badgeClass = 'bg-amber-600 text-white';
            iconHtml = '<i class="fas fa-times-circle text-4xl text-amber-600"></i>';
            statusTitle = 'INVALID / UNRECOGNIZED PASS';
        } else if (status === 'OFFLINE_VERIFIED') {
            bgClass = 'bg-sky-50 border-sky-500 text-sky-950';
            badgeClass = 'bg-sky-600 text-white';
            iconHtml = '<i class="fas fa-wifi text-4xl text-sky-600"></i>';
            statusTitle = 'OFFLINE ENTRY APPROVED';
        }

        let studentHtml = '';
        if (student) {
            studentHtml = `
                <div class="mt-3 pt-3 border-t border-slate-200/60 grid grid-cols-2 gap-2 text-left text-sm">
                    <div><span class="text-xs text-slate-500 block">STUDENT</span><strong class="font-bold text-slate-900">${student.name}</strong></div>
                    <div><span class="text-xs text-slate-500 block">ROLL NUMBER</span><strong class="font-bold text-blue-600 font-mono">${student.roll_no}</strong></div>
                    <div><span class="text-xs text-slate-500 block">SEMESTER</span><span class="font-medium">${student.semester}</span></div>
                    <div><span class="text-xs text-slate-500 block">PHONE</span><span class="font-mono text-xs">${student.phone}</span></div>
                </div>
            `;
        }

        let duplicateDetailHtml = '';
        if (status === 'DUPLICATE' && prevTime) {
            duplicateDetailHtml = `
                <div class="mt-2.5 p-2.5 bg-rose-100/80 rounded-lg text-xs text-rose-900 font-medium">
                    <i class="fas fa-history mr-1"></i> Prior Check-in: <strong>${prevTime}</strong> by <strong>${prevAdmin || 'Gate Admin'}</strong>
                </div>
            `;
        }

        container.innerHTML = `
            <div class="p-5 rounded-xl border-2 shadow-lg ${bgClass} animate-pop text-center relative">
                <button onclick="document.getElementById('scan-result-card').classList.add('hidden')" class="absolute top-3 right-3 text-slate-400 hover:text-slate-600 text-lg">
                    <i class="fas fa-times"></i>
                </button>
                <div class="flex items-center justify-center space-x-3 mb-2">
                    ${iconHtml}
                    <div class="text-left">
                        <span class="inline-block px-2.5 py-0.5 rounded-full text-xs font-black tracking-wider uppercase ${badgeClass}">${statusTitle}</span>
                        <h3 class="text-base font-bold mt-0.5 leading-snug">${message}</h3>
                    </div>
                </div>
                ${duplicateDetailHtml}
                ${studentHtml}
            </div>
        `;
    },

    handleManualSearchInput(query) {
        query = (query || '').trim().toLowerCase();
        const resultsBox = document.getElementById('manual-search-results');
        if (!resultsBox) return;

        if (query.length < 2) {
            resultsBox.innerHTML = '';
            resultsBox.classList.add('hidden');
            return;
        }

        // Search in local roster cache for instant speed
        const roster = window.OfflineSyncManager.getCachedRoster();
        const matches = roster.filter(s => 
            s.roll_no.toLowerCase().includes(query) ||
            s.name.toLowerCase().includes(query) ||
            (s.phone && s.phone.includes(query))
        ).slice(0, 5);

        if (matches.length === 0) {
            resultsBox.innerHTML = '<div class="p-3 text-xs text-slate-500 text-center">No student found matching query</div>';
            resultsBox.classList.remove('hidden');
            return;
        }

        resultsBox.innerHTML = matches.map(s => {
            const isChecked = s.status === 'checked_in';
            const statusBadge = isChecked 
                ? '<span class="px-2 py-0.5 bg-emerald-100 text-emerald-800 text-2xs font-bold rounded">CHECKED IN</span>'
                : '<span class="px-2 py-0.5 bg-amber-100 text-amber-800 text-2xs font-bold rounded">PENDING</span>';

            const actionBtn = isChecked
                ? `<span class="text-xs text-slate-400 font-medium">Already Admitted</span>`
                : `<button onclick="ScannerController.executeCheckIn(null, ${s.id}, 'MANUAL_SEARCH')" class="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-bold shadow-sm transition">
                    <i class="fas fa-check-double mr-1"></i> Verify Entry
                   </button>`;

            return `
                <div class="p-3 border-b border-slate-100 hover:bg-slate-50 flex items-center justify-between transition">
                    <div>
                        <div class="flex items-center space-x-2">
                            <strong class="text-sm text-slate-900">${s.name}</strong>
                            <span class="font-mono text-xs text-blue-600 font-bold">${s.roll_no}</span>
                            ${statusBadge}
                        </div>
                        <div class="text-xs text-slate-500 mt-0.5">${s.semester} &bull; ${s.phone}</div>
                    </div>
                    <div>
                        ${actionBtn}
                    </div>
                </div>
            `;
        }).join('');

        resultsBox.classList.remove('hidden');
    }
};

window.ScannerController = ScannerController;
