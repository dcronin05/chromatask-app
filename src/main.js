import './style.css';

// ==========================================
// 1. STATE & ROUTING
// ==========================================

let tasks = [];
let activeTaskId = null;
let currentView = 'DASHBOARD'; // 'DASHBOARD' or 'ARCHIVE'
let activeFilters = {
  search: '',
  priority: 'ALL',
  tag: null
};

// ==========================================
// 2. BACKEND API SYNCING
// ==========================================

async function fetchTasks() {
  try {
    const response = await fetch('/api/tasks');
    if (!response.ok) throw new Error('Failed to fetch tasks');
    tasks = await response.json();
  } catch (error) {
    console.error('API Error:', error);
    showToast('Failed to load tasks from server.');
  }
}

async function apiCreateTask(taskData) {
  try {
    const response = await fetch('/api/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(taskData)
    });
    if (!response.ok) throw new Error('Failed to create task');
    showToast('Task created successfully');
    await fetchTasks();
    renderView();
  } catch (error) {
    console.error(error);
    showToast('Error creating task.');
  }
}

async function apiUpdateTask(taskId, updateData) {
  try {
    const response = await fetch(`/api/tasks/${taskId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updateData)
    });
    if (!response.ok) throw new Error('Failed to update task');
    await fetchTasks();
    renderView();
  } catch (error) {
    console.error(error);
    showToast('Error saving changes to server.');
  }
}

async function apiDeleteTask(taskId) {
  try {
    const response = await fetch(`/api/tasks/${taskId}`, {
      method: 'DELETE'
    });
    if (!response.ok) throw new Error('Failed to delete task');
    showToast('Task soft-deleted and moved to Archive');
    closeDetailDrawer();
    await fetchTasks();
    renderView();
  } catch (error) {
    console.error(error);
    showToast('Error deleting task.');
  }
}

async function apiRestoreTask(taskId) {
  try {
    const response = await fetch(`/api/tasks/${taskId}/restore`, {
      method: 'POST'
    });
    if (!response.ok) throw new Error('Failed to restore task');
    showToast('Task restored back to Board!');
    await fetchTasks();
    renderView();
  } catch (error) {
    console.error(error);
    showToast('Error restoring task.');
  }
}

async function apiResetDatabase() {
  try {
    const response = await fetch('/api/reset', {
      method: 'POST'
    });
    if (!response.ok) throw new Error('Failed to reset database');
    showToast('Database reset successfully. Core task restored!');
    closeDetailDrawer();
    await fetchTasks();
    renderView();
  } catch (error) {
    console.error(error);
    showToast('Error resetting database.');
  }
}

async function apiFetchTaskHistory(taskId) {
  try {
    const response = await fetch(`/api/tasks/${taskId}/history`);
    if (!response.ok) throw new Error('Failed to fetch history');
    return await response.json();
  } catch (error) {
    console.error(error);
    return [];
  }
}

// ==========================================
// 3. YOUTUBE PLAYER INTEGRATION
// ==========================================

let ytPlayer = null;
let ytPlayerReady = false;

window.onYouTubeIframeAPIReady = () => {
  console.log("YouTube Player API is loaded.");
  if (activeTaskId) {
    const task = tasks.find(t => t.task_id === activeTaskId);
    if (task && task.media_metadata && task.media_metadata.video_id) {
      initYoutubePlayer(task.media_metadata.video_id);
    }
  }
};

function initYoutubePlayer(videoId) {
  ytPlayerReady = false;
  const container = document.getElementById('yt-player-container');
  if (!container) return;

  container.innerHTML = '<div id="yt-iframe-placeholder"></div>';

  if (window.YT && window.YT.Player) {
    ytPlayer = new window.YT.Player('yt-iframe-placeholder', {
      height: '100%',
      width: '100%',
      videoId: videoId,
      playerVars: {
        'playsinline': 1,
        'rel': 0,
        'modestbranding': 1
      },
      events: {
        'onReady': () => {
          ytPlayerReady = true;
        }
      }
    });
  }
}

function loadVideo(videoId) {
  if (ytPlayer && ytPlayerReady && typeof ytPlayer.cueVideoById === 'function') {
    try {
      ytPlayer.cueVideoById(videoId);
    } catch (e) {
      initYoutubePlayer(videoId);
    }
  } else {
    initYoutubePlayer(videoId);
  }
}

function parseTimestamp(ts) {
  const clean = ts.replace(/[\[\]]/g, '').trim();
  const parts = clean.split(':').map(Number);
  if (parts.length === 3) {
    return parts[0] * 3600 + parts[1] * 60 + parts[2];
  } else if (parts.length === 2) {
    return parts[0] * 60 + parts[1];
  }
  return 0;
}

// ==========================================
// 4. RENDERING SYSTEM
// ==========================================

function getPriorityLabel(priority) {
  return priority.charAt(0).toUpperCase() + priority.slice(1).toLowerCase();
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function isOverdue(dateStr) {
  if (!dateStr) return false;
  return new Date(dateStr) < new Date();
}

// Render either Dashboard Board or Archive list depending on state
function renderView() {
  if (currentView === 'DASHBOARD') {
    document.getElementById('board-container').style.display = 'grid';
    document.getElementById('archive-container').style.display = 'none';
    document.getElementById('sidebar-filters-section').style.display = 'block';
    document.getElementById('header-search-box').style.display = 'flex';
    document.getElementById('btn-add-task').style.display = 'inline-flex';
    document.getElementById('page-title').textContent = 'Workspace';
    
    renderBoard();
  } else {
    document.getElementById('board-container').style.display = 'none';
    document.getElementById('archive-container').style.display = 'block';
    document.getElementById('sidebar-filters-section').style.display = 'none';
    document.getElementById('header-search-box').style.display = 'none';
    document.getElementById('btn-add-task').style.display = 'none';
    document.getElementById('page-title').textContent = 'Archive & Logs';
    
    renderArchive();
  }
}

// Render active board tasks
function renderBoard() {
  const columns = {
    TODO: document.getElementById('cards-todo'),
    IN_PROGRESS: document.getElementById('cards-in-progress'),
    COMPLETED: document.getElementById('cards-completed')
  };

  Object.values(columns).forEach(col => {
    if (col) col.innerHTML = '';
  });

  let counts = { TODO: 0, IN_PROGRESS: 0, COMPLETED: 0 };
  let allTags = new Set();

  tasks.forEach(task => {
    // Only display active (non-deleted) tasks on Kanban Board
    if (task.is_deleted) return;

    if (task.task_specific_tags) {
      task.task_specific_tags.forEach(tag => allTags.add(tag));
    }

    const matchesSearch = activeFilters.search === '' || 
      task.title.toLowerCase().includes(activeFilters.search.toLowerCase()) || 
      task.description.toLowerCase().includes(activeFilters.search.toLowerCase());
      
    const matchesPriority = activeFilters.priority === 'ALL' || task.priority === activeFilters.priority;
    
    const matchesTag = !activeFilters.tag || (task.task_specific_tags && task.task_specific_tags.includes(activeFilters.tag));

    if (matchesSearch && matchesPriority && matchesTag) {
      counts[task.status]++;
      const card = createTaskCard(task);
      if (columns[task.status]) {
        columns[task.status].appendChild(card);
      }
    }
  });

  document.getElementById('count-todo').textContent = counts.TODO;
  document.getElementById('count-in-progress').textContent = counts.IN_PROGRESS;
  document.getElementById('count-completed').textContent = counts.COMPLETED;

  const total = tasks.filter(t => !t.is_deleted).length;
  const completed = tasks.filter(t => t.status === 'COMPLETED' && !t.is_deleted).length;
  document.getElementById('task-metrics-summary').textContent = 
    `${completed} of ${total} tasks completed • ${tasks.filter(t => t.status === 'IN_PROGRESS' && !t.is_deleted).length} in progress`;

  renderSidebarTags(allTags);
}

function renderSidebarTags(tagSet) {
  const container = document.getElementById('sidebar-tags-container');
  if (!container) return;

  container.innerHTML = '';
  if (tagSet.size === 0) {
    container.innerHTML = '<span class="text-muted" style="font-size: 12px; padding-left: 8px;">No tags found</span>';
    return;
  }

  tagSet.forEach(tag => {
    const pill = document.createElement('span');
    pill.className = `sidebar-tag-pill ${activeFilters.tag === tag ? 'active' : ''}`;
    pill.textContent = `#${tag}`;
    pill.addEventListener('click', () => {
      activeFilters.tag = activeFilters.tag === tag ? null : tag;
      renderBoard();
    });
    container.appendChild(pill);
  });
}

