const tokenStore = window.sessionStorage;

const state = {
  token: tokenStore.getItem("vpn-panel-token") || "",
  overview: null,
  users: [],
  selectedUser: null,
  selectedFile: "readme",
};

const authLayer = document.getElementById("authLayer");
const authForm = document.getElementById("authForm");
const authError = document.getElementById("authError");
const tokenInput = document.getElementById("tokenInput");
const refreshButton = document.getElementById("refreshButton");
const createUserForm = document.getElementById("createUserForm");
const createUserInput = document.getElementById("createUserInput");
const serviceGrid = document.getElementById("serviceGrid");
const proxyPanel = document.getElementById("proxyPanel");
const loadPanel = document.getElementById("loadPanel");
const rescueFeeds = document.getElementById("rescueFeeds");
const usersList = document.getElementById("usersList");
const userCount = document.getElementById("userCount");
const selectedUserTitle = document.getElementById("selectedUserTitle");
const selectedUserMeta = document.getElementById("selectedUserMeta");
const quotaForm = document.getElementById("quotaForm");
const quotaInput = document.getElementById("quotaInput");
const disableQuotaButton = document.getElementById("disableQuotaButton");
const resetUsageButton = document.getElementById("resetUsageButton");
const suspendUserButton = document.getElementById("suspendUserButton");
const resumeUserButton = document.getElementById("resumeUserButton");
const fileTabs = document.getElementById("fileTabs");
const configViewer = document.getElementById("configViewer");
const copySubscriptionButton = document.getElementById("copySubscriptionButton");
const downloadZipButton = document.getElementById("downloadZipButton");
const deleteUserButton = document.getElementById("deleteUserButton");

const FILE_ORDER = ["readme", "xray", "singbox", "hy2", "wg", "awg", "proxy", "mtproto", "uris", "subscription_url"];
const FILE_LABELS = {
  readme: "README",
  xray: "xray",
  singbox: "singbox",
  hy2: "hy2",
  wg: "wg",
  awg: "awg",
  proxy: "proxy",
  mtproto: "mtproto",
  uris: "uris",
  subscription_url: "sub url",
};

function formatBytes(value) {
  const amount = Number(value || 0);
  if (!Number.isFinite(amount) || amount <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB", "PB"];
  let current = amount;
  let index = 0;
  while (current >= 1024 && index < units.length - 1) {
    current /= 1024;
    index += 1;
  }
  return index === 0 ? `${Math.round(current)} ${units[index]}` : `${current.toFixed(1)} ${units[index]}`;
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (state.token) {
    headers.set("Authorization", `Bearer ${state.token}`);
  }

  const response = await fetch(path, { ...options, headers });
  if (response.status === 401 || response.status === 503) {
    authLayer.classList.remove("is-hidden");
    throw new Error((await response.json().catch(() => ({}))).error || "Unauthorized");
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error || `HTTP ${response.status}`);
  }
  return response.json();
}

