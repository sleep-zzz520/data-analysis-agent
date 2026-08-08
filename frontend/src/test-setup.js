// Node 24/25 在当前运行环境会注入无效的 --localstorage-file，导致 happy-dom
// 暴露一个没有 Web Storage 方法的 localStorage。测试只需要进程内存储即可。
if (!globalThis.localStorage || typeof globalThis.localStorage.getItem !== 'function') {
  const values = new Map()
  globalThis.localStorage = {
    getItem: (key) => values.has(String(key)) ? values.get(String(key)) : null,
    setItem: (key, value) => values.set(String(key), String(value)),
    removeItem: (key) => values.delete(String(key)),
    clear: () => values.clear(),
    key: (index) => Array.from(values.keys())[index] || null,
    get length() { return values.size }
  }
}
