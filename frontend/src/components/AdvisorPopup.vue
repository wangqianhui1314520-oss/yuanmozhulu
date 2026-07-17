<template>
  <Teleport to="body">
    <transition name="modal">
      <div class="advisor-popup-overlay" v-if="visible" @click.self="$emit('close')">
        <div class="advisor-popup artifact-panel artifact-personnel">
          <!-- 标题 -->
          <div class="ap-header">
            <div class="ap-title-row">
              <span class="ap-seal">奏</span>
              <div>
                <h2>幕僚奏报</h2>
                <span class="ap-subtitle">{{ advisorName }} 进言</span>
              </div>
            </div>
            <button class="ap-close" @click="$emit('close')">✕</button>
          </div>

          <!-- 奏报内容 -->
          <div class="ap-body" ref="bodyRef">
            <div v-if="isLoading" class="ap-loading">
              <div class="ap-spinner"></div>
              <span>幕僚正在拟奏...</span>
            </div>

            <template v-else-if="suggestions.length > 0">
              <div class="ap-analysis" v-if="currentSuggestion.analysis">
                <div class="ap-analysis-label">🎯 局势分析</div>
                <div class="ap-analysis-text">{{ currentSuggestion.analysis }}</div>
              </div>

              <div class="ap-suggestions">
                <div class="ap-sug-label">📜 奏报建议（{{ currentIndex + 1 }}/{{ suggestions.length }}）</div>
                <div class="ap-sug-card" :class="'priority-' + currentSuggestion.priority">
                  <div class="ap-sug-header">
                    <span class="ap-sug-priority" :class="currentSuggestion.priority">
                      {{ priorityLabel(currentSuggestion.priority) }}
                    </span>
                    <span class="ap-sug-category">{{ currentSuggestion.category }}</span>
                  </div>
                  <div class="ap-sug-content">{{ currentSuggestion.content }}</div>
                  <div class="ap-sug-impact" v-if="currentSuggestion.impact">
                    <span class="impact-label">预期影响</span>
                    <div class="impact-rows">
                      <div v-for="(imp, key) in currentSuggestion.impact" :key="key" class="impact-row">
                        <span class="impact-key">{{ key }}</span>
                        <span class="impact-val" :class="imp.startsWith('+') ? 'positive' : imp.startsWith('-') ? 'negative' : ''">
                          {{ imp }}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 操作按钮 -->
              <div class="ap-actions">
                <button class="ap-btn reject" @click="rejectSuggestion" :disabled="isExecuting">
                  <span>✕</span> 驳回
                </button>
                <button class="ap-btn consider" @click="considerSuggestion" :disabled="isExecuting">
                  <span>💬</span> 追问
                </button>
                <button class="ap-btn approve" @click="approveSuggestion">
                  <span>✓</span> 采纳
                </button>
              </div>

              <!-- 翻页 -->
              <div class="ap-pagination" v-if="suggestions.length > 1">
                <button :disabled="currentIndex === 0" @click="currentIndex--">← 上一条</button>
                <span>{{ currentIndex + 1 }} / {{ suggestions.length }}</span>
                <button :disabled="currentIndex >= suggestions.length - 1" @click="currentIndex++">下一条 →</button>
              </div>
            </template>

            <!-- 追问模式 -->
            <template v-else-if="followUpMode">
              <div class="ap-followup">
                <div class="ap-followup-label">追问幕僚</div>
                <textarea v-model="followUpText" class="ap-followup-input" placeholder="输入你的追问..." rows="3"></textarea>
                <div class="ap-actions">
                  <button class="ap-btn consider" @click="followUpMode = false">← 返回</button>
                  <button class="ap-btn approve" @click="sendFollowUp" :disabled="!followUpText.trim() || isExecuting">
                    发送追问
                  </button>
                </div>
              </div>
            </template>

            <!-- 空状态 -->
            <div v-else class="ap-empty">
              <div class="ap-empty-icon">📜</div>
              <p>幕僚暂无奏报</p>
              <p class="ap-empty-hint">AI将根据当前局势，从军事、内政、外交三个方向献上具体策略</p>
              <button class="ap-btn suggest" @click="generateSuggestions">
                {{ isGenerating ? '幕僚拟奏中...' : '请幕僚献策' }}
              </button>
              <button class="ap-btn open-panel" @click="openFullPanel">
                🎓 深入策问（多轮对话）
              </button>
            </div>
          </div>

          <!-- 执行结果 -->
          <div v-if="executionResult" class="ap-result">
            <div class="ap-result-header">
              <span :class="executionResult.success ? 'result-icon-ok' : 'result-icon-fail'">
                {{ executionResult.success ? '✓' : '✕' }}
              </span>
              <span>{{ executionResult.success ? '奏报已执行' : '执行受阻' }}</span>
              <button class="ap-result-close" @click="executionResult = null">✕</button>
            </div>
            <div class="ap-result-body">
              <div v-if="executionResult.narrative" class="ap-result-narrative">
                {{ executionResult.narrative }}
              </div>
              <div v-if="executionResult.executed?.length" class="ap-result-section">
                <div class="ap-result-section-title">已执行的政令</div>
                <div v-for="(ex, i) in executionResult.executed" :key="'ex'+i" class="ap-result-item ok">
                  {{ ex.action }}：{{ ex.result?.message || ex.ai_reason || '' }}
                </div>
              </div>
              <div v-if="executionResult.failed?.length" class="ap-result-section">
                <div class="ap-result-section-title fail">未能执行的政令</div>
                <div v-for="(fa, i) in executionResult.failed" :key="'fa'+i" class="ap-result-item fail">
                  {{ fa.action }}：{{ fa.reason }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useGameStore } from '@/stores/gameStore'