function createTaskCard(task) {
  const card = document.createElement('div');
  card.className = `task-card ${task.is_core ? 'protected-core' : ''}`;
  card.setAttribute('draggable', 'true');
  card.setAttribute('id', `card-${task.task_id}`);
  card.dataset.id = task.task_id;

  const priorityBadge = `<span class="badge badge-priority-${task.priority}">${getPriorityLabel(task.priority)}</span>`;
  const coreBadge = task.is_core ? `<span class="badge badge-core">Seed Task</span>` : '';

  let dueHTML = '';
  if (task.due_date) {
    const isOver = isOverdue(task.due_date) && task.status !== 'COMPLETED';
    dueHTML = `
      <div class="card-due ${isOver ? 'overdue' : ''}">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        <span>${isOver ? 'Overdue: ' : ''}${formatDate(task.due_date)}</span>
      </div>
    `;
  }

  let collabHTML = '';
  if (task.collaborators && task.collaborators.length > 0) {
    collabHTML = `
      <div class="card-avatars">
        ${task.collaborators.map(c => {
          const initials = c.name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
          return `<div class="collab-avatar" title="${c.name} (${c.role}) - ${c.status}">${initials}</div>`;
        }).join('')}
      </div>
    `;
  }

  card.innerHTML = `
    <div class="card-header">
      <h3 class="card-title">${task.title}</h3>
    </div>
    <div class="card-badges">
      ${priorityBadge}
      ${coreBadge}
    </div>
    <p class="card-desc">${task.description || 'No description provided.'}</p>
    <div class="card-meta-row">
      ${dueHTML}
      ${collabHTML}
    </div>
  `;

  card.addEventListener('dragstart', (e) => {
    e.dataTransfer.setData('text/plain', task.task_id);
    card.classList.add('dragging');
  });

  card.addEventListener('dragend', () => {
    card.classList.remove('dragging');
  });

  card.addEventListener('click', (e) => {
    if (e.target.closest('.collab-avatar')) return;
    openDetailDrawer(task.task_id);
  });

  return card;
}

