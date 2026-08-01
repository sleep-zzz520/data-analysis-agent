import { defineStore } from 'pinia'
import * as cfgApi from '../api/config.js'

const SID_KEY = 'da_session_id'
const stored_sid = localStorage.getItem(SID_KEY) || crypto.randomUUID()

export const useConfigStore = defineStore('config', {
  state: () => ({
    llmList: [], dbList: [],
    currentLlmId: null, currentDbId: null,
    sessionId: stored_sid
  }),
  getters: {
    currentLlm: (s) => s.llmList.find((x) => x.id === s.currentLlmId) || null,
    currentDb:  (s) => s.dbList.find((x) => x.id === s.currentDbId) || null,
    ready: (s) => !!s.currentLlmId && !!s.currentDbId
  },
  actions: {
    async loadAll() {
      const [llm, db] = await Promise.all([cfgApi.listLlm(), cfgApi.listDb()])
      this.llmList = llm || []; this.dbList = db || []
      this.currentLlmId = (this.currentLlmId && this.llmList.some((x) => x.id === this.currentLlmId))
        ? this.currentLlmId : (this.llmList.find((x) => x.is_default)?.id ?? this.llmList[0]?.id ?? null)
      this.currentDbId = (this.currentDbId && this.dbList.some((x) => x.id === this.currentDbId))
        ? this.currentDbId : (this.dbList.find((x) => x.is_default)?.id ?? this.dbList[0]?.id ?? null)
    },
    newSession() {
      this.sessionId = crypto.randomUUID()
      localStorage.setItem(SID_KEY, this.sessionId)
    },
    setSession(id) {
      this.sessionId = id
      localStorage.setItem(SID_KEY, id)
    }
  }
})