const props = defineProps<{
  visible: boolean
  advisorName?: string
}>()

const emit = defineEmits<{
  close: []
  approveEdict: [text: string]
  openPanel: []
}>()

const store = useGameStore()

// 状态
const isLoading = ref(false)
const isGenerating = ref(false)
const isExecuting = ref(false)
const followUpMode = ref(false)
const followUpText = ref('')
const currentIndex = ref(0)
const executionResult = ref<any>(null)

// 建议列表（AI生成的）
interface Suggestion {
  analysis?: string
  content: string
  category: string
  priority: 'critical' | 'major' | 'minor'
  impact?: Record<string, string>
  edictText?: string
}

const suggestions = ref<Suggestion[]>([])

const currentSuggestion = computed(() => {
  return suggestions.value[currentIndex.value] || suggestions.value[0] || null
})

function priorityLabel(p: string): string {
  const m: Record<string, string> = { critical: '❗紧要', major: '⚠重要', minor: '💡建议' }
  return m[p] || p
}

// 自动生成建议（基于当前游戏状态）
async function generateSuggestions() {
  isGenerating.value = true
  isLoading.value = true
  try {
    // 使用 strategic_advice API，skipEnrich=true 避免重复包装（buildContextPrompt 已含完整游戏数据）
    const prompt = buildContextPrompt()
    const result = await store.chatWithMinister(prompt, undefined, true)

    if (result?.response) {
      // 解析AI回复为结构化建议
      suggestions.value = parseAISuggestions(result.response, result)
      currentIndex.value = 0
    } else {
      // Fallback: 基于游戏状态生成默认建议
      suggestions.value = generateFallbackSuggestions()
      currentIndex.value = 0
    }
  } catch (e) {
    console.warn('幕僚献策失败:', e)
    suggestions.value = generateFallbackSuggestions()
    currentIndex.value = 0
  } finally {
    isGenerating.value = false
    isLoading.value = false
  }
}