// Render Archived Tasks list view
async function renderArchive() {
  const tbody = document.getElementById('archive-table-body');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 24px;">Loading archive records...</td></tr>';

  try {
    // Query all tasks including deleted ones from server
    const response = await fetch('/api/tasks?include_deleted=true');
    if (!response.ok) throw new Error();
    const allTasks = await response.json();
    const deletedTasks = allTasks.filter(t => t.is_deleted);

    tbody.innerHTML = '';
    
    if (deletedTasks.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 32px; color: var(--color-text-muted);">No archived or deleted tasks found.</td></tr>';
      document.getElementById('task-metrics-summary').textContent = '0 archived tasks';
      return;
    }

    document.getElementById('task-metrics-summary').textContent = `${deletedTasks.length} archived tasks`;

    deletedTasks.forEach(task => {
      const tr = document.createElement('tr');
      
      const priorityLabel = getPriorityLabel(task.priority);
      const deletedDate = formatDate(task.deleted_at || task.updated_at);
      
      tr.innerHTML = `
        <td class="archive-title-cell">${task.title}</td>
        <td><span class="badge" style="background: rgba(255,255,255,0.05); color: var(--color-text-secondary);">${task.status}</span></td>
        <td><span class="badge badge-priority-${task.priority}">${priorityLabel}</span></td>
        <td>${deletedDate}</td>
        <td class="archive-action-cell">
          <button class="btn btn-secondary btn-sm btn-view-history" data-id="${task.task_id}">Timeline</button>
          <button class="btn btn-primary btn-sm btn-restore-task" data-id="${task.task_id}">Restore</button>
        </td>
      `;

      // Event bindings
      tr.querySelector('.btn-view-history').addEventListener('click', () => {
        openDetailDrawer(task.task_id);
      });
      tr.querySelector('.btn-restore-task').addEventListener('click', () => {
        apiRestoreTask(task.task_id);
      });

      tbody.appendChild(tr);
    });
  } catch (error) {
    console.error(error);
    tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #f43f5e; padding: 24px;">Failed to load archive files.</td></tr>';
  }
}

// ==========================================
// 5. DRAWER LOGIC
// ==========================================

