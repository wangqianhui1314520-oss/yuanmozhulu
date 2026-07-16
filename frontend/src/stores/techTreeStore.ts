/**
 * 科技树（国策）状态管理 Store
 * 管理势力科技研究进度、可用科技列表
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getTechTree, researchPolicy as apiResearchPolicy } from '@/services/api'

export interface PolicyNode {
  id: string
  name: string
  tier: number
  cost: number
  requires: string[]
  effects: Record<string, number>
  description: string
  unlocked: boolean
  available: boolean  // 前置已满足，可以研究
}

export interface TechBranch {
  id: string
  name: string
  icon: string
  description: string
  nodes: PolicyNode[]
}

export interface TechCategory {
  id: string
  name: string
  icon: string
  description: string
  branches: TechBranch[]
}

export const useTechTreeStore = defineStore('techTree', () => {
  // ===== 状态 =====
  const categories = ref<TechCategory[]>([])
  const unlockedPolicies = ref<string[]>([])
  const treasury = ref(0)
  const isLoading = ref(false)
  const errorMessage = ref('')
  const selectedBranch = ref('')
  const showResearchResult = ref(false)
  const researchResult = ref<{ success: boolean; message: string } | null>(null)

  // ===== 计算属性 =====
  const totalUnlocked = computed(() => unlockedPolicies.value.length)
  const totalAvailable = computed(() => {
    let count = 0
    for (const cat of categories.value) {
      for (const branch of cat.branches) {
        count += branch.nodes.filter(n => n.available && !n.unlocked).length
      }
    }
    return count
  })

  // ===== 方法 =====

  /** 加载科技树数据 */
  async function loadTechTree(factionId: string) {
    if (!factionId) return
    isLoading.value = true
    errorMessage.value = ''
    try {
      const data = await getTechTree(factionId)
      if (data) {
        categories.value = data.categories || []
        unlockedPolicies.value = data.unlocked_policies || []
        treasury.value = data.treasury || 0
      }
    } catch (e) {
      console.warn('加载科技树失败:', e)
      errorMessage.value = '加载科技树失败，请稍后重试'
    } finally {
      isLoading.value = false
    }
  }

  /** 研究一项国策 */
  async function research(factionId: string, policyId: string): Promise<boolean> {
    try {
      const data = await apiResearchPolicy(factionId, policyId)
      if (data?.success) {
        // 更新本地状态
        if (!unlockedPolicies.value.includes(policyId)) {
          unlockedPolicies.value.push(policyId)
        }
        // 更新树中节点状态
        for (const cat of categories.value) {
          for (const branch of cat.branches) {
            for (const node of branch.nodes) {
              if (node.id === policyId) {
                node.unlocked = true
                node.available = false
              }
              // 重新计算可用性
              if (!node.unlocked) {
                node.available = node.requires.every(r => unlockedPolicies.value.includes(r))
              }
            }
          }
        }
        treasury.value = data.treasury

        researchResult.value = { success: true, message: `成功研究「${data.policy_name || policyId}」` }
        showResearchResult.value = true
        setTimeout(() => { showResearchResult.value = false }, 3000)
        return true
      } else {
        researchResult.value = { success: false, message: (data as any)?.msg || '研究失败' }
        showResearchResult.value = true
        setTimeout(() => { showResearchResult.value = false }, 3000)
        return false
      }
    } catch (e: any) {
      researchResult.value = {
        success: false,
        message: e?.response?.data?.msg || e?.message || '研究失败',
      }
      showResearchResult.value = true
      setTimeout(() => { showResearchResult.value = false }, 3000)
      return false
    }
  }

  /** 检查银两是否足够研究 */
  function canAffordResearch(cost: number): boolean {
    return treasury.value >= cost
  }

  return {
    categories, unlockedPolicies, treasury, isLoading, errorMessage,
    selectedBranch, showResearchResult, researchResult,
    totalUnlocked, totalAvailable,
    loadTechTree, research, canAffordResearch,
  }
})
