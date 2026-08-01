<template>
  <div class="app">
    <header class="topbar">
      <div class="topbar-inner">
        <span class="brand">
          <svg class="brand-icon" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="url(#grad)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <defs><linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#1F1F1F"/><stop offset="100%" stop-color="#444444"/></linearGradient></defs>
            <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
          </svg>
          数据分析 Agent
        </span>
        <nav class="nav">
          <router-link to="/chat" class="navlink" active-class="active">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            分析对话
          </router-link>
          <router-link to="/config" class="navlink" active-class="active">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
            配置中心
          </router-link>
        </nav>
      </div>
    </header>
    <main class="page" :class="{ 'page-fluid': $route.name === 'chat' }"><router-view /></main>
  </div>
</template>

<style>
/* ── Design System Tokens ── */
:root {
  --bg-primary: #FFFFFF;
  --bg-secondary: #F7F8FA;
  --bg-tertiary: #F2F3F5;
  --text-primary: #1D2129;
  --text-secondary: #4E5969;
  --text-tertiary: #86909C;
  --brand-start: #1F1F1F;
  --brand-end: #444444;
  --brand-gradient: linear-gradient(135deg, #1F1F1F 0%, #444444 100%);
  --border-color: #E5E6EB;
  --border-light: #F0F1F3;
  --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.04);
  --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.06);
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.08);
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-xl: 24px;
  --font-stack: -apple-system, BlinkMacSystemFont, "PingFang SC", "Helvetica Neue", Arial, sans-serif;
  --font-mono: "SF Mono", "Fira Code", "Consolas", monospace;
  --transition: all 0.2s ease;
}

/* ── Reset & Base ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: 15px; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }
body {
  font-family: var(--font-stack);
  color: var(--text-primary);
  background: var(--bg-secondary);
  line-height: 1.6;
}

/* ── App Shell ── */
.app { min-height: 100vh; display: flex; flex-direction: column; }

/* ── Topbar ── */
.topbar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-color);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
}
.topbar-inner {
  max-width: 1200px; margin: 0 auto;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px; height: 56px;
}
.brand {
  display: flex; align-items: center; gap: 8px;
  font-weight: 700; font-size: 17px; color: var(--text-primary);
  letter-spacing: -0.02em;
}
.brand-icon { flex: none; }

/* ── Navigation ── */
.nav { display: flex; align-items: center; gap: 4px; }
.navlink {
  display: flex; align-items: center; gap: 6px;
  padding: 7px 14px; border-radius: var(--radius-sm);
  font-size: 14px; font-weight: 500;
  color: var(--text-secondary);
  text-decoration: none;
  transition: var(--transition);
}
.navlink:hover { color: var(--text-primary); background: var(--bg-tertiary); }
.navlink.active {
  color: var(--brand-start);
  background: rgba(0, 0, 0, 0.06);
  font-weight: 600;
}

/* ── Page Container ── */
.page {
  flex: 1;
  max-width: 1200px; width: 100%;
  margin: 0 auto;
  padding: 20px 24px;
}
/* 聊天页通栏：去掉左右留白，让历史会话贴左、对话区贴右 */
.page-fluid {
  max-width: none;
  padding: 20px 0;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: #E5E6EB;
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: #C0C2C8;
}

/* ── Selection ── */
::selection { background: rgba(0, 0, 0, 0.12); }
</style>
