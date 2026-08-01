<template>
  <div class="chart-view" v-if="chartConfig || imageBase64">
    <!-- 静态图表图片 -->
    <div v-if="imageBase64" class="static-chart">
      <img :src="`data:image/png;base64,${imageBase64}`" alt="图表" class="chart-image" />
    </div>
    
    <!-- ECharts 交互图 -->
    <div v-if="chartConfig" class="chart-container" :class="{ 'with-image': imageBase64 }">
      <div ref="chartRef" class="echarts-chart"></div>
    </div>
    
    <!-- 空状态 -->
    <div v-else class="empty-state">
      <p>暂无图表数据</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  chartConfig: Object,
  imageBase64: String  // 新增：base64 编码的图表图片
})

const chartRef = ref(null)
let chartInstance = null

// 解析图表配置（兼容字符串和对象）
const parsedChartConfig = computed(() => {
  if (!props.chartConfig) return null
  if (typeof props.chartConfig === 'string') {
    try {
      return JSON.parse(props.chartConfig)
    } catch (e) {
      return null
    }
  }
  return props.chartConfig
})

onMounted(() => {
  updateChart()
})

watch(() => [parsedChartConfig.value, props.imageBase64], () => {
  updateChart()
}, { deep: true })

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

const updateChart = () => {
  if (chartRef.value && parsedChartConfig.value) {
    if (!chartInstance) {
      chartInstance = echarts.init(chartRef.value)
    }
    chartInstance.setOption(parsedChartConfig.value)
  }
}
</script>

<style scoped>
.chart-view {
  width: 100%;
  padding: 16px;
  background: var(--bg-primary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
}

.static-chart {
  margin-bottom: 16px;
  text-align: center;
}

.chart-image {
  max-width: 100%;
  height: auto;
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-sm);
}

.chart-container {
  width: 100%;
  min-height: 400px;
  transition: all 0.3s ease;
}

.chart-container.with-image {
  min-height: 500px;  /* 有静态图时，增加高度 */
}

.echarts-chart {
  width: 100%;
  height: 400px;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--text-secondary);
}
</style>
