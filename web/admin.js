const tokenStore = window.sessionStorage;

const state = {
  token: tokenStore.getItem("vpn-panel-token") || "",
  overview: null,
  users: [],
  selectedUser: null,
  selectedFile: "readme",
  userFilter: "all",
  searchQuery: "",
  toastTimer: null,
};

const authLayer = document.getElementById("authLayer");
const authForm = document.getElementById("authForm");
const authError = document.getElementById("authError");
const tokenInput = document.getElementById("tokenInput");
const refreshButton = document.getElementById("refreshButton");
const createUserForm = document.getElementById("createUserForm");
const createUserInput = document.getElementById("createUserInput");
const summaryGrid = document.getElementById("summaryGrid");
const serviceGrid = document.getElementById("serviceGrid");
const proxyPanel = document.getElementById("proxyPanel");
const loadPanel = document.getElementById("loadPanel");
const topUsagePanel = document.getElementById("topUsagePanel");
const rescueFeeds = document.getElementById("rescueFeeds");
const usersList = document.getElementById("usersList");
const userCount = document.getElementById("userCount");
const userSearchInput = document.getElementById("userSearchInput");
const userFilterTabs = document.getElementById("userFilterTabs");
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
const navToggleButton = document.getElementById("navToggleButton");
const mobileBackdrop = document.getElementById("mobileBackdrop");
const actionToast = document.getElementById("actionToast");

const FILE_ORDER = ["readme", "xray", "singbox", "hy2", "wg", "awg", "proxy", "mtproto", "uris", "subscription_url"];
const FILE_LABELS = {
  readme: "README",
  xray: "Xray",
  singbox: "sing-box",
  hy2: "Hysteria2",
  wg: "WireGuard",
  awg: "AmneziaWG",
  proxy: "Proxy",
  mtproto: "MTProto",
  uris: "URIs",
  subscription_url: "Sub URL",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

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

function clampPercent(value) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) {
    return null;
  }
  return Math.max(0, Math.min(100, Math.round(amount)));
}

function showToast(message, kind = "success") {
  window.clearTimeout(state.toastTimer);
  actionToast.textContent = message;
  actionToast.className = `action-toast is-visible is-${kind}`;
  state.toastTimer = window.setTimeout(() => {
    actionToast.className = "action-toast";
  }, 2200);
}

function setNavOpen(open) {
  const next = Boolean(open);
  document.body.classList.toggle("nav-open", next);
  navToggleButton.setAttribute("aria-expanded", String(next));
}

function setAuthVisible(visible) {
  authLayer.classList.toggle("is-hidden", !visible);
}

function servicePill(stateValue) {
  const normalized = String(stateValue || "unknown").toLowerCase();
  return `<span class="state-pill ${escapeHtml(normalized)}">${escapeHtml(normalized)}</span>`;
}

