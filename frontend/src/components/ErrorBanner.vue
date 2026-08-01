<template>
  <div v-if="error" class="error-banner">
    <svg class="icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <line x1="12" y1="8" x2="12" y2="12"/>
      <line x1="12" y1="16" x2="12.01" y2="16"/>
    </svg>
    <span class="message">{{ error }}</span>
    <button v-if="onRetry" class="retry-btn" @click="onRetry">重试</button>
    <button class="close-btn" @click="$emit('dismiss')" title="关闭">
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18"/>
        <line x1="6" y1="6" x2="18" y2="18"/>
      </svg>
    </button>
  </div>
</template>

<script setup>
defineProps({
  error: String,
  onRetry: Function
})
defineEmits(['dismiss'])
</script>

<style scoped>
.error-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: rgba(239, 68, 68, 0.04);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: var(--radius-md);
  color: #DC2626;
  font-size: 14px;
}

.icon {
  flex-shrink: 0;
  color: #EF4444;
}

.message {
  flex: 1;
  color: #B91C1C;
}

.retry-btn {
  padding: 6px 12px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-sm);
  color: #DC2626;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: var(--transition);
}

.retry-btn:hover {
  background: rgba(239, 68, 68, 0.15);
}

.close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: none;
  border: none;
  color: #86909C;
  cursor: pointer;
  border-radius: 4px;
  transition: var(--transition);
}

.close-btn:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #DC2626;
}
</style>