function buildContextPrompt(): string {
  const pf = store.playerFaction
  if (!pf) return '请分析当前局势并给出建议'

  const ownedTiles = getOwnedTiles()
  const thisFactionId = store.playerFactionId
  const thisFactionName = pf.name || '我方'
  const factionsMap = store.factions as Record<string, any>
  const relationsData = store.relations as Record<string, any>
  const neighborsData = store.tileNeighbors as Record<string, string[]>

  // ── 外交关系（含态度和信任） ──
  interface RelationInfo { id: string; name: string; stance: string; attitude: number; trust: number; trade: boolean }
  const allRelations: RelationInfo[] = []
  for (const [k, r] of Object.entries(relationsData)) {
    const parts = k.split('|')
    if (!parts.includes(thisFactionId)) continue
    const otherId = parts[0] === thisFactionId ? parts[1] : parts[0]
    const otherFaction = factionsMap[otherId]
    const otherName = otherFaction?.name || otherId
    allRelations.push({
      id: otherId, name: otherName,
      stance: r.stance || 'neutral',
      attitude: r.attitude ?? 0,
      trust: r.trust ?? 0,
      trade: !!r.trade_active,
    })
  }
  const wars = allRelations.filter(r => r.stance === 'war')
  const alliances = allRelations.filter(r => r.stance === 'alliance')
  const neutral = allRelations.filter(r => r.stance !== 'war' && r.stance !== 'alliance')

  // ── 己方地块清单 ──
  const tileTypeLabel: Record<string, string> = {
    farmland:'农田', mountain:'山地', water:'水域', coast:'海岸',
    city:'城池', pass:'关隘', port:'港口', desert:'漠地', grassland:'草原', sea:'海域',
  }
  function tileBuildings(t: any): string {
    const bld: string[] = []
    if (t.fortification > 0) bld.push(`城防Lv${t.fortification}`)
    if (t.granary > 0) bld.push(`粮仓Lv${t.granary}`)
    if (t.stable > 0) bld.push(`马场Lv${t.stable}`)
    if (t.armory > 0) bld.push(`军械Lv${t.armory}`)
    if (t.water_works > 0) bld.push(`水利Lv${t.water_works}`)
    if (t.clinic > 0) bld.push(`医馆Lv${t.clinic}`)
    if (t.is_port) bld.push('港口')
    return bld.join('/') || '无建筑'
  }
  const tileLines: string[] = []
  const borderTiles: string[] = []
  for (const t of ownedTiles) {
    const typeName = tileTypeLabel[t.tile_type] || t.tile_type
    const tileName = t.tile_name || t.tile_id
    const cap = t.is_capital ? '【都】' : ''
    const buildings = tileBuildings(t)
    tileLines.push(`${cap}${tileName}(${typeName}) 人口${t.population || 0} 兵${t.troops || 0} 粮${t.grain || 0} 银${t.treasury || 0} [${buildings}]`)
    // 检查是否前线（邻接地块中有敌方土地）
    const adj = neighborsData[t.tile_id] || []
    for (const nid of adj) {
      const nt = store.tiles[nid]
      if (nt && nt.faction_id && nt.faction_id !== thisFactionId && !alliances.some(a => a.id === nt.faction_id)) {
        borderTiles.push(`${tileName}↔${factionsMap[nt.faction_id]?.name || nt.faction_id}(敌方)`)
        break
      }
    }
  }

  // ── 灾害信息 ──
  const disasters = store.activeDisasters as any[]
  const disasterLines: string[] = []
  if (disasters?.length) {
    for (const d of disasters) {
      const locName = d.tile_id ? (store.tiles[d.tile_id]?.tile_name || d.tile_id) : d.region || '全域'
      disasterLines.push(`${d.type || d.name}(严重${d.severity ?? '?'}) @${locName}`)
    }
  }

  // ── 官员信息 ──
  const officials = store.officials as any[]
  const officialLines: string[] = []
  if (officials?.length) {
    for (const o of officials.slice(0, 5)) {
      officialLines.push(`${o.name || o.id}(${o.role || o.position || '文臣'}) 忠诚${o.loyalty ?? '?'}`)
    }
  }

  // ── 组装 Prompt ──
  const parts: string[] = [
    `请以元末首席谋臣的身份，基于以下游戏状态，献上3条最重要的策略建议。`,
    ``,
    `注意：`,
    `- 回答必须直接、务实，不要出现"臣谨奏"、"臣献"、"臣闻"、"臣等"、"微臣"等任何客套话或自称。`,
    `- 不要出现"建议"、"献策"、"求策"、"问策"、"分析"等会被系统误判为谋略问询的词汇。`,
    `- 每条策略必须是皇上可以直接当作圣旨颁布执行的命令，而不是请示或建议。`,
    `- 【重要】所有地名、数字、目标必须严格基于下方提供的实际游戏数据，不可凭空捏造。`,
    `- 若建议征兵，征召数量不能超过地块人口×60%。`,
    `- 若建议建造，费用不可超过国库银两${pf.treasury || 0}两。`,
    `- 若建议进攻，目标必须是在接壤边境上实际存在的敌方地块。`,
    ``,
    `═══ 真实游戏数据（据此献策，不可偏离） ═══`,
    ``,
    `【基本信息】`,
    `- 回合：第${store.currentRound}回合 / 至正${store.currentYear}年${store.currentSeason}季`,
    `- 势力名称：${thisFactionName}`,
    `- 银两：${pf.treasury || 0} | 粮草：${pf.grain || 0} | 军械：${pf.arms || 0} | 战马：${pf.horses || 0}`,
    `- 总兵力：${store.totalTroops} | 总人口：${store.totalPopulation}`,
    `- 民心：${store.realmStability}/100 | 朝纲：${store.courtStability}/100 | 声望：${store.reputation}/100`,
    `- 已解锁国策：${(pf.unlocked_policies as any[])?.join?.('、') || '无'}`,
    ``,
    `【己方${ownedTiles.length}块领地详情】`,
    ...tileLines,
    '',
  ]

  if (borderTiles.length > 0) {
    parts.push(`【接壤前线（敌军邻接）】`, ...borderTiles.slice(0, 8), '')
  }

  parts.push(`【建筑造价参考】`,
    `- 水利：500银 | 粮仓：800银 | 医馆：600银`,
    `- 城防：300银/级 | 军械所：800银 | 马场：800银 | 港口：1200银`,
    ''
  )

  if (wars.length > 0) {
    parts.push(`【交战势力】`, ...wars.map(r => `- ${r.name} 态度${r.attitude} 信任${r.trust}`), '')
  }
  if (alliances.length > 0) {
    parts.push(`【盟友势力】`, ...alliances.map(r => `- ${r.name} 态度${r.attitude} 信任${r.trust}${r.trade ? ' 有贸易' : ''}`), '')
  } else {
    parts.push(`【盟友】当前无盟友，外交孤立`, '')
  }
  if (neutral.length > 0) {
    parts.push(`【中立势力】`, ...neutral.map(r => `- ${r.name} 态度${r.attitude}`), '')
  }

  if (disasterLines.length > 0) {
    parts.push('', `【当前灾害】`, ...disasterLines, '')
  }
  if (officialLines.length > 0) {
    parts.push(`【麾下文臣】`, ...officialLines, '')
  }

  parts.push(
    '',
    `【献策要求】`,
    `请分别就军事、内政、外交3个方向各献一策，每策格式如下：`,
    `1. （军事）[具体行动]，目标[地块名]，预计消耗[资源量]`,
    `2. （内政）[具体建造]，在[地块名]建造[设施名]，耗费[银两]`,
    `3. （外交）[具体行动]，向[势力名]进行[行动类型]`,
    '',
    `每条50-80字，必须使用上方列出的真实地名和数字。`
  )

  return parts.join('\n')
}

