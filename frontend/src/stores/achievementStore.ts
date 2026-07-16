/**
 * 成就系统状态管理 Store
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getAchievements } from '@/services/api'

export interface AchievementInfo {
  id: string
  name: string
  description: string
  icon: string
  category: string
  rarity: string
  unlocked: boolean
  isNew: boolean
  unlockedAt?: string
  unlockedRound?: number
}

export const useAchievementStore = defineStore('achievement', () => {
  // ===== 状态 =====
  const allAchievements = ref<AchievementInfo[]>([])
  const isLoading = ref(false)

  // ===== 计算属性 =====
  const unlockedCount = computed(() => allAchievements.value.filter(a => a.unlocked).length)
  const totalCount = computed(() => allAchievements.value.length)
  const newCount = computed(() => allAchievements.value.filter(a => a.isNew).length)

  // ===== 方法 =====

  async function loadAchievements(factionId: string) {
    if (!factionId) return
    isLoading.value = true
    try {
      const data = await getAchievements(factionId)
      if (data?.achievements) {
        allAchievements.value = data.achievements
      }
    } catch (e) {
      console.warn('加载成就失败:', e)
    } finally {
      isLoading.value = false
    }
  }

  return {
    allAchievements, isLoading,
    unlockedCount, totalCount, newCount,
    loadAchievements,
  }
})
