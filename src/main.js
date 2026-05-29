import './style.css';

// ==========================================
// 1. STATE & ROUTING
// ==========================================

let tasks = [];
let activeTaskId = null;
let currentView = 'DASHBOARD'; // 'DASHBOARD', 'ARCHIVE', or 'DOCS'
let currentDocsSubtab = 'explorer'; // 'explorer', 'api', 'health', or 'guides'
let currentDocsCommit = ''; // Selected commit hash for versioning (empty string means Live Code)
let activeFilters = {
  search: '',
  priority: 'ALL',
  tag: null
};

// ==========================================
// TASK DISPLAY CONFIGURATION (Single Source of Truth)
// ==========================================
const TASK_DISPLAY_CONFIG = [
  {
    key: 'title',
    label: 'Title',
    render: (val) => val || '<em class="text-muted">Empty</em>',
    equals: (a, b) => a === b
  },
  {
    key: 'description',
    label: 'Description',
    render: (val) => val || '<em class="text-muted">Empty</em>',
    equals: (a, b) => a === b
  },
  {
    key: 'status',
    label: 'Status',
    render: (val) => `<span class="badge" style="background: rgba(255,255,255,0.05);">${val}</span>`,
    equals: (a, b) => a === b
  },
  {
    key: 'priority',
    label: 'Priority',
    render: (val) => `<span class="badge badge-priority-${val}">${val}</span>`,
    equals: (a, b) => a === b
  },
  {
    key: 'due_date',
    label: 'Due Date',
    render: (val) => val ? formatDate(val) : '<em class="text-muted">None</em>',
    equals: (a, b) => {
      if (!a && !b) return true;
      if (!a || !b) return false;
      return a.slice(0, 16) === b.slice(0, 16);
    }
  },
  {
    key: 'task_specific_tags',
    label: 'Tags',
    render: (val) => (val || []).map(t => `<span class="detail-tag-badge">#${t}</span>`).join(' ') || '<em class="text-muted">None</em>',
    equals: (a, b) => JSON.stringify(a) === JSON.stringify(b)
  },
  {
    key: 'collaborators',
    label: 'Collaborators',
    render: (val) => (val || []).map(c => `<span class="badge" style="background: rgba(255,255,255,0.03); margin-bottom: 2px;">${c.name} (${c.role})</span>`).join('<br>') || '<em class="text-muted">None</em>',
    equals: (a, b) => JSON.stringify(a) === JSON.stringify(b)
  },
  {
    key: 'curated_video_bookmarks',
    label: 'Video Bookmarks',
    render: (val) => (val || []).map(b => `<span style="font-size:11px;"><code>${b.timestamp}</code> ${b.label}</span>`).join('<br>') || '<em class="text-muted">None</em>',
    equals: (a, b) => JSON.stringify(a) === JSON.stringify(b)
  }
];

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
    showToast('Database wiped successfully!');
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
// 4. GENERAL UI RENDERING
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

function renderView() {
  if (currentView === 'DASHBOARD') {
    document.getElementById('board-container').style.display = 'grid';
    document.getElementById('archive-container').style.display = 'none';
    document.getElementById('docs-container').style.display = 'none';
    document.getElementById('sidebar-filters-section').style.display = 'block';
    document.getElementById('header-search-box').style.display = 'flex';
    document.getElementById('btn-add-task').style.display = 'inline-flex';
    document.getElementById('page-title').textContent = 'Workspace';
    
    renderBoard();
  } else if (currentView === 'ARCHIVE') {
    document.getElementById('board-container').style.display = 'none';
    document.getElementById('archive-container').style.display = 'block';
    document.getElementById('docs-container').style.display = 'none';
    document.getElementById('sidebar-filters-section').style.display = 'none';
    document.getElementById('header-search-box').style.display = 'none';
    document.getElementById('btn-add-task').style.display = 'none';
    document.getElementById('page-title').textContent = 'Archive & Logs';
    
    renderArchive();
  } else if (currentView === 'DOCS') {
    document.getElementById('board-container').style.display = 'none';
    document.getElementById('archive-container').style.display = 'none';
    document.getElementById('docs-container').style.display = 'flex';
    document.getElementById('sidebar-filters-section').style.display = 'none';
    document.getElementById('header-search-box').style.display = 'none';
    document.getElementById('btn-add-task').style.display = 'none';
    document.getElementById('page-title').textContent = 'Developer Console';
    document.getElementById('task-metrics-summary').textContent = 'Programmatic OOP Reflection & Quality';

    loadDocsSubtab(currentDocsSubtab);
  }
}

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