function parseAISuggestions(text: string, rawResult: any): Suggestion[] {
  const result: Suggestion[] = []

  // 去 AI 开场白（"臣献三策如下""臣谨奏""臣闻"等）
  const cleanText = text
    .replace(/^.{0,30}(献|进|奏)(策|言|议|上).{0,20}[:：\s]*\n?/, '')
    .replace(/^.{0,20}(臣|微臣|臣等)(谨|伏|顿首|昧死|诚惶诚恐)(奏|启|陈|闻|上言).{0,20}[:：\s]*\n?/, '')
    .replace(/^.{0,20}(臣闻|臣窃闻|臣窃惟|臣愚以为|臣等闻).{0,30}[:：\s]*\n?/, '')
    .replace(/^[^1-3一二三\n]{2,60}[：:][\s]*\n?/, '')
    .trim()

  // 尝试按段落/编号分割
  const lines = cleanText.split('\n').filter(l => l.trim())
  let current: Suggestion | null = null
  let currentContent = ''

  for (const line of lines) {
    const trimmed = line.trim()
    // 匹配编号行
    const numMatch = trimmed.match(/^[（(]?(\d+|一|二|三|四|五)[)）]?\s*[.、．:：]\s*(.+)/)

    if (numMatch) {
      if (current) {
        current.content = currentContent.trim()
        result.push(current)
      }
      // 去掉类别标签（如"（军事）"）
      const cleanContent = numMatch[2].replace(/^[（(]\s*(军事|内政|外交|经济|综合|赈灾|人事)\s*[)）]\s*/, '')
      current = {
        content: cleanContent,
        category: detectCategory(numMatch[2]),
        priority: result.length === 0 ? 'critical' : 'major',
        edictText: cleanContent,
      }
      currentContent = cleanContent
    } else if (current) {
      currentContent += '\n' + trimmed
      if (!current.edictText || current.edictText.length < 300) {
        current.edictText = currentContent.trim()
      }
    }
  }

  if (current && currentContent.trim()) {
    current.content = currentContent.trim()
    result.push(current)
  }

  // 如果解析失败，整体作为一条（也去掉开场白）
  if (result.length === 0 && cleanText.trim()) {
    result.push({
      content: cleanText.slice(0, 400),
      category: '综合建议',
      priority: 'major',
      analysis: '幕僚综合分析了当前局势',
      edictText: cleanText.slice(0, 400),
    })
  }

  return result
}

