<template>
  <div class="variable-selector">
    <div class="selector-header">
      <h3>变量选择</h3>
      <div class="search-box">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索变量..."
          class="search-input"
        />
        <span class="search-icon">🔍</span>
      </div>
    </div>

    <div class="info-bar">
      <span class="info-text">
        已选中 {{ selectedCount }} 个变量
      </span>
      <button
        @click="applySelection"
        class="apply-btn"
        :disabled="selectedCount === 0 || loading"
      >
        {{ loading ? '加载中...' : '应用选择' }}
      </button>
    </div>

    <div class="categories-container">
      <div
        v-for="(vars, category) in filteredCategories"
        :key="category"
        class="category-section"
      >
        <div
          class="category-header"
          @click="toggleCategory(category)"
        >
          <span class="category-icon">{{ getCategoryIcon(category) }}</span>
          <span class="category-name">{{ category }}</span>
          <span class="category-count">({{ vars.length }})</span>
          <span class="toggle-icon">{{ expandedCategories[category] ? '▼' : '▶' }}</span>
        </div>

        <div
          v-show="expandedCategories[category]"
          class="variables-list"
        >
          <div
            v-for="variable in vars"
            :key="variable"
            class="variable-item"
            @click="toggleVariable(variable)"
          >
            <input
              type="checkbox"
              :id="variable"
              :checked="isSelected(variable)"
              @change="toggleVariable(variable)"
              class="variable-checkbox"
            />
            <label
              :for="variable"
              class="variable-label"
            >
              {{ formatVariableName(variable) }}
            </label>
          </div>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading-overlay">
      <div class="spinner"></div>
      <p>加载数据中...</p>
    </div>

    <div v-if="error" class="error-message">
      {{ error }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useDroneStore } from '@/store/drone'
import { storeToRefs } from 'pinia'

const droneStore = useDroneStore()
const {
  categorizedVars,
  selectedVariables,
  loading,
  error
} = storeToRefs(droneStore.replayAnalysis)

const searchQuery = ref('')
const expandedCategories = ref({})

// 计算属性
const selectedCount = computed(() => selectedVariables.value.length)

const filteredCategories = computed(() => {
  const query = searchQuery.value.toLowerCase().trim()
  
  if (!query) {
    return categorizedVars.value
  }

  const filtered = {}
  for (const [category, vars] of Object.entries(categorizedVars.value)) {
    const matchedVars = vars.filter(v => v.toLowerCase().includes(query))
    if (matchedVars.length > 0) {
      filtered[category] = matchedVars
    }
  }
  return filtered
})

// 方法
function getCategoryIcon(category) {
  const icons = {
    'PWMS': '⚙️',
    'STATES': '📊',
    'DATACTRL': '🎛️',
    'GNCBUS': '🛰️',
    'AVOIFLAG': '🚨',
    'DATAFUTABA': '📡',
    'DATAGCS': '💻',
    'PARAM': '⚙️',
    'ESC': '🔋'
  }
  return icons[category] || '📁'
}

function formatVariableName(variable) {
  // 将下划线替换为空格，提高可读性
  return variable.replace(/_/g, ' ')
}

function isSelected(variable) {
  return selectedVariables.value.includes(variable)
}

function toggleVariable(variable) {
  droneStore.toggleVariable(variable, !isSelected(variable))
}

function toggleCategory(category) {
  expandedCategories.value[category] = !expandedCategories.value[category]
}

async function applySelection() {
  if (selectedCount.value === 0) {
    return
  }

  try {
    await droneStore.fetchChartSeries(selectedVariables.value)
  } catch (err) {
    console.error('应用选择失败:', err)
  }
}

// 生命周期
onMounted(async () => {
  // 初始化所有分类为展开状态
  for (const category of Object.keys(categorizedVars.value)) {
    expandedCategories.value[category] = true
  }
  
  // 初始化时获取变量列表
  await droneStore.fetchHeaders()
})

// 监听分类变更，默认展开新分类
watch(categorizedVars, (newCategories) => {
  for (const category of Object.keys(newCategories)) {
    if (!(category in expandedCategories.value)) {
      expandedCategories.value[category] = true
    }
  }
}, { deep: true })
</script>

<style scoped>
.variable-selector {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1a1a1a;
  color: #e0e0e0;
}

.selector-header {
  padding: 15px;
  border-bottom: 1px solid #333;
}

.selector-header h3 {
  margin: 0 0 10px 0;
  font-size: 16px;
  color: #3274F6;
}

.search-box {
  position: relative;
}

.search-input {
  width: 100%;
  padding: 8px 35px 8px 10px;
  background: #2a2a2a;
  border: 1px solid #444;
  border-radius: 4px;
  color: #e0e0e0;
  font-size: 13px;
}

.search-input:focus {
  outline: none;
  border-color: #3274F6;
}

.search-icon {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 14px;
  opacity: 0.5;
}

.info-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  background: #252525;
  border-bottom: 1px solid #333;
}

.info-text {
  font-size: 12px;
  color: #aaa;
}

.apply-btn {
  padding: 6px 15px;
  background: #3274F6;
  border: none;
  border-radius: 4px;
  color: white;
  font-size: 12px;
  cursor: pointer;
}

.apply-btn:hover:not(:disabled) {
  background: #4285f4;
}

.apply-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.categories-container {
  flex: 1;
  overflow-y: auto;
  padding: 10px 0;
}

.category-section {
  margin-bottom: 5px;
}

.category-header {
  display: flex;
  align-items: center;
  padding: 10px 15px;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s;
}

.category-header:hover {
  background: #2a2a2a;
}

.category-icon {
  margin-right: 8px;
  font-size: 14px;
}

.category-name {
  flex: 1;
  font-weight: 600;
  font-size: 13px;
  color: #3274F6;
}

.category-count {
  margin-right: 10px;
  color: #888;
  font-size: 12px;
}

.toggle-icon {
  color: #666;
  font-size: 10px;
}

.variables-list {
  background: #1f1f1f;
  max-height: 300px;
  overflow-y: auto;
}

.variable-item {
  display: flex;
  align-items: center;
  padding: 6px 15px;
  transition: background 0.2s;
}

.variable-item:hover {
  background: #2a2a2a;
}

.variable-checkbox {
  margin-right: 8px;
  cursor: pointer;
}

.variable-label {
  flex: 1;
  font-size: 12px;
  color: #ccc;
  cursor: pointer;
}

.variable-item:hover .variable-label {
  color: #fff;
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: white;
  font-size: 14px;
}

.spinner {
  width: 30px;
  height: 30px;
  border: 3px solid #333;
  border-top-color: #3274F6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 10px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-message {
  padding: 15px;
  background: #3d1818;
  color: #ff6b6b;
  border: 1px solid #5c2b2b;
  border-radius: 4px;
  margin: 10px;
  font-size: 13px;
}

/* 滚动条样式 */
.categories-container::-webkit-scrollbar,
.variables-list::-webkit-scrollbar {
  width: 6px;
}

.categories-container::-webkit-scrollbar-thumb,
.variables-list::-webkit-scrollbar-thumb {
  background: #444;
  border-radius: 3px;
}

.categories-container::-webkit-scrollbar-thumb:hover,
.variables-list::-webkit-scrollbar-thumb:hover {
  background: #555;
}
</style>