async function renderArchive() {
  const tbody = document.getElementById('archive-table-body');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 24px;">Loading archive records...</td></tr>';

  try {
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
    tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #f43f5e; padding: 24px;">Failed to load archive.</td></tr>';
  }
}

// ==========================================
// 5. DETAIL DRAWER LOGIC
// ==========================================

async function openDetailDrawer(taskId) {
  let task = tasks.find(t => t.task_id === taskId);
  if (!task) {
    try {
      const res = await fetch(`/api/tasks/${taskId}`);
      if (res.ok) task = await res.json();
    } catch(e) {}
  }
  if (!task) return;

  activeTaskId = taskId;

  const coreBadge = document.getElementById('detail-core-badge');
  coreBadge.style.display = task.is_core ? 'inline-flex' : 'none';

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
    } else if (log.action === 'UPDATED' || log.action === 'ROLLBACK') {
      actionText = log.action === 'ROLLBACK' ? 'Task Rolled Back' : 'Task Updated';
      
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
          <button class="timeline-diff-toggle" data-history-id="${log.history_id}">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="transition: transform var(--transition-fast);">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
            <span>Show Highlighted Diff</span>
          </button>
          ${formatInlineDiff(changes)}
        `;
      }
    }

    const logTime = new Date(log.timestamp).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const logDate = new Date(log.timestamp).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

    const timeTravelBtn = `
      <button class="btn-time-travel" data-history-id="${log.history_id}" title="Inspect state at this version">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <polyline points="12 6 12 12 16 14"/>
        </svg>
      </button>
    `;

    item.innerHTML = `
      <div class="timeline-bullet"></div>
      <div class="timeline-content">
        <div class="timeline-header" style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
          <div style="display: flex; align-items: center; gap: 6px;">
            <span class="timeline-action">${actionText}</span>
            ${timeTravelBtn}
          </div>
          <span class="timeline-time">${logDate} ${logTime}</span>
        </div>
        ${detailsHTML}
      </div>
    `;

    container.appendChild(item);
  });

  // Bind toggle diff buttons
  container.querySelectorAll('.timeline-diff-toggle').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const pane = e.currentTarget.nextElementSibling;
      if (pane && pane.classList.contains('timeline-diff-pane')) {
        const isCollapsed = pane.style.display === 'none' || !pane.style.display;
        pane.style.display = isCollapsed ? 'flex' : 'none';
        
        // Toggle text and SVG arrow orientation
        const btnText = btn.querySelector('span');
        const btnSvg = btn.querySelector('svg');
        if (isCollapsed) {
          btnText.textContent = 'Hide Highlighted Diff';
          btnSvg.style.transform = 'rotate(180deg)';
        } else {
          btnText.textContent = 'Show Highlighted Diff';
          btnSvg.style.transform = 'rotate(0deg)';
        }
      }
    });
  });

  // Bind time-travel inspect buttons
  container.querySelectorAll('.btn-time-travel').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const historyId = e.currentTarget.dataset.historyId;
      openTimeTravelModal(taskId, historyId);
    });
  });
}

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

function handleDrawerFieldChange(field, val) {
  if (!activeTaskId) return;
  const task = tasks.find(t => t.task_id === activeTaskId);
  if (!task) return;

  const payload = { ...task };
  
  if (field === 'title') payload.title = val.trim();
  if (field === 'description') payload.description = val.trim();
  if (field === 'status') payload.status = val;
  if (field === 'due_date') payload.due_date = val ? new Date(val).toISOString() : null;

  apiUpdateTask(activeTaskId, payload).then(() => {
    renderDetailHistoryTimeline(activeTaskId);
  });
}

// ==========================================
// 6. DEVELOPER DOCS & CODE HEALTH ACTIONS
// ==========================================

function loadDocsSubtab(subtab) {
  currentDocsSubtab = subtab;

  // Toggle subnav header styling
  document.querySelectorAll('.docs-subnav-btn').forEach(btn => {
    btn.classList.remove('active');
  });
  const activeBtn = document.querySelector(`.docs-subnav-btn[data-subtab="${subtab}"]`);
  if (activeBtn) activeBtn.classList.add('active');

  // Toggle panel visibility
  document.querySelectorAll('.docs-subtab-panel').forEach(panel => {
    panel.style.display = 'none';
  });
  const activePanel = document.getElementById(`panel-${subtab}`);
  if (activePanel) activePanel.style.display = 'flex';

  // Load specific tab data
  if (subtab === 'explorer') {
    loadClassExplorer();
  } else if (subtab === 'api') {
    loadApiReference();
  } else if (subtab === 'health') {
    loadCodeHealth();
  } else if (subtab === 'guides') {
    loadArchitectureGuides();
  } else if (subtab === 'tests') {
    loadTestSuite();
  }
}

async function loadClassExplorer() {
  const container = document.getElementById('class-explorer-container');
  if (!container) return;
  
  container.innerHTML = '<div style="grid-column: 1/-1; text-align:center; padding: 24px;">Loading codebase files...</div>';

  try {
    const url = currentDocsCommit ? `/api/docs/metadata?commit=${currentDocsCommit}` : '/api/docs/metadata';
    const response = await fetch(url);
    if (!response.ok) throw new Error();
    const data = await response.json();

    container.innerHTML = '';
    
    data.files.forEach(file => {
      file.classes.forEach(cls => {
        const card = document.createElement('div');
        card.className = 'class-card';

        const docstringHTML = cls.docstring ? `
          <div class="class-docstring">"${cls.docstring.trim()}"</div>
        ` : '';

        const methodsHTML = cls.methods.length > 0 ? `
          <div class="class-methods-section">
            <span class="class-methods-title">Methods</span>
            <div class="methods-list">
              ${cls.methods.map(m => `
                <div class="method-item">
                  <div class="method-item-header">
                    <span class="method-signature">
                      def <span class="method-name">${m.name}</span>(<span class="method-args">${m.args.join(', ')}</span>)
                    </span>
                    <span class="method-line-badge">Line ${m.line}</span>
                  </div>
                  ${m.docstring ? `<p class="method-doc">${m.docstring.trim()}</p>` : ''}
                </div>
              `).join('')}
            </div>
          </div>
        ` : '<p class="text-muted" style="font-size:11px;">No class methods defined.</p>';

        card.innerHTML = `
          <div class="class-card-header">
            <h3>${cls.name}</h3>
            <span class="class-card-file">${file.file_name}</span>
          </div>
          ${docstringHTML}
          ${methodsHTML}
        `;

        container.appendChild(card);
      });
    });
  } catch (error) {
    console.error(error);
    container.innerHTML = '<div style="grid-column: 1/-1; text-align:center; color: #f43f5e; padding: 24px;">Failed to reflect OOP codebase metadata.</div>';
  }
}

async function loadApiReference() {
  const tbody = document.getElementById('api-ref-table-body');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="3" style="text-align: center; padding: 24px;">Loading specifications...</td></tr>';

  try {
    const endpoints = [
      { path: '/api/tasks', method: 'GET', desc: 'Queries active tasks list (or archived if include_deleted=true).' },
      { path: '/api/tasks', method: 'POST', desc: 'Creates a new task. Requires a JSON body (title is mandatory) and logs a CREATED event.' },
      { path: '/api/tasks/<id>', method: 'GET', desc: 'Queries a single task object by ID.' },
      { path: '/api/tasks/<id>', method: 'PUT', desc: 'Updates task values. Diffs inputs against current data and auto-logs UPDATED logs detailing differences.' },
      { path: '/api/tasks/<id>', method: 'DELETE', desc: 'Soft-deletes task (sets is_deleted = true) and logs a DELETED event.' },
      { path: '/api/tasks/<id>/restore', method: 'POST', desc: 'Restores a soft-deleted task back to the Kanban board and logs a RESTORED event.' },
      { path: '/api/tasks/<id>/history', method: 'GET', desc: 'Fetches the chronological audit timeline history logs for a task.' },
      { path: '/api/reset', method: 'POST', desc: 'Wipes all database tasks and history logs, leaving a blank canvas.' },
      { path: '/api/docs/metadata', method: 'GET', desc: 'Dynamically parses codebase modules (using python ast) and reflects OOP class metadata.' },
      { path: '/api/docs/health', method: 'GET', desc: 'Compiles real-time AST syntax lint warnings and calculates a codebase quality score.' },
      { path: '/api/docs/guides', method: 'GET', desc: 'Returns a list of available static guide filenames.' },
      { path: '/api/docs/guides/<name>', method: 'GET', desc: 'Reads and retrieves guide contents.' }
    ];

    tbody.innerHTML = '';
    endpoints.forEach(e => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="api-route-cell">${e.path}</td>
        <td><span class="api-method-badge ${e.method}">${e.method}</span></td>
        <td class="api-desc-cell">${e.desc}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: #f43f5e; padding: 24px;">Failed to load API Reference.</td></tr>';
  }
}

async function loadCodeHealth() {
  const tbody = document.getElementById('warnings-table-body');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 24px;">Analyzing code quality...</td></tr>';

  try {
    const url = currentDocsCommit ? `/api/docs/health?commit=${currentDocsCommit}` : '/api/docs/health';
    const response = await fetch(url);
    if (!response.ok) throw new Error();
    const data = await response.json();

    // 1. Update summary statistics
    document.getElementById('health-stat-files').textContent = data.files_scanned || 0;
    document.getElementById('health-stat-classes').textContent = data.stats.classes || 0;
    document.getElementById('health-stat-methods').textContent = data.stats.methods || 0;
    
    const score = data.score || 0;
    document.getElementById('health-score-text').textContent = `${score}%`;

    // 2. Animate SVG circular ring
    const fillCircle = document.getElementById('health-gauge-fill');
    if (fillCircle) {
      const circumference = 2 * Math.PI * 50; // r=50 -> ~314.16
      const offset = circumference - (score / 100) * circumference;
      fillCircle.style.strokeDashoffset = offset;
      
      // Dynamic coloring based on score
      if (score >= 90) {
        fillCircle.style.stroke = '#10b981'; // Green
      } else if (score >= 70) {
        fillCircle.style.stroke = '#fbbf24'; // Amber Gold
      } else {
        fillCircle.style.stroke = '#f43f5e'; // Red
      }
    }

    // 3. Render warnings table
    tbody.innerHTML = '';
    const warnings = data.warnings || [];
    
    if (warnings.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="4" style="text-align: center; padding: 36px; color: var(--color-status-completed); font-weight: 500;">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="vertical-align: middle; margin-right: 6px;"><polyline points="20 6 9 17 4 12"/></svg>
            Excellent! Your codebase is 100% clean and documented.
          </td>
        </tr>
      `;
      return;
    }

    warnings.forEach(w => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="warning-file">${w.file}</td>
        <td class="warning-scope">${w.scope}</td>
        <td class="warning-issue">
          <span class="warning-issue-badge ${w.severity}">${w.severity}</span>
          ${w.issue}
        </td>
        <td>${w.line}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (error) {
    console.error(error);
    tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #f43f5e; padding: 24px;">Failed to load codebase health audit report.</td></tr>';
  }
}