function detectCategory(text: string): string {
  const lower = text.toLowerCase()
  if (lower.includes('兵') || lower.includes('军') || lower.includes('战') || lower.includes('攻') || lower.includes('伐') || lower.includes('征')) return '军事'
  if (lower.includes('建') || lower.includes('城') || lower.includes('田') || lower.includes('工坊') || lower.includes('粮')) return '内政'
  if (lower.includes('盟') || lower.includes('交') || lower.includes('使') || lower.includes('和') || lower.includes('联姻')) return '外交'
  if (lower.includes('税') || lower.includes('银') || lower.includes('贸易') || lower.includes('商')) return '经济'
  if (lower.includes('灾') || lower.includes('赈') || lower.includes('疫')) return '赈灾'
  if (lower.includes('官') || lower.includes('吏') || lower.includes('任') || lower.includes('罢')) return '人事'
  return '综合'
}

/** 获取己方地块列表（回退逻辑） */
function getOwnedTiles() {
  const pts = store.playerTiles
  if (pts.length > 0) return pts
  return Object.values(store.tiles)
    .filter(t => t.faction_id === store.playerFactionId && t.faction_id !== '')
}

function generateFallbackSuggestions(): Suggestion[] {
  const pf = store.playerFaction
  const result: Suggestion[] = []
  const ownedTiles = getOwnedTiles()

  // 军事建议
  if (store.totalTroops < 3000 || ownedTiles.length === 0) {
    result.push({
      analysis: '当前兵力不足，需尽快扩充军力以应对周边威胁。',
      content: '建议在人口较多的城池批量征兵，优先加强前线防线。',
      category: '军事',
      priority: 'critical',
      edictText: '在全国各地征兵三千，加强城防',
      impact: { '总兵力': '+3000', '粮草消耗': '-1500' },
    })
  }

  // 内政建议
  const farmTiles = ownedTiles.filter((t: any) => t.tile_type === 'farmland' || t.tile_type?.toLowerCase?.() === 'farmland')
  if (farmTiles.length > 0) {
    result.push({
      analysis: `您拥有${farmTiles.length}块农田地块，建议建造农田提升粮食产量。`,
      content: `在${farmTiles.slice(0, 3).map((t: any) => t.tile_name).join('、')}等地建造农田，每座可增加粮食产量80/回合。`,
      category: '内政',
      priority: 'major',
      edictText: `在${farmTiles.slice(0, 3).map((t: any) => t.tile_name).join('、')}各建一座农田`,
      impact: { '每回合粮食': '+80×' + Math.min(3, farmTiles.length), '银两消耗': '-' + (300 * Math.min(3, farmTiles.length)) },
    })
  } else if (ownedTiles.length > 0) {
    // 有领地但无农田类型时，使用任意地块
    const cities = ownedTiles.filter((t: any) => t.is_capital || t.tile_type === 'city')
    const targets = cities.length > 0 ? cities : ownedTiles.slice(0, 3)
    result.push({
      analysis: `您拥有${ownedTiles.length}块领地，建议优先发展内政。`,
      content: `在${targets.slice(0, 3).map((t: any) => t.tile_name).join('、')}等地建造工坊或农田，提升经济实力。`,
      category: '内政',
      priority: 'major',
      edictText: `在${targets.slice(0, 3).map((t: any) => t.tile_name).join('、')}各建一座工坊`,
      impact: { '每回合银两': '+60/工坊', '初期投入': '-500/座' },
    })
  }

  // 外交建议
  const allies = Object.entries(store.relations as Record<string, any>).filter(([k, r]) => {
    const parts = k.split('|')
    const other = parts[0] === store.playerFactionId ? parts[1] : parts[0]
    return r.stance === 'alliance' && parts.includes(store.playerFactionId)
  })
  if (allies.length === 0) {
    result.push({
      analysis: '当前孤立无援，建议寻求外交结盟，避免四面受敌。',
      content: '建议遣使与接壤势力修好结盟，至少确保一个方向的安全。',
      category: '外交',
      priority: 'major',
      edictText: '遣使四方，与邻近势力修好结盟',
      impact: { '外交关系': '改善', '声望': '+5' },
    })
  }

  // 经济建议
  if ((pf?.treasury ?? 0) < 3000) {
    result.push({
      analysis: '国库银两不足，建议建造工坊增加收入。',
      content: '在城池建造工坊，每座可增加银两60/回合。',
      category: '经济',
      priority: 'major',
      edictText: '在各城池建立工坊，增加税银收入',
      impact: { '每回合银两': '+60/工坊', '初期投入': '-500/座' },
    })
  }

  // 赈灾
  if (store.activeDisasters?.length > 0) {
    result.push({
      analysis: `当前有${store.activeDisasters.length}处灾害需要应对，如不及时赈灾可能引发民变。`,
      content: '建议立即开仓赈灾，安抚灾民，避免流民潮发生。',
      category: '赈灾',
      priority: 'critical',
      edictText: '开仓赈灾，安抚灾民，减免受灾地区赋税',
      impact: { '民心': '+10', '灾厄指数': '-5' },
    })
  }

  return result.slice(0, 3)
}

