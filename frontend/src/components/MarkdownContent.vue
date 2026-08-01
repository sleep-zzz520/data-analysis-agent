<template>
  <div class="md" v-html="html"></div>
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps({ content: String })

marked.setOptions({ gfm: true, breaks: true })

const html = computed(() => {
  const raw = props.content || ''
  // async: false → 同步返回 HTML 字符串（marked v18）
  const unsafe = marked.parse(raw, { async: false })
  return DOMPurify.sanitize(unsafe)
})
</script>

<style scoped>
/* ── Markdown 渲染样式 ── */
.md { line-height: 1.75; font-size: 14.5px; word-break: break-word; }
.md > :first-child { margin-top: 0; }
.md > :last-child { margin-bottom: 0; }

.md p { margin: 0.45em 0; }
.md h1, .md h2, .md h3, .md h4, .md h5, .md h6 {
  margin: 0.9em 0 0.4em;
  font-weight: 700;
  line-height: 1.4;
  color: var(--text-primary);
}
.md h1 { font-size: 1.35em; border-bottom: 1px solid var(--border-light); padding-bottom: 0.25em; }
.md h2 { font-size: 1.2em; }
.md h3 { font-size: 1.08em; }
.md h4, .md h5, .md h6 { font-size: 1em; }

.md strong { font-weight: 700; color: var(--text-primary); }
.md em { font-style: italic; }

.md ul, .md ol { margin: 0.45em 0; padding-left: 1.4em; }
.md li { margin: 0.2em 0; }
.md li::marker { color: var(--brand-start); }
.md ul ul, .md ol ul, .md ul ol, .md ol ol { margin: 0.15em 0; }

.md blockquote {
  margin: 0.6em 0;
  padding: 0.3em 0.9em;
  border-left: 3px solid var(--brand-start);
  background: rgba(0, 0, 0, 0.04);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  color: var(--text-secondary);
}
.md blockquote p { margin: 0.2em 0; }

.md code {
  font-family: var(--font-mono);
  font-size: 0.88em;
  background: rgba(0, 0, 0, 0.06);
  color: #1F1F1F;
  padding: 0.12em 0.35em;
  border-radius: 4px;
}
.md pre {
  margin: 0.7em 0;
  padding: 12px 14px;
  background: #1E1E2E;
  border-radius: var(--radius-sm);
  overflow-x: auto;
  line-height: 1.55;
}
.md pre code {
  background: none;
  color: #CDD6F4;
  padding: 0;
  font-size: 12.5px;
}

.md table {
  border-collapse: collapse;
  margin: 0.7em 0;
  width: 100%;
  font-size: 13px;
  display: block;
  overflow-x: auto;
}
.md th, .md td {
  border: 1px solid var(--border-color);
  padding: 6px 10px;
  text-align: left;
  white-space: nowrap;
}
.md th { background: var(--bg-tertiary); font-weight: 600; }
.md tr:nth-child(even) td { background: rgba(0, 0, 0, 0.015); }

.md hr {
  border: none;
  border-top: 1px solid var(--border-color);
  margin: 0.9em 0;
}

.md a { color: var(--brand-start); text-decoration: none; }
.md a:hover { text-decoration: underline; }

.md img { max-width: 100%; border-radius: var(--radius-sm); }
</style>