function busyState(control, busy) {
  if (!control) {
    return () => {};
  }
  const previousDisabled = control.disabled;
  const previousText = control.textContent;
  if (busy) {
    control.disabled = true;
    control.textContent = "Working...";
  }
  return () => {
    control.disabled = previousDisabled;
    control.textContent = previousText;
  };
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
    setAuthVisible(true);
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

function getVisibleUsers() {
  const query = state.searchQuery.trim().toLowerCase();
  return state.users.filter((user) => {
    if (state.userFilter !== "all" && user.state !== state.userFilter) {
      return false;
    }
    if (!query) {
      return true;
    }
    return [user.name, user.subscription_url, user.state].some((value) => String(value || "").toLowerCase().includes(query));
  });
}

function syncFilterButtons() {
  userFilterTabs.querySelectorAll("[data-filter]").forEach((node) => {
    const active = node.getAttribute("data-filter") === state.userFilter;
    node.classList.toggle("is-active", active);
    node.setAttribute("aria-selected", String(active));
  });
}

function renderOverview() {
  const status = state.overview?.status || {};
  const ports = status.ports || {};
  const load = status.load || {};
  const sub = state.overview?.sub || {};
  const feeds = state.overview?.rescue_feeds || [];
  const topUsage = status.top_usage || [];

  const summaryItems = [
    {
      label: "Users",
      value: status.users ?? 0,
      hint: `${status.active_users ?? 0} active users`,
    },
    {
      label: "Suspended",
      value: status.suspended_users ?? 0,
      hint: `${status.users ?? 0} total identities`,
    },
    {
      label: "Control plane",
      value: status.server_host || "n/a",
      hint: sub.base_url || "Subscription endpoint unavailable",
    },
    {
      label: "Traffic leader",
      value: topUsage.length ? topUsage[0].name : "No traffic yet",
      hint: topUsage.length ? formatBytes(topUsage[0].total_bytes) : "Waiting for usage data",
    },
  ];

  summaryGrid.innerHTML = summaryItems
    .map(
      (item) => `
        <div class="summary-card">
          <span>${escapeHtml(item.label)}</span>
          <strong>${escapeHtml(item.value)}</strong>
          <div class="muted">${escapeHtml(item.hint)}</div>
        </div>
      `,
    )
    .join("");

  const services = status.services || [];
  serviceGrid.innerHTML = services
    .map(
      (item) => `
        <div class="service-row">
          <div>
            <div class="service-name">${escapeHtml(item.name)}</div>
            <div class="muted">${escapeHtml(item.unit)}</div>
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
    .map(([label, value]) => `<div class="proxy-line"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`)
    .join("");

  const loadLines = [
    ["CPU load", `${load.cpu?.load1 ?? "n/a"} / ${load.cpu?.load5 ?? "n/a"} / ${load.cpu?.load15 ?? "n/a"}`],
    [
      "Memory",
      `${formatBytes(load.memory?.used_bytes)} / ${formatBytes(load.memory?.total_bytes)}${load.memory?.used_percent != null ? ` (${load.memory.used_percent}%)` : ""}`,
    ],
    [
      "Disk",
      `${formatBytes(load.disk?.used_bytes)} / ${formatBytes(load.disk?.total_bytes)}${load.disk?.used_percent != null ? ` (${load.disk.used_percent}%)` : ""}`,
    ],
    ["Network RX", formatBytes(load.network?.rx_bytes)],
    ["Network TX", formatBytes(load.network?.tx_bytes)],
  ];
  loadPanel.innerHTML = loadLines
    .map(([label, value]) => `<div class="proxy-line"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`)
    .join("");

  topUsagePanel.innerHTML = topUsage.length
    ? topUsage
        .map((item) => {
          const usagePercent = clampPercent(item.usage_percent);
          const percentText = usagePercent == null ? "no quota" : `${usagePercent}%`;
          return `
            <div class="usage-row">
              <div>
                <div class="service-name">${escapeHtml(item.name)}</div>
                <span class="muted">${escapeHtml(formatBytes(item.total_bytes))}</span>
              </div>
              <span class="usage-chip">${escapeHtml(percentText)}</span>
            </div>
          `;
        })
        .join("")
    : `<div class="muted">No traffic data yet.</div>`;

  rescueFeeds.innerHTML = feeds
    .map((item) => {
      const mirrorLinks = (item.mirrors || [])
        .map((mirror, index) => `<a href="${encodeURI(mirror)}" target="_blank" rel="noreferrer">Mirror ${index + 1}</a>`)
        .join("");
      return `
        <div class="rescue-feed">
          <h3>${escapeHtml(item.title)}</h3>
          <div class="muted">${escapeHtml(item.description)}</div>
          <div class="feed-links">
            <a href="${encodeURI(item.primary)}" target="_blank" rel="noreferrer">Primary feed</a>
            ${mirrorLinks}
          </div>
        </div>
      `;
    })
    .join("");
}

function renderUsers() {
  syncFilterButtons();
  const visibleUsers = getVisibleUsers();
  const suspendedTotal = state.users.filter((user) => user.state === "suspended").length;
  userCount.textContent = `${visibleUsers.length} shown of ${state.users.length}, ${suspendedTotal} suspended`;

  if (!state.users.length) {
    usersList.innerHTML = `<div class="muted">No users yet. Create the first identity from the form above.</div>`;
    return;
  }

  if (!visibleUsers.length) {
    usersList.innerHTML = `<div class="muted">No users match the current search or filter.</div>`;
    return;
  }

  usersList.innerHTML = visibleUsers
    .map((user) => {
      const usagePercent = clampPercent(user.usage_percent);
      const usageWidth = usagePercent == null ? 0 : usagePercent;
      const usageBadge = usagePercent == null ? "" : `<span class="usage-chip">${escapeHtml(`${usagePercent}% used`)}</span>`;
      return `
        <button type="button" class="user-row ${state.selectedUser?.name === user.name ? "is-active" : ""}" data-user="${escapeHtml(user.name)}">
          <div class="user-main">
            <div class="user-row-head">
              <div class="user-name">${escapeHtml(user.name)}</div>
              <div class="user-pills">
                <span class="state-pill ${escapeHtml(user.state)}">${escapeHtml(user.state)}</span>
                ${usageBadge}
              </div>
            </div>
            <span class="user-sub">${escapeHtml(user.subscription_url)}</span>
            <div class="user-protocols muted">${escapeHtml(user.protocols)}</div>
            <div class="usage-meter" aria-hidden="true"><span style="width:${usageWidth}%"></span></div>
          </div>
          <div class="user-traffic">
            <div class="traffic-block">
              <span class="traffic-label">Used</span>
              <strong>${escapeHtml(user.used_human || "0 B")}</strong>
            </div>
            <div class="traffic-block">
              <span class="traffic-label">Quota</span>
              <strong class="traffic-value">${escapeHtml(user.quota_human || "unlimited")}</strong>
            </div>
          </div>
        </button>
      `;
    })
    .join("");

  usersList.querySelectorAll("[data-user]").forEach((node) => {
    node.addEventListener("click", () => {
      const name = node.getAttribute("data-user");
      if (name) {
        selectUser(name);
      }
    });
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
    selectedUserMeta.innerHTML = `
      <div class="meta-item meta-placeholder">
        <span>Inspector</span>
        <strong>Select a user to inspect generated bundle files, traffic counters and subscription details.</strong>
      </div>
    `;
    fileTabs.innerHTML = "";
    quotaInput.value = "";
    configViewer.textContent = "Select a user to inspect generated configs.";
    return;
  }

  selectedUserTitle.textContent = user.name;
  quotaInput.value = user.quota_bytes ? String((user.quota_bytes / (1024 ** 3)).toFixed(2).replace(/\.00$/, "")) : "";

  const metaItems = [
    ["Created", user.created],
    ["State", user.state],
    ["Traffic", formatBytes(user.usage?.total_bytes ?? user.used_bytes)],
    ["Quota", user.quota_human || "unlimited"],
    ["Subscription URL", user.subscription_url],
    ["Protocols", user.protocols],
    ["Shareable URIs", String(user.shareable_uris.length)],
    ["Updated", user.usage?.updated_at || user.updated_at || "n/a"],
  ];

  selectedUserMeta.innerHTML = metaItems
    .map(
      ([label, value]) => `
        <div class="meta-item">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </div>
      `,
    )
    .join("");

  fileTabs.innerHTML = FILE_ORDER.map((kind) => {
    const active = state.selectedFile === kind;
    return `
      <button
        type="button"
        class="${active ? "is-active" : "ghost"}"
        data-kind="${kind}"
        role="tab"
        aria-selected="${active ? "true" : "false"}"
      >
        ${escapeHtml(FILE_LABELS[kind])}
      </button>
    `;
  }).join("");

  fileTabs.querySelectorAll("[data-kind]").forEach((node) => {
    node.addEventListener("click", () => {
      const kind = node.getAttribute("data-kind");
      if (kind) {
        loadFile(kind);
      }
    });
  });
}

async function loadDashboard({ silent = false } = {}) {
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

  const target =
    state.users.find((user) => user.name === state.selectedUser?.name)?.name ||
    getVisibleUsers()[0]?.name ||
    state.users[0].name;
  await selectUser(target, { silent });
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
  configViewer.textContent = "Loading file...";
  try {
    const payload = await api(`/api/users/${encodeURIComponent(state.selectedUser.name)}/file/${encodeURIComponent(kind)}`);
    configViewer.textContent = payload.content || "Binary file. Use download ZIP.";
  } catch (error) {
    if (!silent) {
      configViewer.textContent = String(error.message || error);
    }
  }
}

async function runAction(task, { control, successMessage, errorPrefix = "Action failed" } = {}) {
  const release = busyState(control, true);
  try {
    await task();
    if (successMessage) {
      showToast(successMessage, "success");
    }
  } catch (error) {
    showToast(`${errorPrefix}: ${String(error.message || error)}`, "error");
    throw error;
  } finally {
    release();
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
    showToast("Panel unlocked", "success");
  } catch (error) {
    authError.textContent = String(error.message || error);
  }
});

refreshButton.addEventListener("click", async () => {
  try {
    await runAction(() => loadDashboard({ silent: true }), {
      control: refreshButton,
      successMessage: "Dashboard refreshed",
      errorPrefix: "Refresh failed",
    });
  } catch (_error) {
    // Toast already shown.
  }
});

createUserForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = createUserInput.value.trim();
  if (!name) {
    return;
  }

  try {
    await runAction(
      async () => {
        await api("/api/users", {
          method: "POST",
          body: JSON.stringify({ name }),
        });
        createUserInput.value = "";
        state.selectedFile = "readme";
        await loadDashboard({ silent: true });
        await selectUser(name);
      },
      {
        control: createUserForm.querySelector('button[type="submit"]'),
        successMessage: `User ${name} created`,
        errorPrefix: "User creation failed",
      },
    );
  } catch (_error) {
    // Toast already shown.
  }
});

userSearchInput.addEventListener("input", () => {
  state.searchQuery = userSearchInput.value;
  renderUsers();
});

userFilterTabs.querySelectorAll("[data-filter]").forEach((node) => {
  node.addEventListener("click", () => {
    state.userFilter = node.getAttribute("data-filter") || "all";
    renderUsers();
  });
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

  try {
    await runAction(
      async () => {
        await api(`/api/users/${encodeURIComponent(state.selectedUser.name)}/quota`, {
          method: "POST",
          body: JSON.stringify({ quota_gb: Number(quotaGb) }),
        });
        await selectUser(state.selectedUser.name);
        await loadDashboard({ silent: true });
      },
      {
        control: quotaForm.querySelector('button[type="submit"]'),
        successMessage: `Quota updated for ${state.selectedUser.name}`,
        errorPrefix: "Quota update failed",
      },
    );
  } catch (_error) {
    // Toast already shown.
  }
});

disableQuotaButton.addEventListener("click", async () => {
  if (!state.selectedUser) {
    return;
  }

  try {
    await runAction(
      async () => {
        await api(`/api/users/${encodeURIComponent(state.selectedUser.name)}/quota`, {
          method: "POST",
          body: JSON.stringify({ disable: true }),
        });
        await selectUser(state.selectedUser.name);
        await loadDashboard({ silent: true });
      },
      {
        control: disableQuotaButton,
        successMessage: `Quota disabled for ${state.selectedUser.name}`,
        errorPrefix: "Disabling quota failed",
      },
    );
  } catch (_error) {
    // Toast already shown.
  }
});

resetUsageButton.addEventListener("click", async () => {
  if (!state.selectedUser) {
    return;
  }

  try {
    await runAction(
      async () => {
        await api(`/api/users/${encodeURIComponent(state.selectedUser.name)}/reset-usage`, { method: "POST" });
        await selectUser(state.selectedUser.name);
        await loadDashboard({ silent: true });
      },
      {
        control: resetUsageButton,
        successMessage: `Usage reset for ${state.selectedUser.name}`,
        errorPrefix: "Usage reset failed",
      },
    );
  } catch (_error) {
    // Toast already shown.
  }
});

suspendUserButton.addEventListener("click", async () => {
  if (!state.selectedUser) {
    return;
  }

  try {
    await runAction(
      async () => {
        await api(`/api/users/${encodeURIComponent(state.selectedUser.name)}/suspend`, { method: "POST" });
        await selectUser(state.selectedUser.name);
        await loadDashboard({ silent: true });
      },
      {
        control: suspendUserButton,
        successMessage: `User ${state.selectedUser.name} suspended`,
        errorPrefix: "Suspend failed",
      },
    );
  } catch (_error) {
    // Toast already shown.
  }
});

resumeUserButton.addEventListener("click", async () => {
  if (!state.selectedUser) {
    return;
  }

  try {
    await runAction(
      async () => {
        await api(`/api/users/${encodeURIComponent(state.selectedUser.name)}/resume`, { method: "POST" });
        await selectUser(state.selectedUser.name);
        await loadDashboard({ silent: true });
      },
      {
        control: resumeUserButton,
        successMessage: `User ${state.selectedUser.name} resumed`,
        errorPrefix: "Resume failed",
      },
    );
  } catch (_error) {
    // Toast already shown.
  }
});

copySubscriptionButton.addEventListener("click", async () => {
  if (!state.selectedUser) {
    return;
  }

  try {
    await navigator.clipboard.writeText(state.selectedUser.subscription_url);
    showToast("Subscription URL copied", "success");
  } catch (error) {
    showToast(`Copy failed: ${String(error.message || error)}`, "error");
  }
});

downloadZipButton.addEventListener("click", async () => {
  if (!state.selectedUser) {
    return;
  }

  try {
    await runAction(
      () => downloadWithAuth(`/download/users/${encodeURIComponent(state.selectedUser.name)}/zip`, `${state.selectedUser.name}.zip`),
      {
        control: downloadZipButton,
        successMessage: `ZIP download started for ${state.selectedUser.name}`,
        errorPrefix: "ZIP download failed",
      },
    );
  } catch (_error) {
    // Toast already shown.
  }
});

deleteUserButton.addEventListener("click", async () => {
  if (!state.selectedUser) {
    return;
  }
  if (!window.confirm(`Delete user ${state.selectedUser.name}?`)) {
    return;
  }

  const deletedName = state.selectedUser.name;
  try {
    await runAction(
      async () => {
        await api(`/api/users/${encodeURIComponent(deletedName)}`, { method: "DELETE" });
        state.selectedUser = null;
        state.selectedFile = "readme";
        await loadDashboard({ silent: true });
      },
      {
        control: deleteUserButton,
        successMessage: `User ${deletedName} deleted`,
        errorPrefix: "Delete failed",
      },
    );
  } catch (_error) {
    // Toast already shown.
  }
});

navToggleButton.addEventListener("click", () => {
  setNavOpen(!document.body.classList.contains("nav-open"));
});

mobileBackdrop.addEventListener("click", () => {
  setNavOpen(false);
});

window.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    setNavOpen(false);
  }
});

window.addEventListener("resize", () => {
  if (window.innerWidth > 1120) {
    setNavOpen(false);
  }
});

window.addEventListener("load", async () => {
  tokenInput.value = state.token;
  userSearchInput.value = state.searchQuery;
  syncFilterButtons();

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
  if (!state.token || document.hidden) {
    return;
  }
  try {
    await loadDashboard({ silent: true });
  } catch (_error) {
    // Leave the current screen in place if background refresh fails.
  }
}, 30000);