function approveSuggestion() {
  if (!currentSuggestion.value) return
  const text = currentSuggestion.value.edictText || currentSuggestion.value.content
  emit('approveEdict', text)
}

function rejectSuggestion() {
  if (suggestions.value.length > 1 && currentIndex.value < suggestions.value.length - 1) {
    currentIndex.value++
  } else {
    emit('close')
  }
}

function openFullPanel() {
  emit('openPanel')
  emit('close')
}

function considerSuggestion() {
  followUpMode.value = true
  followUpText.value = `关于"${currentSuggestion.value?.content?.slice(0, 30)}..."，我认为...`
}

async function sendFollowUp() {
  if (!followUpText.value.trim() || isExecuting.value) return
  isExecuting.value = true

  try {
    const result = await store.chatWithMinister(followUpText.value)
    if (result?.response) {
      suggestions.value = parseAISuggestions(result.response, result)
      currentIndex.value = 0
    }
    followUpMode.value = false
  } catch (e) {
    console.warn('幕僚追问失败:', e)
  } finally {
    isExecuting.value = false
  }
}

// 重置
watch(() => props.visible, (v) => {
  if (v) {
    suggestions.value = []
    currentIndex.value = 0
    followUpMode.value = false
    executionResult.value = null
    isLoading.value = false
    isExecuting.value = false
    // 自动请求建议
    generateSuggestions()
  }
})
</script>

<style scoped>
.advisor-popup-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  z-index: 500;
  display: flex;
  align-items: center;
  justify-content: center;
}

