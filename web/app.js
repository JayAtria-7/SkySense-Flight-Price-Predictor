const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const state = {
  meta: null,
  lastEcho: null,
  lastResponse: null,
  routeHint: null,
};

function currency(n) {
  try { return new Intl.NumberFormat(undefined, { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n); }
  catch { return Math.round(n).toLocaleString(); }
}

async function loadMeta() {
  let ok = false;
  try {
    const res = await fetch('/api/metadata');
    if (res.ok) {
      state.meta = await res.json();
      ok = true;
    }
  } catch {}
  if (!ok) {
    // Fallback allowed values if API not reachable, to keep UI usable
    state.meta = {
      allowed: {
        city: ['Delhi','Mumbai','Bangalore','Kolkata','Hyderabad','Chennai'],
        airline: ['Unknown','Vistara','Air_India','Indigo','GO_FIRST','AirAsia','SpiceJet'],
        time: ['Unknown','Early_Morning','Morning','Afternoon','Evening','Night','Late_Night'],
        stops: ['zero','one','two_or_more'],
        class: ['Economy','Business'],
      },
      defaults: { global_duration_median: 2.2 },
    };
  }
  const { allowed, defaults } = state.meta;

  const cityOpts = ['<option value="">Select</option>', ...allowed.city.map(c => `<option value="${c}">${c}</option>`)].join('');
  $('#source_city').innerHTML = cityOpts;
  $('#destination_city').innerHTML = cityOpts;

  const airlineOpts = ['<option value="">Unknown</option>', ...allowed.airline.filter(a=>a!=='Unknown').map(a => `<option value="${a}">${a}</option>`)].join('');
  $('#airline').innerHTML = airlineOpts;

  const timeOpts = ['<option value="">Unknown</option>', ...allowed.time.filter(t=>t!=='Unknown').map(t => `<option value="${t}">${t}</option>`)].join('');
  $('#departure_time').innerHTML = timeOpts;
  $('#arrival_time').innerHTML = timeOpts;
}

function validate() {
  const errors = [];
  const src = $('#source_city').value;
  const dst = $('#destination_city').value;
  const stops = $('#stops').value;
  const daysLeft = $('#days_left').value;

  if (!src) errors.push('Source City is required.');
  if (!dst) errors.push('Destination City is required.');
  if (src && dst && src === dst) errors.push('Source and destination can’t be the same.');
  if (!stops) errors.push('Stops is required.');

  if (daysLeft === '' || daysLeft === null) errors.push('Days Left is required.');
  else if (!Number.isInteger(Number(daysLeft)) || Number(daysLeft) < 0) errors.push('Days left must be an integer 0 or greater.');

  const dur = $('#duration').value;
  if (dur !== '' && Number(dur) <= 0) errors.push('Duration must be greater than 0.');

  const box = $('#form-errors');
  box.innerHTML = errors.map(e => `<div>• ${e}</div>`).join('');
  $('#predict').disabled = errors.length > 0;
  return errors.length === 0;
}

function collectPayload() {
  const payload = {
    source_city: $('#source_city').value,
    destination_city: $('#destination_city').value,
    class: $('input[name="class"]:checked').value,
    stops: $('#stops').value,
    days_left: Number($('#days_left').value),
    duration: $('#duration').value === '' ? null : Number($('#duration').value),
    airline: $('#airline').value || null,
    departure_time: $('#departure_time').value || null,
    arrival_time: $('#arrival_time').value || null,
    flight: $('#flight').value || null,
  };
  try { localStorage.setItem('flight-form', JSON.stringify(payload)); } catch {}
  return payload;
}

async function updateDurationHint() {
  const dur = $('#duration').value;
  const src = $('#source_city').value;
  const dst = $('#destination_city').value;
  const hint = $('#duration_hint');
  const badge = $('#duration_imputed');
  if (dur || !src || !dst) {
    hint.textContent = '';
    badge.classList.add('hidden');
    return;
  }
  try {
    const res = await fetch(`/api/route-median?source_city=${encodeURIComponent(src)}&destination_city=${encodeURIComponent(dst)}`);
    if (res.ok) {
      const data = await res.json();
      const val = data.route_median ?? data.global_median;
      state.routeHint = val;
      hint.textContent = `Suggested duration (median): ${val?.toFixed ? val.toFixed(2) : val} h`;
      badge.classList.remove('hidden');
    }
  } catch {}
}

async function predict(payload) {
  const btn = $('#predict');
  btn.disabled = true; btn.textContent = 'Predicting…';
  try {
    const res = await fetch('/api/predict', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    state.lastEcho = data.echo;
    state.lastResponse = data;
    renderResult(data);
  } catch (e) {
    $('#form-errors').innerHTML = `<div>${String(e)}</div>`;
  } finally {
    btn.textContent = 'Predict';
    validate();
  }
}

function renderResult(data) {
  $('#result').classList.remove('hidden');
  $('#predicted').textContent = currency(data.predicted_price);
  $('#range').textContent = `${currency(data.lower_bound)} – ${currency(data.upper_bound)}`;
  $('#contributors').innerHTML = data.top_contributors.map(c => `<li>${c.feature}: ${c.direction}${c.contribution.toFixed(0)}</li>`).join('');
  const assumptions = Object.entries(data.assumptions_used).map(([k,v]) => `<li>${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}</li>`).join('');
  $('#assumptions').innerHTML = assumptions || '<li>None</li>';

  // Scenario compare table: append a row when predictions are triggered from scenario chips
  const table = $('#scenario-table');
  if (state.lastEcho && state._scenarioLabel) {
    table.classList.remove('hidden');
    const tr = document.createElement('tr');
    const assumptionsBrief = Object.keys(data.assumptions_used).length
      ? Object.entries(data.assumptions_used).map(([k,v]) => `${k}=${typeof v==='object'?v.value:v}`).join('; ')
      : '—';
    tr.innerHTML = `<td>${state._scenarioLabel}</td><td>${currency(data.predicted_price)}</td><td>${assumptionsBrief}</td>`;
    table.querySelector('tbody').appendChild(tr);
    state._scenarioLabel = null; // reset
  }
}

function copyJSON() {
  if (!state.lastResponse) return;
  navigator.clipboard.writeText(JSON.stringify(state.lastResponse, null, 2));
}

function copyCSV() {
  if (!state.lastResponse) return;
  const flat = {
    predicted_price: state.lastResponse.predicted_price,
    lower_bound: state.lastResponse.lower_bound,
    upper_bound: state.lastResponse.upper_bound,
    ...state.lastResponse.echo,
  };
  const keys = Object.keys(flat);
  const csv = keys.join(',') + '\n' + keys.map(k => flat[k]).join(',');
  navigator.clipboard.writeText(csv);
}

function applyScenario(code) {
  const map = {
    days_1: () => $('#days_left').value = 1,
    days_7: () => $('#days_left').value = 7,
    days_14: () => $('#days_left').value = 14,
    days_30: () => $('#days_left').value = 30,
    class_econ: () => $$('input[name="class"]').find(r => r.value === 'Economy').checked = true,
    class_bus: () => $$('input[name="class"]').find(r => r.value === 'Business').checked = true,
    stops_zero: () => $('#stops').value = 'zero',
    stops_one: () => $('#stops').value = 'one',
  };
  if (map[code]) { map[code](); validate(); }
}

function bind() {
  // Preset chips
  $$('.chips [data-days]').forEach(btn => btn.addEventListener('click', () => {
    $('#days_left').value = btn.dataset.days; validate();
  }));

  // Scenario chips
  $$('.scenarios [data-scenario]').forEach(btn => btn.addEventListener('click', async () => {
    applyScenario(btn.dataset.scenario);
    if (validate()) {
      state._scenarioLabel = btn.textContent.trim();
      await predict(collectPayload());
    }
  }));

  // Field validation
  ['change','input','blur'].forEach(ev => {
    ['#source_city','#destination_city','#stops','#days_left','#duration','#airline','#departure_time','#arrival_time'].forEach(sel => {
      $(sel).addEventListener(ev, validate);
    });
  });
  ['#source_city','#destination_city','#duration'].forEach(sel => {
    $(sel).addEventListener('change', updateDurationHint);
    $(sel).addEventListener('input', updateDurationHint);
  });
  $$('input[name="class"]').forEach(r => r.addEventListener('change', validate));

  // Buttons
  $('#predict-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!validate()) return;
    const payload = collectPayload();
    await predict(payload);
  });

  $('#reset').addEventListener('click', () => setTimeout(validate, 0));
  $('#clear').addEventListener('click', () => {
    $('#predict-form').reset();
    validate();
    updateDurationHint();
    try { localStorage.removeItem('flight-form'); } catch {}
  });

  $('#edit-assumptions').addEventListener('click', () => {
    document.getElementById('duration').focus();
  });
  $('#copy-json').addEventListener('click', copyJSON);
  $('#copy-csv').addEventListener('click', copyCSV);

  // Swap cities
  $('#swap').addEventListener('click', () => {
    const s = $('#source_city');
    const d = $('#destination_city');
    const tmp = s.value; s.value = d.value; d.value = tmp;
    validate(); updateDurationHint();
  });
}

window.addEventListener('DOMContentLoaded', async () => {
  await loadMeta();
  // Restore saved form state if available
  try {
    const saved = JSON.parse(localStorage.getItem('flight-form') || 'null');
    if (saved) {
      $('#source_city').value = saved.source_city || '';
      $('#destination_city').value = saved.destination_city || '';
      $$('input[name="class"]').forEach(r => r.checked = (r.value === (saved.class || 'Economy')));
      $('#stops').value = saved.stops || '';
      $('#days_left').value = (saved.days_left ?? '');
      $('#duration').value = (saved.duration ?? '') === null ? '' : (saved.duration ?? '');
      $('#airline').value = saved.airline || '';
      $('#departure_time').value = saved.departure_time || '';
      $('#arrival_time').value = saved.arrival_time || '';
      $('#flight').value = saved.flight || '';
    }
  } catch {}
  bind();
  validate();
  updateDurationHint();
});