async function loadArchitectureGuides() {
  const container = document.getElementById('guides-list-container');
  if (!container) return;

  container.innerHTML = '<div style="padding: 12px; font-size: 12px;">Loading guides...</div>';

  try {
    const response = await fetch('/api/docs/guides');
    if (!response.ok) throw new Error();
    const guides = await response.json();

    container.innerHTML = '';
    
    if (guides.length === 0) {
      container.innerHTML = '<div class="text-muted" style="padding:12px;">No guides configured.</div>';
      return;
    }

    guides.forEach((g, idx) => {
      const btn = document.createElement('button');
      btn.className = `guide-btn ${idx === 0 ? 'active' : ''}`;
      btn.textContent = g.replace(/_/g, ' ');
      btn.dataset.name = g;
      
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.guide-btn').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        fetchAndShowGuide(g);
      });

      container.appendChild(btn);
    });

    // Load first guide by default
    if (guides.length > 0) {
      fetchAndShowGuide(guides[0]);
    }
  } catch (error) {
    console.error(error);
    container.innerHTML = '<div style="color: #f43f5e; padding: 12px;">Error listing documentation guides.</div>';
  }
}

async function fetchAndShowGuide(guideName) {
  const pane = document.getElementById('guide-preview-body');
  if (!pane) return;

  pane.innerHTML = '<div style="text-align: center; padding: 64px 20px;">Fetching guide content...</div>';

  try {
    const url = currentDocsCommit ? `/api/docs/guides/${guideName}?commit=${currentDocsCommit}` : `/api/docs/guides/${guideName}`;
    const response = await fetch(url);
    if (!response.ok) throw new Error();
    const data = await response.json();

    // Parse Markdown content to HTML
    pane.innerHTML = parseMarkdown(data.content);
  } catch (error) {
    console.error(error);
    pane.innerHTML = '<div style="text-align: center; color: #f43f5e; padding: 64px 20px;">Failed to read guide.</div>';
  }
}

