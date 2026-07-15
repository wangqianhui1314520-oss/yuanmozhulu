<template>
  <div
    class="layer-panel-root"
    :class="{ collapsed: isCollapsed, dragging: isDragging }"
    :style="panelStyle"
    ref="panelRef"
  >
    <!-- 折叠按钮 -->
    <button class="layer-collapse-btn" @click="isCollapsed = !isCollapsed" :title="isCollapsed ? '展开图层' : '收起图层'">
      {{ isCollapsed ? '☰' : '✕' }}
    </button>

    <div v-if="!isCollapsed" class="layer-panel-body">
      <!-- 标题栏（拖拽把手） -->
      <div class="layer-header" @pointerdown="startDrag">
        <span class="layer-header-title">图 层</span>
        <div class="layer-header-actions">
          <button class="layer-preset-btn" @click="$emit('resetAll')" title="复位全部">↺</button>
        </div>
      </div>

      <!-- 预设快捷栏 -->
      <div class="presets-row">
        <button
          v-for="preset in presets"
          :key="preset.id"
          class="preset-chip"
          @click="$emit('applyPreset', preset.id)"
          :title="preset.description"
        >{{ preset.icon }} {{ preset.name }}</button>
      </div>

      <!-- 分类图层列表 -->
      <div v-for="cat in categories" :key="cat.id" class="layer-category">
        <div class="category-header" @click="toggleCategory(cat.id)">
          <span class="category-caret">{{ expandedCategories.has(cat.id) ? '▼' : '▶' }}</span>
          <span class="category-icon">{{ cat.icon }}</span>
          <span class="category-name">{{ cat.name }}</span>
          <span class="category-count">{{ getCatLayerCount(cat.id) }}</span>
        </div>

        <div v-if="expandedCategories.has(cat.id)" class="category-layers">
          <div
            v-for="layer in getCatLayers(cat.id)"
            :key="layer.id"
            class="layer-item"
            :class="{
              hidden: !layer.visible,
              locked: layer.locked,
              faded: layer.faded,
            }"
          >
            <!-- 显隐切换 -->
            <label class="layer-toggle" :title="layer.tooltip">
              <input
                type="checkbox"
                :checked="layer.visible"
                :disabled="layer.locked"
                @change="$emit('toggleLayer', layer.id)"
              />
              <span class="layer-icon">{{ layer.icon }}</span>
              <span class="layer-name">{{ layer.nameShort }}</span>
            </label>

            <!-- 行内操作 -->
            <div class="layer-actions">
              <!-- 透明度快速调节 -->
              <div class="opacity-mini" :title="`透明度: ${Math.round(layer.opacity * 100)}%`">
                <input
                  type="range"
                  min="0"
                  max="100"
                  :value="Math.round(layer.opacity * 100)"
                  @input="onOpacityChange(layer.id, $event)"
                  class="opacity-slider-mini"
                />
              </div>
              <!-- 锁定 -->
              <button
                class="layer-act-btn"
                :class="{ active: layer.locked }"
                @click="$emit('toggleLock', layer.id)"
                :title="layer.locked ? '解锁' : '锁定'"
              >{{ layer.locked ? '🔒' : '🔓' }}</button>
              <!-- 淡化 -->
              <button
                class="layer-act-btn"
                :class="{ active: layer.faded }"
                @click="$emit('toggleFade', layer.id)"
                title="淡化"
              >💧</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { LAYER_CATEGORIES, LAYER_PRESETS } from '@/utils/layerConfig'
import type { LayerRuntimeState } from '@/utils/layerUtils'

const props = defineProps<{
  layers: Record<string, LayerRuntimeState>
  layersByCategory: Record<string, LayerRuntimeState[]>
}>()

const emit = defineEmits<{
  toggleLayer: [layerId: string]
  setOpacity: [layerId: string, opacity: number]
  toggleLock: [layerId: string]
  toggleFade: [layerId: string]
  moveUp: [layerId: string]
  moveDown: [layerId: string]
  resetAll: []
  applyPreset: [presetId: string]
}>()

const isCollapsed = ref(false)
const expandedCategories = ref(new Set(LAYER_CATEGORIES.map(c => c.id)))
const categories = LAYER_CATEGORIES
const presets = LAYER_PRESETS.slice(0, 5)

// ===== 拖拽逻辑 =====
const panelRef = ref<HTMLElement>()
const isDragging = ref(false)
const panelOffset = ref({ x: -12, y: 72 })   // 初始偏移（对应 right:12, top:72）
let dragStart = { x: 0, y: 0 }

const panelStyle = computed(() => {
  if (!isDragging.value && panelOffset.value.x === -12 && panelOffset.value.y === 72) {
    return {}  // 初始位置用 CSS 的 right/top
  }
  return {
    right: 'auto',
    left: `${panelOffset.value.x}px`,
    top: `${panelOffset.value.y}px`,
  }
})

function startDrag(e: PointerEvent) {
  // 不拦截按钮点击
  if ((e.target as HTMLElement).closest('button')) return
  isDragging.value = true
  const rect = panelRef.value!.getBoundingClientRect()
  // 首次拖拽：将 right 转换为 left
  if (panelOffset.value.x === -12) {
    panelOffset.value = { x: rect.left, y: rect.top }
  }
  dragStart = { x: e.clientX - rect.left, y: e.clientY - rect.top }
  ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
  document.addEventListener('pointermove', onDrag)
  document.addEventListener('pointerup', stopDrag)
}

