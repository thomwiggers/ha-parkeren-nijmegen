(function () {
  'use strict';

  const DOMAIN = 'parkeren_nijmegen';

  // Entity/device IDs are instance-specific (they embed the user's account
  // identifier), so they're discovered at runtime from the entity/device
  // registries instead of being hardcoded here. Each sensor is identified by
  // an attribute unique to its role, since names/entity_ids are localized
  // and vary per installation.
  let _resolvedCache = null;

  function resolveIntegration(hass) {
    if (_resolvedCache) return _resolvedCache;
    if (!hass || !hass.devices || !hass.entities) return null;

    const device = Object.values(hass.devices).find(d =>
      (d.identifiers || []).some(([domain]) => domain === DOMAIN)
    );
    if (!device) return null;

    const candidateIds = Object.values(hass.entities)
      .filter(e => e.platform === DOMAIN && e.device_id === device.id)
      .map(e => e.entity_id);

    const findBy = (pred) => candidateIds.find(id => {
      const st = hass.states[id];
      return st && pred(st.attributes || {});
    });

    const zone = findBy(a => 'is_chargeable_now' in a);
    const balance = findBy(a => 'remaining_minutes' in a);
    const active = findBy(a => Array.isArray(a.reservations));
    const favorites = findBy(a => Array.isArray(a.license_plates));
    const planned = candidateIds.find(id => {
      if ([zone, balance, active, favorites].includes(id)) return false;
      const st = hass.states[id];
      return st && st.attributes?.device_class !== 'timestamp';
    });

    if (!zone || !balance || !active || !favorites || !planned) return null;

    _resolvedCache = {
      deviceId: device.id,
      ZONE_ENTITY: zone,
      BALANCE_ENTITY: balance,
      ACTIVE_ENTITY: active,
      FAVORITES_ENTITY: favorites,
      PLANNED_ENTITY: planned,
    };
    return _resolvedCache;
  }

  function pad(n) { return String(n).padStart(2, '0'); }

  function fmtLocal(d) {
    if (!d) return '';
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function parseDT(s) {
    if (!s) return null;
    const d = new Date(s);
    return isNaN(d.getTime()) ? null : d;
  }

  function fmtDisplay(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return `${pad(d.getDate())}-${pad(d.getMonth()+1)} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  // ── Card 1: New Reservation ───────────────────────────────────────────────

  const CARD1_STYLES = `
    :host { display: block; }
    ha-input, ha-textfield { width: 100%; }
    .content { padding: 16px; }
    .status { padding: 8px 12px; border-radius: 8px; margin-bottom: 12px; font-size: 14px; }
    .status.success { background: var(--success-color, #4caf50); color: #fff; }
    .status.warning { background: var(--warning-color, #ff9800); color: #fff; }
    .zone-row {
      display: flex; justify-content: space-between; align-items: center;
      padding: 6px 0; margin-bottom: 8px;
      border-bottom: 1px solid var(--divider-color); font-size: 14px;
    }
    .balance { color: var(--secondary-text-color); font-size: 13px; }
    .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
    .chip {
      display: inline-flex; align-items: center; gap: 4px;
      padding: 4px 10px; border-radius: 16px;
      border: 1px solid var(--primary-color); cursor: pointer;
      font-size: 13px; color: var(--primary-color); background: transparent;
    }
    .chip.active { background: var(--primary-color); color: #fff; }
    .row { margin-bottom: 8px; }
    .datetime-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 8px; }
    .actions {
      display: flex; align-items: center;
      justify-content: space-between; margin-top: 8px;
    }
  `;

  class ParkerenReserveringCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
      this._hass = null;
      this._config = null;
      this._vals = { plate: '', start: '', end: '' };
      this._addFavVals = { plate: '', name: '' };
      this._showAddFav = false;
      this._busy = false;
      this._status = null;
      this._statusType = 'info';
      this._stOut = null;
      this._lastHassKey = null;
      this._res = null;
    }

    setConfig(config) { this._config = config; this._render(); }

    _hassKey(hass) {
      if (!this._res) return 'unresolved';
      const zone = hass.states[this._res.ZONE_ENTITY];
      return [
        zone?.state, zone?.attributes?.next_window_start, zone?.attributes?.next_window_end,
        hass.states[this._res.BALANCE_ENTITY]?.state,
        JSON.stringify(hass.states[this._res.FAVORITES_ENTITY]?.attributes?.license_plates),
      ].join('|');
    }

    set hass(hass) {
      this._hass = hass;
      this._res = this._res || resolveIntegration(hass);
      this._initDefaultTimes();
      const key = this._hassKey(hass);
      if (key === this._lastHassKey) return;
      this._lastHassKey = key;
      if (this.shadowRoot.activeElement) return;
      this._render();
    }

    _initDefaultTimes() {
      if (this._vals.end || !this._res) return;
      const zone = this._hass?.states[this._res.ZONE_ENTITY];
      if (!zone) return;
      const now = new Date();
      if (!this._vals.start) {
        const ns = zone.attributes?.next_window_start;
        if (ns && zone.state === 'gratis') {
          const s = new Date(ns);
          this._vals.start = fmtLocal(s > now ? s : now);
        } else {
          this._vals.start = fmtLocal(new Date(now.getTime() + 60000));
        }
      }
      const ne = zone.attributes?.next_window_end;
      if (ne) {
        const e = new Date(ne);
        const adj = (e.getHours() === 0 && e.getMinutes() === 0) ? new Date(e.getTime() - 60000) : e;
        this._vals.end = fmtLocal(adj);
      }
    }

    _setStatus(msg, type = 'info', ms = 0) {
      if (this._stOut) clearTimeout(this._stOut);
      this._status = msg; this._statusType = type;
      if (ms) this._stOut = setTimeout(() => { this._status = null; this._render(); }, ms);
      this._render();
    }

    _favs() {
      if (!this._res) return [];
      return this._hass?.states[this._res.FAVORITES_ENTITY]?.attributes?.license_plates || [];
    }

    _zoneLabel() {
      const z = this._res && this._hass?.states[this._res.ZONE_ENTITY];
      if (!z) return '';
      return (z.state === 'betaald' || z.attributes?.is_chargeable_now)
        ? '⚠ Betaalde zone actief'
        : '✓ Gratis parkeren nu';
    }

    _balanceLabel() {
      const b = this._res && this._hass?.states[this._res.BALANCE_ENTITY];
      if (!b) return '';
      const h = parseFloat(b.state);
      return isNaN(h) ? '' : `${h.toFixed(1)} h tegoed`;
    }

    _normPlate(s) { return (s || '').trim().toUpperCase().replace(/[\s-]/g, ''); }

    _isFav(normPlate) {
      return Boolean(normPlate) && this._favs().some(f => this._normPlate(f.license_plate) === normPlate);
    }

    async _start() {
      if (this._busy || !this._res) return;
      const plate = this._normPlate(this._vals.plate);
      if (!plate) { this._setStatus('Voer een kenteken in', 'warning'); return; }
      const start = parseDT(this._vals.start);
      const end = parseDT(this._vals.end);
      if (!start || !end) { this._setStatus('Vul start- en eindtijd in', 'warning'); return; }
      if (end <= start) { this._setStatus('Eindtijd moet na starttijd zijn', 'warning'); return; }
      this._busy = true; this._render();
      try {
        await this._hass.callService(DOMAIN, 'start_reservation', {
          device_id: this._res.deviceId, license_plate: plate,
          start_time: start.toISOString(), end_time: end.toISOString(),
        });
        this._vals.plate = '';
        this._setStatus('Reservering aangemaakt', 'success', 5000);
      } catch (e) {
        this._setStatus('Fout: ' + (e?.message || String(e)), 'warning');
      } finally {
        this._busy = false; this._render();
      }
    }

    async _addFav(plate, name) {
      if (!this._res) return;
      if (!plate) { this._setStatus('Voer een kenteken in', 'warning'); return; }
      if (this._isFav(plate)) { this._setStatus('Al een favoriet', 'warning'); return; }
      try {
        await this._hass.callService(DOMAIN, 'add_favorite', {
          device_id: this._res.deviceId, license_plate: plate,
          ...(name ? { name } : {}),
        });
        this._addFavVals = { plate: '', name: '' };
        this._showAddFav = false;
        this._setStatus('Favoriet toegevoegd', 'success', 5000);
      } catch (e) {
        this._setStatus('Fout: ' + (e?.message || String(e)), 'warning');
      }
    }

    async _rmFav(plate) {
      if (!this._res) return;
      try {
        await this._hass.callService(DOMAIN, 'remove_favorite', { device_id: this._res.deviceId, license_plate: plate });
        this._setStatus('Favoriet verwijderd', 'success', 5000);
      } catch (e) {
        this._setStatus('Fout: ' + (e?.message || String(e)), 'warning');
      }
    }

    _selectFav(plate) {
      this._vals.plate = plate;
      this._render();
    }

    _render() {
      if (!this._config || !this._hass) return;
      if (!this._res) {
        this.shadowRoot.innerHTML = `<ha-card><div class="content">Parkeren Nijmegen entiteiten niet gevonden.</div></ha-card>`;
        return;
      }
      const cfg = this._config;
      const showStart = cfg.show_start_time !== false;
      const showEnd = cfg.show_end_time !== false;
      const favs = this._favs();
      const normPlate = this._normPlate(this._vals.plate);
      const isFav = this._isFav(normPlate);
      const zoneLabel = this._zoneLabel();
      const balLabel = this._balanceLabel();

      this.shadowRoot.innerHTML = `
        <style>${CARD1_STYLES}</style>
        <ha-card>
          <div class="content">
            ${cfg.title ? `<div style="font-size:18px;font-weight:500;margin-bottom:12px;">${cfg.title}</div>` : ''}
            ${this._status ? `<div class="status ${this._statusType}">${this._status}</div>` : ''}
            ${zoneLabel ? `<div class="zone-row">
              <span>${zoneLabel}</span>
              ${balLabel ? `<span class="balance">${balLabel}</span>` : ''}
            </div>` : ''}
            <div class="chips">${favs.map(f => {
              const sel = this._normPlate(f.license_plate) === normPlate;
              const eName = (f.name || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
              const ePlate = f.license_plate.replace(/"/g, '&quot;');
              return `<span class="chip${sel ? ' active' : ''}" data-act="sel" data-plate="${ePlate}" data-name="${eName}">
                ${f.name || f.license_plate}
              </span>`;
            }).join('')}
              <span class="chip" id="toggle-add-fav" style="border-style:dashed;">+ Favoriet</span>
            </div>
            ${this._showAddFav ? `<div class="add-fav-form">
              <ha-input id="fav-plate" appearance="material"></ha-input>
              <ha-input id="fav-name" appearance="material" style="margin-top:8px;"></ha-input>
              <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:8px;">
                <ha-button id="fav-cancel">Annuleren</ha-button>
                <ha-button id="fav-save" unelevated>Opslaan</ha-button>
              </div>
            </div>` : ''}
            <div class="row">
              <ha-input id="plate" appearance="material" with-clear autocomplete="off"></ha-input>
            </div>
            ${(showStart || showEnd) ? `<div class="datetime-row">
              ${showStart ? `<ha-input id="start" appearance="material" type="datetime-local"></ha-input>` : ''}
              ${showEnd ? `<ha-input id="end" appearance="material" type="datetime-local"></ha-input>` : ''}
            </div>` : ''}
            <div class="actions">
              <span>
                ${(normPlate && !isFav) ? `<ha-button id="addfav">+ Favoriet</ha-button>` : ''}
                ${(normPlate && isFav) ? `<ha-button id="rmfav" class="warning">− Favoriet</ha-button>` : ''}
              </span>
              <ha-button id="start-btn" unelevated ?disabled="${this._busy}">
                ${this._busy ? 'Bezig…' : 'Start reservering'}
              </ha-button>
            </div>
          </div>
        </ha-card>`;

      // Set properties that don't work as HTML attributes
      const q = id => this.shadowRoot.getElementById(id);
      const plate = q('plate');
      if (plate) { plate.label = 'Kenteken'; plate.value = this._vals.plate; plate.placeholder = 'AB12CD'; }
      const start = q('start');
      if (start) { start.label = 'Starttijd'; start.value = this._vals.start; }
      const end = q('end');
      if (end) { end.label = 'Eindtijd'; end.value = this._vals.end; }
      const startBtn = q('start-btn');
      if (startBtn) startBtn.disabled = this._busy;

      // Events
      plate?.addEventListener('input', e => { this._vals.plate = e.target.value ?? e.detail?.value ?? ''; });
      plate?.addEventListener('change', e => { this._vals.plate = e.target.value ?? e.detail?.value ?? ''; });
      start?.addEventListener('change', e => {
        this._vals.start = e.target.value ?? e.detail?.value ?? '';
        const s = parseDT(this._vals.start), en = parseDT(this._vals.end);
        if (s && en && s.toDateString() !== en.toDateString()) {
          const ne = new Date(en);
          ne.setFullYear(s.getFullYear(), s.getMonth(), s.getDate());
          this._vals.end = fmtLocal(ne);
          this._render();
        }
      });
      end?.addEventListener('change', e => { this._vals.end = e.target.value ?? e.detail?.value ?? ''; });
      q('start-btn')?.addEventListener('click', () => void this._start());
      q('addfav')?.addEventListener('click', () => {
        this._addFavVals = { plate: normPlate, name: '' };
        this._showAddFav = true;
        this._render();
      });
      q('rmfav')?.addEventListener('click', () => {
        const fav = this._favs().find(f => this._normPlate(f.license_plate) === normPlate);
        if (fav) void this._rmFav(fav.license_plate);
      });
      q('toggle-add-fav')?.addEventListener('click', e => {
        e.stopPropagation();
        this._showAddFav = !this._showAddFav;
        this._render();
      });
      const favPlate = q('fav-plate');
      const favName = q('fav-name');
      if (favPlate) { favPlate.label = 'Kenteken'; favPlate.value = this._addFavVals.plate; favPlate.placeholder = 'AB12CD'; }
      if (favName) { favName.label = 'Naam (optioneel)'; favName.value = this._addFavVals.name; }
      favPlate?.addEventListener('input', e => { this._addFavVals.plate = e.target.value ?? ''; });
      favName?.addEventListener('input', e => { this._addFavVals.name = e.target.value ?? ''; });
      q('fav-save')?.addEventListener('click', () => {
        void this._addFav(this._normPlate(this._addFavVals.plate), this._addFavVals.name.trim());
      });
      q('fav-cancel')?.addEventListener('click', () => {
        this._showAddFav = false;
        this._addFavVals = { plate: '', name: '' };
        this._render();
      });

      this.shadowRoot.querySelectorAll('[data-act]').forEach(el => {
        el.addEventListener('click', e => {
          e.stopPropagation();
          if (el.dataset.act === 'sel') this._selectFav(el.dataset.plate);
        });
      });
    }

    getCardSize() { return 4; }

    static getStubConfig() {
      return { type: 'custom:parkeren-reservering-card', show_name: true, show_start_time: true, show_end_time: true };
    }
  }

  customElements.define('parkeren-reservering-card', ParkerenReserveringCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: 'parkeren-reservering-card',
    name: 'Parkeren Nijmegen – Nieuwe reservering',
    description: 'Maak een bezoekersparkeerreservering aan via de Parkeren Nijmegen integratie.',
  });

  // ── Card 2: Active Reservations ──────────────────────────────────────────

  const CARD2_STYLES = `
    :host { display: block; }
    .content { padding: 16px; }
    .status { padding: 8px 12px; border-radius: 8px; margin-bottom: 12px; font-size: 14px; }
    .status.success { background: var(--success-color, #4caf50); color: #fff; }
    .status.warning { background: var(--warning-color, #ff9800); color: #fff; }
    .empty { font-size: 14px; color: var(--secondary-text-color); }
    .res {
      border: 1px solid var(--divider-color); border-radius: var(--ha-card-border-radius, 12px);
      padding: 12px; margin-bottom: 8px;
    }
    .res-name { font-weight: 600; margin-bottom: 4px; }
    .res-detail { font-size: 13px; color: var(--secondary-text-color); }
    .res-times { font-size: 13px; color: var(--secondary-text-color); margin: 6px 0; }
    .res-actions { display: flex; justify-content: flex-end; margin-top: 8px; }
    .badge { display: inline-block; font-size: 11px; padding: 2px 7px; border-radius: 10px; margin-left: 6px; vertical-align: middle; }
    .badge.active { background: var(--success-color, #4caf50); color: #fff; }
    .badge.planned { background: var(--info-color, #2196f3); color: #fff; }
  `;

  class ParkerenActiefCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
      this._hass = null;
      this._config = null;
      this._busy = new Set();
      this._status = null;
      this._statusType = 'info';
      this._stOut = null;
      this._resList = null;
      this._lastResKey = null;
      this._res = null;
    }

    setConfig(config) { this._config = config; this._render(); }

    set hass(hass) {
      this._hass = hass;
      this._res = this._res || resolveIntegration(hass);
      if (!this._res) { this._render(); return; }
      const key = `${hass.states[this._res.ACTIVE_ENTITY]?.state}:${hass.states[this._res.PLANNED_ENTITY]?.state}`;
      if (key === this._lastResKey) return;
      this._lastResKey = key;
      void this._fetchReservations();
      this._render();
    }

    async _fetchReservations() {
      if (!this._res) return;
      try {
        const result = await this._hass.callService(DOMAIN, 'list_reservations', { device_id: this._res.deviceId }, undefined, false, true);
        this._resList = result?.response?.reservations || result?.reservations || [];
        this._render();
      } catch (e) {
        console.error('parkeren: list_reservations failed', e);
        this._resList = this._resList || [];
      }
    }

    _setStatus(msg, type = 'info', ms = 0) {
      if (this._stOut) clearTimeout(this._stOut);
      this._status = msg; this._statusType = type;
      if (ms) this._stOut = setTimeout(() => { this._status = null; this._render(); }, ms);
      this._render();
    }

    async _end(id) {
      if (this._busy.has(id) || !this._res) return;
      this._busy.add(id); this._render();
      try {
        await this._hass.callService(DOMAIN, 'end_reservation', { device_id: this._res.deviceId, reservation_id: id });
        this._resList = (this._resList || []).filter(r => (r.id || r.reservation_id) !== id);
        this._setStatus('Reservering beëindigd', 'success', 5000);
      } catch (e) {
        this._setStatus('Fout: ' + (e?.message || String(e)), 'warning');
      } finally {
        this._busy.delete(id); this._render();
      }
    }

    _render() {
      if (!this._config || !this._hass) return;
      if (!this._res) {
        this.shadowRoot.innerHTML = `<ha-card><div class="content">Parkeren Nijmegen entiteiten niet gevonden.</div></ha-card>`;
        return;
      }
      const reservations = this._resList;

      this.shadowRoot.innerHTML = `
        <style>${CARD2_STYLES}</style>
        <ha-card>
          <div class="content">
            ${this._config.title ? `<div style="font-size:18px;font-weight:500;margin-bottom:12px;">${this._config.title}</div>` : ''}
            ${this._status ? `<div class="status ${this._statusType}">${this._status}</div>` : ''}
            ${reservations === null ? '<div class="empty">Reserveringen laden…</div>' : ''}
            ${reservations !== null && !reservations.length ? '<div class="empty">Geen reserveringen</div>' : ''}
            ${(reservations || []).map(r => {
              const name = r.name || r.favorite_name || '';
              const display = name || r.license_plate || r.reservation_id;
              const isActive = r.is_active === true;
              const rid = r.id || r.reservation_id;
              return `<div class="res">
                <div class="res-name">${display}<span class="badge ${isActive ? 'active' : 'planned'}">${isActive ? 'Actief' : 'Gepland'}</span></div>
                ${(name && r.license_plate) ? `<div class="res-detail">Kenteken: ${r.license_plate}</div>` : ''}
                <div class="res-times">${fmtDisplay(r.start_time)} → ${fmtDisplay(r.end_time)}</div>
                <div class="res-actions">
                  <ha-button data-id="${rid}" class="end-btn">Stop reservering</ha-button>
                </div>
              </div>`;
            }).join('')}
          </div>
        </ha-card>`;

      this.shadowRoot.querySelectorAll('.end-btn').forEach(btn => {
        if (this._busy.has(btn.dataset.id)) btn.disabled = true;
        btn.addEventListener('click', () => void this._end(btn.dataset.id));
      });
    }

    getCardSize() { return 3; }

    static getStubConfig() {
      return { type: 'custom:parkeren-actief-card' };
    }
  }

  customElements.define('parkeren-actief-card', ParkerenActiefCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: 'parkeren-actief-card',
    name: 'Parkeren Nijmegen – Actieve reserveringen',
    description: 'Beheer actieve bezoekersparkeerreserveringen via de Parkeren Nijmegen integratie.',
  });
})();