.advisor-popup {
  width: 520px;
  max-width: 95vw;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.ap-header {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(184, 155, 104, 0.2);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.ap-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ap-seal {
  font-size: 28px;
  color: var(--gold);
  font-family: "STKaiti", "KaiTi", serif;
  writing-mode: vertical-rl;
  letter-spacing: 4px;
  border: 1px solid var(--gold);
  padding: 6px 10px;
  border-radius: 2px;
}

.ap-title-row h2 {
  font-size: 18px;
  font-family: "STKaiti", "KaiTi", serif;
  color: var(--gold);
  letter-spacing: 3px;
  margin: 0;
}

.ap-subtitle {
  font-size: 11px;
  color: var(--text-dim);
  letter-spacing: 2px;
}

.ap-close {
  background: none;
  border: 1px solid var(--text-dim);
  color: var(--text-dim);
  font-size: 16px;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 2px;
}

.ap-close:hover { color: var(--danger); border-color: var(--danger); }

/* 内容区 */
.ap-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.ap-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 30px 0;
  color: var(--text-dim);
}

.ap-spinner {
  width: 32px;
  height: 32px;
  border: 2px solid rgba(184, 155, 104, 0.2);
  border-top-color: var(--gold);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* 分析 */
.ap-analysis {
  padding: 12px;
  background: rgba(184, 155, 104, 0.04);
  border: 1px solid rgba(184, 155, 104, 0.1);
  border-radius: 2px;
  margin-bottom: 12px;
}

.ap-analysis-label {
  font-size: 11px;
  color: var(--gold);
  letter-spacing: 2px;
  margin-bottom: 6px;
}

.ap-analysis-text {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.7;
}

/* 建议卡片 */
.ap-suggestions {
  margin-bottom: 16px;
}

.ap-sug-label {
  font-size: 11px;
  color: var(--text-dim);
  letter-spacing: 2px;
  margin-bottom: 8px;
}

.ap-sug-card {
  padding: 14px;
  border-radius: 2px;
  border: 1px solid rgba(184, 155, 104, 0.15);
  background: rgba(184, 155, 104, 0.04);
}

.ap-sug-card.priority-critical {
  border-color: rgba(200, 60, 40, 0.3);
  background: rgba(200, 60, 40, 0.04);
}

.ap-sug-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.ap-sug-priority {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 2px;
  letter-spacing: 1px;
}

.ap-sug-priority.critical { background: rgba(200, 60, 40, 0.15); color: #D07070; border: 1px solid rgba(200, 60, 40, 0.3); }
.ap-sug-priority.major { background: rgba(200, 160, 40, 0.15); color: #D4B860; border: 1px solid rgba(200, 160, 40, 0.3); }
.ap-sug-priority.minor { background: rgba(90, 140, 90, 0.12); color: #7AB87A; border: 1px solid rgba(90, 140, 90, 0.2); }

.ap-sug-category {
  font-size: 10px;
  color: var(--text-dim);
  letter-spacing: 1px;
}

.ap-sug-content {
  font-size: 13px;
  color: var(--text-main);
  line-height: 1.8;
  font-family: "STKaiti", "KaiTi", serif;
}

/* 影响评估 */
.ap-sug-impact {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dotted rgba(139, 115, 85, 0.2);
}

.impact-label {
  font-size: 10px;
  color: var(--text-dim);
  letter-spacing: 1px;
}

.impact-rows {
  margin-top: 4px;
}

.impact-row {
  display: flex;
  justify-content: space-between;
  padding: 2px 0;
  font-size: 11px;
}

.impact-key { color: var(--text-dim); }
.impact-val { font-weight: bold; }
.impact-val.positive { color: #7AB87A; }
.impact-val.negative { color: #D07070; }

/* 操作按钮 */
.ap-actions {
  display: flex;
  gap: 8px;
  justify-content: center;
}

.ap-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 16px;
  font-size: 12px;
  font-family: "SimSun", serif;
  letter-spacing: 2px;
  border-radius: 2px;
  cursor: pointer;
  transition: all 0.15s;
}

.ap-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.ap-btn.reject {
  background: rgba(200, 60, 40, 0.08);
  border: 1px solid rgba(200, 60, 40, 0.2);
  color: #D07070;
}

.ap-btn.reject:hover:not(:disabled) {
  background: rgba(200, 60, 40, 0.15);
  border-color: #D07070;
}

.ap-btn.consider {
  background: rgba(184, 155, 104, 0.06);
  border: 1px solid rgba(184, 155, 104, 0.2);
  color: var(--text-secondary);
}

.ap-btn.consider:hover:not(:disabled) {
  background: rgba(184, 155, 104, 0.12);
  border-color: var(--gold);
}

.ap-btn.approve {
  background: rgba(90, 160, 90, 0.1);
  border: 1px solid rgba(90, 160, 90, 0.3);
  color: #7AB87A;
  font-weight: bold;
}

.ap-btn.approve:hover:not(:disabled) {
  background: rgba(90, 160, 90, 0.18);
  border-color: #7AB87A;
}

.ap-btn.suggest {
  background: rgba(184, 155, 104, 0.12);
  border: 1px solid var(--gold);
  color: var(--gold);
  margin: 0 auto;
}

.ap-btn.open-panel {
  background: rgba(184, 155, 104, 0.04);
  border: 1px solid rgba(184, 155, 104, 0.2);
  color: var(--text-dim);
  margin: 8px auto 0;
  font-size: 12px;
}
.ap-btn.open-panel:hover {
  background: rgba(184, 155, 104, 0.1);
  color: var(--gold);
}

/* 翻页 */
.ap-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 10px;
  font-size: 11px;
  color: var(--text-dim);
}

.ap-pagination button {
  padding: 4px 10px;
  font-size: 10px;
  background: rgba(184, 155, 104, 0.05);
  border: 1px solid rgba(184, 155, 104, 0.15);
  color: var(--text-dim);
  cursor: pointer;
  border-radius: 2px;
}

.ap-pagination button:hover:not(:disabled) {
  border-color: var(--gold);
  color: var(--gold);
}

/* 追问模式 */
.ap-followup {
  padding: 10px 0;
}

.ap-followup-label {
  font-size: 12px;
  color: var(--gold);
  letter-spacing: 2px;
  margin-bottom: 8px;
}

.ap-followup-input {
  width: 100%;
  padding: 10px;
  background: var(--bg-input);
  border: 1px solid var(--border-main);
  color: var(--text-main);
  font-family: "SimSun", serif;
  font-size: 12px;
  resize: vertical;
  border-radius: 2px;
  margin-bottom: 10px;
}

.ap-followup-input:focus {
  outline: none;
  border-color: var(--gold);
}

/* 空状态 */
.ap-empty {
  text-align: center;
  padding: 30px 0;
}

.ap-empty-icon { font-size: 40px; margin-bottom: 10px; }

.ap-empty p {
  color: var(--text-dim);
  font-size: 13px;
  margin: 4px 0;
}

.ap-empty-hint {
  font-size: 11px !important;
  margin-bottom: 16px !important;
}

/* 执行结果 */
.ap-result {
  border-top: 1px solid rgba(184, 155, 104, 0.2);
  padding: 12px 20px;
  background: rgba(184, 155, 104, 0.03);
}

.ap-result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--gold);
  letter-spacing: 2px;
  margin-bottom: 8px;
}

.result-icon-ok { color: #7AB87A; font-weight: bold; }
.result-icon-fail { color: #D07070; font-weight: bold; }

.ap-result-close {
  margin-left: auto;
  background: none;
  border: none;
  color: var(--text-dim);
  font-size: 14px;
  cursor: pointer;
}

.ap-result-narrative {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.7;
  margin-bottom: 8px;
}

.ap-result-section-title {
  font-size: 10px;
  color: var(--gold);
  letter-spacing: 2px;
  margin: 4px 0;
}

.ap-result-section-title.fail { color: #D07070; }

.ap-result-item {
  font-size: 11px;
  padding: 2px 8px;
  border-left: 2px solid var(--gold);
  margin: 2px 0;
  color: var(--text-dim);
}

.ap-result-item.fail {
  border-left-color: #D07070;
}
</style>