function onDrag(e: PointerEvent) {
  if (!isDragging.value) return
  panelOffset.value = {
    x: e.clientX - dragStart.x,
    y: e.clientY - dragStart.y,
  }
}

function stopDrag() {
  isDragging.value = false
  document.removeEventListener('pointermove', onDrag)
  document.removeEventListener('pointerup', stopDrag)
}

onUnmounted(() => {
  document.removeEventListener('pointermove', onDrag)
  document.removeEventListener('pointerup', stopDrag)
})

function toggleCategory(catId: string) {
  if (expandedCategories.value.has(catId)) {
    expandedCategories.value.delete(catId)
  } else {
    expandedCategories.value.add(catId)
  }
}

function getCatLayers(catId: string): LayerRuntimeState[] {
  return props.layersByCategory[catId] || []
}

function getCatLayerCount(catId: string): string {
  const layers = getCatLayers(catId)
  const visible = layers.filter(l => l.visible).length
  return `${visible}/${layers.length}`
}

function onOpacityChange(layerId: string, event: Event) {
  const target = event.target as HTMLInputElement
  const val = parseInt(target.value) / 100
  emit('setOpacity', layerId, val)
}
</script>

<style scoped>
.layer-panel-root {
  position: absolute;
  top: 72px;
  right: 12px;
  z-index: 500;
  background: rgba(28, 24, 18, 0.92);
  border: 1px solid rgba(180, 160, 120, 0.35);
  border-radius: 4px;
  color: #c4b898;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 12px;
  min-width: 200px;
  max-width: 240px;
  backdrop-filter: blur(8px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.45);
  user-select: none;
}
.layer-panel-root.dragging {
  opacity: 0.92;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
  transition: none;
}
.layer-panel-root.collapsed {
  min-width: auto;
  background: rgba(28, 24, 18, 0.75);
}
.layer-collapse-btn {
  position: absolute;
  top: 2px;
  right: 4px;
  background: none;
  border: none;
  color: #8a7a6a;
  cursor: pointer;
  font-size: 13px;
  padding: 2px 4px;
  line-height: 1;
}
.layer-collapse-btn:hover { color: #c8b080; }
.layer-panel-body { padding: 6px 8px; }

.layer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid rgba(180, 160, 120, 0.2);
  cursor: grab;
}
.layer-header:active { cursor: grabbing; }
.layer-header-title {
  font-size: 14px;
  color: #d4c090;
  letter-spacing: 4px;
}
.layer-header-actions { display: flex; gap: 2px; }
.layer-preset-btn {
  background: rgba(180, 160, 120, 0.15);
  border: 1px solid rgba(180, 160, 120, 0.2);
  color: #a08a60;
  cursor: pointer;
  font-size: 14px;
  padding: 1px 6px;
  border-radius: 2px;
}
.layer-preset-btn:hover { background: rgba(180, 160, 120, 0.3); }

.presets-row {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid rgba(180, 160, 120, 0.1);
}
.preset-chip {
  background: rgba(180, 160, 120, 0.12);
  border: 1px solid rgba(180, 160, 120, 0.18);
  color: #a09070;
  cursor: pointer;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 2px;
  font-family: inherit;
  white-space: nowrap;
}
.preset-chip:hover { background: rgba(200, 180, 120, 0.25); color: #d4c090; }

.layer-category { margin-bottom: 2px; }
.category-header {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 4px;
  cursor: pointer;
  border-radius: 2px;
  font-size: 11px;
  color: #b0a080;
}
.category-header:hover { background: rgba(180, 160, 120, 0.1); }
.category-caret { font-size: 8px; width: 10px; color: #8a7a6a; }
.category-icon { font-size: 11px; }
.category-name { flex: 1; letter-spacing: 1px; }
.category-count { font-size: 9px; color: #6a5a4a; }

.category-layers { padding-left: 4px; }
.layer-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px 4px;
  border-radius: 2px;
  transition: opacity 0.2s;
}
.layer-item.hidden { opacity: 0.45; }
.layer-item.faded { opacity: 0.35; }
.layer-item:hover { background: rgba(180, 160, 120, 0.08); }

.layer-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  flex: 1;
  min-width: 0;
}
.layer-toggle input[type="checkbox"] {
  accent-color: #b8a050;
  cursor: pointer;
  width: 12px;
  height: 12px;
}
.layer-toggle input[type="checkbox"]:disabled { opacity: 0.4; cursor: not-allowed; }
.layer-icon { font-size: 12px; width: 16px; text-align: center; flex-shrink: 0; }
.layer-name { font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.layer-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}
.opacity-mini {
  width: 40px;
  display: flex;
  align-items: center;
}
.opacity-slider-mini {
  width: 100%;
  height: 3px;
  -webkit-appearance: none;
  appearance: none;
  background: rgba(180, 160, 120, 0.25);
  border-radius: 2px;
  outline: none;
  cursor: pointer;
}
.opacity-slider-mini::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 8px;
  height: 8px;
  background: #b8a050;
  border-radius: 50%;
  cursor: pointer;
}
.layer-act-btn {
  background: none;
  border: none;
  color: #6a5a4a;
  cursor: pointer;
  font-size: 10px;
  padding: 0 2px;
  line-height: 1;
  opacity: 0.5;
}
.layer-act-btn:hover, .layer-act-btn.active { opacity: 1; color: #b8a050; }
</style>