async function openDetailDrawer(taskId) {
  // Try to find in cache first, otherwise fall back
  let task = tasks.find(t => t.task_id === taskId);
  if (!task) {
    try {
      const res = await fetch(`/api/tasks/${taskId}`);
      if (res.ok) task = await res.json();
    } catch(e) {}
  }
  if (!task) return;

  activeTaskId = taskId;

  // Toggle visual badge for seeds
  const coreBadge = document.getElementById('detail-core-badge');
  coreBadge.style.display = task.is_core ? 'inline-flex' : 'none';

  // Toggle active delete/restore wording in detail footer
  const deleteBtn = document.getElementById('btn-delete-task');
  if (task.is_deleted) {
    deleteBtn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
      <span>Restore Task</span>
    `;
    deleteBtn.className = 'btn btn-primary btn-full';
  } else {
    deleteBtn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
      <span>Delete Task</span>
    `;
    deleteBtn.className = 'btn btn-danger btn-full';
  }

  // Bind values
  const priorityBadge = document.getElementById('detail-priority-badge');
  priorityBadge.textContent = task.priority;
  priorityBadge.className = `badge badge-priority-${task.priority}`;

  document.getElementById('detail-title').textContent = task.title;
  document.getElementById('detail-status-select').value = task.status;
  document.getElementById('detail-due-date').value = task.due_date ? task.due_date.slice(0, 16) : '';
  document.getElementById('detail-description').value = task.description || '';

  renderDetailTags(task);
  renderDetailCollaborators(task);

  // Video Section
  const videoSection = document.getElementById('drawer-video-section');
  if (task.media_metadata && task.media_metadata.video_id) {
    videoSection.style.display = 'flex';
    document.getElementById('video-title').textContent = task.media_metadata.title || task.title;
    document.getElementById('video-creator').textContent = `By ${task.media_metadata.creator_or_channel || 'Unknown Creator'}`;
    document.getElementById('video-duration').textContent = `Duration: 46:01`;
    document.getElementById('video-views').textContent = task.media_metadata.metrics_at_creation?.view_count 
      ? `Views: ${Number(task.media_metadata.metrics_at_creation.view_count).toLocaleString()}`
      : '';
    loadVideo(task.media_metadata.video_id);
  } else {
    videoSection.style.display = 'none';
  }

  // Bookmarks Section
  const bookmarksSection = document.getElementById('drawer-bookmarks-section');
  if (task.curated_video_bookmarks && task.curated_video_bookmarks.length > 0) {
    bookmarksSection.style.display = 'flex';
    renderDetailBookmarks(task);
  } else {
    bookmarksSection.style.display = task.media_metadata ? 'flex' : 'none';
    document.getElementById('bookmarks-list-container').innerHTML = 
      '<p class="text-muted" style="font-size: 12px; font-style: italic; padding: 8px 0;">No bookmarks set yet.</p>';
  }

  // Render Activity Log History Timeline
  renderDetailHistoryTimeline(taskId);

  document.getElementById('detail-drawer').classList.add('open');
}

function closeDetailDrawer() {
  document.getElementById('detail-drawer').classList.remove('open');
  activeTaskId = null;
  if (ytPlayer && ytPlayerReady && typeof ytPlayer.pauseVideo === 'function') {
    try { ytPlayer.pauseVideo(); } catch(e) {}
  }
}