async function loadTestSuite() {
  const tbody = document.getElementById('tests-table-body');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 24px;">Loading test suite status...</td></tr>';

  try {
    const response = await fetch('/api/docs/tests');
    if (!response.ok) throw new Error();
    const data = await response.json();
    renderTestResults(data);
  } catch (error) {
    console.error('Failed to load test suite status:', error);
    tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--color-danger); padding: 24px;">Failed to load test suite.</td></tr>';
  }
}

async function runTestSuite(scope = null) {
  const globalBtn = document.getElementById('btn-run-tests');
  const globalSpinner = document.getElementById('tests-btn-spinner');
  const globalBtnText = document.getElementById('btn-run-tests-text');
  
  if (globalBtn) globalBtn.disabled = true;
  if (globalSpinner) globalSpinner.style.display = 'inline-block';
  if (globalBtnText) globalBtnText.textContent = scope ? 'Running Scope...' : 'Running All...';

  document.querySelectorAll('.btn-run-single-test').forEach(btn => {
    btn.disabled = true;
    if (scope && btn.dataset.scope === scope) {
      btn.classList.add('running-single');
    }
  });

  try {
    const response = await fetch('/api/docs/tests/run', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ scope })
    });
    if (!response.ok) throw new Error();
    const data = await response.json();
    renderTestResults(data);
  } catch (error) {
    console.error('Failed to run test suite:', error);
    alert('Failed to execute test suite.');
  } finally {
    if (globalBtn) globalBtn.disabled = false;
    if (globalSpinner) globalSpinner.style.display = 'none';
    if (globalBtnText) globalBtnText.textContent = 'Run All Tests';
    
    document.querySelectorAll('.btn-run-single-test').forEach(btn => {
      btn.disabled = false;
      btn.classList.remove('running-single');
    });
  }
}