async function downloadWithAuth(path, filenameHint) {
  const response = await fetch(path, {
    headers: state.token ? { Authorization: `Bearer ${state.token}` } : {},
  });
  if (!response.ok) {
    throw new Error(`Download failed: ${response.status}`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filenameHint;
  link.click();
  URL.revokeObjectURL(url);
}

function setAuthVisible(visible) {
  authLayer.classList.toggle("is-hidden", !visible);
}

function servicePill(stateValue) {
  const normalized = String(stateValue || "unknown").toLowerCase();
  return `<span class="state-pill ${normalized}">${normalized}</span>`;
}

function renderOverview() {
  const services = state.overview?.status?.services || [];
  const ports = state.overview?.status?.ports || {};
  const load = state.overview?.status?.load || {};
  const feeds = state.overview?.rescue_feeds || [];

  serviceGrid.innerHTML = services
    .map(
      (item) => `
      <div class="service-row">
        <div>
          <div class="service-name">${item.name}</div>
          <div class="muted">${item.unit}</div>
        </div>
        ${servicePill(item.state)}
      </div>
    `,
    )
    .join("");

  const proxyLines = [
    ["HTTP proxy", ports.http_proxy || "n/a"],
    ["SOCKS5 proxy", ports.socks5_proxy || "n/a"],
    ["MTProto", ports.mtproto || "n/a"],
    ["Subscription", ports.subscription || "n/a"],
  ];
  proxyPanel.innerHTML = proxyLines
    .map(([label, value]) => `<div class="proxy-line"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");

  const loadLines = [
    ["CPU load", `${load.cpu?.load1 ?? "n/a"} / ${load.cpu?.load5 ?? "n/a"} / ${load.cpu?.load15 ?? "n/a"}`],
    ["Memory", `${formatBytes(load.memory?.used_bytes)} / ${formatBytes(load.memory?.total_bytes)}${load.memory?.used_percent != null ? ` (${load.memory.used_percent}%)` : ""}`],
    ["Disk", `${formatBytes(load.disk?.used_bytes)} / ${formatBytes(load.disk?.total_bytes)}${load.disk?.used_percent != null ? ` (${load.disk.used_percent}%)` : ""}`],
    ["Network RX", formatBytes(load.network?.rx_bytes)],
    ["Network TX", formatBytes(load.network?.tx_bytes)],
  ];
  loadPanel.innerHTML = loadLines
    .map(([label, value]) => `<div class="proxy-line"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");

  rescueFeeds.innerHTML = feeds
    .map((item) => {
      const mirrorLinks = item.mirrors
        .map((mirror, index) => `<a href="${mirror}" target="_blank" rel="noreferrer">Mirror ${index + 1}</a>`)
        .join("");
      return `
        <div class="rescue-feed">
          <h3>${item.title}</h3>
          <div class="muted">${item.description}</div>
          <div class="feed-links">
            <a href="${item.primary}" target="_blank" rel="noreferrer">Primary feed</a>
            ${mirrorLinks}
          </div>
        </div>
      `;
    })
    .join("");
}

function renderUsers() {
  const suspended = state.users.filter((user) => user.state === "suspended").length;
  userCount.textContent = `${state.users.length} total, ${suspended} suspended`;
  if (!state.users.length) {
    usersList.innerHTML = `<div class="muted">No users yet. Create the first identity from the top form.</div>`;
    return;
  }
  usersList.innerHTML = state.users
    .map(
      (user) => `
      <button class="user-row ${state.selectedUser?.name === user.name ? "is-active" : ""}" data-user="${user.name}">
        <div>
          <div class="user-row-head">
            <div class="user-name">${user.name}</div>
            <span class="state-pill ${user.state}">${user.state}</span>
          </div>
          <span class="user-sub">${user.subscription_url}</span>
        </div>
        <div class="user-traffic">
          <strong>${user.used_human || "0 B"}</strong>
          <span class="muted">${user.quota_human || "unlimited"}</span>
        </div>
      </button>
    `,
    )
    .join("");

  usersList.querySelectorAll("[data-user]").forEach((node) => {
    node.addEventListener("click", () => selectUser(node.getAttribute("data-user")));
  });
}

function renderSelectedUser() {
  const user = state.selectedUser;
  const enabled = Boolean(user);
  copySubscriptionButton.disabled = !enabled;
  downloadZipButton.disabled = !enabled;
  deleteUserButton.disabled = !enabled;
  disableQuotaButton.disabled = !enabled;
  resetUsageButton.disabled = !enabled;
  suspendUserButton.disabled = !enabled || user?.state === "suspended";
  resumeUserButton.disabled = !enabled || user?.state !== "suspended";

  if (!user) {
    selectedUserTitle.textContent = "No user selected";
    selectedUserMeta.innerHTML = "";
    fileTabs.innerHTML = "";
    quotaInput.value = "";
    configViewer.textContent = "Select a user to inspect generated configs.";
    return;
  }

  selectedUserTitle.textContent = user.name;
  quotaInput.value = user.quota_bytes ? String((user.quota_bytes / (1024 ** 3)).toFixed(2).replace(/\.00$/, "")) : "";
  selectedUserMeta.innerHTML = `
    <div class="meta-item"><span>Created</span><strong>${user.created}</strong></div>
    <div class="meta-item"><span>State</span><strong>${user.state}</strong></div>
    <div class="meta-item"><span>Traffic</span><strong>${formatBytes(user.usage?.total_bytes ?? user.used_bytes)}</strong></div>
    <div class="meta-item"><span>Quota</span><strong>${user.quota_human || "unlimited"}</strong></div>
    <div class="meta-item"><span>Subscription URL</span><strong>${user.subscription_url}</strong></div>
    <div class="meta-item"><span>Protocols</span><strong>${user.protocols}</strong></div>
    <div class="meta-item"><span>Shareable URIs</span><strong>${user.shareable_uris.length}</strong></div>
    <div class="meta-item"><span>Updated</span><strong>${user.usage?.updated_at || user.updated_at || "n/a"}</strong></div>
  `;

  fileTabs.innerHTML = FILE_ORDER.map((kind) => {
    const active = state.selectedFile === kind ? "ghost" : "";
    return `<button class="${active}" data-kind="${kind}">${FILE_LABELS[kind]}</button>`;
  }).join("");

  fileTabs.querySelectorAll("[data-kind]").forEach((node) => {
    node.addEventListener("click", () => loadFile(node.getAttribute("data-kind")));
  });
}

async function loadDashboard() {
  state.overview = await api("/api/overview");
  const usersPayload = await api("/api/users");
  state.users = usersPayload.items || [];
  renderOverview();
  renderUsers();

  if (!state.users.length) {
    state.selectedUser = null;
    renderSelectedUser();
    return;
  }

  const target = state.users.find((user) => user.name === state.selectedUser?.name)?.name || state.users[0].name;
  await selectUser(target, { silent: true });
}

async function selectUser(name, { silent = false } = {}) {
  state.selectedUser = await api(`/api/users/${encodeURIComponent(name)}`);
  renderUsers();
  renderSelectedUser();
  await loadFile(state.selectedFile, { silent });
}

async function loadFile(kind, { silent = false } = {}) {
  if (!state.selectedUser) {
    return;
  }
  state.selectedFile = kind;
  renderSelectedUser();
  try {
    const payload = await api(`/api/users/${encodeURIComponent(state.selectedUser.name)}/file/${encodeURIComponent(kind)}`);
    configViewer.textContent = payload.content || "Binary file. Use download ZIP.";
  } catch (error) {
    if (!silent) {
      configViewer.textContent = String(error.message || error);
    }
  }
}

authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  state.token = tokenInput.value.trim();
  tokenStore.setItem("vpn-panel-token", state.token);
  authError.textContent = "";
  try {
    await loadDashboard();
    setAuthVisible(false);
  } catch (error) {
    authError.textContent = String(error.message || error);
  }
});

refreshButton.addEventListener("click", async () => {
  await loadDashboard();
});

createUserForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = createUserInput.value.trim();
  if (!name) {
    return;
  }
  await api("/api/users", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
  createUserInput.value = "";
  state.selectedFile = "readme";
  await loadDashboard();
  await selectUser(name);
});

quotaForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.selectedUser) {
    return;
  }
  const quotaGb = quotaInput.value.trim();
  if (!quotaGb) {
    return;
  }
  await api(`/api/users/${encodeURIComponent(state.selectedUser.name)}/quota`, {
    method: "POST",
    body: JSON.stringify({ quota_gb: Number(quotaGb) }),
  });
  await selectUser(state.selectedUser.name);
  await loadDashboard();
});

disableQuotaButton.addEventListener("click", async () => {
  if (!state.selectedUser) {
    return;
  }
  await api(`/api/users/${encodeURIComponent(state.selectedUser.name)}/quota`, {
    method: "POST",
    body: JSON.stringify({ disable: true }),
  });
  await selectUser(state.selectedUser.name);
  await loadDashboard();
});

resetUsageButton.addEventListener("click", async () => {
  if (!state.selectedUser) {
    return;
  }
  await api(`/api/users/${encodeURIComponent(state.selectedUser.name)}/reset-usage`, { method: "POST" });
  await selectUser(state.selectedUser.name);
  await loadDashboard();
});

suspendUserButton.addEventListener("click", async () => {
  if (!state.selectedUser) {
    return;
  }
  await api(`/api/users/${encodeURIComponent(state.selectedUser.name)}/suspend`, { method: "POST" });
  await selectUser(state.selectedUser.name);
  await loadDashboard();
});

resumeUserButton.addEventListener("click", async () => {
  if (!state.selectedUser) {
    return;
  }
  await api(`/api/users/${encodeURIComponent(state.selectedUser.name)}/resume`, { method: "POST" });
  await selectUser(state.selectedUser.name);
  await loadDashboard();
});

copySubscriptionButton.addEventListener("click", async () => {
  if (!state.selectedUser) {
    return;
  }
  await navigator.clipboard.writeText(state.selectedUser.subscription_url);
  copySubscriptionButton.textContent = "Copied";
  window.setTimeout(() => {
    copySubscriptionButton.textContent = "Copy sub URL";
  }, 1200);
});

downloadZipButton.addEventListener("click", async () => {
  if (!state.selectedUser) {
    return;
  }
  await downloadWithAuth(`/download/users/${encodeURIComponent(state.selectedUser.name)}/zip`, `${state.selectedUser.name}.zip`);
});

deleteUserButton.addEventListener("click", async () => {
  if (!state.selectedUser) {
    return;
  }
  if (!window.confirm(`Delete user ${state.selectedUser.name}?`)) {
    return;
  }
  await api(`/api/users/${encodeURIComponent(state.selectedUser.name)}`, { method: "DELETE" });
  state.selectedUser = null;
  state.selectedFile = "readme";
  await loadDashboard();
});

window.addEventListener("load", async () => {
  tokenInput.value = state.token;
  if (!state.token) {
    setAuthVisible(true);
    return;
  }
  try {
    await loadDashboard();
    setAuthVisible(false);
  } catch (error) {
    authError.textContent = String(error.message || error);
    setAuthVisible(true);
  }
});

window.setInterval(async () => {
  if (!state.token) {
    return;
  }
  try {
    await loadDashboard();
  } catch (_error) {
    // Leave the current screen in place if background refresh fails.
  }
}, 30000);