// Renders historical timeline events for a task
async function renderDetailHistoryTimeline(taskId) {
  const container = document.getElementById('detail-timeline-container');
  if (!container) return;
  
  container.innerHTML = '<p class="text-muted" style="font-size: 12px; padding: 8px 0;">Loading log history...</p>';
  
  const history = await apiFetchTaskHistory(taskId);
  container.innerHTML = '';

  if (history.length === 0) {
    container.innerHTML = '<p class="text-muted" style="font-size: 12px; font-style: italic;">No logs recorded.</p>';
    return;
  }

  history.forEach(log => {
    const item = document.createElement('div');
    item.className = `timeline-item ${log.action.toLowerCase()}`;
    
    let actionText = '';
    let detailsHTML = '';
    
    if (log.action === 'CREATED') {
      actionText = 'Task Created';
      detailsHTML = `<div class="timeline-details">Initialized title: "<strong>${log.details.title || ''}</strong>"</div>`;
    } else if (log.action === 'DELETED') {
      actionText = 'Task Deleted (Archived)';
    } else if (log.action === 'RESTORED') {
      actionText = 'Task Restored';
    } else if (log.action === 'UPDATED') {
      actionText = 'Task Updated';
      
      const changes = log.details.changes || [];
      if (changes.length > 0) {
        detailsHTML = `
          <ul class="timeline-changes">
            ${changes.map(c => {
              let oldVal = c.old;
              let newVal = c.new;
              
              if (c.field === 'due_date') {
                oldVal = oldVal ? formatDate(oldVal) : 'None';
                newVal = newVal ? formatDate(newVal) : 'None';
              } else if (typeof oldVal === 'object' || Array.isArray(oldVal)) {
                // Return counts or brief strings for lists
                oldVal = Array.isArray(oldVal) ? `${oldVal.length} items` : 'Updated';
                newVal = Array.isArray(newVal) ? `${newVal.length} items` : 'Updated';
              }
              
              return `
                <li>
                  <strong>${c.field.replace(/_/g, ' ')}</strong>: 
                  <span class="timeline-changes-diff">"${oldVal}" ➜ "${newVal}"</span>
                </li>
              `;
            }).join('')}
          </ul>
        `;
      }
    }

    const logTime = new Date(log.timestamp).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const logDate = new Date(log.timestamp).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

    item.innerHTML = `
      <div class="timeline-bullet"></div>
      <div class="timeline-content">
        <div class="timeline-header">
          <span class="timeline-action">${actionText}</span>
          <span class="timeline-time">${logDate} ${logTime}</span>
        </div>
        ${detailsHTML}
      </div>
    `;

    container.appendChild(item);
  });
}

// -----------------
// Sub-renders in Drawer
// -----------------

function renderDetailTags(task) {
  const container = document.getElementById('detail-tags-container');
  container.innerHTML = '';
  if (!task.task_specific_tags) return;
  task.task_specific_tags.forEach((tag, idx) => {
    const badge = document.createElement('span');
    badge.className = 'detail-tag-badge';
    badge.innerHTML = `
      <span>#${tag}</span>
      <button class="btn-remove-tag" data-index="${idx}" aria-label="Delete tag">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    `;
    container.appendChild(badge);
  });
}

function renderDetailCollaborators(task) {
  const container = document.getElementById('collaborators-list-container');
  container.innerHTML = '';
  if (!task.collaborators || task.collaborators.length === 0) {
    container.innerHTML = '<p class="text-muted" style="font-size:12px; font-style:italic;">No collaborators invited yet.</p>';
    return;
  }
  task.collaborators.forEach((collab, idx) => {
    const initials = collab.name.split(' ').map(n => n[0]).join('').slice(0,2).toUpperCase();
    const item = document.createElement('div');
    item.className = 'collaborator-item';
    item.innerHTML = `
      <div class="collab-left">
        <div class="collab-avatar-lg">${initials}</div>
        <div class="collab-info">
          <span class="collab-name">${collab.name}</span>
          <span class="collab-role">${collab.role}</span>
        </div>
      </div>
      <div class="collab-right">
        <select class="collab-status-select" data-index="${idx}">
          <option value="INVITED" ${collab.status === 'INVITED' ? 'selected' : ''}>Invited</option>
          <option value="JOINED" ${collab.status === 'JOINED' ? 'selected' : ''}>Joined</option>
          <option value="DECLINED" ${collab.status === 'DECLINED' ? 'selected' : ''}>Declined</option>
        </select>
        <button class="btn-remove-collab" data-index="${idx}">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
    `;
    container.appendChild(item);
  });
}

function renderDetailBookmarks(task) {
  const container = document.getElementById('bookmarks-list-container');
  container.innerHTML = '';
  task.curated_video_bookmarks.forEach((bm, idx) => {
    const item = document.createElement('div');
    item.className = 'bookmark-item';
    item.innerHTML = `
      <span class="bookmark-time-badge">${bm.timestamp}</span>
      <div class="bookmark-info">
        <span class="bookmark-label">${bm.label}</span>
        ${bm.note ? `<span class="bookmark-note">${bm.note}</span>` : ''}
      </div>
      <button class="btn-delete-bookmark" data-index="${idx}">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
      </button>
    `;
    
    item.addEventListener('click', (e) => {
      if (e.target.closest('.btn-delete-bookmark')) return;
      const seconds = parseTimestamp(bm.timestamp);
      if (ytPlayer && ytPlayerReady && typeof ytPlayer.seekTo === 'function') {
        ytPlayer.seekTo(seconds, true);
        try { ytPlayer.playVideo(); } catch(e) {}
        showToast(`Seeking video to ${bm.timestamp}`);
      }
    });

    container.appendChild(item);
  });
}