function renderTestResults(data) {
  const total = data.stats.total || 0;
  const passed = data.stats.passed || 0;
  const failed = data.stats.failed || 0;
  const duration = data.duration || 0.00;
  const successRate = data.stats.success_rate || 0;

  const totalEl = document.getElementById('tests-stat-total');
  const passedEl = document.getElementById('tests-stat-passed');
  const failedEl = document.getElementById('tests-stat-failed');
  const durationEl = document.getElementById('tests-stat-duration');
  const scoreTextEl = document.getElementById('tests-score-text');

  if (totalEl) totalEl.textContent = total;
  if (passedEl) passedEl.textContent = passed;
  if (failedEl) failedEl.textContent = failed;
  if (durationEl) durationEl.textContent = `${duration.toFixed(2)}s`;
  if (scoreTextEl) scoreTextEl.textContent = `${successRate}%`;

  const fillCircle = document.getElementById('tests-gauge-fill');
  if (fillCircle) {
    const circumference = 2 * Math.PI * 50;
    const offset = circumference - (successRate / 100) * circumference;
    fillCircle.style.strokeDashoffset = offset;
    
    if (successRate >= 90) {
      fillCircle.style.stroke = 'var(--color-success)';
    } else if (successRate >= 70) {
      fillCircle.style.stroke = '#f59e0b';
    } else {
      fillCircle.style.stroke = 'var(--color-danger)';
    }
  }

  const tbody = document.getElementById('tests-table-body');
  if (!tbody) return;

  if (!data.results || data.results.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 24px;">No test results available. Click Run All to execute tests.</td></tr>';
    return;
  }

  tbody.innerHTML = '';
  data.results.forEach((test, idx) => {
    const tr = document.createElement('tr');
    
    let component = 'Models';
    if (test.class.includes('Repository')) {
      component = 'Repositories';
    } else if (test.class.includes('Service')) {
      component = 'Services';
    } else if (test.class.includes('API') || test.class.includes('Flask')) {
      component = 'APIs';
    }

    let badgeClass = 'status-pending';
    if (test.status === 'PASS') {
      badgeClass = 'status-pass';
    } else if (test.status === 'FAIL') {
      badgeClass = 'status-fail';
    } else if (test.status === 'ERROR') {
      badgeClass = 'status-error';
    }
    
    let errorLogHTML = '';
    if (test.status === 'FAIL' || test.status === 'ERROR') {
      errorLogHTML = `
        <div class="test-details-container" style="margin-top: 8px;">
          <button class="btn-toggle-traceback" data-trace-id="trace-${idx}">Show Traceback Details</button>
          <pre class="test-traceback-pane" id="trace-${idx}">${escapeHtml(test.message)}</pre>
        </div>
      `;
    } else if (test.status === 'PENDING') {
      errorLogHTML = `
        <div style="margin-top: 4px;">
          <span style="font-size: 11px; color: var(--color-text-muted); font-style: italic;">Not run yet</span>
        </div>
      `;
    }

    const caseScope = `${test.class}.${test.name}`;

    tr.innerHTML = `
      <td><span class="badge font-display" style="font-size: 10px; font-weight: 700;">${component}</span></td>
      <td>
        <div style="display: flex; flex-direction: column; gap: 4px;">
          <span style="font-weight: 600; font-family: var(--font-sans); color: var(--color-text-primary);">${test.name.replace(/_/g, ' ')}</span>
          <span style="font-size: 11px; color: var(--color-text-muted);">${test.class}.${test.name}()</span>
        </div>
      </td>
      <td>
        <span class="test-status-badge ${badgeClass}">${test.status}</span>
      </td>
      <td>
        <div style="display: flex; flex-direction: column; gap: 4px; align-items: flex-start;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="text-muted" style="font-size: 11px;">Duration: ${test.duration.toFixed(3)}s</span>
            <button class="btn-run-single-test" data-scope="${caseScope}">
              <span>▶</span> Run Case
            </button>
          </div>
          ${errorLogHTML}
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });

  tbody.querySelectorAll('.btn-toggle-traceback').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const traceId = e.currentTarget.dataset.traceId;
      const pane = document.getElementById(traceId);
      if (pane) {
        const isHidden = pane.style.display === 'none' || !pane.style.display;
        pane.style.display = isHidden ? 'block' : 'none';
        e.currentTarget.textContent = isHidden ? 'Hide Traceback Details' : 'Show Traceback Details';
      }
    });
  });

  tbody.querySelectorAll('.btn-run-single-test').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const scope = e.currentTarget.dataset.scope;
      runTestSuite(scope);
    });
  });
}

function escapeHtml(text) {
  if (!text) return '';
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

async function fetchDocsCommits() {
  const select = document.getElementById('docs-version-select');
  if (!select) return;
  
  try {
    const response = await fetch('/api/docs/commits');
    if (!response.ok) throw new Error();
    const commits = await response.json();
    
    const currentVal = select.value;
    
    select.innerHTML = '<option value="">Live Code (Local Disk)</option>';
    
    commits.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c.hash;
      opt.textContent = `${c.hash} - ${c.subject} (${c.date})`;
      select.appendChild(opt);
    });
    
    if ([...select.options].some(o => o.value === currentVal)) {
      select.value = currentVal;
    } else {
      currentDocsCommit = '';
    }
  } catch (err) {
    console.error('Failed to fetch doc commits:', err);
  }
}

// Client-side simple Markdown regex-to-html parser
function parseMarkdown(md) {
  if (!md) return '';
  let html = md;

  // Escape HTML elements to prevent scripting injections
  html = html.replace(/</g, '&lt;').replace(/>/g, '&gt;');

  // 1. Code blocks (Fenced pre blocks)
  html = html.replace(/```([a-zA-Z0-9_\-]+)?\n([\s\S]*?)```/g, (match, lang, code) => {
    return `<pre><code class="language-${lang || 'text'}">${code.trim()}</code></pre>`;
  });

  // 2. Inline Code block highlights
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // 3. Headers (H3, H2, H1)
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

  // 4. Horizontal Rule lines
  html = html.replace(/^---$/gim, '<hr>');

  // 5. Bold markup
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

  // 6. Bullet lists
  html = html.replace(/^\s*-\s+(.*$)/gim, '<li>$1</li>');
  html = html.replace(/^\s*\*\s+(.*$)/gim, '<li>$1</li>');
  html = html.replace(/(<li>[\s\S]*?<\/li>)+/g, '<ul>$&</ul>');

  // 7. Process paragraphs dynamically
  const lines = html.split('\n');
  let finalHtml = '';
  let inPre = false;
  let inUl = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.startsWith('<pre>')) inPre = true;
    if (line.endsWith('</pre>')) inPre = false;
    if (line.startsWith('<ul>')) inUl = true;
    if (line.endsWith('</ul>')) inUl = false;

    if (!line) {
      finalHtml += '\n';
      continue;
    }

    if (!inPre && !inUl && !line.startsWith('<h') && !line.startsWith('<hr') && !line.startsWith('<ul') && !line.startsWith('</ul') && !line.startsWith('<li')) {
      finalHtml += `<p>${lines[i]}</p>\n`;
    } else {
      finalHtml += lines[i] + '\n';
    }
  }

  return `<div class="guide-content">${finalHtml}</div>`;
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
// MODAL UTILITIES (RESTORED)
// ==========================================
function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.add('open');
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.remove('open');
}

// ==========================================
// TIME-TRAVEL & SIDE-BY-SIDE DIFF LOGIC
// ==========================================
function formatInlineDiff(changes) {
  if (!changes || changes.length === 0) return '';
  
  let html = `<div class="timeline-diff-pane">`;
  
  changes.forEach(c => {
    let oldVal = c.old;
    let newVal = c.new;
    
    if (Array.isArray(oldVal) || Array.isArray(newVal)) {
      const oldArr = Array.isArray(oldVal) ? oldVal : [];
      const newArr = Array.isArray(newVal) ? newVal : [];
      
      const removed = oldArr.filter(x => !newArr.includes(x));
      const added = newArr.filter(x => !oldArr.includes(x));
      const unchanged = oldArr.filter(x => newArr.includes(x));
      
      let diffHtml = '';
      removed.forEach(r => {
        diffHtml += `<span class="diff-val-box diff-deleted">#${r}</span> `;
      });
      added.forEach(a => {
        diffHtml += `<span class="diff-val-box diff-added">#${a}</span> `;
      });
      unchanged.forEach(u => {
        diffHtml += `<span class="diff-val-box diff-unchanged">#${u}</span> `;
      });
      
      html += `
        <div class="timeline-diff-row">
          <span class="timeline-diff-field">${c.field.replace(/_/g, ' ')}</span>
          <span class="timeline-diff-vals">${diffHtml || 'None'}</span>
        </div>
      `;
    } else if (c.field === 'collaborators') {
      const oldNames = (oldVal || []).map(col => `${col.name} (${col.role})`);
      const newNames = (newVal || []).map(col => `${col.name} (${col.role})`);
      
      const removed = oldNames.filter(x => !newNames.includes(x));
      const added = newNames.filter(x => !oldNames.includes(x));
      const unchanged = oldNames.filter(x => newNames.includes(x));
      
      let diffHtml = '';
      removed.forEach(r => {
        diffHtml += `<span class="diff-val-box diff-deleted">${r}</span> `;
      });
      added.forEach(a => {
        diffHtml += `<span class="diff-val-box diff-added">${a}</span> `;
      });
      unchanged.forEach(u => {
        diffHtml += `<span class="diff-val-box diff-unchanged">${u}</span> `;
      });
      
      html += `
        <div class="timeline-diff-row">
          <span class="timeline-diff-field">collaborators</span>
          <span class="timeline-diff-vals">${diffHtml || 'None'}</span>
        </div>
      `;
    } else if (c.field === 'curated_video_bookmarks') {
      const oldBms = (oldVal || []).map(b => `${b.timestamp} - ${b.label}`);
      const newBms = (newVal || []).map(b => `${b.timestamp} - ${b.label}`);
      
      const removed = oldBms.filter(x => !newBms.includes(x));
      const added = newBms.filter(x => !oldBms.includes(x));
      
      let diffHtml = '';
      removed.forEach(r => {
        diffHtml += `<span class="diff-val-box diff-deleted">${r}</span> `;
      });
      added.forEach(a => {
        diffHtml += `<span class="diff-val-box diff-added">${a}</span> `;
      });
      
      html += `
        <div class="timeline-diff-row">
          <span class="timeline-diff-field">video bookmarks</span>
          <span class="timeline-diff-vals">${diffHtml || 'No changes'}</span>
        </div>
      `;
    } else {
      let displayOld = oldVal === null ? 'None' : oldVal;
      let displayNew = newVal === null ? 'None' : newVal;
      
      if (c.field === 'due_date') {
        displayOld = oldVal ? formatDate(oldVal) : 'None';
        displayNew = newVal ? formatDate(newVal) : 'None';
      }
      
      html += `
        <div class="timeline-diff-row">
          <span class="timeline-diff-field">${c.field.replace(/_/g, ' ')}</span>
          <span class="timeline-diff-vals">
            <span class="diff-val-box diff-deleted">${displayOld}</span>
            <span class="timeline-diff-arrow">➜</span>
            <span class="diff-val-box diff-added">${displayNew}</span>
          </span>
        </div>
      `;
    }
  });
  
  html += `</div>`;
  return html;
}

