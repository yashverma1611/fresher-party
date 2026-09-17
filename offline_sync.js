/**
 * Offline Synchronization & Caching Manager
 * Enables scanning and verifying passes even when campus Wi-Fi disconnects.
 */

const OfflineSyncManager = {
    STORAGE_ROSTER_KEY: 'event_roster_cache',
    STORAGE_QUEUE_KEY: 'event_offline_scans_queue',

    isOnline: navigator.onLine,

    init() {
        window.addEventListener('online', () => {
            this.isOnline = true;
            this.notifyStatusChange();
            this.autoSyncQueue();
        });

        window.addEventListener('offline', () => {
            this.isOnline = false;
            this.notifyStatusChange();
        });

        // Initial sync of roster if online
        if (this.isOnline) {
            this.downloadRoster();
        }
    },

    notifyStatusChange() {
        window.dispatchEvent(new CustomEvent('network-status-change', {
            detail: { isOnline: this.isOnline, queueCount: this.getQueueCount() }
        }));
    },

    async downloadRoster() {
        try {
            const res = await fetch('/api/offline-roster');
            if (res.ok) {
                const data = await res.json();
                if (data.roster) {
                    localStorage.setItem(this.STORAGE_ROSTER_KEY, JSON.stringify({
                        timestamp: data.timestamp,
                        roster: data.roster
                    }));
                    console.log(`[OfflineSync] Cached ${data.roster.length} students locally.`);
                }
            }
        } catch (e) {
            console.warn('[OfflineSync] Could not download roster cache:', e);
        }
    },

    getCachedRoster() {
        const cached = localStorage.getItem(this.STORAGE_ROSTER_KEY);
        if (!cached) return [];
        try {
            return JSON.parse(cached).roster || [];
        } catch (e) {
            return [];
        }
    },

    lookupTokenOffline(token) {
        const roster = this.getCachedRoster();
        return roster.find(s => s.pass_token === token || s.roll_no.toLowerCase() === token.toLowerCase());
    },

    getQueue() {
        const raw = localStorage.getItem(this.STORAGE_QUEUE_KEY);
        if (!raw) return [];
        try {
            return JSON.parse(raw) || [];
        } catch (e) {
            return [];
        }
    },

    getQueueCount() {
        return this.getQueue().length;
    },

    enqueueScan(passToken, method = 'OFFLINE_SYNC') {
        const queue = this.getQueue();
        const now = new Date().toISOString().replace('T', ' ').substring(0, 19);
        queue.push({
            pass_token: passToken,
            method: method,
            timestamp: now
        });
        localStorage.setItem(this.STORAGE_QUEUE_KEY, JSON.stringify(queue));

        // Optimistically update local cached roster status so same token scanned twice offline alerts duplicate!
        const roster = this.getCachedRoster();
        const student = roster.find(s => s.pass_token === passToken);
        if (student) {
            student.status = 'checked_in';
            student.checked_in_at = now;
            student.scanned_by_admin_name = 'Offline Scanner (Pending Sync)';
            localStorage.setItem(this.STORAGE_ROSTER_KEY, JSON.stringify({ timestamp: now, roster }));
        }

        this.notifyStatusChange();
    },

    async syncQueue(sessionToken) {
        const queue = this.getQueue();
        if (queue.length === 0) return { synced: 0, duplicates: 0 };

        try {
            const res = await fetch('/api/sync-offline-scans', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${sessionToken}`
                },
                body: JSON.stringify({ scans: queue })
            });

            if (res.ok) {
                const data = await res.json();
                localStorage.removeItem(this.STORAGE_QUEUE_KEY);
                this.downloadRoster(); // refresh clean state
                this.notifyStatusChange();
                return data;
            } else {
                throw new Error('Sync failed with status ' + res.status);
            }
        } catch (e) {
            console.error('[OfflineSync] Error syncing queue:', e);
            throw e;
        }
    },

    autoSyncQueue() {
        const token = localStorage.getItem('event_admin_token');
        if (token && this.getQueueCount() > 0) {
            console.log('[OfflineSync] Network restored. Auto-syncing queued scans...');
            this.syncQueue(token).then(res => {
                if (window.showToast) {
                    window.showToast(`Auto-synced ${res.synced} offline scans!`, 'success');
                }
            }).catch(err => {
                console.warn('[OfflineSync] Auto-sync failed, will retry later:', err);
            });
        }
    }
};

window.OfflineSyncManager = OfflineSyncManager;
OfflineSyncManager.init();