// Auto-save edited fields
function handleDrawerFieldChange(field, val) {
  if (!activeTaskId) return;
  const task = tasks.find(t => t.task_id === activeTaskId);
  if (!task) return;

  const payload = { ...task };
  
  if (field === 'title') payload.title = val.trim();
  if (field === 'description') payload.description = val.trim();
  if (field === 'status') payload.status = val;
  if (field === 'due_date') payload.due_date = val ? new Date(val).toISOString() : null;

  // Send update to server
  apiUpdateTask(activeTaskId, payload).then(() => {
    renderDetailHistoryTimeline(activeTaskId);
  });
}

// ==========================================
// 6. MODALS
// ==========================================

function openModal(id) {
  document.getElementById(id).classList.add('open');
}

function closeModal(id) {
  document.getElementById(id).classList.remove('open');
}

// ==========================================
// 7. TOAST FEEDBACK UTILITY
// ==========================================

function showToast(message) {
  let toast = document.getElementById('app-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'app-toast';
    toast.className = 'toast-msg';
    document.body.appendChild(toast);
  }
  toast.innerHTML = `
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
    <span>${message}</span>
  `;
  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
  }, 3000);
}

// ==========================================
// 8. EVENT BINDINGS
// ==========================================

document.addEventListener('DOMContentLoaded', async () => {
  // Initial fetch and draw
  await fetchTasks();
  renderView();

  // --- View toggling ---
  document.getElementById('nav-all').addEventListener('click', (e) => {
    document.querySelectorAll('.sidebar-nav .nav-item').forEach(el => el.classList.remove('active'));
    e.currentTarget.classList.add('active');
    currentView = 'DASHBOARD';
    activeFilters.tag = null;
    activeFilters.priority = 'ALL';
    renderView();
  });

  document.getElementById('nav-archive').addEventListener('click', (e) => {
    document.querySelectorAll('.sidebar-nav .nav-item').forEach(el => el.classList.remove('active'));
    e.currentTarget.classList.add('active');
    currentView = 'ARCHIVE';
    renderView();
  });

  // --- Priority filters ---
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.sidebar-nav .nav-item').forEach(el => el.classList.remove('active'));
      e.currentTarget.classList.add('active');
      
      const filterVal = e.currentTarget.dataset.filter;
      if (filterVal.startsWith('priority-')) {
        activeFilters.priority = filterVal.split('-')[1];
      }
      activeFilters.tag = null;
      renderBoard();
    });
  });

  // --- Search input ---
  document.getElementById('search-input').addEventListener('input', (e) => {
    activeFilters.search = e.target.value;
    renderBoard();
  });

  // --- Reset database ---
  document.getElementById('btn-reset-db').addEventListener('click', () => {
    if (confirm('Are you sure you want to reset the database? This will clear all tasks and history, and restore the initial Cheetah Conservation seed task.')) {
      apiResetDatabase();
    }
  });

  // --- Drag and Drop ---
  document.querySelectorAll('.column-cards').forEach(col => {
    col.addEventListener('dragover', (e) => {
      e.preventDefault();
      col.classList.add('drag-over');
    });

    col.addEventListener('dragleave', () => {
      col.classList.remove('drag-over');
    });

    col.addEventListener('drop', (e) => {
      e.preventDefault();
      col.classList.remove('drag-over');
      const taskId = e.dataTransfer.getData('text/plain');
      const newStatus = col.dataset.status;

      const task = tasks.find(t => t.task_id === taskId);
      if (task && task.status !== newStatus) {
        const payload = { ...task, status: newStatus };
        apiUpdateTask(taskId, payload).then(() => {
          showToast(`Moved to ${newStatus.replace('_', ' ')}`);
          if (activeTaskId === taskId) {
            document.getElementById('detail-status-select').value = newStatus;
            renderDetailHistoryTimeline(taskId);
          }
        });
      }
    });
  });

  // --- Drawer controls ---
  document.getElementById('drawer-close').addEventListener('click', closeDetailDrawer);

  document.getElementById('detail-title').addEventListener('blur', (e) => {
    handleDrawerFieldChange('title', e.target.textContent);
  });
  document.getElementById('detail-title').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      e.target.blur();
    }
  });

  document.getElementById('detail-description').addEventListener('blur', (e) => {
    handleDrawerFieldChange('description', e.target.value);
  });

  document.getElementById('detail-status-select').addEventListener('change', (e) => {
    handleDrawerFieldChange('status', e.target.value);
  });

  document.getElementById('detail-due-date').addEventListener('change', (e) => {
    handleDrawerFieldChange('due_date', e.target.value);
  });

  // Drawer Tags
  document.getElementById('btn-add-tag').addEventListener('click', () => {
    if (!activeTaskId) return;
    const task = tasks.find(t => t.task_id === activeTaskId);
    const input = document.getElementById('new-tag-input');
    const val = input.value.trim();
    if (val && task) {
      const payload = { ...task };
      if (!payload.task_specific_tags) payload.task_specific_tags = [];
      if (!payload.task_specific_tags.includes(val)) {
        payload.task_specific_tags.push(val);
        apiUpdateTask(activeTaskId, payload).then(() => {
          // Re-get from state
          const updatedTask = tasks.find(t => t.task_id === activeTaskId);
          renderDetailTags(updatedTask);
          renderDetailHistoryTimeline(activeTaskId);
          input.value = '';
        });
      }
    }
  });

  document.getElementById('detail-tags-container').addEventListener('click', (e) => {
    const btn = e.target.closest('.btn-remove-tag');
    if (!btn || !activeTaskId) return;
    const task = tasks.find(t => t.task_id === activeTaskId);
    if (task) {
      const idx = parseInt(btn.dataset.index);
      const payload = { ...task };
      payload.task_specific_tags.splice(idx, 1);
      apiUpdateTask(activeTaskId, payload).then(() => {
        const updatedTask = tasks.find(t => t.task_id === activeTaskId);
        renderDetailTags(updatedTask);
        renderDetailHistoryTimeline(activeTaskId);
      });
    }
  });

  // Drawer Collaborators
  document.getElementById('btn-add-collaborator').addEventListener('click', () => openModal('collaborator-modal'));
  document.getElementById('collab-close-btn').addEventListener('click', () => closeModal('collaborator-modal'));
  document.getElementById('collab-cancel-btn').addEventListener('click', () => closeModal('collaborator-modal'));

  document.getElementById('collaborators-list-container').addEventListener('change', (e) => {
    const select = e.target.closest('.collab-status-select');
    if (!select || !activeTaskId) return;
    const task = tasks.find(t => t.task_id === activeTaskId);
    if (task) {
      const idx = parseInt(select.dataset.index);
      const payload = { ...task };
      payload.collaborators[idx].status = select.value;
      apiUpdateTask(activeTaskId, payload).then(() => {
        renderDetailHistoryTimeline(activeTaskId);
      });
    }
  });

  document.getElementById('collaborators-list-container').addEventListener('click', (e) => {
    const btn = e.target.closest('.btn-remove-collab');
    if (!btn || !activeTaskId) return;
    const task = tasks.find(t => t.task_id === activeTaskId);
    if (task && confirm('Remove this collaborator?')) {
      const idx = parseInt(btn.dataset.index);
      const payload = { ...task };
      payload.collaborators.splice(idx, 1);
      apiUpdateTask(activeTaskId, payload).then(() => {
        const updatedTask = tasks.find(t => t.task_id === activeTaskId);
        renderDetailCollaborators(updatedTask);
        renderDetailHistoryTimeline(activeTaskId);
      });
    }
  });

  // Drawer Bookmarks
  document.getElementById('btn-add-bookmark').addEventListener('click', () => openModal('bookmark-modal'));
  document.getElementById('bookmark-close-btn').addEventListener('click', () => closeModal('bookmark-modal'));
  document.getElementById('bookmark-cancel-btn').addEventListener('click', () => closeModal('bookmark-modal'));

  document.getElementById('bookmarks-list-container').addEventListener('click', (e) => {
    const btn = e.target.closest('.btn-delete-bookmark');
    if (!btn || !activeTaskId) return;
    const task = tasks.find(t => t.task_id === activeTaskId);
    if (task && confirm('Delete this video bookmark?')) {
      const idx = parseInt(btn.dataset.index);
      const payload = { ...task };
      payload.curated_video_bookmarks.splice(idx, 1);
      apiUpdateTask(activeTaskId, payload).then(() => {
        const updatedTask = tasks.find(t => t.task_id === activeTaskId);
        renderDetailBookmarks(updatedTask);
        renderDetailHistoryTimeline(activeTaskId);
      });
    }
  });

  // Detail Drawer Main Delete Action (handles soft-delete or restore)
  document.getElementById('btn-delete-task').addEventListener('click', () => {
    if (!activeTaskId) return;
    const task = tasks.find(t => t.task_id === activeTaskId);
    if (!task) return;

    if (task.is_deleted) {
      // Restore task
      apiRestoreTask(activeTaskId);
    } else {
      // Soft-delete task
      if (confirm(`Are you sure you want to delete task "${task.title}"?`)) {
        apiDeleteTask(activeTaskId);
      }
    }
  });

  // --- Modals Form Submissions ---

  // Task creation form
  document.getElementById('task-modal').addEventListener('submit', (e) => {
    e.preventDefault();
    const title = document.getElementById('form-title').value.trim();
    const priority = document.getElementById('form-priority').value;
    const due = document.getElementById('form-due').value;
    const desc = document.getElementById('form-desc').value.trim();
    const videoUrl = document.getElementById('form-video').value.trim();
    const tagsVal = document.getElementById('form-tags').value.trim();

    const tags = tagsVal ? tagsVal.split(',').map(t => t.trim()).filter(t => t.length > 0) : [];

    let media = null;
    if (videoUrl) {
      let videoId = '';
      const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
      const match = videoUrl.match(regExp);
      if (match && match[2].length === 11) {
        videoId = match[2];
        media = {
          platform: 'YouTube',
          original_url: videoUrl,
          video_id: videoId,
          title: title,
          creator_or_channel: 'Custom URL Link'
        };
      }
    }

    const newTaskData = {
      title: title,
      description: desc,
      status: 'TODO',
      priority: priority,
      due_date: due ? new Date(due).toISOString() : null,
      is_deleted: false,
      collaborators: [],
      attachment_type: media ? 'VIDEO_LINK' : null,
      media_metadata: media,
      task_specific_tags: tags,
      curated_video_bookmarks: media ? [] : null
    };

    apiCreateTask(newTaskData);
    closeModal('task-modal');
  });

  // Collaborator Invite form
  document.getElementById('collaborator-form').addEventListener('submit', (e) => {
    e.preventDefault();
    if (!activeTaskId) return;
    const task = tasks.find(t => t.task_id === activeTaskId);
    if (!task) return;

    const name = document.getElementById('collab-name').value.trim();
    const role = document.getElementById('collab-role').value.trim();

    const payload = { ...task };
    if (!payload.collaborators) payload.collaborators = [];
    payload.collaborators.push({
      user_id: 'user_' + Date.now(),
      name: name,
      role: role,
      status: 'INVITED'
    });

    apiUpdateTask(activeTaskId, payload).then(() => {
      const updatedTask = tasks.find(t => t.task_id === activeTaskId);
      renderDetailCollaborators(updatedTask);
      renderDetailHistoryTimeline(activeTaskId);
      closeModal('collaborator-modal');
    });
  });

  // Bookmark Add form
  document.getElementById('bookmark-form').addEventListener('submit', (e) => {
    e.preventDefault();
    if (!activeTaskId) return;
    const task = tasks.find(t => t.task_id === activeTaskId);
    if (!task) return;

    const time = document.getElementById('bookmark-time').value.trim();
    const label = document.getElementById('bookmark-label').value.trim();
    const note = document.getElementById('bookmark-note').value.trim();

    let formattedTime = time;
    if (!formattedTime.startsWith('[')) {
      formattedTime = `[${formattedTime}]`;
    }

    const payload = { ...task };
    if (!payload.curated_video_bookmarks) payload.curated_video_bookmarks = [];
    payload.curated_video_bookmarks.push({
      timestamp: formattedTime,
      label: label,
      note: note || null
    });

    payload.curated_video_bookmarks.sort((a, b) => {
      return parseTimestamp(a.timestamp) - parseTimestamp(b.timestamp);
    });

    apiUpdateTask(activeTaskId, payload).then(() => {
      const updatedTask = tasks.find(t => t.task_id === activeTaskId);
      renderDetailBookmarks(updatedTask);
      renderDetailHistoryTimeline(activeTaskId);
      closeModal('bookmark-modal');
    });
  });
});