async function openTimeTravelModal(taskId, historyId) {
  try {
    const response = await fetch(`/api/tasks/${taskId}/history/${historyId}`);
    if (!response.ok) throw new Error('Failed to fetch reconstructed task state');
    const data = await response.json();

    const reconstructed = data.reconstructed;
    const log = data.log;
    const current = tasks.find(t => t.task_id === taskId);
    
    if (!current) throw new Error('Current live task state not found');

    // 1. Update Subtitle
    const logTime = new Date(log.timestamp).toLocaleString();
    document.getElementById('time-travel-subtitle').textContent = 
      `Comparing version after event [${log.action}] at ${logTime} with current live task state.`;

    // 2. Render side-by-side diff
    const container = document.getElementById('time-travel-diff-body');
    container.innerHTML = '';

    // Build left & right columns
    const leftCol = document.createElement('div');
    leftCol.className = 'diff-column old';
    leftCol.innerHTML = `<h3>Historical State (${log.action})</h3>`;

    const rightCol = document.createElement('div');
    rightCol.className = 'diff-column new';
    rightCol.innerHTML = `<h3>Current Live State</h3>`;

    TASK_DISPLAY_CONFIG.forEach(f => {
      const valOld = reconstructed[f.key];
      const valNew = current[f.key];

      const isChanged = !f.equals(valOld, valNew);
      const cardClass = `diff-field-card ${isChanged ? 'changed' : ''}`;

      const reprOld = f.render(valOld);
      const reprNew = f.render(valNew);

      // Add diff styling highlight classes if changed
      const valClassOld = isChanged ? 'diff-val-box diff-deleted' : 'diff-val-box diff-unchanged';
      const valClassNew = isChanged ? 'diff-val-box diff-added' : 'diff-val-box diff-unchanged';

      leftCol.innerHTML += `
        <div class="${cardClass}">
          <span class="diff-field-lbl">${f.label}</span>
          <div class="${valClassOld}">${reprOld}</div>
        </div>
      `;

      rightCol.innerHTML += `
        <div class="${cardClass}">
          <span class="diff-field-lbl">${f.label}</span>
          <div class="${valClassNew}">${reprNew}</div>
        </div>
      `;
    });

    container.appendChild(leftCol);
    container.appendChild(rightCol);

    // 3. Bind Rollback Button with these parameters
    const rollbackBtn = document.getElementById('time-travel-rollback-btn');
    const newRollbackBtn = rollbackBtn.cloneNode(true);
    rollbackBtn.parentNode.replaceChild(newRollbackBtn, rollbackBtn);
    
    newRollbackBtn.addEventListener('click', async () => {
      if (confirm(`Are you sure you want to rollback this task to the state of ${logTime}? This will record a new ROLLBACK event.`)) {
        try {
          const res = await fetch(`/api/tasks/${taskId}/rollback/${historyId}`, { method: 'POST' });
          if (!res.ok) throw new Error('Rollback failed on server');
          showToast('Task successfully rolled back!');
          closeModal('time-travel-modal');
          await fetchTasks();
          renderView();
          openDetailDrawer(taskId);
        } catch (err) {
          console.error(err);
          showToast('Error performing rollback.');
        }
      }
    });

    openModal('time-travel-modal');
  } catch (err) {
    console.error(err);
    showToast('Failed to open Time-Travel inspector.');
  }
}

// ==========================================
// 8. EVENT BINDINGS
// ==========================================

document.addEventListener('DOMContentLoaded', async () => {
  await fetchTasks();
  renderView();

  // --- View toggles ---
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

  document.getElementById('nav-docs').addEventListener('click', async (e) => {
    document.querySelectorAll('.sidebar-nav .nav-item').forEach(el => el.classList.remove('active'));
    e.currentTarget.classList.add('active');
    currentView = 'DOCS';
    await fetchDocsCommits();
    renderView();
  });

  // --- Sub-navigation clicks inside Dev Docs ---
  document.querySelectorAll('.docs-subnav-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const subtab = e.currentTarget.dataset.subtab;
      loadDocsSubtab(subtab);
    });
  });

  const selectEl = document.getElementById('docs-version-select');
  if (selectEl) {
    selectEl.addEventListener('change', (e) => {
      currentDocsCommit = e.target.value;
      loadDocsSubtab(currentDocsSubtab);
    });
  }

  const runTestsBtn = document.getElementById('btn-run-tests');
  if (runTestsBtn) {
    runTestsBtn.addEventListener('click', () => {
      runTestSuite();
    });
  }

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
    if (confirm('Are you sure you want to reset the database? This will clear all tasks and history, leaving a blank canvas.')) {
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

  // Time Travel Modal
  document.getElementById('time-travel-close-btn').addEventListener('click', () => closeModal('time-travel-modal'));
  document.getElementById('time-travel-cancel-btn').addEventListener('click', () => closeModal('time-travel-modal'));

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

  // Drawer Main delete/restore button
  document.getElementById('btn-delete-task').addEventListener('click', () => {
    if (!activeTaskId) return;
    const task = tasks.find(t => t.task_id === activeTaskId);
    if (!task) return;

    if (task.is_deleted) {
      apiRestoreTask(activeTaskId);
    } else {
      if (confirm(`Are you sure you want to delete task "${task.title}"?`)) {
        apiDeleteTask(activeTaskId);
      }
    }
  });

  // --- Modals Form Submissions ---

  // Task creation form
  document.getElementById('task-form').addEventListener('submit', (e) => {
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

  // --- Click outside modal overlay to close it ---
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        closeModal(overlay.id);
      }
    });
  });

  // --- Escape key press to close active modals ---
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay.open').forEach(overlay => {
        closeModal(overlay.id);
      });
    }
  });
});
