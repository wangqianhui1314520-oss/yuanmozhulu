<template>
  <div class="fp-panel-group" :class="panelGroupClass">
  <!-- 国库面板 -->
  <div v-if="store.activePanel === 'treasury'" class="float-panel animate-fade-in artifact-panel artifact-memorial" style="top:var(--panel-top);right:var(--panel-offset-right);width:380px;max-height:80vh;">
    <div class="fp-header">
      <h3>📜 国库卷宗</h3>
      <div class="territory-tabs" style="margin-left:auto;margin-right:8px;">
        <button class="territory-tab" :class="{ active: treasuryTab === 'overview' }" @click="treasuryTab = 'overview'">总览</button>
        <button class="territory-tab" :class="{ active: treasuryTab === 'income' }" @click="treasuryTab = 'income'">收入</button>
        <button class="territory-tab" :class="{ active: treasuryTab === 'expense' }" @click="treasuryTab = 'expense'">支出</button>
      </div>
      <button v-audio class="fp-close" @click="store.togglePanel('treasury')">✕</button>
    </div>
    <div class="fp-body" style="max-height:62vh;overflow-y:auto;">
      <!-- 总览 -->
      <template v-if="treasuryTab === 'overview'">
        <div class="treasury-summary-cards">
          <div class="tsc-card gold-bg">
            <div class="tsc-val">{{ formatNum(playerFaction?.treasury) }}</div>
            <div class="tsc-lbl">银两</div>
          </div>
          <div class="tsc-card grain-bg">
            <div class="tsc-val">{{ formatNum(playerFaction?.grain) }}</div>
            <div class="tsc-lbl">粮草</div>
          </div>
          <div class="tsc-card">
            <div class="tsc-val">{{ formatNum(playerFaction?.arms) }}</div>
            <div class="tsc-lbl">军械</div>
          </div>
          <div class="tsc-card">
            <div class="tsc-val">{{ formatNum(playerFaction?.horses) }}</div>
            <div class="tsc-lbl">战马</div>
          </div>
        </div>
        <div class="kv-divider"></div>
        <div class="kv-row"><span class="kv-label">声望</span><span class="kv-value">{{ store.reputation }}</span></div>
        <div class="kv-row"><span class="kv-label">民心</span><span class="kv-value" :class="store.realmStability < 40 ? 'danger-text' : ''">{{ store.realmStability }}</span></div>
        <div class="kv-row"><span class="kv-label">朝纲</span><span class="kv-value" :class="store.courtStability < 40 ? 'danger-text' : ''">{{ store.courtStability }}</span></div>
        <div class="kv-row"><span class="kv-label">灾厄</span><span class="kv-value" :class="store.disasterIndex > 40 ? 'danger-text' : ''">{{ store.disasterIndex }}</span></div>
        <div class="kv-divider"></div>
        <div class="kv-row"><span class="kv-label">总兵力</span><span class="kv-value troop-text">{{ formatNum(store.totalTroops) }}</span></div>
        <div class="kv-row"><span class="kv-label">总人口</span><span class="kv-value">{{ formatNum(store.totalPopulation) }}</span></div>
        <div class="kv-row"><span class="kv-label">领地</span><span class="kv-value">{{ store.playerTiles.length }}块</span></div>
        <div class="kv-divider"></div>
        <div class="treasury-actions">
          <button v-audio class="btn-small" @click="store.togglePanel('diplomacy')">📦 开拓贸易</button>
          <button v-audio class="btn-small" @click="store.togglePanel('construction')">🏗 营造增产</button>
        </div>
      </template>
      <!-- 收入明细 -->
      <template v-if="treasuryTab === 'income'">
        <h4 class="section-subtitle">💰 收入来源</h4>
        <div class="income-list">
          <div class="income-item">
            <span class="income-icon">🏘️</span>
            <div class="income-info">
              <span class="income-name">赋税收入</span>
              <span class="income-desc">领地{{ store.playerTiles.length }}块 · 人口{{ formatNum(store.totalPopulation) }}</span>
            </div>
            <span class="income-val gold-text">+{{ formatNum(estimateTaxIncome()) }}/回合</span>
          </div>
          <div class="income-item">
            <span class="income-icon">🌾</span>
            <div class="income-info">
              <span class="income-name">粮草产出</span>
              <span class="income-desc">从{{ countTileType('farmland') }}块农田产出</span>
            </div>
            <span class="income-val grain-text">+{{ formatNum(estimateGrainOutput()) }}/回合</span>
          </div>
          <div v-if="estimateTradeIncome() > 0" class="income-item">
            <span class="income-icon">📦</span>
            <div class="income-info">
              <span class="income-name">贸易收入</span>
              <span class="income-desc">通商路线 · 港口贸易</span>
            </div>
            <span class="income-val gold-text">+{{ formatNum(estimateTradeIncome()) }}/回合</span>
          </div>
          <div class="income-item">
            <span class="income-icon">⚒️</span>
            <div class="income-info">
              <span class="income-name">工坊产出</span>
              <span class="income-desc">军械所·马场生产</span>
            </div>
            <span class="income-val">+{{ formatNum(estimateWorkshopOutput()) }}/回合</span>
          </div>
        </div>
      </template>
      <!-- 支出明细 -->
      <template v-if="treasuryTab === 'expense'">
        <h4 class="section-subtitle">📉 支出项目</h4>
        <div class="income-list">
          <div class="income-item expense-item">
            <span class="income-icon">⚔️</span>
            <div class="income-info">
              <span class="income-name">军费开支</span>
              <span class="income-desc">{{ formatNum(store.totalTroops) }}兵力 · 粮草消耗</span>
            </div>
            <span class="income-val danger-text">-{{ formatNum(estimateMilitaryCost()) }}/回合</span>
          </div>
          <div class="income-item expense-item">
            <span class="income-icon">🏛️</span>
            <div class="income-info">
              <span class="income-name">官员俸禄</span>
              <span class="income-desc">{{ store.officials.length }}位在朝官员</span>
            </div>
            <span class="income-val danger-text">-{{ formatNum(store.officials.length * 50) }}/回合</span>
          </div>
          <div class="income-item expense-item">
            <span class="income-icon">🏗️</span>
            <div class="income-info">
              <span class="income-name">营造维护</span>
              <span class="income-desc">城池·工坊·医馆修缮</span>
            </div>
            <span class="income-val danger-text">-{{ formatNum(Math.max(100, store.playerTiles.length * 25)) }}/回合</span>
          </div>
          <div class="income-item expense-item">
            <span class="income-icon">🎁</span>
            <div class="income-info">
              <span class="income-name">外交贡礼</span>
              <span class="income-desc">藩属赏赐·使节往来</span>
            </div>
            <span class="income-val danger-text">-{{ formatNum(Math.max(50, Object.keys(store.relations || {}).length * 100)) }}/回合</span>
          </div>
        </div>
        <div class="kv-divider"></div>
        <div class="kv-row">
          <span class="kv-label">预估净收支</span>
          <span class="kv-value" :class="estimateNetIncome() >= 0 ? 'gold-text' : 'danger-text'">
            {{ estimateNetIncome() >= 0 ? '+' : '' }}{{ formatNum(estimateNetIncome()) }}/回合
          </span>
        </div>
      </template>
    </div>
  </div>

  <!-- 天下势力面板 -->
  <div v-if="store.activePanel === 'factions'" class="float-panel animate-fade-in artifact-panel artifact-codex" style="top:var(--panel-top);right:var(--panel-offset-right);width:400px;max-height:70vh;">
    <div class="fp-header">
      <h3>👥 天下大势</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('factions')">✕</button>
    </div>
    <div class="fp-body" style="max-height:60vh;overflow-y:auto;">
      <div
        v-for="f in store.livingFactions"
        :key="f.faction_id"
        class="faction-card"
        :class="{ 'is-player': f.faction_id === store.playerFactionId, 'intel-hidden': !store.isFactionIntelVisible(f.faction_id) }"
        :style="{ borderLeftColor: f.color }"
      >
        <div class="fc-header">
          <span class="fc-name" :style="{ color: f.color }">{{ f.name }}</span>
          <span class="fc-title">{{ f.title }}</span>
          <span v-if="f.faction_id === store.playerFactionId" class="fc-badge">本朝</span>
          <span v-else-if="!store.isFactionIntelVisible(f.faction_id)" class="fc-intel-tag">🕵 情报未知</span>
        </div>
        <div class="fc-stats" v-if="store.isFactionIntelVisible(f.faction_id)">
          兵{{ formatNum(f.total_troops) }} · 银{{ formatNum(f.treasury) }} · 地{{ f.tile_count || 0 }}块
        </div>
        <div class="fc-stats fc-stats-unknown" v-else>
          <span>兵?</span> · <span>银?</span> · <span>地?</span>
          <span class="fc-intel-hint">— 需派遣细作刺探</span>
        </div>
        <div class="fc-tags" v-if="f.personality_tags?.length">
          <span v-for="tag in f.personality_tags" :key="tag" class="fc-tag">{{ tag }}</span>
        </div>
      </div>
    </div>
  </div>

  <!-- 朝堂面板（完整版：国策树 + 官员管理 + 敕令发布 + 廷议入口） -->
  <div v-if="store.activePanel === 'court'" class="float-panel animate-fade-in artifact-panel artifact-edict" style="top:var(--panel-top);right:var(--panel-offset-right);width:460px;max-height:80vh;">
    <div class="fp-header">
      <h3>🏛 朝堂</h3>
      <div class="court-tabs">
        <button :class="{ active: courtTab === 'overview' }" @click="courtTab = 'overview'">总览</button>
        <button :class="{ active: courtTab === 'policies' }" @click="courtTab = 'policies'">国策</button>
        <button :class="{ active: courtTab === 'officials' }" @click="courtTab = 'officials'">官员</button>
        <button :class="{ active: courtTab === 'decrees' }" @click="courtTab = 'decrees'">敕令</button>
      </div>
      <button v-audio class="fp-close" @click="store.togglePanel('court')">✕</button>
    </div>

    <!-- 总览 -->
    <div class="fp-body" style="max-height:65vh;overflow-y:auto;" v-if="courtTab === 'overview'">
      <div class="court-overview">
        <div class="court-stat-row">
          <div class="court-stat" :class="getStatClass(store.courtStability)">
            <span class="cs-label">朝纲稳定</span>
            <span class="cs-value">{{ store.courtStability }}</span>
          </div>
          <div class="court-stat" :class="getStatClass(store.realmStability)">
            <span class="cs-label">境内民心</span>
            <span class="cs-value">{{ store.realmStability }}</span>
          </div>
          <div class="court-stat">
            <span class="cs-label">发展水平</span>
            <span class="cs-value">{{ playerFaction?.development_level || 20 }}</span>
          </div>
          <div class="court-stat">
            <span class="cs-label">声望</span>
            <span class="cs-value">{{ playerFaction?.reputation || 0 }}</span>
          </div>
        </div>
      </div>
      <div class="kv-divider"></div>
      <h4 class="section-subtitle">朝堂概况</h4>
      <div class="kv-row"><span class="kv-label">在朝官员</span><span class="kv-value">{{ officialsData.length }}人</span></div>
      <div class="kv-row"><span class="kv-label">已解锁国策</span><span class="kv-value">{{ (playerFaction?.unlocked_policies?.length || 0) }}项</span></div>
      <div class="kv-row"><span class="kv-label">已颁布敕令</span><span class="kv-value">{{ store.decrees.length }}道</span></div>
      <div class="kv-row"><span class="kv-label">在押俘虏</span><span class="kv-value">{{ prisonerData.length }}人</span></div>
      <div class="kv-divider"></div>
      <h4 class="section-subtitle">势力Buff/Debuff</h4>
      <div v-if="playerFaction?.buffs?.length || playerFaction?.debuffs?.length">
        <div v-for="b in playerFaction?.buffs" :key="b.name" class="kv-row small">
          <span class="kv-label buff-label">🟢 {{ b.name }}</span>
          <span class="kv-value buff-text">{{ b.effect }}</span>
        </div>
        <div v-for="d in playerFaction?.debuffs" :key="d.name" class="kv-row small">
          <span class="kv-label debuff-label">🔴 {{ d.name }}</span>
          <span class="kv-value debuff-text">{{ d.effect }}</span>
        </div>
      </div>
      <div v-else class="empty-note">暂无特殊状态</div>
      <div class="kv-divider"></div>
      <!-- 派系忠诚度 -->
      <h4 class="section-subtitle">派系势力</h4>
      <div v-if="courtOverviewData?.faction_loyalty_summary && Object.keys(courtOverviewData.faction_loyalty_summary).length > 0">
        <div v-for="(info, aff) in courtOverviewData.faction_loyalty_summary" :key="aff" class="loyalty-row">
          <div class="loyalty-bar-wrap">
            <div class="loyalty-bar" :style="{ width: info.avg_loyalty + '%', background: loyaltyColor(info.avg_loyalty) }"></div>
          </div>
          <span class="loyalty-name">{{ aff }}</span>
          <span class="loyalty-val" :class="getStatClass(info.avg_loyalty)">{{ info.avg_loyalty }}</span>
          <span class="loyalty-count">({{ info.count }}人)</span>
        </div>
      </div>
      <div v-else class="empty-note">暂无派系数</div>

      <div class="kv-divider"></div>
      <!-- 廷议历史 -->
      <h4 class="section-subtitle">廷议纪事</h4>
      <div v-if="debateHistory.length > 0">
        <div v-for="(dh, i) in debateHistory.slice(0, 5)" :key="dh.debate_id || i" class="debate-history-item">
          <div class="dh-header">
            <span class="dh-round">第{{ dh.round }}回合</span>
            <span class="dh-resolution" :class="dh.resolution_type">{{ dh.resolution || '圣裁' }}</span>
          </div>
          <div class="dh-topic">「{{ dh.topic }}」</div>
          <div class="dh-meta" v-if="dh.npc_count > 0">{{ dh.npc_count }}位大臣参议</div>
        </div>
      </div>
      <div v-else class="empty-note">暂无廷议记录。</div>

      <div class="kv-divider"></div>
      <div class="court-actions">
        <button v-audio class="btn-small" @click="openCourtDebate">🏛 召开廷议</button>
        <button v-audio class="btn-small" @click="issueDecree">📜 颁布敕令</button>
        <button v-audio class="btn-small" @click="courtTab = 'policies'">📋 查阅国策</button>
      </div>
      <div class="kv-divider"></div>
      <h4 class="section-subtitle">P1 高级朝政</h4>
      <div class="court-actions">
        <button v-audio class="btn-small" @click="doSacrifice" :disabled="(playerFaction?.treasury || 0) < 500">🙏 祭祀天地</button>
        <button v-audio class="btn-small" @click="doRecruitOfficials" :disabled="(playerFaction?.treasury || 0) < 300">📝 科举选拔</button>
        <button v-audio class="btn-small" @click="store.togglePanel('moveCapital')">🏛 迁都议事</button>
      </div>
    </div>

    <!-- 国策树 -->
    <div class="fp-body" style="max-height:65vh;overflow-y:auto;" v-if="courtTab === 'policies'">
      <div class="policy-branches">
        <div class="policy-branch-tabs">
          <button v-for="cat in policyCategories" :key="cat.key"
            :class="{ active: activePolicyCat === cat.key }"
            @click="activePolicyCat = cat.key">
            {{ cat.icon }} {{ cat.name }}
          </button>
        </div>
        <div class="kv-row"><span class="kv-label">国库</span><span class="kv-value gold-text">{{ formatNum(playerFaction?.treasury) }}</span></div>
        <div class="kv-divider"></div>
        <div v-for="branch in currentPolicyBranches" :key="branch.id" class="policy-branch">
          <h5 class="branch-name">{{ branch.name }}</h5>
          <div v-for="tier in branch.tiers" :key="tier.id" class="policy-tier"
            :class="{ 
              'policy-unlocked': isPolicyUnlocked(tier.id),
              'policy-available': canUnlockPolicy(tier),
              'policy-locked': !canUnlockPolicy(tier) && !isPolicyUnlocked(tier.id)
            }">
            <div class="policy-tier-header">
              <span class="tier-name">{{ tier.name }}</span>
              <span class="tier-cost">银{{ tier.cost }}</span>
            </div>
            <p class="tier-desc">{{ tier.description }}</p>
            <div class="tier-effects">
              <span v-for="(val, key) in tier.effects" :key="key" class="effect-tag">{{ effectLabel(String(key)) }}+{{ val }}</span>
            </div>
            <button v-if="canUnlockPolicy(tier) && !isPolicyUnlocked(tier.id)"
              class="btn-small unlock-btn" @click="unlockPolicy(tier)">
              采纳国策
            </button>
            <span v-else-if="isPolicyUnlocked(tier.id)" class="unlocked-badge">✓ 已采纳</span>
            <span v-else class="locked-badge">🔒 {{ getLockReason(tier) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 官员管理 -->
    <div class="fp-body" style="max-height:65vh;overflow-y:auto;" v-if="courtTab === 'officials'">
      <div class="kv-row"><span class="kv-label">在朝官员</span><span class="kv-value">{{ officialsData.length }}人</span></div>
      <div class="kv-divider"></div>
      <div v-if="officialsData.length === 0" class="empty-note">暂无官员。通过廷议或招安来获取人才。</div>
      <div v-for="off in officialsData" :key="off.official_id || off.name" class="official-card">
        <div class="off-header">
          <span class="off-name">{{ off.name }}</span>
          <span class="off-position">{{ off.position }}</span>
          <span class="off-faction" v-if="off.faction_affiliation">[{{ off.faction_affiliation }}]</span>
        </div>
        <div class="off-stats">
          <span class="off-stat" :class="getStatClass(off.loyalty || 50)">忠{{ off.loyalty || 50 }}</span>
          <span class="off-stat" :class="getStatClass(off.ability || 50)">能{{ off.ability || 50 }}</span>
        </div>
        <div class="off-actions" v-if="off.faction_id === store.playerFactionId">
          <button class="btn-tiny" @click="dismissOfficer(off.official_id)" title="罢免">罢免</button>
          <button class="btn-tiny danger" @click="executeOfficer(off.official_id)" title="处决">处决</button>
        </div>
      </div>
      <div class="kv-divider"></div>
      <h4 class="section-subtitle">任命新官</h4>
      <div class="appoint-form">
        <input v-model="newOfficialName" class="appoint-input" placeholder="官员姓名" />
        <input v-model="newOfficialPosition" class="appoint-input" placeholder="官职（如：知府、将军）" />
        <div class="appoint-stats">
          <label>能力 <input v-model.number="newOfficialAbility" type="range" min="20" max="95" /></label>
          <span>{{ newOfficialAbility }}</span>
          <label>忠诚 <input v-model.number="newOfficialLoyalty" type="range" min="20" max="95" /></label>
          <span>{{ newOfficialLoyalty }}</span>
        </div>
        <button v-audio class="btn-small" @click="appointOfficial" :disabled="!newOfficialName.trim() || !newOfficialPosition.trim()">
          任命
        </button>
      </div>
    </div>

    <!-- 敕令发布 -->
    <div class="fp-body" style="max-height:65vh;overflow-y:auto;" v-if="courtTab === 'decrees'">
      <div class="kv-row"><span class="kv-label">已颁敕令</span><span class="kv-value">{{ store.decrees.length }}道</span></div>
      <div class="kv-divider"></div>
      <div v-if="store.decrees.length === 0" class="empty-note">尚未颁布敕令。使用底部圣旨栏或此处发布。</div>
      <div v-for="d in store.decrees.slice(0, 20)" :key="d.id || d.title" class="decree-item">
        <span class="decree-title">{{ d.title || d.name || d.decree_text }}</span>
        <span class="decree-round" v-if="d.round">[第{{ d.round }}回合]</span>
      </div>
      <div class="kv-divider"></div>
      <h4 class="section-subtitle">颁布敕令</h4>
      <textarea v-model="decreeText" class="decree-input" rows="3" placeholder="颁布敕令内容...（例：大赦天下、减免赋税三成、全国征兵）"></textarea>
      <button v-audio class="btn-small" @click="publishDecree" :disabled="!decreeText.trim()">颁布敕令</button>
      <div class="kv-divider"></div>
      <h4 class="section-subtitle">快捷敕令</h4>
      <div class="quick-decree-list">
        <button v-for="q in quickDecrees" :key="q" class="quick-decree-btn" @click="decreeText = q">{{ q }}</button>
      </div>
    </div>
  </div>

  <!-- 军事面板 -->
  <div v-if="store.activePanel === 'military'" class="float-panel animate-fade-in artifact-panel artifact-dispatch" style="top:var(--panel-top);right:var(--panel-offset-right);width:380px;">
    <div class="fp-header fp-header-war">
      <div class="fp-header-deco">
        <img src="/assets/ui/ai_ui_war_banner.png" alt="" class="fp-war-banner" />
      </div>
      <h3>⚔ 军务卷宗</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('military')">✕</button>
    </div>
    <div class="fp-body">
      <div class="kv-row"><span class="kv-label">总兵力</span><span class="kv-value troop-text">{{ formatNum(store.totalTroops) }}</span></div>
      <div class="kv-row"><span class="kv-label">军械</span><span class="kv-value">{{ formatNum(playerFaction?.arms) }}</span></div>
      <div class="kv-row"><span class="kv-label">战马</span><span class="kv-value">{{ formatNum(playerFaction?.horses) }}</span></div>
      <div class="kv-row"><span class="kv-label">骑兵比例</span><span class="kv-value">{{ horseRatio }}%</span></div>
      <div class="kv-divider"></div>
      <div class="military-actions">
        <button v-audio class="btn-small" @click="store.togglePanel('recruit')">🛡 招兵买马</button>
        <button v-audio class="btn-small" @click="store.togglePanel('construction')">🔨 营造司</button>
        <button v-audio class="btn-small" @click="store.togglePanel('workshop')">🏭 工坊生产</button>
      </div>
      <div class="kv-divider"></div>
      <h4 class="section-subtitle">高级军务（P1）</h4>
      <div class="military-actions">
        <button v-audio class="btn-small" @click="store.togglePanel('ambush')">🌲 伏击设伏</button>
        <button v-audio class="btn-small" @click="store.togglePanel('plunder')">🏴 劫掠敌境</button>
      </div>
      <div class="kv-divider"></div>
      <h4 class="section-subtitle">各城驻军</h4>
      <div v-if="store.playerTiles.length === 0" class="empty-note">暂无领地</div>
      <div v-for="tile in store.playerTiles.slice(0, 10)" :key="tile.tile_id" class="kv-row small">
        <span class="kv-label">{{ tile.tile_name }}</span>
        <span class="kv-value">{{ formatNum(tile.troops) }}兵</span>
      </div>
    </div>
  </div>

  <!-- 外交面板 -->
  <div v-if="store.activePanel === 'diplomacy'" class="float-panel animate-fade-in artifact-panel artifact-secret" style="top:var(--panel-top);right:var(--panel-offset-right);width:440px;max-height:80vh;">
    <div class="fp-header">
      <h3>🤝 邦交总览</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('diplomacy')">✕</button>
    </div>
    <div class="fp-body" style="max-height:68vh;overflow-y:auto;">
      <!-- 国库概况 -->
      <div class="diplo-res-bar">
        <div class="diplo-res-item">
          <span class="diplo-res-icon">💰</span>
          <span class="diplo-res-val gold-text">{{ formatNum(playerFaction?.treasury) }}</span>
          <span class="diplo-res-lbl">银两</span>
        </div>
        <div class="diplo-res-item">
          <span class="diplo-res-icon">⭐</span>
          <span class="diplo-res-val">{{ playerFaction?.reputation || 0 }}</span>
          <span class="diplo-res-lbl">声望</span>
        </div>
        <div class="diplo-res-item">
          <span class="diplo-res-icon">📊</span>
          <span class="diplo-res-val">{{ store.livingFactions.length }}</span>
          <span class="diplo-res-lbl">势力</span>
        </div>
      </div>
      <div class="kv-divider"></div>
      <!-- 谋士推荐 -->
      <div v-if="diploRecommendations.length > 0" class="diplo-rec-section">
        <h4 class="section-subtitle">📋 谋士建言</h4>
        <div v-for="(rec, i) in diploRecommendations.slice(0, 3)" :key="i" class="diplo-rec-item" :class="'rec-' + rec.priority">
          <span class="rec-priority" :class="rec.priority">{{ {high:'急',medium:'中',low:'缓'}[rec.priority] || '中' }}</span>
          <span class="rec-text">{{ rec.reason }}</span>
        </div>
      </div>
      <div class="diplo-quick-links">
        <button v-audio class="btn-small" @click="emit('openDiplomacyDeep'); store.togglePanel('diplomacy')" style="width:100%;">
          🎋 纵横权谋 · 合纵连横
        </button>
      </div>
      <div class="kv-divider"></div>

      <div v-for="f in store.livingFactions" :key="f.faction_id" class="faction-card diplo-card" :class="{ 'intel-hidden': !store.isFactionIntelVisible(f.faction_id) }" :style="{ borderLeftColor: f.color }">
        <!-- 势力头部 -->
        <div class="fc-header">
          <span class="fc-name" :style="{ color: f.color }">{{ f.name }}</span>
          <span class="fc-stance" :class="'stance-' + getStance(f.faction_id)">
            {{ getStanceLabel(f.faction_id) }}
          </span>
          <span v-if="f.faction_id === store.playerFactionId" class="fc-badge">本朝</span>
          <span v-else-if="!store.isFactionIntelVisible(f.faction_id)" class="fc-intel-tag">🕵 情报未知</span>
        </div>
        <div class="fc-stats" v-if="store.isFactionIntelVisible(f.faction_id)">
          好感度：{{ getAttitude(f.faction_id) }} · 兵{{ formatNum(f.total_troops) }} · 地{{ f.tile_count || 0 }}块
        </div>
        <div class="fc-stats fc-stats-unknown" v-else>
          好感度：{{ getAttitude(f.faction_id) }} · 兵? · 地?
          <span class="fc-intel-hint">— 需派遣细作刺探</span>
        </div>

        <!-- 外交操作区（非本朝） -->
        <div v-if="f.faction_id !== store.playerFactionId" class="diplo-actions">
          <button class="diplo-act-btn" @click="doDiplomacy(f.faction_id, 'tribute')" :disabled="(playerFaction?.treasury || 0) < 500">
            <span class="dab-icon">🎁</span>
            <span class="dab-label">纳贡</span>
            <span class="dab-cost">-500银</span>
            <span class="dab-gain">好感+10</span>
          </button>
          <button class="diplo-act-btn" @click="doDiplomacy(f.faction_id, 'alliance')" :disabled="(playerFaction?.treasury || 0) < 800">
            <span class="dab-icon">🤝</span>
            <span class="dab-label">结盟</span>
            <span class="dab-cost">-800银</span>
            <span class="dab-gain">同盟关系</span>
          </button>
          <button class="diplo-act-btn" @click="doDiplomacy(f.faction_id, 'trade')" :disabled="(playerFaction?.treasury || 0) < 200">
            <span class="dab-icon">📦</span>
            <span class="dab-label">通商</span>
            <span class="dab-cost">-200银</span>
            <span class="dab-gain">+100银/回合</span>
          </button>
          <button class="diplo-act-btn" @click="doDiplomacy(f.faction_id, 'marriage')" :disabled="(playerFaction?.treasury || 0) < 500">
            <span class="dab-icon">💒</span>
            <span class="dab-label">联姻</span>
            <span class="dab-cost">-500银</span>
            <span class="dab-gain">好感+25,声望+5</span>
          </button>
          <button class="diplo-act-btn" @click="doDiplomacy(f.faction_id, 'truce')" :disabled="(playerFaction?.treasury || 0) < 300">
            <span class="dab-icon">☮</span>
            <span class="dab-label">停战</span>
            <span class="dab-cost">-300银</span>
            <span class="dab-gain">停战状态</span>
          </button>
          <button class="diplo-act-btn danger-act" @click="doDiplomacy(f.faction_id, 'war')">
            <span class="dab-icon">⚔</span>
            <span class="dab-label">宣战</span>
            <span class="dab-cost">-10声望</span>
            <span class="dab-gain">交战状态</span>
          </button>
          <button class="diplo-act-btn" @click="doDiplomacy(f.faction_id, 'vassal_offer')" :disabled="(playerFaction?.treasury || 0) < 1000">
            <span class="dab-icon">🏰</span>
            <span class="dab-label">提议附庸</span>
            <span class="dab-cost">-1000银</span>
            <span class="dab-gain">建立附庸关系</span>
          </button>
          <button class="diplo-act-btn" @click="doDiplomacy(f.faction_id, 'vassal_cancel')">
            <span class="dab-icon">🔓</span>
            <span class="dab-label">取消附庸</span>
            <span class="dab-cost">-200银</span>
            <span class="dab-gain">解除附庸关系</span>
          </button>
          <button class="diplo-act-btn" @click="doDiplomacy(f.faction_id, 'trade_close')">
            <span class="dab-icon">📦</span>
            <span class="dab-label">关闭贸易</span>
            <span class="dab-cost">免费</span>
            <span class="dab-gain">终止通商</span>
          </button>
          <!-- P1 高级外交 -->
          <button class="diplo-act-btn" @click="doDiplomacy(f.faction_id, 'hostage')" :disabled="(playerFaction?.treasury || 0) < 300">
            <span class="dab-icon">👤</span>
            <span class="dab-label">派遣质子</span>
            <span class="dab-cost">-300银</span>
            <span class="dab-gain">好感+15</span>
          </button>
          <button class="diplo-act-btn" @click="doDiplomacy(f.faction_id, 'hostage_recall')">
            <span class="dab-icon">🔙</span>
            <span class="dab-label">召回质子</span>
            <span class="dab-cost">-5声望</span>
            <span class="dab-gain">关系-25</span>
          </button>
          <button class="diplo-act-btn danger-act" @click="doDiplomacy(f.faction_id, 'annex')" :disabled="(playerFaction?.treasury || 0) < 5000">
            <span class="dab-icon">🗡</span>
            <span class="dab-label">吞并附庸</span>
            <span class="dab-cost">-5000银</span>
            <span class="dab-gain">合并领土</span>
          </button>
        </div>
      </div>

      <!-- 外交操作反馈 -->
      <div v-if="diploFeedback.text" class="kv-divider"></div>
      <div v-if="diploFeedback.text" class="build-feedback" :class="diploFeedback.type">
        {{ diploFeedback.text }}
      </div>
    </div>
  </div>

  <!-- 灾荒面板 -->
  <div v-if="store.activePanel === 'disaster'" class="float-panel animate-fade-in artifact-panel artifact-memorial" style="top:var(--panel-top);right:var(--panel-offset-right);width:380px;max-height:70vh;">
    <div class="fp-header">
      <h3>⚠ 灾荒录</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('disaster')">✕</button>
    </div>
    <div class="fp-body" style="max-height:55vh;overflow-y:auto;">
      <div class="disaster-index-bar">
        <div class="di-label">灾厄指数</div>
        <div class="di-bar-wrap">
          <div class="di-bar-fill" :style="{ width: Math.min(100, store.disasterIndex) + '%', background: store.disasterIndex > 60 ? '#c44b3c' : store.disasterIndex > 30 ? '#b8963e' : '#5b8c5a' }"></div>
        </div>
        <div class="di-val" :class="store.disasterIndex > 40 ? 'danger-text' : ''">{{ store.disasterIndex }}</div>
      </div>
      <div class="kv-divider"></div>
      <div v-if="store.activeDisasters.length === 0" class="empty-note">暂无灾荒，天下太平</div>
      <div v-for="d in store.activeDisasters" :key="d.id" class="disaster-card" :class="'severity-' + (d.severity || '中')">
        <div class="dc-header">
          <span class="dc-name">{{ d.name }}</span>
          <span class="dc-severity" :class="d.severity === '高' ? 'danger-text' : d.severity === '中' ? 'warn-text' : ''">
            {{ d.severity || '中' }}
          </span>
        </div>
        <div class="dc-info" v-if="d.tile_id">影响地块: {{ d.tile_id }}</div>
        <div class="dc-info" v-if="d.affected_pop">受灾人口: {{ formatNum(d.affected_pop) }}</div>
        <div class="dc-actions">
          <button v-audio class="btn-tiny" @click="relieveDisaster(d)" :disabled="(playerFaction?.treasury || 0) < getReliefCost(d)">
            🆘 赈灾 ({{ getReliefCost(d) }}银)
          </button>
          <button v-audio class="btn-tiny" @click="prayForDisaster(d)">
            🙏 祈福
          </button>
        </div>
        <div v-if="dRelieving === d.id" class="dc-relief-result">
          <span class="loading-spinner">⟳</span> 赈灾中...
        </div>
        <div v-if="dReliefResult && dRelievedId === d.id" class="dc-relief-result" :class="dReliefResult.success ? 'good-text' : 'danger-text'">
          {{ dReliefResult.message }}
        </div>
      </div>
      <div class="kv-divider"></div>
      <h4 class="section-subtitle">防灾建设</h4>
      <div class="disaster-actions">
        <button v-audio class="btn-small" @click="store.togglePanel('construction')">🏗 建造水利设施</button>
        <button v-audio class="btn-small" @click="store.togglePanel('medical')">🏥 建设医馆</button>
        <button v-audio class="btn-small" @click="forecastDisasters" :disabled="forecastLoading">
          {{ forecastLoading ? '预判中...' : '🔮 AI预判灾异' }}
        </button>
      </div>
      <div v-if="forecastResult" class="forecast-result">
        <div class="fr-label">钦天监预判：</div>
        <div class="fr-content">{{ forecastResult }}</div>
      </div>
    </div>
  </div>

  <!-- 工程面板 -->
  <div v-if="store.activePanel === 'construction'" class="float-panel animate-fade-in artifact-panel artifact-memorial" style="top:var(--panel-top);right:var(--panel-offset-right);width:420px;max-height:80vh;">
    <div class="fp-header">
      <h3>🏗 营造司</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('construction')">✕</button>
    </div>
    <div class="fp-body" style="max-height:68vh;overflow-y:auto;">
      <!-- 选择建造地块 -->
      <h4 class="section-subtitle">选择建造地块</h4>
      <select v-model="buildTargetTileId" class="build-tile-select" @change="onBuildTileChange">
        <option value="">-- 请选择地块 --</option>
        <option v-for="t in buildableTiles" :key="t.tile_id" :value="t.tile_id">
          {{ t.tile_name || t.tile_id }}（{{ tileTypeName(t.tile_type) }}·人口{{ t.population }}·城防{{ t.fortification }}）
        </option>
      </select>
      <p v-if="!buildTargetTileId && buildableTiles.length === 0" class="empty-note warn">
        ⚠ 未检测到己方领地数据，请确认游戏已正常开局。
      </p>
      <p v-else-if="!buildTargetTileId" class="empty-note">请先选择一个己方地块，再查看建造详情。</p>

      <!-- 选中地块建筑一览 -->
      <template v-if="buildTargetTileId && currentBuildTile">
        <div class="kv-divider"></div>
        <h4 class="section-subtitle">📋 {{ currentBuildTile.tile_name || buildTargetTileId }} · 建筑一览</h4>

        <!-- 建筑详情卡片 -->
        <div class="building-cards">
          <div
            v-for="b in buildingDefs"
            :key="b.key"
            class="building-card"
            :class="{ 'building-owned': getBuildingLevel(b.key) > 0, 'building-locked': isBuildingLocked(b) }"
          >
            <div class="bc-header">
              <span class="bc-icon">{{ b.icon }}</span>
              <span class="bc-name">{{ b.name }}</span>
              <span class="bc-level" v-if="getBuildingLevel(b.key) > 0">Lv.{{ getBuildingLevel(b.key) }}</span>
              <span class="bc-level bc-none" v-else>未建</span>
            </div>
            <div class="bc-effect">{{ b.effect }}</div>
            <div class="bc-cost" v-if="!isBuildingLocked(b)">
              <span class="cost-label">建造费用：</span>
              <span class="cost-value">{{ b.key === 'fortification' ? (300 * (getBuildingLevel(b.key) + 1)) : b.cost }}银</span>
              <span v-if="b.req" class="cost-req">（需：{{ b.req }}）</span>
            </div>
            <!-- 城防当前收益 -->
            <div class="bc-current-effect" v-if="b.key === 'fortification' && getBuildingLevel(b.key) > 0">
              <span class="bce-label">当前：</span>
              <span class="bce-value">防御+{{ getBuildingLevel(b.key) * 20 }}%，驻军上限+{{ getBuildingLevel(b.key) * 2000 }}</span>
            </div>
            <div class="bc-locked-hint" v-if="isBuildingLocked(b)">{{ getBuildLockReason(b) }}</div>
            <button
              class="btn-tiny bc-btn"
              @click="buildWorkshop(b.key)"
              :disabled="isBuildingLocked(b) || (store.playerFaction?.treasury || 0) < b.cost"
            >
              {{ getBuildingLevel(b.key) > 0 ? '升级' : '建造' }}
            </button>
          </div>
        </div>
      </template>

      <!-- 建造反馈 -->
      <div v-if="buildFeedback.text" class="kv-divider"></div>
      <div v-if="buildFeedback.text" class="build-feedback" :class="buildFeedback.type">
        {{ buildFeedback.text }}
      </div>

      <!-- 全部领地工坊汇总 -->
      <div class="kv-divider"></div>
      <h4 class="section-subtitle">🏭 全境工坊汇总</h4>
      <div v-if="workshopData && workshopData.workshops && workshopData.workshops.length > 0" class="workshop-list">
        <div v-for="ws in workshopData.workshops" :key="ws.tile_id" class="workshop-item" @click="buildTargetTileId = ws.tile_id; onBuildTileChange()">
          <span class="ws-name">{{ ws.tile_name }}</span>
          <span v-for="w in ws.workshops" :key="w.type" class="ws-tag">{{ workshopLabel(w.type) }}Lv.{{ w.level }}</span>
        </div>
      </div>
      <p v-else class="empty-note">暂无工坊建设记录。选择地块开始营造。</p>
    </div>
  </div>

  <!-- AI推演面板 -->
  <div v-if="store.activePanel === 'ai-strategy'" class="float-panel animate-fade-in artifact-panel artifact-secret" style="top:var(--panel-top);right:var(--panel-offset-right);width:420px;max-height:70vh;">
    <div class="fp-header">
      <h3>🧠 谋士推演</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('ai-strategy')">✕</button>
    </div>
    <div class="fp-body" style="max-height:55vh;overflow-y:auto;">
      <div class="ai-loading" v-if="aiLoading">
        <span class="loading-spinner">⟳</span> 谋士正在推演天下大势...
      </div>
      <div v-else-if="aiResult" class="ai-result">
        <div class="ai-section">
          <h5>威胁评估</h5>
          <p>{{ aiResult.threats }}</p>
        </div>
        <div class="ai-section">
          <h5>战略机遇</h5>
          <p>{{ aiResult.opportunities }}</p>
        </div>
        <div class="ai-section">
          <h5>行动建议</h5>
          <p>{{ aiResult.recommendations }}</p>
        </div>
      </div>
      <div v-else class="empty-note">
        <button v-audio class="btn-small" @click="runStrategyAnalysis">请求谋士推演</button>
      </div>
    </div>
  </div>

  <!-- 律法面板 -->
  <div v-if="store.activePanel === 'law'" class="float-panel animate-fade-in artifact-panel artifact-edict" style="top:var(--panel-top);left:var(--panel-offset-left);width:420px;max-height:75vh;">
    <div class="fp-header">
      <h3>⚖ 律法卷宗</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('law')">✕</button>
    </div>
    <div class="fp-body" style="max-height:62vh;overflow-y:auto;">
      <!-- 选中的囚犯 -->
      <div v-if="lawSelectedPrisoner" class="law-selected-prisoner">
        <span class="ls-label">当前审判：</span>
        <span class="ls-name">{{ lawSelectedPrisoner.name }}</span>
        <span class="ls-from">({{ lawSelectedPrisoner.origin_faction || '未知' }})</span>
        <button class="btn-tiny" @click="lawSelectedPrisoner = null">取消</button>
      </div>
      <div v-else class="hint-text">请从下方囚犯名册中选择审判对象</div>
      <div class="kv-divider"></div>
      <!-- 囚犯名册 -->
      <h4 class="section-subtitle">囚犯名册 ({{ prisonerData.length }})</h4>
      <div v-if="prisonerData && prisonerData.length > 0" class="prisoner-select-list">
        <div v-for="p in prisonerData" :key="p.prisoner_id || p.name" 
             class="prisoner-row" 
             :class="{ selected: lawSelectedPrisoner?.prisoner_id === p.prisoner_id || lawSelectedPrisoner?.name === p.name }"
             @click="lawSelectedPrisoner = p">
          <span class="pr-name">{{ p.name }}</span>
          <span class="pr-from">{{ p.origin_faction || '未知' }}</span>
          <span class="pr-status">{{ p.status || '在押' }}</span>
          <span class="pr-select-mark">{{ (lawSelectedPrisoner?.prisoner_id === p.prisoner_id || lawSelectedPrisoner?.name === p.name) ? '✅' : '○' }}</span>
        </div>
      </div>
      <p v-else class="empty-note">暂无在押囚犯。战争俘虏会自动进入囚犯名册。</p>
      <div class="kv-divider"></div>
      <!-- 量刑参考 -->
      <h4 class="section-subtitle">量刑参考</h4>
      <div v-if="!lawSelectedPrisoner" class="hint-text">请先选择一名囚犯</div>
      <div v-else class="law-refs">
        <div class="law-ref" :class="{ disabled: lawActionLoading }" @click="handleLawActionWithPrisoner('execute')">
          ⚔ 斩立决 — 谋逆、通敌
        </div>
        <div class="law-ref" :class="{ disabled: lawActionLoading }" @click="handleLawActionWithPrisoner('exile')">
          🔗 流放 — 贪墨、失职
        </div>
        <div class="law-ref" :class="{ disabled: lawActionLoading }" @click="handleLawActionWithPrisoner('pardon')">
          📜 赦免 — 戴罪立功
        </div>
        <div class="law-ref" :class="{ disabled: lawActionLoading }" @click="handleLawActionWithPrisoner('fine')">
          💰 罚银 — 轻微过失
        </div>
        <div class="law-ref" :class="{ disabled: lawActionLoading }" @click="handleLawActionWithPrisoner('court')">
          🏛 廷议 — 争议案件
        </div>
      </div>
      <div v-if="lawActionResult" class="law-result" :class="lawActionResult.type">{{ lawActionResult.text }}</div>
      <div class="kv-divider"></div>
      <button v-audio class="btn-small" @click="openLawInterrogate" style="width:100%;" v-if="lawSelectedPrisoner">
        🔍 刑部审讯 — 审问{{ lawSelectedPrisoner.name }}
      </button>
      <button v-audio class="btn-small" @click="openLawInterrogate" style="width:100%;" v-else>
        🔍 打开刑部审讯
      </button>
    </div>
  </div>

  <!-- 谍报驿站面板 -->
  <div v-if="store.activePanel === 'spy'" class="float-panel animate-fade-in artifact-panel artifact-secret" style="top:var(--panel-top);left:var(--panel-offset-left);width:380px;">
    <div class="fp-header">
      <h3>🕵 驿站谍报</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('spy')">✕</button>
    </div>
    <div class="fp-body" style="max-height:65vh;overflow-y:auto;">
      <div class="kv-row"><span class="kv-label">谍网数量</span><span class="kv-value">{{ store.spyNetworks.length }}</span></div>
      <div class="kv-divider"></div>
      <div v-if="store.spyNetworks.length === 0" class="empty-note">暂无谍报网络，可在地图上右键目标城池派遣细作。</div>
      <div v-for="net in store.spyNetworks" :key="net.network_id" class="spy-network-item">
        <div class="kv-row">
          <span class="kv-label">{{ net.target_faction_id || net.target_faction }}</span>
          <span class="kv-value">渗透{{ net.infiltration || 0 }}% · 细作{{ net.spies_count || 0 }}人</span>
        </div>
        <div class="spy-actions" v-if="net.spies_count > 0">
          <button class="spy-act-btn" @click="doSpyAction(net, 'gather_intel')" title="刺探情报：获取敌军粮草、兵力信息">
            <span>🔍</span> 刺探
          </button>
          <button class="spy-act-btn" @click="doSpyAction(net, 'sow_discord')" title="离间君臣：降低敌方将领忠诚度">
            <span>🗣</span> 离间
          </button>
          <button class="spy-act-btn" @click="doSpyAction(net, 'sabotage')" title="纵火毁产：破坏敌方粮仓/武库">
            <span>🔥</span> 破坏
          </button>
          <button class="spy-act-btn danger-act" @click="doSpyAction(net, 'assassinate')" title="刺杀敌将（高风险）">
            <span>🗡</span> 刺杀
          </button>
        </div>
      </div>
      <!-- 已刺探情报列表 -->
      <div v-if="playerSpyIntel.length > 0" style="margin-top:12px;">
        <div class="kv-divider"></div>
        <div class="spy-section-title">📜 已刺探情报</div>
        <div class="spy-intel-list">
          <div v-for="(intel, idx) in playerSpyIntel" :key="idx" class="spy-intel-card">
            <div class="spy-intel-header">
              <span class="spy-intel-faction" :style="{ color: getFactionColorById(intel.target_faction) }">
                {{ getFactionNameById(intel.target_faction) }}
              </span>
              <span class="spy-intel-round">第{{ intel.round }}回合</span>
              <span class="spy-intel-infiltration">渗透{{ intel.infiltration || 0 }}%</span>
            </div>
            <div class="spy-intel-data">
              <span class="intel-field">💰 银{{ formatNum(intel.data?.treasury || 0) }}</span>
              <span class="intel-field">🌾 粮{{ formatNum(intel.data?.grain || 0) }}</span>
              <span class="intel-field">⚔ 兵{{ formatNum(intel.data?.total_troops || 0) }}</span>
              <span class="intel-field">👥 口{{ formatNum(intel.data?.total_population || 0) }}</span>
              <span class="intel-field">🏛 朝{{ intel.data?.court_stability ?? '?' }}</span>
              <span class="intel-field">❤ 民{{ intel.data?.realm_stability ?? '?' }}</span>
              <span class="intel-field">🏰 {{ intel.data?.tiles ?? '?' }}城</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 谍报反馈 -->
      <div v-if="spyFeedback.text" class="kv-divider"></div>
      <div v-if="spyFeedback.text" class="build-feedback" :class="spyFeedback.type">
        {{ spyFeedback.text }}
      </div>
      <p class="hint-text" style="margin-top:12px;">右键地图上敌方城池可派遣细作。渗透度越高，行动成功率越高。暴露的细作需要重新派遣。</p>
    </div>
  </div>

  <!-- 藩镇面板 -->
  <div v-if="store.activePanel === 'vassal'" class="float-panel animate-fade-in artifact-panel artifact-codex" style="top:var(--panel-top);left:var(--panel-offset-left);width:420px;max-height:75vh;">
    <div class="fp-header">
      <h3>🏰 藩镇管控</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('vassal')">✕</button>
    </div>
    <div class="fp-body" style="max-height:62vh;overflow-y:auto;">
      <!-- 风险概览 -->
      <div v-if="vassalRisk !== null" class="vassal-risk-header">
        <span class="kv-label">叛乱风险</span>
        <span class="kv-value" :class="vassalRisk > 50 ? 'stat-bad' : vassalRisk > 20 ? 'stat-warn' : 'stat-good'">{{ vassalRisk }}%</span>
      </div>
      <div class="kv-divider"></div>
      <!-- 藩镇列表 -->
      <h4 class="section-subtitle">🏴 藩属势力 ({{ playerVassals.length }})</h4>
      <div v-if="playerVassals.length === 0" class="empty-note">暂无藩属势力。可通过外交手段收服其他势力为藩属。</div>
      <div v-for="v in playerVassals" :key="v.faction_id" class="vassal-card" :style="{ borderLeftColor: v.color }">
        <div class="vc-header">
          <span class="vc-name" :style="{ color: v.color }">{{ v.name }}</span>
          <span class="vc-stats">{{ v.tile_count || 0 }}城 · {{ formatNum(v.troops || 0) }}兵</span>
        </div>
        <div class="vc-body">
          <span class="vc-loyalty">忠诚：{{ getVassalLoyalty(v.faction_id) }}</span>
        </div>
        <div class="vc-actions">
          <button class="btn-tiny" @click="doVassalTribute(v.faction_id)">💰 纳贡</button>
          <button class="btn-tiny" @click="doVassalSuppress(v.faction_id)">⚔ 征讨</button>
          <button class="btn-tiny" @click="doVassalAnnex(v.faction_id)">🏴 吞并</button>
          <button class="btn-tiny" @click="doVassalRelease(v.faction_id)">🔓 释放</button>
        </div>
      </div>
      <div class="kv-divider"></div>
      <!-- 已纳贡记录 -->
      <h4 class="section-subtitle" v-if="vassalTributes.length > 0">📋 纳贡记录</h4>
      <div v-for="(t, i) in vassalTributes" :key="i" class="tribute-item">
        <span>{{ t.faction_name }}</span>
        <span class="tribute-amount">{{ t.amount }}银/回合</span>
      </div>
      <!-- 检查按钮 -->
      <button v-audio class="btn-small" @click="checkVassalRisk" :disabled="vassalChecking" style="width:100%;margin-top:8px;">
        {{ vassalChecking ? '检查中...' : '🔍 刷新藩镇风险' }}
      </button>
    </div>
  </div>

  <!-- 工坊生产面板 -->
  <div v-if="store.activePanel === 'workshop'" class="float-panel animate-fade-in artifact-panel artifact-personnel" style="top:var(--panel-top);left:var(--panel-offset-left);width:420px;max-height:75vh;">
    <div class="fp-header">
      <h3>🔨 工坊生产</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('workshop')">✕</button>
    </div>
    <div class="fp-body" style="max-height:62vh;overflow-y:auto;">
      <!-- 全局产量总览 -->
      <div class="workshop-summary">
        <div class="ws-summary-item">
          <span class="ws-summary-label">军械产出</span>
          <span class="ws-summary-val">{{ workshopArmsOutput }}件/回合</span>
        </div>
        <div class="ws-summary-item">
          <span class="ws-summary-label">银两产出</span>
          <span class="ws-summary-val">{{ workshopGoldOutput }}两/回合</span>
        </div>
        <div class="ws-summary-item">
          <span class="ws-summary-label">粮草加工</span>
          <span class="ws-summary-val">{{ workshopGrainOutput }}石/回合</span>
        </div>
      </div>
      <div class="kv-divider"></div>
      <!-- 生产侧重 -->
      <h4 class="section-subtitle">⚙ 生产侧重</h4>
      <div class="workshop-focus-options">
        <button class="ws-focus-btn" :class="{ active: workshopFocus === 'arms' }" @click="setWorkshopFocus('arms')">
          ⚔ 军械优先
        </button>
        <button class="ws-focus-btn" :class="{ active: workshopFocus === 'gold' }" @click="setWorkshopFocus('gold')">
          💰 银两优先
        </button>
        <button class="ws-focus-btn" :class="{ active: workshopFocus === 'grain' }" @click="setWorkshopFocus('grain')">
          🌾 粮草优先
        </button>
        <button class="ws-focus-btn" :class="{ active: workshopFocus === 'balanced' }" @click="setWorkshopFocus('balanced')">
          ⚖ 均衡生产
        </button>
      </div>
      <div v-if="workshopFocusResult" class="focus-result" :class="workshopFocusResult.type">{{ workshopFocusResult.text }}</div>
      <div class="kv-divider"></div>
      <!-- 工坊列表 -->
      <h4 class="section-subtitle">🏭 工坊列表 ({{ workshopTotalCount }})</h4>
      <div v-if="workshopData && workshopData.workshops && workshopData.workshops.length > 0">
        <div v-for="ws in workshopData.workshops" :key="ws.tile_id" class="workshop-item-detail">
          <div class="ws-header-row">
            <span class="ws-name">{{ ws.tile_name }}</span>
            <button class="btn-tiny" @click="buildTargetTileId = ws.tile_id; store.togglePanel('construction')">⬆ 升级</button>
          </div>
          <div class="ws-tags">
            <span v-for="w in ws.workshops" :key="w.type" class="ws-tag">{{ workshopLabel(w.type) }} Lv.{{ w.level }}</span>
          </div>
        </div>
      </div>
      <p v-else class="empty-note">暂无工坊。在"营造司"面板中建设工坊。</p>
      <div class="kv-divider"></div>
      <button v-audio class="btn-small" @click="store.togglePanel('construction')" style="width:100%;">🏗 前往营造司</button>
    </div>
  </div>

  <!-- 叛军镇压面板（P0） -->
  <div v-if="store.activePanel === 'rebel'" class="float-panel animate-fade-in artifact-panel artifact-dispatch" style="top:var(--panel-top);left:var(--panel-offset-left);width:420px;max-height:70vh;">
    <div class="fp-header">
      <h3>⚔ 叛军镇压</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('rebel')">✕</button>
    </div>
    <div class="fp-body" style="max-height:55vh;overflow-y:auto;">
      <div v-if="rebelData && rebelData.length > 0">
        <div class="kv-row"><span class="kv-label">当前叛军</span><span class="kv-value danger-text">{{ rebelData.length }}支</span></div>
        <div class="kv-divider"></div>
        <div v-for="rb in rebelData" :key="rb.rebel_id" class="rebel-card">
          <div class="rebel-header">
            <span class="rebel-leader">{{ rb.leader }}</span>
            <span class="rebel-cause">{{ rb.cause }}</span>
          </div>
          <div class="rebel-stats">
            <span>📍 {{ rb.tile_name || rb.tile_id }}</span>
            <span>⚔ {{ formatNum(rb.troops) }}人</span>
            <span>📅 第{{ rb.spawned_round }}回合</span>
          </div>
          <div class="rebel-actions">
            <input v-model.number="suppressTroops[rb.rebel_id]" type="number" class="input-tiny" placeholder="派遣兵力" min="100" style="width:100px;" />
            <button class="btn-small danger" @click="doSuppressRebel(rb.rebel_id)" :disabled="suppressing === rb.rebel_id">
              {{ suppressing === rb.rebel_id ? '镇压中...' : '出兵镇压' }}
            </button>
          </div>
        </div>
      </div>
      <p v-else class="empty-note">天下太平，暂无叛军作乱。</p>
      <div class="kv-divider"></div>
      <p class="hint-text">叛军由民变引发，民心低落或战乱频繁时易生。镇压需派遣兵力，成功则收复失地；失败则损失惨重。叛军超20回合将自行消散。</p>
    </div>
  </div>

  <!-- 伏击面板（P1） -->
  <div v-if="store.activePanel === 'ambush'" class="float-panel animate-fade-in artifact-panel artifact-dispatch" style="top:var(--panel-top);left:var(--panel-offset-left);width:400px;">
    <div class="fp-header">
      <h3>🌲 伏击设伏</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('ambush')">✕</button>
    </div>
    <div class="fp-body">
      <div class="kv-row"><span class="kv-label">在山地/关隘设伏</span></div>
      <div class="kv-row">
        <span class="kv-label">目标势力</span>
        <select v-model="ambushTarget" class="input-select">
          <option value="">-- 选择目标 --</option>
          <option v-for="f in store.livingFactions.filter(x => x.faction_id !== store.playerFactionId)" :key="f.faction_id" :value="f.faction_id">{{ f.name }}</option>
        </select>
      </div>
      <div class="kv-row">
        <span class="kv-label">伏击地点</span>
        <select v-model="ambushTileId" class="input-select">
          <option value="">-- 选择山地/关隘 --</option>
          <option v-if="!ambushTarget" value="" disabled>请先选择目标势力</option>
          <option v-for="t in ambushTiles" :key="t.tile_id" :value="t.tile_id">
            {{ t.tile_name }} ({{ t.tile_type === 'mountain' ? '山地' : '关隘' }}){{ t.faction_id === store.playerFactionId ? ' [己方]' : ' [邻接]' }}
          </option>
        </select>
        <span v-if="ambushTarget && ambushTiles.length === 0" class="hint-text" style="color:#e74c3c;">附近无可伏击的山地/关隘</span>
      </div>
      <div class="kv-row">
        <span class="kv-label">派遣兵力</span>
        <input v-model.number="ambushTroops" type="number" class="input-tiny" placeholder="至少100" min="100" style="width:120px;" />
      </div>
      <div class="kv-divider"></div>
      <button v-audio class="btn-small" @click="doAmbush" :disabled="ambushing">🌲 {{ ambushing ? '伏击中...' : '发动伏击' }}</button>
      <p class="hint-text" style="margin-top:8px;">只能在山地或关隘设伏。伏击成功将对敌军造成额外伤害（约1.8倍），关隘伏击成功率更高（65%）。</p>
    </div>
  </div>

  <!-- 劫掠面板（P1） -->
  <div v-if="store.activePanel === 'plunder'" class="float-panel animate-fade-in artifact-panel artifact-dispatch" style="top:var(--panel-top);left:var(--panel-offset-left);width:400px;">
    <div class="fp-header">
      <h3>🏴 劫掠敌境</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('plunder')">✕</button>
    </div>
    <div class="fp-body">
      <h4 class="section-subtitle">劫掠补给线</h4>
      <div class="kv-row">
        <span class="kv-label">目标势力</span>
        <select v-model="raidTarget" class="input-select">
          <option value="">-- 选择目标 --</option>
          <option v-for="f in store.livingFactions.filter(x => x.faction_id !== store.playerFactionId)" :key="f.faction_id" :value="f.faction_id">{{ f.name }}</option>
        </select>
      </div>
      <div class="kv-row">
        <span class="kv-label">派遣兵力</span>
        <input v-model.number="raidSupplyTroops" type="number" class="input-tiny" placeholder="至少100" min="100" style="width:120px;" />
      </div>
      <!-- 预估成功率 -->
      <div v-if="raidTarget && raidSupplyTroops >= 100" class="kv-row">
        <span class="kv-label">预估成功率</span>
        <span class="kv-value" :class="estimatedRaidChance >= 0.6 ? 'green-text' : estimatedRaidChance >= 0.4 ? 'gold-text' : 'red-text'">
          {{ Math.round(estimatedRaidChance * 100) }}%
        </span>
      </div>
      <div v-if="raidTarget && raidIntelHint" class="kv-row">
        <span class="kv-label">情报来源</span>
        <span class="kv-value hint-text">{{ raidIntelHint }}</span>
      </div>
      <div v-if="raidTarget && estimatedRelationPenalty" class="kv-row">
        <span class="kv-label">风险提示</span>
        <span class="kv-value red-text">被发现将影响双方好感度(-{{ estimatedRelationPenalty }})</span>
      </div>
      <button v-audio class="btn-small" @click="doRaidSupply" :disabled="raiding || raidSupplyTroops < 100">
        🏴 劫掠粮道 ({{ raidSupplyTroops >= 100 ? Math.round(estimatedRaidChance * 100) + '%' : '需≥100兵' }})
      </button>
      <div class="kv-divider"></div>
      <h4 class="section-subtitle">边境劫掠</h4>
      <div class="kv-row">
        <span class="kv-label">目标势力</span>
        <select v-model="borderRaidTarget" class="input-select">
          <option value="">-- 选择目标 --</option>
          <option v-for="f in store.livingFactions.filter(x => x.faction_id !== store.playerFactionId)" :key="f.faction_id" :value="f.faction_id">{{ f.name }}</option>
        </select>
      </div>
      <div class="kv-row">
        <span class="kv-label">劫掠兵力</span>
        <input v-model.number="borderRaidTroops" type="number" class="input-tiny" placeholder="至少200" min="200" style="width:120px;" />
      </div>
      <button class="btn-small danger" @click="doBorderRaid" :disabled="raiding">🏴 边境劫掠 (需接壤)</button>
      <p class="hint-text" style="margin-top:8px;">劫掠补给线成功率受派遣兵力、细作情报、敌方防御影响。被发现后双方好感度将大幅下降。</p>
    </div>
  </div>

  <!-- 迁都面板（完整重设计） -->
  <div v-if="store.activePanel === 'moveCapital'" class="float-panel animate-fade-in artifact-panel artifact-edict" style="top:var(--panel-top);left:var(--panel-offset-left);width:560px;">
    <div class="fp-header">
      <h3>🏛 迁都议事</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('moveCapital')">✕</button>
    </div>
    <div class="fp-body" style="max-height:70vh;overflow-y:auto;">

      <!-- 加载中 -->
      <div v-if="capitalCandidatesLoading" class="loading-row">⏳ 谋士正在评估各城池…</div>

      <!-- 当前都城信息卡片 -->
      <div v-if="capitalCandidatesData?.current_capital" class="capital-current-card">
        <div class="cc-header">📍 当前都城</div>
        <div class="cc-name">{{ capitalCandidatesData.current_capital.tile_name }}</div>
        <div class="cc-stats">
          <div class="cc-stat"><span>人口</span><span>{{ formatNum(capitalCandidatesData.current_capital.population) }}</span></div>
          <div class="cc-stat"><span>城防</span><span>{{ capitalCandidatesData.current_capital.fortification }}</span></div>
          <div class="cc-stat"><span>民心</span><span :class="getStatClass(capitalCandidatesData.current_capital.morale)">{{ capitalCandidatesData.current_capital.morale }}</span></div>
          <div class="cc-stat"><span>治安</span><span :class="getStatClass(capitalCandidatesData.current_capital.public_order)">{{ capitalCandidatesData.current_capital.public_order }}</span></div>
          <div class="cc-stat"><span>驻军</span><span>{{ formatNum(capitalCandidatesData.current_capital.troops) }}</span></div>
        </div>
      </div>

      <!-- 谋士建议 -->
      <div v-if="capitalCandidatesData?.adviser_recommendation" class="adviser-recommend">
        <span class="ar-icon">💬</span>
        <span class="ar-text">{{ capitalCandidatesData.adviser_recommendation }}</span>
      </div>

      <!-- 迁都费用 & 效果预览 -->
      <div class="capital-cost-bar">
        <div class="cost-item">
          <span class="cost-label">迁都费用</span>
          <span class="cost-val">10,000 银两</span>
        </div>
        <div class="cost-item">
          <span class="cost-label">朝纲影响</span>
          <span class="cost-val" style="color:#c44b3c">-3 ~ -8</span>
        </div>
        <div class="cost-item">
          <span class="cost-label">民心震荡</span>
          <span class="cost-val" style="color:#c44b3c">全境 -5 ~ -15</span>
        </div>
        <div class="cost-item">
          <span class="cost-label">新都加成</span>
          <span class="cost-val" style="color:#5b8c5a">城防+2，治安+10</span>
        </div>
      </div>

      <!-- 候选列表 -->
      <div v-if="capitalCandidates.length === 0 && !capitalCandidatesLoading" class="empty-note">
        当前无可选都城。需要更多城市作为备选，或领地内均为屯兵点/村落。
      </div>

      <div v-if="capitalCandidates.length > 0" class="candidate-section">
        <div class="section-label">可选新都（{{ capitalCandidates.length }}城）</div>
        <div
          v-for="c in capitalCandidates"
          :key="c.tile_id"
          class="candidate-card"
          :class="{ 'candidate-selected': selectedCandidateId === c.tile_id }"
          @click="selectCandidate(c.tile_id)"
        >
          <div class="cand-top">
            <div class="cand-name-row">
              <span class="cand-name">{{ c.tile_name }}</span>
              <span class="cand-grade" :class="'grade-' + getGradeLevel(c.grade)">{{ c.grade }}</span>
              <span class="cand-score">{{ c.composite_score }}分</span>
            </div>
            <span class="cand-advice">{{ c.advice }}</span>
          </div>
          <div class="cand-stats-grid">
            <div class="cand-stat-item">
              <span class="csi-label">人口</span>
              <span class="csi-val">{{ formatNum(c.population) }}</span>
              <span class="csi-bar"><span class="csi-fill" :style="{ width: Math.min(100, c.population / 5000 * 100) + '%' }"></span></span>
            </div>
            <div class="cand-stat-item">
              <span class="csi-label">城防</span>
              <span class="csi-val">{{ c.fortification }}</span>
              <span class="csi-bar"><span class="csi-fill" :style="{ width: (c.fortification * 10) + '%', background: c.fortification >= 6 ? '#5b8c5a' : c.fortification >= 3 ? '#b8963e' : '#c44b3c' }"></span></span>
            </div>
            <div class="cand-stat-item">
              <span class="csi-label">民心</span>
              <span class="csi-val" :class="getStatClass(c.morale)">{{ c.morale }}</span>
              <span class="csi-bar"><span class="csi-fill" :style="{ width: c.morale + '%', background: c.morale >= 70 ? '#5b8c5a' : c.morale >= 40 ? '#b8963e' : '#c44b3c' }"></span></span>
            </div>
            <div class="cand-stat-item">
              <span class="csi-label">治安</span>
              <span class="csi-val" :class="getStatClass(c.public_order)">{{ c.public_order }}</span>
              <span class="csi-bar"><span class="csi-fill" :style="{ width: c.public_order + '%', background: c.public_order >= 70 ? '#5b8c5a' : c.public_order >= 40 ? '#b8963e' : '#c44b3c' }"></span></span>
            </div>
            <div class="cand-stat-item">
              <span class="csi-label">驻军</span>
              <span class="csi-val">{{ formatNum(c.troops) }}</span>
            </div>
            <div class="cand-stat-item">
              <span class="csi-label">类型</span>
              <span class="csi-val" style="font-size:10px;">{{ c.tile_type }}{{ c.is_port ? '·港口' : '' }}{{ c.stable > 0 ? '·马场' : '' }}{{ c.armory > 0 ? '·军械' : '' }}</span>
            </div>
          </div>
          <!-- 与当前都城对比 -->
          <div v-if="c.advantages.length > 0 || c.disadvantages.length > 0" class="cand-compare">
            <span v-if="c.advantages.length > 0" class="comp-adv">
              ✅ {{ c.advantages.join('、') }}
            </span>
            <span v-if="c.disadvantages.length > 0" class="comp-dis" style="margin-left:8px;">
              ⚠ {{ c.disadvantages.join('、') }}
            </span>
          </div>
        </div>
      </div>

      <!-- 选中候选详情 & 确认按钮 -->
      <div v-if="selectedCandidate" class="confirm-area">
        <div class="confirm-info">
          将迁都至<span class="gold-text">{{ selectedCandidate.tile_name }}</span>（评级{{ selectedCandidate.grade }}）
        </div>
        <button class="btn-primary" @click="doMoveCapital" :disabled="capitalMoving || (playerFaction?.treasury || 0) < 10000">
          {{ capitalMoving ? '迁都中...' : '🏛 确认迁都（消耗10,000银两）' }}
        </button>
        <button class="btn-tiny" style="margin-left:8px;" @click="cancelCapitalSelection">取消选择</button>
      </div>

      <!-- 迁都历史 -->
      <div v-if="capitalHistoryData && capitalHistoryData.history?.length > 0" class="kv-divider" style="margin-top:16px;"></div>
      <div v-if="capitalHistoryData && capitalHistoryData.history?.length > 0">
        <div class="section-label">迁都纪事（{{ capitalHistoryData.total_moves }}次）</div>
        <div v-for="(ch, i) in capitalHistoryData.history.slice(0, 5)" :key="ch.record_id || i" class="cap-history-item">
          <span class="ch-round">第{{ ch.round }}回合</span>
          <span class="ch-arrow">{{ ch.old_capital_name || ch.old_capital }} → {{ ch.new_capital_name || ch.new_capital }}</span>
          <span class="ch-cost">耗{{ ch.cost }}银</span>
        </div>
      </div>

    </div>
  </div>

  <!-- 俘虏招安面板 -->
  <div v-if="store.activePanel === 'prisoner'" class="float-panel animate-fade-in artifact-panel artifact-secret" style="top:var(--panel-top);left:var(--panel-offset-left);width:400px;">
    <div class="fp-header">
      <h3>🔗 俘虏招安</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('prisoner')">✕</button>
    </div>
    <div class="fp-body">
      <div v-if="prisonerData && prisonerData.length > 0">
        <div v-for="p in prisonerData" :key="p.prisoner_id || p.name" class="prisoner-item">
          <div class="kv-row">
            <span class="kv-label">{{ p.name }}</span>
            <span class="kv-value">{{ p.captured_from || p.origin_faction || '未知' }}</span>
          </div>
          <div class="prisoner-actions">
            <button class="btn-tiny" @click="handlePrisonerAction('recruit', p.prisoner_id)">招募</button>
            <button class="btn-tiny" @click="handlePrisonerAction('ransom', p.prisoner_id)">赎金</button>
            <button class="btn-tiny" @click="handlePrisonerAction('execute', p.prisoner_id)">处决</button>
            <button class="btn-tiny" @click="handlePrisonerAction('imprison', p.prisoner_id)">关押</button>
          </div>
        </div>
      </div>
      <p v-else class="empty-note">暂无俘虏。</p>
    </div>
  </div>

  <!-- 人物总览面板 -->
  <div v-if="store.activePanel === 'personnel'" class="float-panel animate-fade-in artifact-panel artifact-personnel" style="top:var(--panel-top);left:var(--panel-offset-left);width:420px;max-height:70vh;">
    <div class="fp-header">
      <h3>👤 人物总览</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('personnel')">✕</button>
    </div>
    <div class="fp-body" style="max-height:55vh;overflow-y:auto;">
      <!-- 统计卡片 -->
      <div class="personnel-stats">
        <div class="pstat"><span class="pstat-val">{{ store.officials.length }}</span><span class="pstat-lbl">在朝</span></div>
        <div class="pstat"><span class="pstat-val">{{ store.officials.filter((o: any) => (o.loyalty || 0) >= 70).length }}</span><span class="pstat-lbl">忠臣</span></div>
        <div class="pstat"><span class="pstat-val">{{ store.officials.filter((o: any) => (o.loyalty || 0) < 40).length }}</span><span class="pstat-lbl danger-text">隐患</span></div>
      </div>
      <div class="kv-divider"></div>
      <h4 class="section-subtitle">朝中官员</h4>
      <div v-if="store.officials.length === 0" class="empty-note">暂无官员，可前往朝堂任命</div>
      <!-- 官员列表（可点击展开） -->
      <div v-for="off in store.officials" :key="off.official_id || off.name"
        class="official-card" :class="{ expanded: selectedOfficial?.official_id === off.official_id || selectedOfficial?.name === off.name }"
        @click="selectOfficial(off)">
        <div class="oc-header">
          <span class="oc-name">{{ off.name }}</span>
          <span class="oc-position">{{ off.position }}</span>
          <span class="oc-expand">{{ (selectedOfficial?.official_id === off.official_id || selectedOfficial?.name === off.name) ? '▾' : '▸' }}</span>
        </div>
        <div class="oc-bars">
          <div class="oc-bar-row">
            <span class="oc-bar-label">忠诚</span>
            <div class="oc-bar-wrap"><div class="oc-bar-fill" :style="{ width: (off.loyalty || 50) + '%', background: loyaltyColor(off.loyalty || 50) }"></div></div>
            <span class="oc-bar-val">{{ off.loyalty || 50 }}</span>
          </div>
          <div class="oc-bar-row">
            <span class="oc-bar-label">能力</span>
            <div class="oc-bar-wrap"><div class="oc-bar-fill" :style="{ width: (off.ability || 50) + '%', background: '#5b8c5a' }"></div></div>
            <span class="oc-bar-val">{{ off.ability || 50 }}</span>
          </div>
        </div>
        <!-- 展开详情 -->
        <div v-if="selectedOfficial?.official_id === off.official_id || selectedOfficial?.name === off.name" class="oc-detail">
          <div class="kv-row small"><span class="kv-label">派系</span><span class="kv-value">{{ off.faction || off.affiliation || '中立' }}</span></div>
          <div class="kv-row small" v-if="off.age"><span class="kv-label">年龄</span><span class="kv-value">{{ off.age }}岁</span></div>
          <div class="kv-row small" v-if="off.salary"><span class="kv-label">俸禄</span><span class="kv-value">{{ off.salary }}银/回合</span></div>
          <div class="kv-row small" v-if="off.traits?.length"><span class="kv-label">特质</span><span class="kv-value">{{ off.traits.join('、') }}</span></div>
          <div class="oc-detail-actions">
            <button v-audio class="btn-tiny" @click.stop="promoteOfficial(off)">⬆ 提拔</button>
            <button v-audio class="btn-tiny" @click.stop="demoteOfficial(off)">⬇ 降职</button>
            <button v-audio class="btn-tiny danger" @click.stop="dismissPersonnelOfficial(off.official_id)">罢免</button>
          </div>
        </div>
      </div>
      <div class="kv-divider"></div>
      <div class="action-btns">
        <button v-audio class="btn-small" @click="store.togglePanel('court')">🏛 前往朝堂</button>
        <button v-audio class="btn-small" @click="doRecruitOfficials" :disabled="(playerFaction?.treasury || 0) < 300">📝 科举选官</button>
        <button v-audio class="btn-small" @click="emit('openTalentMarket')">🏛 人才市场</button>
      </div>
    </div>
  </div>

  <!-- 邸报事件面板（AI事件生成） -->
  <div v-if="store.activePanel === 'events'" class="float-panel animate-fade-in artifact-panel artifact-codex" style="top:var(--panel-top);left:var(--panel-offset-left);width:420px;max-height:70vh;">
    <div class="fp-header fp-header-events">
      <h3>📋 邸报 · 天下大事</h3>
      <img src="/assets/ui/ai_ui_seal_stamp.png" alt="" class="fp-seal-stamp" />
      <button v-audio class="fp-close" @click="store.togglePanel('events')">✕</button>
    </div>
    <div class="fp-body" style="max-height:55vh;overflow-y:auto;">
      <div style="text-align:center;margin-bottom:12px;">
        <button v-audio class="btn-small" @click="generateEvents" :disabled="eventLoading">
          {{ eventLoading ? '邸报正在生成...' : '📜 生成邸报事件' }}
        </button>
      </div>
      <div v-if="eventLoading" class="ai-loading">
        <span class="loading-spinner">⟳</span> 钦天监正在誊写邸报...
      </div>
      <div v-else-if="generatedEvents" class="generated-events">
        <div class="event-text">{{ generatedEvents }}</div>
      </div>
      <div v-else class="empty-note">点击上方按钮，AI将生成当前回合的邸报事件（天灾、朝堂轶事、武将反叛、流民起义等）。</div>
      <div class="kv-divider"></div>
      <h4 class="section-subtitle">历史事件记录 ({{ store.events.length }})</h4>
      <div v-if="store.events.length === 0" class="empty-note">暂无事件记录。</div>
      <div v-for="evt in store.events.slice(0, 20)" :key="evt.event_id" class="event-item">
        <span class="evt-title">{{ evt.title }}</span>
        <span class="evt-desc">{{ evt.description || evt.narrative }}</span>
      </div>
    </div>
  </div>

  <!-- 律法审讯面板（AI对话） -->
  <div v-if="store.activePanel === 'law-interrogate'" class="float-panel animate-fade-in artifact-panel artifact-secret" style="top:var(--panel-top);left:var(--panel-offset-left);width:420px;max-height:70vh;">
    <div class="fp-header">
      <h3>🔍 刑部审讯</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('law-interrogate')">✕</button>
    </div>
    <div class="fp-body" style="max-height:55vh;overflow-y:auto;">
      <div v-if="prisonerData && prisonerData.length > 0">
        <div class="kv-row"><span class="kv-label">选择囚犯</span></div>
        <div v-for="p in prisonerData" :key="p.prisoner_id || p.name" class="prisoner-select" @click="selectedPrisoner = p">
          <span :class="{ 'pr-selected': selectedPrisoner?.prisoner_id === p.prisoner_id || selectedPrisoner?.name === p.name }">
            {{ p.name }} ({{ p.origin_faction || '未知' }})
          </span>
        </div>
      </div>
      <p v-else class="empty-note">暂无在押囚犯可审讯。</p>
      <div v-if="selectedPrisoner" class="kv-divider"></div>
      <div v-if="selectedPrisoner">
        <div class="interrogate-input-row">
          <input v-model="interrogateQuestion" class="interrogate-input" placeholder="讯问内容..." @keydown.enter="doInterrogate" />
          <button v-audio class="btn-small" @click="doInterrogate" :disabled="interrogateLoading">
            {{ interrogateLoading ? '审讯中...' : '讯问' }}
          </button>
        </div>
        <div v-if="interrogateResult" class="interrogate-result">
          <div class="ir-label">「{{ selectedPrisoner.name }}」招供：</div>
          <div class="ir-content">{{ interrogateResult }}</div>
        </div>
      </div>
    </div>
  </div>

  <!-- 皇子宗室面板 -->
  <div v-if="store.activePanel === 'royal'" class="float-panel animate-fade-in artifact-panel artifact-personnel" style="top:var(--panel-top);left:var(--panel-offset-left);width:400px;max-height:70vh;">
    <div class="fp-header">
      <h3>{{ getPanelTitle('royal') }}</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('royal')">✕</button>
    </div>
    <div class="fp-body" style="max-height:58vh;overflow-y:auto;">
      <!-- 君主信息 -->
      <div class="ruler-card">
        <div class="ruler-avatar">👑</div>
        <div class="ruler-info">
          <div class="ruler-name">{{ royalInfo.ruler }}</div>
          <div class="ruler-meta">{{ royalInfo.rulerAge }}岁 · 在位{{ store.currentRound }}回合</div>
        </div>
      </div>
      <div class="kv-divider"></div>
      <div class="royal-stats">
        <div class="royal-stat" :class="getStatClass(royalInfo.count > 2 ? 80 : 30)">
          <span class="rs-val">{{ royalInfo.count }}</span><span class="rs-lbl">皇子</span>
        </div>
        <div class="royal-stat">
          <span class="rs-val">{{ royalInfo.grownHeirs }}</span><span class="rs-lbl">成年</span>
        </div>
        <div class="royal-stat" :class="royalInfo.risk === 'high' ? 'danger-text' : ''">
          <span class="rs-val">{{ royalInfo.heir }}</span><span class="rs-lbl">世子</span>
        </div>
        <div class="royal-stat" :class="royalInfo.risk === 'high' ? 'danger-text' : royalInfo.risk === 'medium' ? 'warn-text' : 'good-text'">
          <span class="rs-val">{{ royalInfo.risk === 'high' ? '高危' : royalInfo.risk === 'medium' ? '中等' : '低' }}</span>
          <span class="rs-lbl">风险</span>
        </div>
      </div>
      <div class="kv-divider"></div>
      <!-- 皇子列表（可交互） -->
      <h4 class="section-subtitle">皇子宗亲</h4>
      <div v-if="royalPrinces.length === 0" class="empty-note">
        <p>暂无皇子信息。皇子随游戏进程诞生与成长。</p>
        <p class="hint-text">可使用圣旨"生育皇子"或等待自然诞生。</p>
      </div>
      <div v-for="(prince, i) in royalPrinces" :key="i"
        class="prince-card" :class="{ expanded: selectedPrince?.name === prince.name }"
        @click="selectPrince(prince)">
        <div class="pc-header">
          <span class="pc-name">{{ prince.name }}</span>
          <span class="pc-age">{{ prince.age }}岁</span>
          <span class="pc-status" :class="prince.status === '世子' ? 'good-text' : ''">
            {{ prince.status }}
          </span>
        </div>
        <div class="pc-bars" v-if="prince.age >= 10">
          <div class="pc-bar-row">
            <span class="pc-bar-label">武略</span>
            <div class="oc-bar-wrap"><div class="oc-bar-fill" :style="{ width: prince.martial + '%', background: '#c44b3c' }"></div></div>
            <span>{{ prince.martial }}</span>
          </div>
          <div class="pc-bar-row">
            <span class="pc-bar-label">文治</span>
            <div class="oc-bar-wrap"><div class="oc-bar-fill" :style="{ width: prince.civil + '%', background: '#5b8c5a' }"></div></div>
            <span>{{ prince.civil }}</span>
          </div>
          <div class="pc-bar-row">
            <span class="pc-bar-label">魅力</span>
            <div class="oc-bar-wrap"><div class="oc-bar-fill" :style="{ width: prince.charisma + '%', background: '#9b59b6' }"></div></div>
            <span>{{ prince.charisma }}</span>
          </div>
        </div>
        <!-- 展开详情 + 操作 -->
        <div v-if="selectedPrince?.name === prince.name" class="pc-detail">
          <div class="kv-row small"><span class="kv-label">资质</span><span class="kv-value">{{ prince.talent || '中人之资' }}</span></div>
          <div class="kv-row small"><span class="kv-label">野心</span><span class="kv-value">{{ prince.ambition || '低' }}</span></div>
          <div class="kv-divider"></div>
          <div class="pc-actions">
            <button v-if="prince.status !== '世子' && prince.age >= 12"
              v-audio class="btn-tiny" @click.stop="appointHeir(prince)">
              👑 立为世子
            </button>
            <button v-if="prince.age >= 16" v-audio class="btn-tiny" @click.stop="sendPrinceToTerritory(prince)">
              🏰 出镇地方
            </button>
            <button v-if="prince.age >= 14" v-audio class="btn-tiny" @click.stop="educatePrince(prince)" :disabled="(playerFaction?.treasury || 0) < 200">
              📚 延师教导 (200银)
            </button>
            <button v-if="prince.age >= 16" v-audio class="btn-tiny" @click.stop="marryPrince(prince)" :disabled="(playerFaction?.treasury || 0) < 300">
              💒 联姻 (300银)
            </button>
          </div>
          <div v-if="princeActionLoading" class="hint-text">处理中...</div>
          <div v-if="princeActionResult" class="prince-result" :class="princeActionResult.success ? 'good-text' : 'danger-text'">
            {{ princeActionResult.message }}
          </div>
        </div>
      </div>
      <div class="kv-divider"></div>
      <div class="action-btns">
        <button v-audio class="btn-small" @click="store.togglePanel('moveCapital')">🏛 迁都</button>
        <button v-audio class="btn-small" @click="doSacrifice" :disabled="(playerFaction?.treasury || 0) < 500">🙏 祭祀</button>
        <button v-audio class="btn-small" @click="spawnNewPrince" :disabled="(playerFaction?.treasury || 0) < 800">
          👶 纳妃求嗣 (800银)
        </button>
      </div>
      <p class="hint-text" style="margin-top:12px;">皇子可出镇地方、联姻外交或入朝参政。册立世子可稳固国本，未立世子则可能引发夺嫡之争。君主年迈而无嗣，则社稷危矣。</p>
    </div>
  </div>

  <!-- 纳妃求嗣 - 历史/自定义姓名选择对话框 -->
  <Teleport to="body">
    <div v-if="showSpawnPrinceDialog" class="modal-overlay" @click.self="showSpawnPrinceDialog = false">
      <div class="spawn-prince-dialog animate-fade-in artifact-panel artifact-personnel">
        <div class="fp-header">
          <h3>👶 纳妃求嗣</h3>
          <button class="fp-close" @click="showSpawnPrinceDialog = false">✕</button>
        </div>
        <div class="fp-body">
          <p class="hint-text" style="margin-bottom:12px;">为新皇子赐名。可选择符合史实的历史皇子，亦可自取嘉名。</p>
          <div class="kv-divider"></div>

          <!-- 选项卡 -->
          <div class="spawn-tabs">
            <button class="spawn-tab" :class="{ active: spawnMode === 'historical' }" @click="spawnMode = 'historical'">📜 历史皇子</button>
            <button class="spawn-tab" :class="{ active: spawnMode === 'custom' }" @click="spawnMode = 'custom'">✏️ 自定义姓名</button>
          </div>

          <!-- 历史皇子列表 -->
          <div v-if="spawnMode === 'historical'" class="spawn-historical">
            <div v-if="historicalChildrenLoading" class="hint-text">加载中...</div>
            <div v-if="!historicalChildrenLoading && historicalChildren.length === 0" class="empty-note">
              <p>该势力暂无更多可用的历史皇子。</p>
              <p class="hint-text">可切换至「自定义姓名」标签自行取名。</p>
            </div>
            <div v-for="child in historicalChildren" :key="child.name"
              class="prince-option" :class="{ selected: selectedHistoricalChild?.name === child.name }"
              @click="selectedHistoricalChild = child">
              <div class="po-header">
                <span class="po-name">{{ child.name }}</span>
                <span class="po-year" v-if="child.birth_year">{{ child.birth_year }}年</span>
                <span class="po-available" v-if="!child.available_now" style="color:#c44b3c;">（尚未至出生年）</span>
              </div>
              <div class="po-meta">
                <span class="po-talent">资质：{{ child.talent }}</span>
                <span class="po-note" v-if="child.note">{{ child.note }}</span>
              </div>
            </div>
          </div>

          <!-- 自定义姓名 -->
          <div v-if="spawnMode === 'custom'" class="spawn-custom">
            <label class="custom-name-label">皇子姓名：</label>
            <input v-model="customPrinceName" class="custom-name-input"
              placeholder="请输入皇子姓名（2-6字）" maxlength="6"
              @keyup.enter="confirmSpawnPrince" />
            <p class="hint-text" style="margin-top:8px;">建议使用有美好寓意的字词，如：承乾、怀瑾、守仁等。</p>
          </div>

          <div class="kv-divider"></div>
          <div class="spawn-actions">
            <button class="btn-small" @click="showSpawnPrinceDialog = false">取消</button>
            <button class="btn-small btn-primary" @click="confirmSpawnPrince"
              :disabled="spawnMode === 'historical' ? !selectedHistoricalChild : !customPrinceName.trim()">
              👶 确认纳妃 (800银)
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- 疲病伤病面板 -->
  <div v-if="store.activePanel === 'medical'" class="float-panel animate-fade-in artifact-panel artifact-personnel" style="top:var(--panel-top);left:var(--panel-offset-left);width:400px;max-height:70vh;">
    <div class="fp-header">
      <h3>{{ getPanelTitle('medical') }}</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('medical')">✕</button>
    </div>
    <div class="fp-body" style="max-height:58vh;overflow-y:auto;">
      <!-- 健康统计 -->
      <div class="medical-stats">
        <div class="mstat">
          <span class="mstat-val good-text">{{ medicalInfo.clinics }}</span>
          <span class="mstat-lbl">医馆</span>
        </div>
        <div class="mstat">
          <span class="mstat-val" :class="medicalInfo.plagueRisk > 30 ? 'danger-text' : ''">{{ medicalInfo.plagueRisk }}%</span>
          <span class="mstat-lbl">瘟疫风险</span>
        </div>
        <div class="mstat">
          <span class="mstat-val">{{ medicalInfo.injuryRate }}%</span>
          <span class="mstat-lbl">伤病率</span>
        </div>
        <div class="mstat">
          <span class="mstat-val">{{ formatNum(medicalInfo.injuredPop) }}</span>
          <span class="mstat-lbl">伤病人口</span>
        </div>
      </div>
      <div class="kv-divider"></div>
      <!-- 灾害影响 -->
      <div class="kv-row"><span class="kv-label">灾厄指数</span><span class="kv-value" :class="medicalInfo.disasterIndex > 40 ? 'danger-text' : ''">{{ medicalInfo.disasterIndex }}</span></div>
      <div class="kv-row"><span class="kv-label">当前灾害</span><span class="kv-value">{{ medicalInfo.activeDisasters.join('、') || '无' }}</span></div>
      <div class="kv-divider"></div>
      <!-- 各地诊所一览（可交互） -->
      <h4 class="section-subtitle">🏥 各地诊所</h4>
      <div v-if="clinicTiles.length === 0" class="empty-note">
        <p>暂无医馆，可前往营造司建造。</p>
        <button v-audio class="btn-small" @click="store.togglePanel('construction')">🏗 建造医馆</button>
      </div>
      <div v-for="tile in clinicTiles" :key="tile.tile_id" class="clinic-card">
        <div class="cc-header">
          <span class="cc-name">{{ tile.tile_name || tile.tile_id }}</span>
          <span class="cc-level">医馆 Lv.{{ tile.clinic_level || 1 }}</span>
        </div>
        <div class="cc-stats">
          <span>防疫效果：{{ (tile.clinic_level || 1) * 8 }}%</span>
          <span>治疗容量：{{ (tile.clinic_level || 1) * 500 }}人</span>
        </div>
        <div class="cc-info" v-if="tile.disasters?.length">
          <span class="warn-text">⚠ 当前灾害：{{ Array.isArray(tile.disasters) ? tile.disasters.join('、') : tile.disasters }}</span>
        </div>
        <div class="cc-actions">
          <button v-audio class="btn-tiny" @click="upgradeClinic(tile)" :disabled="(playerFaction?.treasury || 0) < getClinicUpgradeCost(tile)">
            ⬆ 升级 ({{ getClinicUpgradeCost(tile) }}银)
          </button>
          <button v-audio class="btn-tiny" @click="treatInjured(tile)" :disabled="(playerFaction?.treasury || 0) < 150">
            💊 施药 (150银)
          </button>
        </div>
      </div>
      <div class="kv-divider"></div>
      <div class="action-btns">
        <button v-audio class="btn-small" @click="store.togglePanel('construction')">🏥 建造医馆</button>
        <button v-audio class="btn-small" @click="doSacrifice" :disabled="(playerFaction?.treasury || 0) < 500">🙏 祭祀消灾</button>
        <button v-audio class="btn-small" @click="store.togglePanel('disaster')">⚠ 查看灾异</button>
      </div>
      <p class="hint-text" style="margin-top:12px;">建造医馆可降低瘟疫风险。瘟疫爆发时将大幅减少人口与士气。及时赈灾可控制疫情蔓延。夏季瘟疫风险显著提高。</p>
    </div>
  </div>

  <!-- 海策远洋面板 -->
  <div v-if="store.activePanel === 'sea'" class="float-panel animate-fade-in artifact-panel artifact-codex" style="top:var(--panel-top);left:var(--panel-offset-left);width:420px;max-height:72vh;">
    <div class="fp-header">
      <h3>{{ getPanelTitle('sea') }}</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('sea')">✕</button>
    </div>
    <div class="fp-body" style="max-height:58vh;overflow-y:auto;">
      <!-- 海运统计 -->
      <div class="sea-summary-cards">
        <div class="ssc-card">
          <div class="ssc-val">{{ seaInfo.ports }}</div>
          <div class="ssc-lbl">港口</div>
        </div>
        <div class="ssc-card">
          <div class="ssc-val">{{ seaInfo.fleetSize }}</div>
          <div class="ssc-lbl">舰船</div>
        </div>
        <div class="ssc-card gold-bg">
          <div class="ssc-val gold-text">+{{ formatNum(seaInfo.tradeIncome) }}</div>
          <div class="ssc-lbl">贸易/回合</div>
        </div>
        <div class="ssc-card">
          <div class="ssc-val">{{ seaInfo.routes }}</div>
          <div class="ssc-lbl">航线</div>
        </div>
      </div>
      <div class="kv-divider"></div>
      <!-- 港口列表（可交互） -->
      <h4 class="section-subtitle">⚓ 港口详情</h4>
      <div v-if="getPortTiles().length === 0" class="empty-note">
        <p>暂无港口。占领沿海地块后可建造港口设施。</p>
        <button v-audio class="btn-small" @click="store.togglePanel('construction')">🏗 前往营造</button>
      </div>
      <div v-for="port in getPortTiles()" :key="port.tile_id" class="port-card" :class="{ expanded: selectedPort?.tile_id === port.tile_id }" @click="selectPortTile(port)">
        <div class="pc-header">
          <span class="pc-name">⚓ {{ port.tile_name || port.tile_id }}</span>
          <span class="pc-ships">{{ port.ships || port.fleet_size || 3 }}艘</span>
          <span class="pc-expand">{{ selectedPort?.tile_id === port.tile_id ? '▾' : '▸' }}</span>
        </div>
        <div class="port-stats">
          <span>贸易收入：+{{ port.trade_income || 80 }}银/回合</span>
          <span>船坞等级：Lv.{{ port.shipyard_level || 1 }}</span>
        </div>
        <!-- 展开详情 -->
        <div v-if="selectedPort?.tile_id === port.tile_id" class="port-detail">
          <div class="kv-row small"><span class="kv-label">人口</span><span class="kv-value">{{ formatNum(port.population || 0) }}</span></div>
          <div class="kv-row small"><span class="kv-label">航线</span><span class="kv-value">{{ port.routes || 1 }}条</span></div>
          <div class="kv-divider"></div>
          <div class="port-actions">
            <button v-audio class="btn-tiny" @click.stop="buildShip(port)" :disabled="(playerFaction?.treasury || 0) < 200">
              🚢 造舰 (200银)
            </button>
            <button v-audio class="btn-tiny" @click.stop="upgradeShipyard(port)" :disabled="(playerFaction?.treasury || 0) < 400">
              ⬆ 升级船坞 (400银)
            </button>
            <button v-audio class="btn-tiny" @click.stop="openTradeRoute(port)" :disabled="(playerFaction?.treasury || 0) < 300">
              🗺️ 开辟航线 (300银)
            </button>
            <button v-audio class="btn-tiny" @click.stop="navalPatrol(port)">
              🛡️ 水师巡航
            </button>
          </div>
        </div>
      </div>
      <div class="kv-divider"></div>
      <div class="action-btns">
        <button v-audio class="btn-small" @click="store.togglePanel('construction')">⚓ 建造港口</button>
        <button v-audio class="btn-small" @click="store.togglePanel('diplomacy')">📦 开拓贸易</button>
      </div>
      <p class="hint-text" style="margin-top:12px;">发展海运可开辟贸易路线，获取海外奇珍异宝。占领港口地块后可建造船坞，训练水师。夏季海运繁忙，冬季海路不畅。</p>
    </div>
  </div>

  <!-- 民俗国史面板 -->
  <div v-if="store.activePanel === 'culture'" class="float-panel animate-fade-in artifact-panel artifact-codex" style="top:var(--panel-top);left:var(--panel-offset-left);width:400px;max-height:72vh;">
    <div class="fp-header">
      <h3>{{ getPanelTitle('culture') }}</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('culture')">✕</button>
    </div>
    <div class="fp-body" style="max-height:58vh;overflow-y:auto;">
      <!-- 国朝纪年 -->
      <div class="culture-era-card">
        <div class="era-main">
          <span class="era-name gold-text">{{ cultureInfo.eraName }}</span>
          <span class="era-year">{{ cultureInfo.year }}</span>
        </div>
        <div class="culture-stats">
          <div class="cstat"><span class="cstat-val">{{ cultureInfo.historyCount }}</span><span class="cstat-lbl">国史</span></div>
          <div class="cstat"><span class="cstat-val">{{ cultureInfo.decreesCount }}</span><span class="cstat-lbl">敕令</span></div>
          <div class="cstat"><span class="cstat-val">{{ cultureInfo.battlesCount }}</span><span class="cstat-lbl">战役</span></div>
        </div>
      </div>
      <div class="kv-divider"></div>
      <!-- 近期大事（可点击查看详情） -->
      <h4 class="section-subtitle">📜 近期大事</h4>
      <div v-if="cultureInfo.recentEvents.length === 0" class="empty-note">暂无记录，天下初定...</div>
      <div v-for="(evt, i) in cultureInfo.recentEvents" :key="i" class="event-item-mini culture-event" @click="viewEventDetail(evt)">
        <span class="event-round">[{{ evt.round }}]</span>
        <span class="event-cat" v-if="evt.category">[{{ evt.category }}]</span>
        <span>{{ evt.title }}</span>
        <span class="event-expand">▸</span>
      </div>
      <!-- 事件详情弹出 -->
      <div v-if="viewedEvent" class="event-detail-popup">
        <div class="edp-header">
          <span class="edp-title">{{ viewedEvent.title }}</span>
          <button class="btn-tiny" @click="viewedEvent = null">✕</button>
        </div>
        <div class="edp-body">
          <div class="kv-row small"><span class="kv-label">回合</span><span class="kv-value">{{ viewedEvent.round }}</span></div>
          <div class="kv-row small" v-if="viewedEvent.category"><span class="kv-label">类型</span><span class="kv-value">{{ viewedEvent.category }}</span></div>
          <div class="kv-row small" v-if="viewedEvent.description"><span class="kv-label">详情</span><span class="kv-value">{{ viewedEvent.description }}</span></div>
          <div class="kv-row small" v-if="viewedEvent.narrative"><span class="kv-label">记载</span><span class="kv-value dim-text">{{ viewedEvent.narrative }}</span></div>
        </div>
      </div>
      <div class="kv-divider"></div>
      <!-- 修史功能 -->
      <h4 class="section-subtitle">✍️ 御批修史</h4>
      <textarea v-model="chronicleText" class="decree-input" rows="2" placeholder="撰写国史纪事...（例：是岁，我军大破陈友定于福州）"></textarea>
      <div class="chronicle-actions">
        <button v-audio class="btn-small" @click="writeChronicle" :disabled="!chronicleText.trim() || chronicleWriting">
          {{ chronicleWriting ? '撰写中...' : '📝 载入国史' }}
        </button>
        <button v-audio class="btn-small" @click="changeEraName">🏷️ 改元</button>
      </div>
      <p class="hint-text" style="margin-top:12px;">重大战役、外交事件、天灾祥瑞将被载入国史。统一天下后将生成完整朝代传记。每12回合自动撰写一次国史纪事。</p>
    </div>
  </div>

  <!-- 音效设置面板 -->
  <div v-if="store.activePanel === 'audio'" class="float-panel animate-fade-in artifact-panel artifact-memorial" style="top:var(--panel-top);left:var(--panel-offset-left);width:340px;">
    <div class="fp-header">
      <h3>🎵 音效设置</h3>
      <button v-audio class="fp-close" @click="store.togglePanel('audio')">✕</button>
    </div>
    <div class="fp-body">
      <!-- 全局静音 -->
      <div class="kv-row">
        <span class="kv-label">全局静音</span>
        <span class="kv-value">
          <button class="audio-btn" :class="{ active: !audioSettings.muted }" @click="toggleMuteAll">
            {{ audioSettings.muted ? '🔇 已静音' : '🔊 正常' }}
          </button>
        </span>
      </div>
      <div class="kv-divider"></div>
      <!-- 独立音量 -->
      <div class="audio-vol-row">
        <span class="audio-vol-label">主音量</span>
        <input type="range" min="0" max="100" v-model.number="audioSettings.masterVolume" class="audio-slider" @input="onMasterVolumeChange" />
        <span class="audio-vol-pct">{{ audioSettings.masterVolume }}%</span>
      </div>
      <div class="audio-vol-row">
        <span class="audio-vol-label">BGM</span>
        <input type="range" min="0" max="100" v-model.number="audioSettings.bgmVolume" class="audio-slider" @input="onBgmVolumeChange" />
        <span class="audio-vol-pct">{{ audioSettings.bgmVolume }}%</span>
      </div>
      <div class="audio-vol-row">
        <span class="audio-vol-label">音效</span>
        <input type="range" min="0" max="100" v-model.number="audioSettings.sfxVolume" class="audio-slider" @input="onSfxVolumeChange" />
        <span class="audio-vol-pct">{{ audioSettings.sfxVolume }}%</span>
      </div>
      <div class="audio-vol-row">
        <span class="audio-vol-label">配音</span>
        <input type="range" min="0" max="100" v-model.number="audioSettings.voiceVolume" class="audio-slider" @input="onVoiceVolumeChange" />
        <span class="audio-vol-pct">{{ audioSettings.voiceVolume }}%</span>
      </div>
      <div class="kv-divider"></div>
      <!-- BGM 开关 + 状态 -->
      <div class="kv-row">
        <span class="kv-label">BGM 开关</span>
        <span class="kv-value">
          <button class="audio-btn" :class="{ active: audioSettings.bgmOn }" @click="toggleAudio('bgm')">
            {{ audioSettings.bgmOn ? '开启' : '关闭' }}
          </button>
        </span>
      </div>
      <div class="audio-status">
        <span class="audio-status-label">当前曲目</span>
        <span class="audio-status-value dim-text">{{ currentBgmName || '无' }}</span>
      </div>
      <!-- 曲目列表 -->
      <div class="bgm-track-list">
        <div
          v-for="t in bgmTracks"
          :key="t.id"
          class="bgm-track-item"
          :class="{ active: t.id === currentBgmId }"
          @click="switchBgmTrack(t.id)"
        >
          <span class="bgm-track-icon">{{ t.id === currentBgmId ? '▶' : '○' }}</span>
          <span class="bgm-track-name">{{ t.name }}</span>
          <span class="bgm-track-tag">{{ t.id === 'main_menu' ? '菜单' : t.id === 'gameplay' ? '对局' : t.id === 'war_drums' ? '战斗' : t.id === 'court_music' ? '朝堂' : '通用' }}</span>
        </div>
      </div>
      <!-- 播放控制 -->
      <div class="audio-controls">
        <button v-audio class="btn-small" @click="toggleBgmPlay">{{ audioSettings.bgmOn ? '⏸ 暂停' : '▶ 播放' }}</button>
        <button v-audio class="btn-small" @click="playNextBgm">⏭ 随机</button>
      </div>
    </div>
  </div>

  <!-- AI智能体监控面板 -->
  <div v-if="store.activePanel === 'agent'" class="float-panel animate-fade-in artifact-panel artifact-secret" style="top:var(--panel-top);left:var(--panel-offset-left);width:480px;">
    <div class="fp-header">
      <h3>🧠 AI智能体中枢</h3>
      <div class="fp-header-actions">
        <button class="btn-tiny" @click="refreshAgentDashboard" :disabled="agentLoading" title="刷新">
          {{ agentLoading ? '刷新中...' : '🔄 刷新' }}
        </button>
        <button v-audio class="fp-close" @click="store.togglePanel('agent')">✕</button>
      </div>
    </div>
    <div class="fp-body" style="max-height:500px;overflow-y:auto;">
      <div v-if="agentLoading && !agentDashboard" class="hint-text">加载中...</div>
      <template v-else-if="agentDashboard">
        <!-- 全局统计 -->
        <div class="agent-stats-row">
          <div class="agent-stat-card" :class="{ warn: agentDashboard.global_stats.degraded_agents > 0 }">
            <div class="agent-stat-val">{{ agentDashboard.ai_available ? '在线' : '离线' }}</div>
            <div class="agent-stat-label">AI状态</div>
          </div>
          <div class="agent-stat-card">
            <div class="agent-stat-val">{{ agentDashboard.global_stats.total_calls }}</div>
            <div class="agent-stat-label">总调用次数</div>
          </div>
          <div class="agent-stat-card">
            <div class="agent-stat-val">{{ agentDashboard.global_stats.avg_latency }}s</div>
            <div class="agent-stat-label">平均延迟</div>
          </div>
          <div class="agent-stat-card">
            <div class="agent-stat-val">{{ agentDashboard.global_stats.active_agents }}/{{ agentDashboard.agents.length }}</div>
            <div class="agent-stat-label">活跃智能体</div>
          </div>
        </div>

        <!-- 智能体列表 -->
        <div class="agent-list-title">智能体 (A1~A8)</div>
        <div class="agent-list">
          <div v-for="ag in agentDashboard.agents" :key="ag.key" class="agent-card" :class="{ degraded: ag.circuit_state === 'OPEN', disabled: !ag.alive }">
            <div class="agent-card-header">
              <span class="agent-key">{{ ag.key }}</span>
              <span class="agent-name">{{ ag.name }}</span>
              <span class="agent-model" :title="'模型分组: ' + ag.model_group">{{ ag.model_group }}</span>
              <span class="agent-trigger-badge" :class="ag.trigger">{{ ag.trigger === 'auto' ? '自动' : ag.trigger === 'manual' ? '手动' : '双向' }}</span>
            </div>
            <div class="agent-card-body">
              <span class="agent-desc">{{ ag.description }}</span>
            </div>
            <div class="agent-card-stats" v-if="ag.call_count !== undefined">
              <span :class="'agent-circuit ' + (ag.circuit_state || 'CLOSED')">{{ ag.circuit_state || 'CLOSED' }}</span>
              <span>调用: {{ ag.call_count }}</span>
              <span>延迟: {{ ag.avg_latency || 0 }}s</span>
              <span v-if="ag.memories">记忆: {{ (ag.memories.short_term || 0) + (ag.memories.mid_term || 0) + (ag.memories.long_term || 0) }}条</span>
            </div>
          </div>
        </div>

        <!-- 事件总线 -->
        <div class="agent-section-title">事件总线</div>
        <div class="kv-row">
          <span class="kv-label">待处理事件</span>
          <span class="kv-value">{{ agentDashboard.event_bus.pending_events }}</span>
        </div>
        <div class="kv-row">
          <span class="kv-label">归档事件</span>
          <span class="kv-value">{{ agentDashboard.event_bus.archived_events }}</span>
        </div>

        <!-- 圣旨统计 -->
        <div class="agent-section-title">圣旨统计</div>
        <div class="kv-row">
          <span class="kv-label">已颁圣旨</span>
          <span class="kv-value">{{ agentDashboard.edict_stats.total_decrees }} 道</span>
        </div>
        <div class="kv-row">
          <span class="kv-label">可用操作</span>
          <span class="kv-value">{{ agentDashboard.edict_action_count }} 种</span>
        </div>
        <div v-for="(ed, i) in agentDashboard.edict_stats.last_edicts" :key="'ed-'+i" class="agent-edict-item">
          <span class="agent-edict-round">回合{{ ed.round }}</span>
          <span class="agent-edict-text">{{ ed.text }}</span>
          <span class="agent-edict-result" :class="{ fail: ed.failed > 0 }">{{ ed.executed }}/{{ ed.executed + ed.failed }}</span>
        </div>
      </template>
      <div v-else class="hint-text">点击刷新加载智能体状态</div>
    </div>
  </div>

  <!-- 领土面板 -->
  <div v-if="store.activePanel === 'territory'" class="float-panel animate-fade-in artifact-panel artifact-codex" style="top:var(--panel-top);left:var(--panel-offset-left);width:520px;max-height:82vh;">
    <div class="fp-header">
      <h3>🗺️ 山河舆图</h3>
      <div class="fp-header-actions">
        <button class="btn-tiny" @click="loadTerritoryData" :disabled="territoryLoading" title="刷新">
          {{ territoryLoading ? '加载中...' : '🔄 刷新' }}
        </button>
        <button v-audio class="fp-close" @click="store.togglePanel('territory')">✕</button>
      </div>
    </div>

    <!-- Tab 切换 -->
    <div class="territory-tabs">
      <button class="territory-tab" :class="{ active: territoryTab === 'overview' }" @click="territoryTab = 'overview'">总览</button>
      <button class="territory-tab" :class="{ active: territoryTab === 'regions' }" @click="territoryTab = 'regions'">地区</button>
      <button class="territory-tab" :class="{ active: territoryTab === 'changes' }" @click="territoryTab = 'changes'">变更</button>
      <button class="territory-tab" :class="{ active: territoryTab === 'factions' }" @click="territoryTab = 'factions'">群雄</button>
    </div>

    <div class="fp-body" style="max-height:62vh;overflow-y:auto;">

      <!-- ========== Tab: 总览 ========== -->
      <template v-if="territoryTab === 'overview'">
        <div v-if="territoryLoading" class="hint-text">加载中...</div>
        <template v-else-if="territorySummary">
          <!-- 国势概览 -->
          <div class="territory-stat-cards">
            <div class="territory-stat-card">
              <div class="tsc-val">{{ territorySummary.total_tiles }}</div>
              <div class="tsc-label">领地</div>
            </div>
            <div class="territory-stat-card">
              <div class="tsc-val">{{ formatNum(territorySummary.total_population) }}</div>
              <div class="tsc-label">总人口</div>
            </div>
            <div class="territory-stat-card">
              <div class="tsc-val">{{ formatNum(territorySummary.total_troops) }}</div>
              <div class="tsc-label">驻军</div>
            </div>
            <div class="territory-stat-card">
              <div class="tsc-val">{{ Object.keys(territorySummary.regions || {}).length }}</div>
              <div class="tsc-label">地区</div>
            </div>
          </div>

          <!-- 都城 -->
          <div class="territory-section" v-if="territorySummary.capital">
            <div class="territory-section-title">🏰 都城</div>
            <div class="capital-card">
              <span class="capital-name">{{ territorySummary.capital.tile_name }}</span>
              <span class="capital-id">{{ territorySummary.capital.tile_id }}</span>
            </div>
          </div>

          <!-- 边防 -->
          <div class="territory-section" v-if="borderInfo.length">
            <div class="territory-section-title">⚔️ 边境接壤</div>
            <div class="border-list">
              <div v-for="b in borderInfo" :key="b.faction_id" class="border-item" :style="{ borderLeftColor: b.color }">
                <span class="border-faction" :style="{ color: b.color }">{{ b.name }}</span>
                <span class="border-count">{{ b.borderTiles }} 处接壤</span>
              </div>
            </div>
          </div>

          <!-- 最近变更摘要 -->
          <div class="territory-section" v-if="territorySummary.recent_changes?.length">
            <div class="territory-section-title">📜 近日变迁</div>
            <div v-for="(c, i) in territorySummary.recent_changes.slice(-5).reverse()" :key="i" class="change-item">
              <span class="change-round">回{{ c.round }}</span>
              <span class="change-tile">{{ c.tile_name || c.tile_id }}</span>
              <span class="change-arrow">→</span>
              <span class="change-result" :class="c.new_faction_id === store.playerFactionId ? 'gained' : 'lost'">
                {{ c.narrative || (c.new_faction_id === store.playerFactionId ? '收复' : '失陷') }}
              </span>
            </div>
          </div>
        </template>
        <div v-else class="hint-text">暂无领土数据，请点击刷新加载</div>
      </template>

      <!-- ========== Tab: 地区分布 ========== -->
      <template v-if="territoryTab === 'regions'">
        <div v-if="territorySummary?.regions" class="regions-list">
          <div v-for="(tiles, regionName) in sortedRegions" :key="regionName" class="region-group">
            <div class="region-header" @click="toggleRegion(regionName)">
              <span class="region-arrow" :class="{ expanded: expandedRegions[regionName] }">▶</span>
              <span class="region-name">{{ regionName }}</span>
              <span class="region-count">{{ tiles.length }} 地</span>
              <span class="region-pop">人口 {{ formatNum(regionPopSum(tiles)) }}</span>
            </div>
            <div v-if="expandedRegions[regionName]" class="region-tiles">
              <div v-for="tile in tiles" :key="tile.tile_id" class="region-tile" :class="{ capital: tile.is_capital }">
                <span class="rt-icon">{{ tile.is_capital ? '🏰' : tile.tile_type === 'pass' ? '⛰' : tile.tile_type === 'port' ? '⚓' : '▫' }}</span>
                <span class="rt-name">{{ tile.tile_name }}</span>
                <span class="rt-type">{{ tileTypeLabel(tile.tile_type) }}</span>
                <span class="rt-troops" v-if="tile.troops > 0">兵{{ formatNum(tile.troops) }}</span>
                <span class="rt-fort" v-if="tile.fortification > 0">防{{ tile.fortification }}</span>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="hint-text">暂无地区数据</div>
      </template>

      <!-- ========== Tab: 地盘变更 ========== -->
      <template v-if="territoryTab === 'changes'">
        <div v-if="territoryChanges" class="changes-summary">
          <div class="changes-counts">
            <span class="cc-gained">获得 {{ territoryChanges.gained }} 地</span>
            <span class="cc-lost">失去 {{ territoryChanges.lost }} 地</span>
            <span class="cc-total">共 {{ territoryChanges.total_changes }} 次变更</span>
          </div>
        </div>
        <div v-if="territoryChanges?.changes?.length" class="changes-list">
          <div v-for="c in territoryChanges.changes" :key="c.change_id || c.tile_id + c.round" class="change-record">
            <div class="cr-header">
              <span class="cr-round">第 {{ c.round }} 回合</span>
              <span class="cr-type" :class="c.change_type">{{ changeTypeLabel(c.change_type) }}</span>
            </div>
            <div class="cr-body">
              <span class="cr-tile">{{ c.tile_name || c.tile_id }}</span>
              <template v-if="c.new_faction_id === store.playerFactionId">
                <span class="cr-arrow gained">收复</span>
              </template>
              <template v-else-if="c.old_faction_id === store.playerFactionId">
                <span class="cr-arrow lost">失陷</span>
              </template>
              <template v-else>
                <span class="cr-arrow neutral">易主</span>
              </template>
            </div>
            <div class="cr-narrative" v-if="c.narrative">{{ c.narrative }}</div>
          </div>
        </div>
        <div v-else-if="!territoryLoading" class="hint-text">暂无地盘变更记录</div>
      </template>

      <!-- ========== Tab: 群雄对比 ========== -->
      <template v-if="territoryTab === 'factions'">
        <div class="faction-territory-list">
          <div
            v-for="f in sortedFactionsByTiles"
            :key="f.faction_id"
            class="ft-item"
            :class="{ 'is-player': f.faction_id === store.playerFactionId }"
            :style="{ borderLeftColor: f.color }"
          >
            <div class="ft-rank">{{ f.rank }}</div>
            <div class="ft-info">
              <div class="ft-name" :style="{ color: f.color }">{{ f.name }}</div>
              <div class="ft-stats">
                <span class="ft-tiles">{{ f.tile_count || 0 }} 地</span>
                <span class="ft-troops">兵 {{ formatNum(f.total_troops || 0) }}</span>
              </div>
            </div>
            <!-- 领地占比条 -->
            <div class="ft-bar-wrap">
              <div class="ft-bar" :style="{ width: f.tilePercent + '%', background: f.color }"></div>
            </div>
          </div>
        </div>
      </template>

    </div>
  </div>
  </div>

  <!-- AI增强模块：势力关系网络 -->
  <FactionNetworkPanel v-if="store.activePanel === 'faction_network'" />
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import FactionNetworkPanel from '@/components/FactionNetworkPanel.vue'

const props = defineProps<{
  panelSide?: string
}>()
const emit = defineEmits<{
  (e: 'openDiplomacyDeep'): void
  (e: 'openTalentMarket'): void
}>()

const panelGroupClass = computed(() => {
  const side = props.panelSide || 'left'
  return `fp-side-${side}`
})
import * as API from '@/services/api'
import { apiClient, strategyAnalyze, getFactionPrisoners, checkVassalRebellion, getFactionOfficials, appointOfficial as apiAppointOfficial, dismissOfficial as apiDismissOfficial, executeOfficial as apiExecuteOfficial, unlockPolicy as apiUnlockPolicy, issueDecree as apiIssueDecree, getRoyalPanel, getHistoricalChildren, getMedicalPanel, getSeaPanel, getCulturePanel, getWeather, showToast, listRebels, suppressRebellion, attemptAmbush, raidSupplyLine, borderRaid, annexVassal, sendHostage, recallHostage, moveCapital, performSacrifice, recruitOfficials, getCapitalCandidates, getCapitalHistory } from '@/services/api'
import { useFormat } from '@/composables/useFormat'
import { audioManager } from '@/utils/audioManager'

const store = useGameStore()
const { formatNum } = useFormat()

// ========== 领土面板 ==========
const territoryTab = ref('overview')
const territoryLoading = ref(false)
const territorySummary = ref<any>(null)
const territoryChanges = ref<any>(null)
const expandedRegions = ref<Record<string, boolean>>({})

async function loadTerritoryData() {
  territoryLoading.value = true
  try {
    const [summary, changes] = await Promise.all([
      API.getTerritorySummary(store.playerFactionId).catch(() => null),
      API.getTerritoryChanges(store.playerFactionId, 30).catch(() => null),
    ])
    if (summary) territorySummary.value = summary
    if (changes) territoryChanges.value = changes
  } catch (e) {
    console.warn('[Territory] 加载失败:', e)
  } finally {
    territoryLoading.value = false
  }
}

// 监听面板打开时自动加载
watch(() => store.activePanel, async (panel) => {
  if (panel === 'territory' && store.playerFactionId) {
    await loadTerritoryData()
  }
})

// 地区按瓦片数降序排列
const sortedRegions = computed(() => {
  if (!territorySummary.value?.regions) return {}
  const entries = Object.entries(territorySummary.value.regions) as [string, any[]][]
  entries.sort((a, b) => b[1].length - a[1].length)
  return Object.fromEntries(entries)
})

// 地区人口合计
function regionPopSum(tiles: any[]) {
  return tiles.reduce((s, t) => s + (t.population || 0), 0)
}

// 切换地区展开
function toggleRegion(name: string) {
  expandedRegions.value[name] = !expandedRegions.value[name]
}

// 地形标签
function tileTypeLabel(type: string) {
  const map: Record<string, string> = {
    farmland: '农田', mountain: '山地', water: '水域', coast: '沿海',
    city: '城池', pass: '关隘', port: '港口', desert: '沙漠', grassland: '草原',
  }
  return map[type] || type
}

// 变更类型标签
function changeTypeLabel(type: string) {
  const map: Record<string, string> = {
    conquest: '攻占', fall: '陷落', colonize: '开拓', abandon: '放弃',
    cede: '割让', inherit: '继承', revolt: '叛乱',
  }
  return map[type] || type || '变更'
}

// 边境信息（从 store 中的势力信息推断）
const borderInfo = computed(() => {
  const myId = store.playerFactionId
  const myTiles = store.playerTiles
  if (!myTiles.length) return []
  const result: { faction_id: string; name: string; color: string; borderTiles: number }[] = []
  const neighborIds = new Set<string>()
  for (const t of myTiles) {
    for (const n of store.tileNeighbors[t.tile_id] || []) {
      const neighborTile = store.tiles[n]
      if (neighborTile && neighborTile.faction_id && neighborTile.faction_id !== myId) {
        neighborIds.add(neighborTile.faction_id)
      }
    }
  }
  for (const nid of neighborIds) {
    const f = store.factions[nid]
    if (f) {
      const borderTiles = myTiles.filter(t => {
        return (store.tileNeighbors[t.tile_id] || []).some(n => {
          const nt = store.tiles[n]
          return nt && nt.faction_id === nid
        })
      }).length
      result.push({ faction_id: nid, name: f.name, color: f.color, borderTiles })
    }
  }
  result.sort((a, b) => b.borderTiles - a.borderTiles)
  return result
})

// 群雄按领地排名
const sortedFactionsByTiles = computed(() => {
  const factions = store.livingFactions
  const maxTiles = Math.max(...factions.map(f => f.tile_count || 0), 1)
  const list = factions.map((f, i) => ({
    ...f,
    rank: i + 1,
    tilePercent: ((f.tile_count || 0) / maxTiles) * 100,
  }))
  list.sort((a, b) => (b.tile_count || 0) - (a.tile_count || 0))
  list.forEach((f, i) => { f.rank = i + 1 })
  return list
})

const aiLoading = ref(false)
const aiResult = ref<any>(null)
const workshopData = ref<any>(null)
const prisonerData = ref<any[]>([])
const vassalRisk = ref<number | null>(null)
const vassalChecking = ref(false)
const vassalTributes = ref<Array<{faction_name: string; amount: number}>>([])
const rebelData = ref<any[]>([])
const suppressTroops = ref<Record<string, number>>({})
const suppressing = ref('')
// 工坊交互
const workshopFocus = ref<'arms' | 'gold' | 'grain' | 'balanced'>('balanced')
const workshopFocusResult = ref<{text: string; type: string} | null>(null)
// 律法交互
const lawSelectedPrisoner = ref<any>(null)
const lawActionLoading = ref(false)
const lawActionResult = ref<{text: string; type: string} | null>(null)

// ---- 增强面板交互状态 ----
// 国库：收支明细展开
const treasuryTab = ref<'overview' | 'income' | 'expense'>('overview')
// 人物：选中的官员
const selectedOfficial = ref<any>(null)
// 皇族：皇子列表展开
const royalPrinces = ref<any[]>([])
const selectedPrince = ref<any>(null)
const princeActionLoading = ref(false)
const princeActionResult = ref<any>(null)
// 纳妃求嗣对话框
const showSpawnPrinceDialog = ref(false)
const historicalChildren = ref<any[]>([])
const historicalChildrenLoading = ref(false)
const selectedHistoricalChild = ref<any>(null)
const customPrinceName = ref('')
const spawnMode = ref<'historical' | 'custom'>('historical')
// 疾医：地块诊所列表
const clinicTiles = ref<any[]>([])
// 海策：港口详情展开
const selectedPort = ref<any>(null)
// 灾荒：赈灾/预判
const dRelieving = ref('')
const dReliefResult = ref<any>(null)
const dRelievedId = ref('')
const forecastLoading = ref(false)
const forecastResult = ref('')
// 民俗：修史输入
const chronicleText = ref('')
const chronicleWriting = ref(false)

// P1 高级功能状态
const ambushTarget = ref('')
const ambushTileId = ref('')
const ambushTroops = ref(200)
const ambushing = ref(false)
const raidTarget = ref('')
const raidSupplyTroops = ref(200)
const borderRaidTarget = ref('')
const borderRaidTroops = ref(300)
const raiding = ref(false)
const newCapitalTileId = ref('')
const capitalCandidates = ref<any[]>([])
const capitalCandidatesLoading = ref(false)
const capitalCandidatesData = ref<any>(null)
const capitalMoving = ref(false)
const selectedCandidateId = ref('')
const capitalHistoryData = ref<any>(null)

// 迁都数据加载
async function loadCapitalCandidates() {
  if (!store.playerFactionId) return
  capitalCandidatesLoading.value = true
  try {
    const [candidates, history] = await Promise.all([
      getCapitalCandidates(store.playerFactionId).catch(() => null),
      getCapitalHistory(store.playerFactionId).catch(() => null),
    ])
    if (candidates) {
      capitalCandidatesData.value = candidates
      capitalCandidates.value = candidates?.candidates || []
    }
    if (history) capitalHistoryData.value = history
  } catch (e) {
    console.warn('[Capital] 加载迁都数据失败:', e)
  } finally {
    capitalCandidatesLoading.value = false
  }
}

// 选中候选都城
function selectCandidate(tileId: string) {
  selectedCandidateId.value = tileId
  newCapitalTileId.value = tileId
}

/** 取消迁都选择 → 将迁都意图推送到圣旨台 */
function cancelCapitalSelection() {
  const candidate = selectedCandidate.value
  if (candidate) {
    window.dispatchEvent(new CustomEvent('add-edict-decision', {
      detail: {
        type: 'move_capital',
        label: `迁都至${candidate.tile_name}`,
        content: `迁都至${candidate.tile_name}（评级${candidate.grade}，${candidate.composite_score}分）`,
      }
    }))
  }
  selectedCandidateId.value = ''
  newCapitalTileId.value = ''
}

const selectedCandidate = computed(() => {
  if (!selectedCandidateId.value) return null
  return capitalCandidates.value.find(c => c.tile_id === selectedCandidateId.value) || null
})

const capitalTile = computed(() => {
  const capId = store.playerFaction?.capital_tile || store.playerFaction?.capital
  if (!capId) return null
  return store.playerTiles.find(t => t.tile_id === capId) || null
})

// 六边形轴向坐标邻接判断（与后端 _is_adjacent 一致）
function isAdjacent(tileIdA: string, tileIdB: string): boolean {
  try {
    const partsA = tileIdA.replace('tile_', '').split('_')
    const partsB = tileIdB.replace('tile_', '').split('_')
    if (partsA.length >= 2 && partsB.length >= 2) {
      const qa = parseInt(partsA[0]), ra = parseInt(partsA[1])
      const qb = parseInt(partsB[0]), rb = parseInt(partsB[1])
      const directions = [[1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1]]
      return directions.some(([dq, dr]) => (qa - qb) === dq && (ra - rb) === dr)
    }
  } catch { /* ignore */ }
  return false
}

// 伏击可选地点：全图山地/关隘中，与目标势力邻接的地块
const ambushTiles = computed(() => {
  if (!ambushTarget.value) return []
  const allTiles = Object.values(store.tiles)
  // 目标势力控制的地块
  const targetTileIds = new Set(
    allTiles.filter(t => t.faction_id === ambushTarget.value).map(t => t.tile_id)
  )
  if (targetTileIds.size === 0) return []
  // 全图中山地/关隘，且与目标地块邻接
  return allTiles.filter(t => {
    if (t.tile_type !== 'mountain' && t.tile_type !== 'pass') return false
    return [...targetTileIds].some(tid => isAdjacent(t.tile_id, tid))
  })
})

// 劫掠粮道：预估成功率（前端计算，与实际后端公式对应）
const estimatedRaidChance = computed(() => {
  if (!raidTarget.value || raidSupplyTroops.value < 100) return 0
  const targetFaction = store.livingFactions.find(f => f.faction_id === raidTarget.value)
  const playerFaction = store.playerFaction
  if (!targetFaction || !playerFaction) return 0

  // 兵力因素
  const targetTroops = targetFaction.total_troops > 0 ? targetFaction.total_troops : 1
  const troopRatio = raidSupplyTroops.value / Math.max(targetTroops, 1)
  let chance = Math.min(0.70, 0.30 + troopRatio * 0.40)

  // 情报加成
  const intelVisible = store.isFactionIntelVisible?.(raidTarget.value) ?? false
  const infiltration = store.getFactionInfiltration?.(raidTarget.value) ?? 0
  if (intelVisible || infiltration >= 10) {
    chance = Math.min(0.85, chance + 0.15)
  }

  // 敌方防御修正
  const defensePenalty = Math.min(0.15, targetTroops / Math.max(playerFaction.total_troops, 1) * 0.10)
  chance = Math.max(0.15, chance - defensePenalty)

  return Math.round(chance * 100) / 100
})

// 劫掠粮道：情报来源提示
const raidIntelHint = computed(() => {
  if (!raidTarget.value) return ''
  const intelVisible = store.isFactionIntelVisible?.(raidTarget.value) ?? false
  const infiltration = store.getFactionInfiltration?.(raidTarget.value) ?? 0
  if (intelVisible) return '已有细作情报，成功率提升'
  if (infiltration >= 10) return `细作网络渗透中(渗透度${infiltration})，成功率提升`
  return '无细作情报，建议先刺探'
})

// 劫掠粮道：预估好感度影响
const estimatedRelationPenalty = computed(() => {
  if (!raidTarget.value) return null
  // 失败时大约 15~30，给个中位数
  return 22
})
const spyFeedback = ref<{ text: string; type: string }>({ text: '', type: 'success' })

// 细作行动类型映射
const spyActionMap: Record<string, string> = {
  gather_intel: 'intel',
  sow_discord: 'discord',
  sabotage: 'sabotage',
  assassinate: 'assassinate',
}

async function doSpyAction(net: any, actionKey: string) {
  const actionType = spyActionMap[actionKey] || actionKey
  const targetFaction = net.target_faction_id || net.target_faction || net.owner_faction
  if (!targetFaction) {
    spyFeedback.value = { text: '无法识别目标势力', type: 'error' }
    return
  }

  spyFeedback.value = { text: '执行中...', type: 'info' }
  try {
    const result = await store.executeSpyAction(targetFaction, actionType)
    if (result.success) {
      let msg = result.message || '行动成功'
      if (result.data) {
        const d = result.data
        const parts: string[] = []
        if (d.treasury !== undefined) parts.push(`银两: ${d.treasury}`)
        if (d.grain !== undefined) parts.push(`粮草: ${d.grain}`)
        if (d.total_troops !== undefined) parts.push(`兵力: ${d.total_troops}`)
        if (d.total_population !== undefined) parts.push(`人口: ${d.total_population}`)
        if (d.tiles !== undefined) parts.push(`领地: ${d.tiles}块`)
        if (d.court_stability !== undefined) parts.push(`朝纲: ${d.court_stability}`)
        if (d.realm_stability !== undefined) parts.push(`民心: ${d.realm_stability}`)
        if (parts.length > 0) msg += ` | ${parts.join(' · ')}`
      }
      spyFeedback.value = { text: msg, type: 'success' }
      // 刺探成功后刷新世界状态以更新情报可见性
      if (actionType === 'intel') {
        await store.refreshWorldState()
        await store.refreshSpyNetworks()
      }
    } else {
      spyFeedback.value = { text: result.message || '行动失败', type: 'error' }
    }
  } catch (err: any) {
    spyFeedback.value = { text: err?.message || '行动异常', type: 'error' }
  }
}

// ===== 细作已刺探情报 =====
const playerSpyIntel = computed(() => {
  if (!store.spyIntel || store.spyIntel.length === 0) return []
  return store.spyIntel
    .filter((i: any) => i.owner_faction === store.playerFactionId && i.success)
    .sort((a: any, b: any) => (b.round || 0) - (a.round || 0))
    .slice(0, 10)
})

function getFactionNameById(fid: string): string {
  const f = store.factions[fid]
  return f?.name || fid
}

function getFactionColorById(fid: string): string {
  const f = store.factions[fid]
  return f?.color || '#b89b68'
}

// 面板数据（从后端获取）
const royalData = ref<any>(null)
const medicalData = ref<any>(null)
const seaData = ref<any>(null)
const cultureData = ref<any>(null)
const weatherData = ref<any>(null)

// 音效设置
const AUDIO_STORAGE_KEY = 'yuanmo_audio_panel'
const audioSettings = ref({
  muted: false,
  masterVolume: 70,
  bgmVolume: 50,
  sfxVolume: 60,
  voiceVolume: 80,
  bgmOn: true,
})
const bgmTracks = ref<{ id: string; name: string; src: string }[]>([])
const currentBgmId = ref<string | null>(null)
const currentBgmName = ref('')

// AI智能体监控
const agentDashboard = ref<any>(null)
const agentLoading = ref(false)

async function refreshAgentDashboard() {
  agentLoading.value = true
  try {
    const { agentDashboard: fetchAgentDashboard } = await import('@/services/api')
    agentDashboard.value = await fetchAgentDashboard()
  } catch (e) {
    console.warn('Agent Dashboard加载失败:', e)
  } finally {
    agentLoading.value = false
  }
}

// ─── 音频：加载持久化设置 ───
function loadAudioSettings() {
  try {
    const saved = localStorage.getItem(AUDIO_STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved)
      Object.assign(audioSettings.value, parsed)
    }
  } catch { console.warn('[Audio] 加载音频设置失败') }
}

function saveAudioSettings() {
  try {
    localStorage.setItem(AUDIO_STORAGE_KEY, JSON.stringify(audioSettings.value))
  } catch { console.warn('[Audio] 保存音频设置失败') }
}

function applyAllAudioSettings() {
  audioManager.setMuted(audioSettings.value.muted)
  audioManager.setMasterVolume(audioSettings.value.masterVolume / 100)
  audioManager.setBgmVolume(audioSettings.value.bgmVolume / 100)
  audioManager.setSfxVolume(audioSettings.value.sfxVolume / 100)
  audioManager.setVoiceVolume(audioSettings.value.voiceVolume / 100)
  audioManager.setSfxMuted(!audioSettings.value.muted ? false : audioSettings.value.muted)
  if (audioSettings.value.bgmOn) {
    audioManager.resumeBgm()
  } else {
    audioManager.pauseBgm()
  }
}

function syncBgmState() {
  currentBgmId.value = audioManager.getCurrentBgmId()
  currentBgmName.value = audioManager.getCurrentBgmName()
  bgmTracks.value = audioManager.getBgmTracks().map(t => ({ id: t.id, name: t.name, src: t.src }))
}

// 音频初始化
onMounted(() => {
  loadAudioSettings()
  applyAllAudioSettings()
  syncBgmState()
})

// 面板打开时刷新状态
watch(() => store.activePanel, (panel) => {
  if (panel === 'audio') {
    syncBgmState()
  }
})

// ─── 音频操作 ───

function toggleMuteAll() {
  audioSettings.value.muted = !audioSettings.value.muted
  audioManager.setMuted(audioSettings.value.muted)
  saveAudioSettings()
}

function toggleAudio(key: 'bgm') {
  if (key === 'bgm') {
    audioSettings.value.bgmOn = !audioSettings.value.bgmOn
    if (audioSettings.value.bgmOn) {
      audioManager.resumeBgm()
    } else {
      audioManager.pauseBgm()
    }
    saveAudioSettings()
  }
}

function onMasterVolumeChange() {
  audioManager.setMasterVolume(audioSettings.value.masterVolume / 100)
  saveAudioSettings()
}

function onBgmVolumeChange() {
  audioManager.setBgmVolume(audioSettings.value.bgmVolume / 100)
  saveAudioSettings()
}

function onSfxVolumeChange() {
  audioManager.setSfxVolume(audioSettings.value.sfxVolume / 100)
  saveAudioSettings()
}

function onVoiceVolumeChange() {
  audioManager.setVoiceVolume(audioSettings.value.voiceVolume / 100)
  saveAudioSettings()
}

function switchBgmTrack(id: string) {
  audioManager.playBgm(id, 1.0)
  syncBgmState()
  if (!audioSettings.value.bgmOn) {
    audioSettings.value.bgmOn = true
    saveAudioSettings()
  }
}

function playNextBgm() {
  audioManager.playRandomBgm()
  syncBgmState()
}

function toggleBgmPlay() {
  if (audioManager.isBgmPlaying()) {
    audioManager.pauseBgm()
    audioSettings.value.bgmOn = false
  } else {
    if (currentBgmId.value) {
      audioManager.playBgm(currentBgmId.value, 1.0)
    } else {
      audioManager.playBgm('gameplay', 1.0)
    }
    audioSettings.value.bgmOn = true
  }
  syncBgmState()
  saveAudioSettings()
}

// 外交操作反馈
const diploFeedback = ref<{ text: string; type: string }>({ text: '', type: '' })
const diploTimer = ref<ReturnType<typeof setTimeout> | null>(null)
const diploRecommendations = ref<any[]>([])
const diploRecLoading = ref(false)

// 外交面板打开时自动加载推荐
watch(() => store.activePanel, (panel) => {
  if (panel === 'diplomacy' && store.playerFactionId) {
    loadDiplomacyRecommendations()
  }
})

async function loadDiplomacyRecommendations() {
  if (!store.playerFactionId) return
  diploRecLoading.value = true
  try {
    const result = await API.getDiplomaticRecommendations(store.playerFactionId)
    diploRecommendations.value = result?.recommendations || result || []
  } catch {
    diploRecommendations.value = []
  } finally {
    diploRecLoading.value = false
  }
}

// 邸报事件
const eventLoading = ref(false)
const generatedEvents = ref('')

// 律法审讯
const selectedPrisoner = ref<any>(null)
const interrogateQuestion = ref('')
const interrogateLoading = ref(false)
const interrogateResult = ref('')

const playerFaction = computed(() => store.playerFaction)

const horseRatio = computed(() => {
  const horses = playerFaction.value?.horses || 0
  const troops = store.totalTroops || 1
  return Math.min(100, Math.round((horses / troops) * 100))
})

// 藩镇：玩家麾下的藩属列表
const playerVassals = computed(() => {
  const myId = store.playerFactionId
  if (!myId) return []
  const vassalIds = Object.entries(store.vassalRelations || {})
    .filter(([vassalId, suzerainId]) => suzerainId === myId)
    .map(([vassalId]) => vassalId)
  return store.livingFactions.filter(f => vassalIds.includes(f.faction_id))
})

// 工坊产量计算
const workshopTotalCount = computed(() => {
  if (!workshopData.value?.workshops) return 0
  return workshopData.value.workshops.reduce((sum: number, ws: any) => sum + (ws.workshops?.length || 0), 0)
})
const workshopArmsOutput = computed(() => {
  const base = workshopTotalCount.value * 15
  return workshopFocus.value === 'arms' ? Math.floor(base * 1.5) : Math.floor(base)
})
const workshopGoldOutput = computed(() => {
  const base = workshopTotalCount.value * 40
  return workshopFocus.value === 'gold' ? Math.floor(base * 1.5) : Math.floor(base)
})
const workshopGrainOutput = computed(() => {
  const base = workshopTotalCount.value * 30
  return workshopFocus.value === 'grain' ? Math.floor(base * 1.5) : Math.floor(base)
})

// ===== 朝堂面板状态 =====
const courtTab = ref<'overview' | 'policies' | 'officials' | 'decrees'>('overview')
const activePolicyCat = ref('civil')
const officialsData = ref<any[]>([])
const policyData = ref<any>(null)
const decreeText = ref('')
const newOfficialName = ref('')
const newOfficialPosition = ref('')
const newOfficialAbility = ref(50)
const newOfficialLoyalty = ref(60)

// 朝堂 API 数据（增强总览）
const courtOverviewData = ref<any>(null)
const debateHistory = ref<any[]>([])
const courtOverviewLoading = ref(false)

async function refreshCourtData() {
  if (!store.playerFactionId) return
  courtOverviewLoading.value = true
  try {
    const [overview, debateH] = await Promise.all([
      API.getCourtOverview(store.playerFactionId).catch(() => null),
      API.getDebateHistory(store.playerFactionId).catch(() => null),
    ])
    if (overview) courtOverviewData.value = overview
    if (debateH) debateHistory.value = debateH?.history || []
  } catch (e) {
    console.warn('[Court] 加载朝堂数据失败:', e)
  } finally {
    courtOverviewLoading.value = false
  }
}

// （court 面板数据加载已统一由下方 watch 处理，避免重复调用）

const policyCategories = [
  { key: 'civil', icon: '🏛', name: '内政' },
  { key: 'military', icon: '⚔', name: '军事' },
  { key: 'diplomacy', icon: '🤝', name: '外交' },
  { key: 'economy', icon: '💰', name: '经济' },
]

const quickDecrees = [
  '大赦天下，减免赋税三成',
  '全国征兵，整军备战',
  '开科取士，选拔贤能',
  '兴修水利，劝课农桑',
  '遣使通好，改善邦交',
]

const currentPolicyBranches = computed(() => {
  if (!policyData.value) return []
  const cat = policyData.value[activePolicyCat.value]
  return cat?.branches || []
})

// 面板打开时自动加载数据
watch(() => store.activePanel, async (panel) => {
  if (panel === 'construction' || panel === 'workshop') {
    await loadWorkshops()
  }
  if (panel === 'law' || panel === 'prisoner' || panel === 'law-interrogate') {
    await loadPrisoners()
  }
  if (panel === 'spy') {
    await store.refreshSpyNetworks()
  }
  if (panel === 'court') {
    await loadCourtData()
    refreshCourtData()  // 加载朝堂总览/辩论历史（独立数据源）
  }
  if (panel === 'royal') {
    await loadRoyalData()
    if (royalPrinces.value.length === 0) initRoyalPrinces()
  }
  if (panel === 'medical') {
    await loadMedicalData()
    clinicTiles.value = getClinicTiles()
  }
  if (panel === 'sea') {
    await loadSeaData()
  }
  if (panel === 'culture') {
    await loadCultureData()
  }
  if (panel === 'rebel') {
    await loadRebels()
  }
  if (panel === 'agent') {
    await refreshAgentDashboard()
  }
  if (panel === 'moveCapital') {
    await loadCapitalCandidates()
  }
  if (panel === 'vassal') {
    // 藩镇面板打开时自动检查叛乱风险
    await checkVassalRisk()
    await loadVassalTributes()
  }
  if (panel === 'workshop') {
    await loadWorkshops()
  }
  if (panel === 'law') {
    await loadPrisoners()
  }
})

// 切换伏击目标时重置地点选择
watch(ambushTarget, () => {
  ambushTileId.value = ''
})

async function loadRoyalData() {
  try { royalData.value = await getRoyalPanel(store.playerFactionId) } catch { console.warn('皇家面板加载失败') }
}
async function loadMedicalData() {
  try { medicalData.value = await getMedicalPanel(store.playerFactionId) } catch { console.warn('医疗面板加载失败') }
}
async function loadSeaData() {
  try { seaData.value = await getSeaPanel(store.playerFactionId) } catch { console.warn('海贸面板加载失败') }
}
async function loadCultureData() {
  try { cultureData.value = await getCulturePanel(store.playerFactionId) } catch { console.warn('文化面板加载失败') }
}
async function loadWeather() {
  try { weatherData.value = await getWeather() } catch { console.warn('天气数据加载失败') }
}

async function loadWorkshops() {
  try { workshopData.value = await store.refreshWorkshops() } catch { console.warn('工坊数据加载失败') }
}

async function loadPrisoners() {
  try {
    const result = await getFactionPrisoners(store.playerFactionId)
    prisonerData.value = result?.prisoners || []
  } catch { console.warn('加载俘虏数据失败') }
}

async function loadRebels() {
  try {
    const result = await listRebels()
    rebelData.value = result?.rebels || result?.rebel_armies || []
  } catch { console.warn('加载叛军数据失败') }
}

async function doSuppressRebel(rebelId: string) {
  const troops = suppressTroops.value[rebelId] || 0
  if (!troops || troops < 100) {
    showToast('请至少派遣100兵力', 'error')
    return
  }
  suppressing.value = rebelId
  try {
    const result = await suppressRebellion(store.playerFactionId, rebelId, troops)
    if (result?.code === 200 || result?.data?.success) {
      const data = result?.data || result
      showToast(data?.message || '镇压成功', 'success')
      await loadRebels()
      await store.refreshWorldState()
    } else {
      const msg = result?.msg || result?.data?.message || '镇压失败'
      showToast(msg, 'error')
    }
  } catch (e: any) {
    showToast('镇压行动失败', 'error')
  } finally {
    suppressing.value = ''
  }
}

async function checkVassalRisk() {
  try {
    const result = await checkVassalRebellion(store.playerFactionId)
    // 兼容后端返回格式：{ rebellion_risk: { risk: N } } 或 { rebellion_risk: { rebel: ... } } 或 null
    if (result?.rebellion_risk?.risk !== undefined) {
      vassalRisk.value = result.rebellion_risk.risk
    } else if (result?.rebellion_risk?.rebel) {
      vassalRisk.value = 80  // 有人叛乱则高风险
    } else {
      vassalRisk.value = Math.floor(Math.random() * 15)  // 无叛乱则低风险
    }
  } catch { console.warn('加载藩镇风险数据失败') }
}

// 藩镇：获取忠诚度描述
function getVassalLoyalty(factionId: string): string {
  const f = store.factions[factionId]
  if (!f) return '未知'
  // 基于好感度估算忠诚
  const rel = store.relations?.[`${store.playerFactionId}|${factionId}`]
  const attitude = rel?.attitude || 0
  if (attitude > 60) return '忠心'
  if (attitude > 20) return '顺从'
  if (attitude > -20) return '摇摆'
  if (attitude > -60) return '不满'
  return '谋叛'
}

// 藩镇：加载纳贡记录
async function loadVassalTributes() {
  try {
    const result = await API.get(`/api/vassal/tributes/${store.playerFactionId}`)
    const data = result?.data || result
    vassalTributes.value = data?.tributes || []
  } catch {
    vassalTributes.value = []
  }
}

// 藩镇：纳贡
async function doVassalTribute(vassalId: string) {
  try {
    const amount = prompt('输入索贡银两数额：', '500')
    if (!amount || isNaN(Number(amount))) return
    const result = await API.demandTribute({ 
      suzerain_faction: store.playerFactionId, 
      vassal_faction: vassalId, 
      amount: parseInt(amount) 
    })
    const data = result?.data || result
    showToast(data?.message || `已向藩属索贡${amount}银`, 'success')
    await store.refreshWorldState()
  } catch { showToast('纳贡操作失败', 'error') }
}

// 藩镇：征讨
function doVassalSuppress(vassalId: string) {
  const name = store.factions[vassalId]?.name || vassalId
  store.submitCommand('suppress_vassal', { vassal_id: vassalId, vassal_name: name })
  showToast(`已下令征讨藩镇「${name}」`)
}

// 藩镇：吞并
async function doVassalAnnex(vassalId: string) {
  const name = store.factions[vassalId]?.name || vassalId
  if (!confirm(`确定吞并「${name}」？此举可能导致其他藩镇叛乱！`)) return
  try {
    const result = await API.annexVassal(store.playerFactionId, vassalId)
    const data = result?.data || result
    showToast(data?.message || `已吞并「${name}」`, 'success')
    await store.refreshWorldState()
  } catch { showToast('吞并失败', 'error') }
}

// 藩镇：释放（解除宗藩）
async function doVassalRelease(vassalId: string) {
  const name = store.factions[vassalId]?.name || vassalId
  if (!confirm(`确定解除与「${name}」的宗藩关系？该势力将获得独立。`)) return
  try {
    const result = await API.cancelVassal({ suzerain_faction: store.playerFactionId, vassal_faction: vassalId })
    const data = result?.data || result
    showToast(data?.message || `已解除与「${name}」的宗藩关系`, 'success')
    await store.refreshWorldState()
  } catch { showToast('释放失败', 'error') }
}

// 工坊：设置生产侧重
function setWorkshopFocus(focus: 'arms' | 'gold' | 'grain' | 'balanced') {
  workshopFocus.value = focus
  const labels: Record<string, string> = {
    arms: '军械优先 — 全力锻造兵器甲胄',
    gold: '银两优先 — 专注商贸铸造',
    grain: '粮草优先 — 加工储备粮秣',
    balanced: '均衡生产 — 按需分配产出',
  }
  workshopFocusResult.value = { text: `已设置：${labels[focus]}`, type: 'success' }
  // 提交到后端
  store.submitCommand('workshop_focus', { focus })
  setTimeout(() => { workshopFocusResult.value = null }, 3000)
}

// 律法：量刑（需选择囚犯）
async function handleLawActionWithPrisoner(action: string) {
  if (!lawSelectedPrisoner.value) {
    showToast('请先选择一名囚犯', 'error')
    return
  }
  const pid = lawSelectedPrisoner.value.prisoner_id || lawSelectedPrisoner.value.name
  if (!pid) {
    showToast('囚犯数据异常，请刷新重试', 'error')
    return
  }
  lawActionLoading.value = true
  lawActionResult.value = null
  try {
    const result = await API.handlePrisoner({ prisoner_id: pid, action })
    const data = result?.data || result
    if (data?.success) {
      const actionLabels: Record<string, string> = {
        execute: '已处决',
        exile: '已流放',
        pardon: '已赦免',
        fine: '已罚银',
        court: '已提交廷议',
      }
      lawActionResult.value = { 
        text: `${actionLabels[action] || '操作完成'}：${lawSelectedPrisoner.value.name}`, 
        type: 'success' 
      }
      lawSelectedPrisoner.value = null
      await loadPrisoners()
      await store.refreshWorldState()
    } else {
      lawActionResult.value = { text: data?.message || data?.msg || '操作失败', type: 'error' }
    }
  } catch {
    lawActionResult.value = { text: '执法失败，请稍后重试', type: 'error' }
  } finally {
    lawActionLoading.value = false
    setTimeout(() => { lawActionResult.value = null }, 4000)
  }
}

// 律法：打开刑部审讯
function openLawInterrogate() {
  store.togglePanel('law')
  store.togglePanel('law-interrogate')
}

const buildTargetTileId = ref('')
const buildFeedback = ref<{ text: string; type: string }>({ text: '', type: '' })
const buildTimer = ref<ReturnType<typeof setTimeout> | null>(null)

/** 可供建造的地块列表：优先使用 playerTiles，为空时回退到 store.tiles 过滤 */
const buildableTiles = computed(() => {
  const pts = store.playerTiles
  if (pts.length > 0) return pts
  // 回退：直接从 store.tiles 按 faction_id 过滤
  return Object.values(store.tiles)
    .filter(t => t.faction_id === store.playerFactionId && t.faction_id !== '')
    .sort((a, b) => {
      if (a.is_capital && !b.is_capital) return -1
      if (!a.is_capital && b.is_capital) return 1
      return (b.population || 0) - (a.population || 0)
    })
})

// 当前选中的建造地块（响应式计算，playerTiles 为空时回退到 store.tiles）
const currentBuildTile = computed(() => {
  if (!buildTargetTileId.value) return null
  const fromPlayer = store.playerTiles.find(t => t.tile_id === buildTargetTileId.value)
  if (fromPlayer) return fromPlayer
  // 回退：直接从 store.tiles 取值（与 playerFactionId 匹配检查）
  const fromAll = store.tiles[buildTargetTileId.value]
  if (fromAll && fromAll.faction_id === store.playerFactionId) return fromAll
  return null
})

// 建筑定义表：key、名称、图标、效果说明、费用、建造条件
const buildingDefs = [
  {
    key: 'water_works', name: '水利', icon: '🌊', cost: 500,
    effect: '每级人口增长 +0.15%，减少洪水灾害概率',
    req: '',
  },
  {
    key: 'granary', name: '粮仓', icon: '🌾', cost: 800,
    effect: '每级储粮上限 +500 石，减少饥荒风险',
    req: '',
  },
  {
    key: 'clinic', name: '医馆', icon: '🏥', cost: 600,
    effect: '每级人口增长 +0.30%，降低瘟疫风险',
    req: '',
  },
  {
    key: 'fortification', name: '城防', icon: '🏰', cost: 300,
    effect: '每级防御 +20%，驻军上限 +2000；Lv.3+ 可触发围城',
    req: '',
  },
  {
    key: 'armory', name: '军械所', icon: '⚒', cost: 800,
    effect: '每级精锐比例 +0.10（上限1.0），提升部队战力',
    req: '',
  },
  {
    key: 'stable', name: '马场', icon: '🐴', cost: 800,
    effect: '每级解锁战马购买，骑兵部队需要马场支持',
    req: '',
  },
  {
    key: 'port', name: '港口', icon: '⚓', cost: 1200,
    effect: '解锁海上贸易路线，贸易收入 +80银/回合',
    req: '仅海岸/港口地形可建',
  },
]

// 获取建筑当前等级
function getBuildingLevel(key: string): number {
  const t = currentBuildTile.value
  if (!t) return 0
  switch (key) {
    case 'water_works': return t.water_works || 0
    case 'granary': return t.granary || 0
    case 'clinic': return t.clinic || 0
    case 'fortification': return t.fortification || 0
    case 'armory': return t.armory || 0
    case 'stable': return t.stable || 0
    case 'port': return t.is_port ? 1 : 0
    default: return 0
  }
}

// 判断建筑是否被锁定
function isBuildingLocked(b: typeof buildingDefs[number]): boolean {
  const t = currentBuildTile.value
  if (!t) return true
  // 港口只能在海边/港口地形建造
  if (b.key === 'port' && !['coast', 'port', 'water'].includes(t.tile_type)) return true
  return false
}

// 获取建筑锁定原因
function getBuildLockReason(b: typeof buildingDefs[number]): string {
  const t = currentBuildTile.value
  if (!t) return ''
  if (b.key === 'port' && !['coast', 'port', 'water'].includes(t.tile_type)) {
    return `⛔ ${tileTypeName(t.tile_type)}地形不可建港口`
  }
  return ''
}

// 选择地块变化时刷新
function onBuildTileChange() {
  buildFeedback.value = { text: '', type: '' }
}

function tileTypeName(type: string): string {
  const map: Record<string, string> = {
    farmland: '农田', mountain: '山地', water: '水域', coast: '海岸',
    city: '城池', pass: '关隘', port: '港口', desert: '漠地', grassland: '草原',
  }
  return map[type] || type
}

function buildWorkshop(building: string) {
  const def = buildingDefs.find(b => b.key === building)
  const label = def?.name || building
  const cost = def?.cost || 500
  const tileId = buildTargetTileId.value
  const tileName = currentBuildTile.value?.tile_name || tileId
  const curLevel = getBuildingLevel(building)

  if (!tileId) {
    buildFeedback.value = { text: '请先选择建造地块！', type: 'error' }
    showToast('请先选择建造地块！', 'info')
    return
  }

  // 港口特殊处理
  if (building === 'port' && curLevel > 0) {
    buildFeedback.value = { text: '该地块已有港口，无需重复建造。', type: 'error' }
    showToast('该地块已有港口', 'info')
    return
  }

  // 检查银两
  const treasury = store.playerFaction?.treasury || 0
  if (treasury < cost) {
    buildFeedback.value = { text: `银两不足！${label}需要银${cost}两，当前仅有银${treasury}两。`, type: 'error' }
    showToast(`银两不足：需要${cost}两，现有${treasury}两`, 'error')
    return
  }

  // 城防用 fortify 指令，水利用 develop 指令，其余用 build 指令
  if (building === 'fortification') {
    store.submitCommand('fortify', { tile_id: tileId })
  } else if (building === 'water_works') {
    store.submitCommand('develop', { tile_id: tileId, type: 'water' })
  } else {
    store.submitCommand('build', { tile_id: tileId, building })
  }

  const lvText = curLevel > 0 ? `（Lv.${curLevel} → Lv.${curLevel + 1}）` : ''
  buildFeedback.value = { text: `已下旨：在「${tileName}」${curLevel > 0 ? '升级' : '建造'}${label}${lvText}，耗费银${cost}两，将在回合结算时执行。`, type: 'success' }
  showToast(`已下旨在「${tileName}」${curLevel > 0 ? '升级' : '建造'}${label}`, 'success')

  // 加入事件记录
  store.addEvent({
    event_id: `build_${Date.now()}`,
    event_type: 'civil',
    severity: 'trivial',
    round: store.currentRound,
    title: `营造司：${tileName}${curLevel > 0 ? '升级' : '建造'}${label}`,
    description: `在「${tileName}」${curLevel > 0 ? '升级' : '建造'}${label}${lvText}，耗费银${cost}两。`,
    faction_id: store.playerFactionId,
    tile_id: tileId,
    effects: { building: building, level: curLevel + 1 },
    narrative: `营造司奉旨在「${tileName}」${curLevel > 0 ? '升级' : '建造'}${label}${lvText}，预计耗费银${cost}两。`,
  })

  // 4秒后清除反馈
  if (buildTimer.value) clearTimeout(buildTimer.value)
  buildTimer.value = setTimeout(() => { buildFeedback.value = { text: '', type: '' } }, 4000)
}

function handleLawAction(action: string) { store.submitCommand('law', { action }) }
async function handlePrisonerAction(action: string, prisonerId: string) {
  if (!prisonerId) {
    showToast('请先选择一个俘虏', 'error')
    return
  }
  try {
    const result = await API.handlePrisoner({ prisoner_id: prisonerId, action })
    const data = result?.data || result
    if (data?.success) {
      const msg = data?.ransom_amount ? `${data.message} (${data.ransom_amount}银)` : data.message
      showToast(msg || '操作成功', 'success')
      await loadPrisoners()
      await store.refreshWorldState()
    } else {
      showToast(data?.message || data?.msg || '操作失败', 'error')
    }
  } catch { showToast('俘虏处置失败', 'error') }
}

// ---- P1 高级功能处理 ----

async function doAmbush() {
  if (!ambushTarget.value || !ambushTileId.value || !ambushTroops.value) {
    showToast('请填写完整信息', 'error')
    return
  }
  ambushing.value = true
  try {
    const result = await attemptAmbush(store.playerFactionId, ambushTarget.value, ambushTileId.value, ambushTroops.value)
    const data = result?.data || result
    if (data?.success) {
      showToast(data.message || '伏击成功！', 'success')
      await store.refreshWorldState()
    } else {
      showToast(data?.message || data?.msg || '伏击失败', 'error')
    }
  } catch { showToast('伏击行动失败', 'error') }
  finally { ambushing.value = false }
}

async function doRaidSupply() {
  if (!raidTarget.value) { showToast('请选择目标势力', 'error'); return }
  if (raidSupplyTroops.value < 100) { showToast('至少需要100兵力', 'error'); return }
  raiding.value = true
  try {
    const result = await raidSupplyLine(store.playerFactionId, raidTarget.value, raidSupplyTroops.value)
    const data = result?.data || result
    if (data?.success) {
      let msg = data.message || '劫掠成功！'
      if (data.stolen_grain) msg += ` 夺得粮草${data.stolen_grain}`
      if (data.intel_source) msg += ` (${data.intel_source})`
      if (data.relation_change) msg += ` 好感度${data.relation_change}`
      showToast(msg, 'success')
      await store.refreshWorldState()
    } else {
      let msg = data?.message || data?.msg || '劫掠失败'
      if (data?.discovered) msg += ' (双方好感度下降)'
      showToast(msg, 'error')
      await store.refreshWorldState()
    }
  } catch { showToast('劫掠行动失败', 'error') }
  finally { raiding.value = false }
}

async function doBorderRaid() {
  if (!borderRaidTarget.value || !borderRaidTroops.value) { showToast('请填写完整信息', 'error'); return }
  raiding.value = true
  try {
    const result = await borderRaid(store.playerFactionId, borderRaidTarget.value, borderRaidTroops.value)
    const data = result?.data || result
    if (data?.success) {
      showToast(data.message || '边境劫掠成功！', 'success')
      await store.refreshWorldState()
    } else {
      showToast(data?.message || data?.msg || '边境劫掠失败', 'error')
    }
  } catch { showToast('劫掠行动失败', 'error') }
  finally { raiding.value = false }
}

async function doSacrifice() {
  try {
    const result = await performSacrifice(store.playerFactionId)
    const data = result?.data || result
    if (data?.success) {
      showToast(data.message || '祭祀完成！', 'success')
      await store.refreshWorldState()
    } else {
      showToast(data?.message || data?.msg || '祭祀失败', 'error')
    }
  } catch { showToast('祭祀失败', 'error') }
}

async function doRecruitOfficials() {
  try {
    const result = await recruitOfficials(store.playerFactionId, 1)
    const data = result?.data || result
    if (data?.success) {
      showToast(data.message || '选拔成功！', 'success')
      await store.refreshWorldState()
    } else {
      showToast(data?.message || data?.msg || '选拔失败', 'error')
    }
  } catch { showToast('科举选拔失败', 'error') }
}

async function doMoveCapital() {
  if (!newCapitalTileId.value) { showToast('请选择新都城', 'error'); return }
  if ((store.playerFaction?.treasury || 0) < 10000) { showToast('银两不足（需要10,000两）', 'error'); return }
  capitalMoving.value = true
  try {
    const result = await moveCapital(store.playerFactionId, newCapitalTileId.value)
    const data = result?.data || result
    if (data?.success) {
      const capName = data.new_capital_name || newCapitalTileId.value
      const changes: string[] = []
      if (data.court_stability_change !== 0) changes.push(`朝纲${data.court_stability_change >= 0 ? '+' : ''}${data.court_stability_change}`)
      if (data.realm_stability_change !== 0) changes.push(`民心${data.realm_stability_change >= 0 ? '+' : ''}${data.realm_stability_change}`)
      if (data.fortification_gained) changes.push(`新城防${data.fortification_gained >= 0 ? '+' : ''}${data.fortification_gained}`)
      showToast(`迁都${capName}成功！${changes.join('，')}`, 'success')
      newCapitalTileId.value = ''
      selectedCandidateId.value = ''
      capitalCandidates.value = []
      capitalCandidatesData.value = null
      await store.refreshWorldState()
      await loadCapitalCandidates()
    } else {
      showToast(data?.message || data?.msg || '迁都失败', 'error')
    }
  } catch { showToast('迁都失败', 'error') }
  finally { capitalMoving.value = false }
}

// 扩展 doDiplomacy 支持 P1 功能（在原有函数中追加处理）

// ---- 新增面板计算属性 ----

// 皇子宗室面板（优先后端数据，兜底前端计算）
const royalInfo = computed(() => {
  if (royalData.value) {
    return {
      count: royalData.value.heir_count || 0,
      heir: royalData.value.heir_designated
        ? `${royalData.value.ruler_name}世子`
        : '未立',
      ruler: royalData.value.ruler_name,
      rulerAge: royalData.value.ruler_age,
      grownHeirs: royalData.value.grown_heirs || 0,
      risk: royalData.value.succession_risk || 'low',
    }
  }
  // 兜底：根据势力规模估算皇子数量（与势力初始领地数量正相关）
  const ownedCount = store.playerTiles.length
  const estHeirs = Math.max(1, Math.min(8, Math.floor(ownedCount * 0.6 + store.currentRound * 0.05)))
  return {
    count: estHeirs,
    heir: playerFaction.value?.name ? `${playerFaction.value.name}世子` : '未立',
    ruler: playerFaction.value?.name || '——',
    rulerAge: 40 + Math.floor(store.currentRound / 12),
    grownHeirs: Math.max(0, estHeirs - 3),
    risk: estHeirs <= 1 ? 'high' : estHeirs <= 2 ? 'medium' : 'low',
  }
})

// 疲病伤病面板（优先后端数据，兜底前端计算）
const medicalInfo = computed(() => {
  if (medicalData.value) {
    return {
      clinics: medicalData.value.clinics || 0,
      plagueRisk: medicalData.value.plague_risk || 0,
      injuryRate: medicalData.value.injury_rate || 0,
      injuredPop: medicalData.value.injured_population || 0,
      activeDisasters: medicalData.value.active_disasters || [],
      disasterIndex: medicalData.value.disaster_index || 0,
    }
  }
  let clinics = 0
  let activeDisasters: string[] = []
  for (const t of store.playerTiles) {
    clinics += t.clinic || 0
    if (t.disasters?.length) {
      for (const d of t.disasters) {
        if (typeof d === 'string' && !activeDisasters.includes(d)) {
          activeDisasters.push(d)
        }
      }
    }
  }
  const plagueRisk = Math.min(100, activeDisasters.length * 15 + Math.max(0, 20 - clinics * 3))
  const injuryRate = Math.max(0, Math.min(30, 10 - clinics * 2 + store.disasterIndex * 2))
  return { clinics, plagueRisk, injuryRate, injuredPop: 0, activeDisasters, disasterIndex: store.disasterIndex }
})

// 海策远洋面板（优先后端数据，兜底前端计算）
const seaInfo = computed(() => {
  if (seaData.value) {
    return {
      ports: seaData.value.ports || 0,
      fleetSize: seaData.value.fleet_size || 0,
      tradeIncome: seaData.value.trade_income || 0,
      routes: seaData.value.routes || 0,
    }
  }
  let ports = 0
  for (const t of store.playerTiles) {
    if (t.is_port) ports++
  }
  return { ports, fleetSize: ports * 3, tradeIncome: ports * 80, routes: ports > 0 ? 1 : 0 }
})

// 民俗国史面板（优先后端数据，兜底前端计算）
const cultureInfo = computed(() => {
  if (cultureData.value) {
    return {
      eraName: cultureData.value.era_name || '至正',
      year: cultureData.value.year_label || `至正${store.currentYear - 1340}年`,
      historyCount: cultureData.value.history_count || store.events.length,
      decreesCount: cultureData.value.decrees_count || 0,
      battlesCount: cultureData.value.battles_count || 0,
      recentEvents: cultureData.value.recent_events || store.events.slice(0, 20).map((e: any) => ({
        round: e.round,
        title: e.title,
      })),
    }
  }
  return {
    eraName: '至正',
    year: `至正${store.currentYear - 1340}年`,
    historyCount: store.events.length,
    decreesCount: 0,
    battlesCount: 0,
    recentEvents: store.events.slice(0, 20).map((e: any) => ({
      round: e.round,
      title: e.title,
    })),
  }
})

// 邸报事件生成
async function generateEvents() {
  if (!store.aiAvailable) {
    generatedEvents.value = '邸报生成失败（AI服务未就绪，请在设置中配置API Key）。'
    return
  }
  eventLoading.value = true
  generatedEvents.value = ''
  try {
    const result = await store.generateAIEvents()
    if (result?.events_text) {
      generatedEvents.value = result.events_text
    } else {
      generatedEvents.value = '钦天监禀报：今日天象平和，无重大事件。'
    }
  } catch {
    console.warn('邸报生成失败')
    generatedEvents.value = '邸报生成失败（AI服务未就绪）。'
  } finally {
    eventLoading.value = false
  }
}

// 律法审讯
async function doInterrogate() {
  if (!selectedPrisoner.value || !interrogateQuestion.value.trim() || interrogateLoading.value) return
  interrogateLoading.value = true
  interrogateResult.value = ''
  try {
    const response = await store.lawInterrogate(
      selectedPrisoner.value.name,
      interrogateQuestion.value.trim()
    )
    interrogateResult.value = response || `${selectedPrisoner.value.name}沉默不语，拒不招供。`
  } catch {
    console.warn('审讯失败')
    interrogateResult.value = `${selectedPrisoner.value.name}沉默不语，拒不招供。`
  } finally {
    interrogateLoading.value = false
  }
}

function workshopLabel(type: string): string {
  const labels: Record<string, string> = {
    granary: '粮仓', water_works: '水利', clinic: '医馆', port: '港口',
    armory: '军械所', stable: '马场', fortification: '城防',
  }
  return labels[type] || type
}

const panelTitles: Record<string, string> = {
  spy: '🕵 驿站谍报',
  royal: '👑 皇子宗室',
  medical: '🏥 疲病伤病',
  sea: '⛵ 海策远洋',
  vassal: '🏰 藩镇管控',
  workshop: '🔨 工坊生产',
  prisoner: '🔗 俘虏招安',
  personnel: '👤 人物总览',
  culture: '📖 民俗国史',
  events: '📋 大事记',
  audio: '🎵 音效设置',
}

function getPanelTitle(id: string): string {
  return panelTitles[id] || id
}

// formatNum is imported from useFormat composable above

// ===== 国库收支预估函数 =====
function countTileType(type: string): number {
  return store.playerTiles.filter(t => t.tile_type === type).length
}
function estimateTaxIncome(): number {
  const tiles = store.playerTiles.length
  const pop = store.totalPopulation
  const dev = playerFaction.value?.development_level || 20
  return Math.floor(tiles * 40 + pop * 0.02 + dev * 15 + (playerFaction.value?.tax_efficiency || 100) * 0.3)
}
function estimateGrainOutput(): number {
  const farmland = countTileType('farmland')
  const dev = playerFaction.value?.development_level || 20
  return Math.floor(farmland * 120 + (playerFaction.value?.grain_output_bonus || 0) * 5 + dev * 8)
}
function estimateTradeIncome(): number {
  const ports = store.playerTiles.filter(t => t.is_port).length
  const workshops = store.playerTiles.reduce((sum, t) => sum + (t.workshops || 0) + (t.markets || 0), 0)
  return ports * 80 + workshops * 30
}
function estimateWorkshopOutput(): number {
  const armories = store.playerTiles.reduce((sum, t) => sum + (t.armory || 0), 0)
  const stables = store.playerTiles.reduce((sum, t) => sum + (t.stable || 0), 0)
  return armories * 25 + stables * 15
}
function estimateMilitaryCost(): number {
  return Math.floor(store.totalTroops * 0.08 + 50)
}
function estimateNetIncome(): number {
  // 注意：以下为前端预估，可能与后端实际结算有微小差异
  // 真实值请以国库面板的实际变化为准
  const diplomacyCost = Math.max(50, Object.keys(store.relations || {}).length * 100)
  return estimateTaxIncome() + estimateTradeIncome() - estimateMilitaryCost() - store.officials.length * 50 - Math.max(100, store.playerTiles.length * 25) - diplomacyCost
}

// ===== 灾荒面板函数 =====
function getReliefCost(d: any): number {
  const base = 300
  if (d.severity === '高') return base * 2
  if (d.severity === '中') return base
  return Math.floor(base * 0.5)
}
async function relieveDisaster(d: any) {
  if ((playerFaction.value?.treasury || 0) < getReliefCost(d)) return
  dRelieving.value = d.id
  dReliefResult.value = null
  try {
    await API.submitCommand({
      action: 'relief',
      params: { disaster_id: d.id, tile_id: d.tile_id, cost: getReliefCost(d), type: 'relieve' },
      faction_id: store.playerFactionId,
    })
    dRelievedId.value = d.id
    // 即时扣银
    if (playerFaction.value) playerFaction.value.treasury -= getReliefCost(d)
    dReliefResult.value = { success: true, message: `已拨银${getReliefCost(d)}两赈济「${d.name}」，灾情缓解！` }
    // 刷新状态
    setTimeout(() => store.syncFullState(), 2000)
  } catch {
    dRelievedId.value = d.id
    dReliefResult.value = { success: false, message: '赈灾失败，请重试' }
  } finally {
    dRelieving.value = ''
  }
}
async function prayForDisaster(d: any) {
  dRelieving.value = d.id
  dReliefResult.value = null
  try {
    await API.submitCommand({
      action: 'relief',
      params: { tile_id: d.tile_id, type: 'pray', disaster_name: d.name },
      faction_id: store.playerFactionId,
    })
    store.realmStability = Math.min(100, store.realmStability + 2)
    store.addEvent({
      event_id: `pray_${Date.now()}`,
      event_type: 'ritual',
      severity: 'minor',
      round: store.currentRound,
      title: '祈福消灾',
      description: `君主为「${d.name}」祈福，祈求上天息灾。民心+2。`,
      faction_id: store.playerFactionId,
      tile_id: d.tile_id || '',
      effects: { realm_stability: 2 },
      narrative: `天子亲率百官祭祀，祈求「${d.name}」平息。民心稍安。`,
    })
    dRelievedId.value = d.id
    dReliefResult.value = { success: true, message: `已为「${d.name}」祈福，民心+2！` }
  } catch {
    dRelievedId.value = d.id
    dReliefResult.value = { success: false, message: '祈福失败，请重试' }
  } finally {
    dRelieving.value = ''
  }
}
async function forecastDisasters() {
  forecastLoading.value = true
  forecastResult.value = ''
  try {
    const result = await store.forecastDisaster()
    forecastResult.value = result?.forecast || result?.summary || '钦天监禀报：近期天象平和，无明显灾异。'
  } catch {
    forecastResult.value = '钦天监预判失败（AI服务未就绪）。'
  } finally {
    forecastLoading.value = false
  }
}

// ===== 人物面板函数 =====
function selectOfficial(off: any) {
  const id = off.official_id || off.name
  const curId = selectedOfficial.value?.official_id || selectedOfficial.value?.name
  selectedOfficial.value = curId === id ? null : off
}
async function promoteOfficial(off: any) {
  try {
    await API.submitCommand({
      action: 'appoint',
      params: { official_id: off.official_id || off.name, name: off.name, type: 'promote' },
      faction_id: store.playerFactionId,
    })
    store.addEvent({
      event_id: `promote_${Date.now()}`, event_type: 'personnel', severity: 'minor',
      round: store.currentRound, title: `提拔${off.name}`,
      description: `${off.name}因功绩被提拔。`, faction_id: store.playerFactionId,
      tile_id: '', effects: {}, narrative: `朝廷提拔${off.name}以示嘉奖。`,
    })
    showToast(`已提拔${off.name}`, 'success')
  } catch { showToast('提拔失败', 'error') }
}
async function demoteOfficial(off: any) {
  try {
    await API.submitCommand({
      action: 'dismiss',
      params: { official_id: off.official_id || off.name, name: off.name, type: 'demote' },
      faction_id: store.playerFactionId,
    })
    showToast(`已降职${off.name}`, 'success')
  } catch { showToast('降职失败', 'error') }
}
async function dismissPersonnelOfficial(officialId: string) {
  try {
    await apiDismissOfficial(officialId)
    await loadCourtData()
    selectedOfficial.value = null
    showToast('已罢免官员', 'success')
  } catch { showToast('罢免失败', 'error') }
}

// ===== 皇族面板函数 =====
function generatePrinces(): any[] {
  const count = royalInfo.value.count
  const grown = royalInfo.value.grownHeirs
  const rulerName = playerFaction.value?.name || '君主'
  const princes: any[] = []
  const surnames = ['朱', '李', '刘', '陈', '张', '王']
  const givenNames = ['标', '樉', '棡', '棣', '橚', '桢', '榑', '梓', '杞', '檀',
    '基', '标', '桓', '楷', '桂', '植', '楹', '柷', '枋', '榕']
  for (let i = 0; i < count; i++) {
    const age = i < grown ? 14 + i * 4 : 2 + (i - grown) * 3
    princes.push({
      name: (i === 0 && royalInfo.value.heir !== '未立') ? royalInfo.value.heir.replace('世子', '') : `${surnames[i % surnames.length]}${givenNames[i % givenNames.length]}`,
      age: Math.min(age, 35),
      status: i === 0 && royalInfo.value.heir !== '未立' ? '世子' : (age >= 16 ? '成年' : '幼年'),
      martial: 20 + Math.floor(Math.random() * 60),
      civil: 20 + Math.floor(Math.random() * 60),
      charisma: 25 + Math.floor(Math.random() * 55),
      talent: ['天资聪颖', '中人之资', '文武双全', '骁勇善战', '足智多谋', '平庸无奇'][Math.floor(Math.random() * 6)],
      ambition: ['低', '低', '中', '中', '高'][Math.floor(Math.random() * 5)],
    })
  }
  return princes
}
function initRoyalPrinces() {
  royalPrinces.value = generatePrinces()
}
function selectPrince(prince: any) {
  selectedPrince.value = selectedPrince.value?.name === prince.name ? null : prince
  princeActionResult.value = null
}
async function appointHeir(prince: any) {
  princeActionLoading.value = true
  princeActionResult.value = null
  try {
    await API.submitCommand({
      action: 'decree',
      params: { content: `册立${prince.name}为世子`, decree_type: 'heir', prince_name: prince.name },
      faction_id: store.playerFactionId,
    })
    // 更新所有皇子状态
    royalPrinces.value.forEach(p => { p.status = p.name === prince.name ? '世子' : (p.age >= 16 ? '成年' : '幼年') })
    store.courtStability = Math.min(100, store.courtStability + 5)
    store.addEvent({
      event_id: `heir_${Date.now()}`, event_type: 'royal', severity: 'major',
      round: store.currentRound, title: `册立世子`,
      description: `册立${prince.name}为世子，以固国本。朝纲+5。`,
      faction_id: store.playerFactionId, tile_id: '', effects: { court_stability: 5 },
      narrative: `天子册立${prince.name}为世子，昭告天下。`,
    })
    princeActionResult.value = { success: true, message: `已册立${prince.name}为世子！朝纲+5。` }
    showToast(`已册立${prince.name}为世子`, 'success')
  } catch {
    princeActionResult.value = { success: false, message: '册立世子失败，请重试' }
    showToast('册立世子失败', 'error')
  } finally {
    princeActionLoading.value = false
  }
}
async function sendPrinceToTerritory(prince: any) {
  princeActionLoading.value = true
  princeActionResult.value = null
  try {
    await API.submitCommand({
      action: 'enfeoff',
      params: { prince_name: prince.name, type: 'territory' },
      faction_id: store.playerFactionId,
    })
    store.courtStability = Math.max(0, store.courtStability - 2)
    store.addEvent({
      event_id: `territory_${Date.now()}`, event_type: 'royal', severity: 'minor',
      round: store.currentRound, title: `${prince.name}出镇地方`,
      description: `${prince.name}受命出镇地方，督抚一方。朝纲-2。`,
      faction_id: store.playerFactionId, tile_id: '', effects: { court_stability: -2 },
      narrative: `${prince.name}离京赴任，镇守边疆。`,
    })
    princeActionResult.value = { success: true, message: `${prince.name}已出镇地方。` }
    showToast(`${prince.name}已出镇地方`, 'success')
  } catch {
    princeActionResult.value = { success: false, message: '出镇失败，请重试' }
    showToast('出镇失败', 'error')
  } finally {
    princeActionLoading.value = false
  }
}
async function educatePrince(prince: any) {
  if ((playerFaction.value?.treasury || 0) < 200) {
    showToast('银两不足（需要200两）', 'error')
    return
  }
  princeActionLoading.value = true
  princeActionResult.value = null
  try {
    await API.submitCommand({
      action: 'decree',
      params: { content: `延师教导皇子${prince.name}`, decree_type: 'education', prince_name: prince.name, cost: 200 },
      faction_id: store.playerFactionId,
    })
    // 即时扣银
    if (playerFaction.value) playerFaction.value.treasury -= 200
    // 即时提升能力
    prince.martial = Math.min(95, prince.martial + Math.floor(Math.random() * 10))
    prince.civil = Math.min(95, prince.civil + Math.floor(Math.random() * 10))
    prince.charisma = Math.min(95, prince.charisma + Math.floor(Math.random() * 8))
    store.addEvent({
      event_id: `educate_${Date.now()}`, event_type: 'royal', severity: 'minor',
      round: store.currentRound, title: `延师教导${prince.name}`,
      description: `花费200银为${prince.name}延请名师教导。武略/文治/魅力提升。`,
      faction_id: store.playerFactionId, tile_id: '', effects: { treasury: -200 },
      narrative: `朝廷花银200两为${prince.name}延师，望其成才。`,
    })
    princeActionResult.value = { success: true, message: `${prince.name}已完成学业，才略增长！花费200银。` }
  } catch {
    princeActionResult.value = { success: false, message: '教导失败，请重试' }
    showToast('教导失败', 'error')
  } finally {
    princeActionLoading.value = false
  }
}
async function marryPrince(prince: any) {
  if ((playerFaction.value?.treasury || 0) < 300) {
    showToast('银两不足（需要300两）', 'error')
    return
  }
  princeActionLoading.value = true
  princeActionResult.value = null
  try {
    await API.submitCommand({
      action: 'marriage',
      params: { prince_name: prince.name, cost: 300 },
      faction_id: store.playerFactionId,
    })
    // 即时扣银 + 加声望
    if (playerFaction.value) playerFaction.value.treasury -= 300
    store.reputation = Math.min(100, store.reputation + 3)
    store.addEvent({
      event_id: `marry_${Date.now()}`, event_type: 'royal', severity: 'minor',
      round: store.currentRound, title: `${prince.name}成婚`,
      description: `花费300银为${prince.name}举办大婚。声望+3。`,
      faction_id: store.playerFactionId, tile_id: '', effects: { reputation: 3, treasury: -300 },
      narrative: `${prince.name}大婚礼成，各方势力前来道贺，声望+3。`,
    })
    princeActionResult.value = { success: true, message: `${prince.name}已完成大婚，声望+3！花费300银。` }
  } catch {
    princeActionResult.value = { success: false, message: '联姻失败，请重试' }
    showToast('联姻失败', 'error')
  } finally {
    princeActionLoading.value = false
  }
}
async function spawnNewPrince() {
  if ((playerFaction.value?.treasury || 0) < 800) {
    showToast('银两不足（需要800两）', 'error')
    return
  }
  // 先拉取历史子嗣数据
  historicalChildrenLoading.value = true
  historicalChildren.value = []
  selectedHistoricalChild.value = null
  customPrinceName.value = ''
  spawnMode.value = 'historical'
  try {
    const data = await getHistoricalChildren(store.playerFactionId)
    historicalChildren.value = data?.available || []
  } catch {
    historicalChildren.value = []
  }
  historicalChildrenLoading.value = false
  showSpawnPrinceDialog.value = true
}

async function confirmSpawnPrince() {
  let princeName = ''
  let isCustom = false
  if (spawnMode.value === 'custom') {
    princeName = customPrinceName.value.trim()
    if (!princeName) {
      showToast('请输入皇子姓名', 'error')
      return
    }
    isCustom = true
  } else {
    if (!selectedHistoricalChild.value) {
      showToast('请选择一位历史皇子', 'error')
      return
    }
    princeName = selectedHistoricalChild.value.name
    isCustom = false
  }

  if ((playerFaction.value?.treasury || 0) < 800) {
    showToast('银两不足（需要800两）', 'error')
    return
  }

  const newPrince = {
    name: princeName,
    age: 0, status: '新生', martial: 5, civil: 5, charisma: 10,
    talent: selectedHistoricalChild.value?.talent || '尚待观察',
    ambition: '低',
    is_historical: !isCustom,
  }
  try {
    await API.submitCommand({
      action: 'decree',
      params: { content: '纳妃求嗣', decree_type: 'spawn_prince', cost: 800, prince_name: princeName, custom_name: isCustom },
      faction_id: store.playerFactionId,
    })
    // 即时扣银 + 加民心
    if (playerFaction.value) playerFaction.value.treasury -= 800
    store.realmStability = Math.min(100, store.realmStability + 3)
    royalPrinces.value.push(newPrince)
    store.addEvent({
      event_id: `birth_${Date.now()}`, event_type: 'royal', severity: 'major',
      round: store.currentRound, title: '皇子降生',
      description: `新皇子${princeName}降生，举国欢庆。民心+3。花费800银。`,
      faction_id: store.playerFactionId, tile_id: '', effects: { realm_stability: 3, treasury: -800 },
      narrative: `皇宫喜诞麟儿，赐名${princeName}。民心+3。`,
    })
    showToast(`新皇子${princeName}降生！`, 'success')
    showSpawnPrinceDialog.value = false
  } catch {
    showToast('纳妃求嗣失败', 'error')
  }
}

// ===== 疾医面板函数 =====
function getClinicTiles(): any[] {
  return store.playerTiles.filter(t => (t.clinic || t.clinic_level || t.hospital) !== undefined && (t.clinic || t.clinic_level || t.hospital) > 0)
    .map(t => ({ ...t, clinic_level: t.clinic_level || t.clinic || t.hospital || 1 }))
}
function getClinicUpgradeCost(tile: any): number {
  return (tile.clinic_level || 1) * 200
}
async function upgradeClinic(tile: any) {
  const cost = getClinicUpgradeCost(tile)
  if ((playerFaction.value?.treasury || 0) < cost) return
  try {
    await API.submitCommand({
      action: 'build',
      params: { tile_id: tile.tile_id, building: 'clinic', cost },
      faction_id: store.playerFactionId,
    })
    // 即时扣银
    if (playerFaction.value) playerFaction.value.treasury -= cost
    store.addEvent({
      event_id: `clinic_up_${Date.now()}`, event_type: 'construction', severity: 'minor',
      round: store.currentRound, title: `升级${tile.tile_name || tile.tile_id}医馆`,
      description: `花费${cost}银将医馆升级至Lv.${(tile.clinic_level || 1) + 1}。`,
      faction_id: store.playerFactionId, tile_id: tile.tile_id, effects: {}, narrative: `朝廷拨款${cost}银升级${tile.tile_name || tile.tile_id}医馆。`,
    })
    showToast(`${tile.tile_name || tile.tile_id}医馆已升级`, 'success')
  } catch { showToast('升级失败', 'error') }
}
async function treatInjured(tile: any) {
  if ((playerFaction.value?.treasury || 0) < 150) return
  try {
    await API.submitCommand({
      action: 'relief',
      params: { tile_id: tile.tile_id, type: 'treat_injured', cost: 150 },
      faction_id: store.playerFactionId,
    })
    // 即时扣银
    if (playerFaction.value) playerFaction.value.treasury -= 150
    showToast(`已向${tile.tile_name || tile.tile_id}派遣医官施药`, 'success')
  } catch { showToast('施药失败', 'error') }
}

// ===== 海策面板函数 =====
function getPortTiles(): any[] {
  return store.playerTiles.filter(t => t.is_port || t.port_level || t.shipyard_level || t.harbor)
    .map(t => ({
      ...t,
      ships: t.ships || t.fleet_size || (t.shipyard_level || t.port_level || 1) * 3,
      shipyard_level: t.shipyard_level || t.port_level || 1,
      trade_income: t.trade_income || (t.is_port ? 80 : 0),
    }))
}
function selectPortTile(port: any) {
  selectedPort.value = selectedPort.value?.tile_id === port.tile_id ? null : port
}
async function buildShip(port: any) {
  if ((playerFaction.value?.treasury || 0) < 200) return
  try {
    await API.submitCommand({
      action: 'build',
      params: { tile_id: port.tile_id, building: 'ship', cost: 200 },
      faction_id: store.playerFactionId,
    })
    // 即时扣银
    if (playerFaction.value) playerFaction.value.treasury -= 200
    store.addEvent({
      event_id: `ship_${Date.now()}`, event_type: 'military', severity: 'minor',
      round: store.currentRound, title: `在${port.tile_name || port.tile_id}建造舰船`,
      description: `花费200银建造一艘战船。`, faction_id: store.playerFactionId,
      tile_id: port.tile_id, effects: {}, narrative: `${port.tile_name || port.tile_id}船坞新造一艘战船下水。`,
    })
    showToast(`已在${port.tile_name || port.tile_id}建造一艘舰船`, 'success')
  } catch { showToast('造舰失败', 'error') }
}
async function upgradeShipyard(port: any) {
  if ((playerFaction.value?.treasury || 0) < 400) return
  try {
    await API.submitCommand({
      action: 'build',
      params: { tile_id: port.tile_id, building: 'shipyard', cost: 400 },
      faction_id: store.playerFactionId,
    })
    // 即时扣银
    if (playerFaction.value) playerFaction.value.treasury -= 400
    showToast(`${port.tile_name || port.tile_id}船坞已升级`, 'success')
  } catch { showToast('升级失败', 'error') }
}
async function openTradeRoute(port: any) {
  if ((playerFaction.value?.treasury || 0) < 300) return
  try {
    await API.submitCommand({
      action: 'trade',
      params: { tile_id: port.tile_id, type: 'open_route', cost: 300 },
      faction_id: store.playerFactionId,
    })
    // 即时扣银
    if (playerFaction.value) playerFaction.value.treasury -= 300
    showToast(`已从${port.tile_name || port.tile_id}开辟新航线`, 'success')
  } catch { showToast('开辟航线失败', 'error') }
}
async function navalPatrol(port: any) {
  try {
    await API.submitCommand({
      action: 'patrol',
      params: { tile_id: port.tile_id, type: 'naval', port_name: port.tile_name || port.tile_id },
      faction_id: store.playerFactionId,
    })
    store.addEvent({
      event_id: `patrol_${Date.now()}`, event_type: 'military', severity: 'minor',
      round: store.currentRound, title: `水师巡航${port.tile_name || port.tile_id}`,
      description: `派遣水师在${port.tile_name || port.tile_id}海域巡航。`,
      faction_id: store.playerFactionId, tile_id: port.tile_id, effects: {},
      narrative: `水师战船在${port.tile_name || port.tile_id}沿海巡航，震慑海寇。`,
    })
    showToast(`水师已从${port.tile_name || port.tile_id}出航巡航`, 'success')
  } catch {
    showToast('水师巡航失败', 'error')
  }
}

// ===== 民俗面板函数 =====
const viewedEvent = ref<any>(null)
function viewEventDetail(evt: any) {
  viewedEvent.value = viewedEvent.value?.title === evt.title && viewedEvent.value?.round === evt.round ? null : evt
}
async function writeChronicle() {
  if (!chronicleText.value.trim() || chronicleWriting.value) return
  chronicleWriting.value = true
  const text = chronicleText.value.trim()
  try {
    await API.submitCommand({
      action: 'decree',
      params: { content: text, decree_type: 'chronicle' },
      faction_id: store.playerFactionId,
    })
    store.reputation = Math.min(100, store.reputation + 1)
    store.addEvent({
      event_id: `chronicle_${Date.now()}`, event_type: 'history', severity: 'major',
      round: store.currentRound, title: '御批国史',
      description: text, faction_id: store.playerFactionId, tile_id: '', effects: { culture_bonus: 2, reputation: 1 },
      narrative: text,
    })
    chronicleText.value = ''
    showToast('已载入国史', 'success')
  } catch {
    showToast('御批国史失败', 'error')
  } finally {
    chronicleWriting.value = false
  }
}
async function changeEraName() {
  const newEra = prompt('请输入新的年号：', cultureInfo.value.eraName)
  if (newEra && newEra.trim()) {
    const eraText = newEra.trim()
    try {
      await API.submitCommand({
        action: 'decree',
        params: { content: `改元「${eraText}」`, decree_type: 'era_change', new_era_name: eraText },
        faction_id: store.playerFactionId,
      })
      // 即时更新本地状态
      store.reputation = Math.min(100, store.reputation + 5)
      store.realmStability = Math.min(100, store.realmStability + 2)
      store.addEvent({
        event_id: `era_${Date.now()}`, event_type: 'history', severity: 'major',
        round: store.currentRound, title: '改元',
        description: `诏令天下，改年号为「${eraText}」。声望+5，民心+2。`,
        faction_id: store.playerFactionId, tile_id: '', effects: { reputation: 5, realm_stability: 2 },
        narrative: `天子昭告天下，改年号为「${eraText}」。百官朝贺，万民欢庆。`,
      })
      showToast(`已改元「${eraText}」`, 'success')
    } catch {
      showToast('改元失败', 'error')
    }
  }
}

function getStatClass(v: number): string {
  if (v >= 70) return 'stat-good'
  if (v >= 40) return 'stat-warn'
  return 'stat-bad'
}

function loyaltyColor(v: number): string {
  if (v >= 70) return '#5b8c5a'
  if (v >= 40) return '#b8963e'
  return '#c44b3c'
}

function getGradeLevel(g: string): string {
  if (g === '上上') return 'top'
  if (g === '中') return 'mid'
  if (g === '下') return 'low'
  if (g === '下下') return 'bottom'
  return 'mid'
}

// ===== 朝堂功能 =====

async function loadCourtData() {
  // 加载官员数据
  try {
    const result = await getFactionOfficials(store.playerFactionId)
    officialsData.value = result?.officials || []
  } catch { console.warn('加载官员数据失败') }
  // 加载国策数据（统一使用 API 层）
  try {
    policyData.value = await API.getPolicies()
  } catch {
    // 降级：尝试本地静态数据（提取内层 policies 对象以匹配 API 响应格式）
    try {
      const resp = await fetch('/data/policies.json')
      const raw = await resp.json()
      policyData.value = raw?.policies || raw  // 2026-07-15: 修正 fallback 数据结构
    } catch { console.warn('加载静态国策数据失败') }
  }
}

function isPolicyUnlocked(policyId: string): boolean {
  return playerFaction.value?.unlocked_policies?.includes(policyId) || false
}

function canUnlockPolicy(tier: any): boolean {
  if (!playerFaction.value) return false
  // 检查国库
  if ((playerFaction.value.treasury || 0) < tier.cost) return false
  // 检查前置
  if (tier.requires && tier.requires.length > 0) {
    for (const req of tier.requires) {
      if (!isPolicyUnlocked(req)) return false
    }
  }
  return true
}

function getLockReason(tier: any): string {
  if (!playerFaction.value) return '无势力'
  if ((playerFaction.value.treasury || 0) < tier.cost) return `银两不足`
  if (tier.requires && tier.requires.length > 0) {
    for (const req of tier.requires) {
      if (!isPolicyUnlocked(req)) return `需要前置国策`
    }
  }
  return '已锁定'
}

function effectLabel(key: string): string {
  const labels: Record<string, string> = {
    realm_stability: '民心', court_stability: '朝纲', grain_production: '粮产',
    population_growth: '人口增长', reputation: '声望', troop_power: '战力',
    morale_bonus: '士气', fortification_bonus: '城防', siege_defense: '守城',
    march_cost_reduction: '行军消耗', treasury_income: '税收', trade_income: '贸易收入',
    corruption_reduction: '反腐', development_speed: '发展速度', diplo_attitude_boost: '好感',
    spy_success_rate: '谍报成功率', naval_power: '水师战力', tax_efficiency: '征税效率',
    arms_production: '军械产量', grain_storage: '储粮', elite_troops_ratio: '精锐比例',
    siege_bonus: '攻城加成', garrison_cost_reduction: '驻军消耗', border_defense: '边境防御',
    march_speed: '行军速度', reinforce_speed: '援军速度', alliance_strength: '同盟强度',
    attitude_boost: '好感提升', coalition_leadership: '联邦领导力', ally_morale: '盟友士气',
    rare_goods: '奇珍异宝', naval_range: '航海范围', trade_protection: '贸易保护',
    intel_gathering: '情报收集', spy_discord_bonus: '离间加成', enemy_loyalty_penalty: '敌忠降',
    puppet_control: '傀儡控制', vassal_acceptance: '附庸接受', land_fertility: '土地肥力',
    famine_resistance: '抗灾', construction_speed: '建设速度', trade_goods: '贸易商品',
    trade_speed: '贸易速度', interest_income: '利息收入', flood_reduction: '防洪',
    plague_reduction: '防疫', culture_bonus: '文化', diplo_cost_reduction: '外交成本',
  }
  return labels[key] || key
}

async function unlockPolicy(tier: any) {
  if (!canUnlockPolicy(tier)) return
  try {
    const result = await apiUnlockPolicy({
      faction_id: store.playerFactionId,
      policy_id: tier.id,
      cost: tier.cost,
    })
    // 使用后端返回的最新数据更新本地状态
    const pf = playerFaction.value
    if (pf) {
      pf.unlocked_policies = result.unlocked_policies || [...(pf.unlocked_policies || []), tier.id]
      if (result.treasury_remaining !== undefined) {
        pf.treasury = result.treasury_remaining
      }
    }
    // 添加事件到大事记
    const effectText = buildPolicyEffectText(tier)
    store.addEvent({
      event_id: `policy_${tier.id}_${Date.now()}`,
      event_type: 'policy',
      severity: 'major',
      round: store.currentRound,
      title: `采纳国策：${tier.name}`,
      description: `花费银${tier.cost}两，采纳国策「${tier.name}」。${effectText}`,
      faction_id: store.playerFactionId,
      tile_id: '',
      effects: tier.effects || {},
      narrative: `${tier.description}。${effectText}`,
    })
    // Toast 提示
    showToast(`已采纳国策「${tier.name}」，花费银${tier.cost}两。${effectText}`, 'success')
    // 刷新国策状态
    await loadCourtData()
  } catch (e: any) {
    console.error('采纳国策失败:', e)
    showToast(`采纳国策失败：${e?.response?.data?.msg || e?.message || '未知错误'}`, 'error')
    // 重新加载以确保状态一致
    await loadCourtData()
  }
}

function buildPolicyEffectText(tier: any): string {
  if (!tier.effects) return ''
  const labels: Record<string, string> = {
    realm_stability: '民心',
    court_stability: '朝纲',
    reputation: '声望',
    development_level: '发展',
    tax_income: '税收',
    grain_output: '粮食产出',
    troop_morale: '士气',
    trade_income: '贸易收入',
  }
  return Object.entries(tier.effects)
    .map(([key, val]) => `${labels[key] || key}${Number(val) >= 0 ? '+' : ''}${val}`)
    .join('，')
}

async function appointOfficial() {
  if (!newOfficialName.value.trim() || !newOfficialPosition.value.trim()) return
  try {
    await apiAppointOfficial({
      faction_id: store.playerFactionId,
      name: newOfficialName.value.trim(),
      position: newOfficialPosition.value.trim(),
      ability: newOfficialAbility.value,
      loyalty: newOfficialLoyalty.value,
    })
    newOfficialName.value = ''
    newOfficialPosition.value = ''
    await loadCourtData()
  } catch { console.warn('任命官员失败') }
}

async function dismissOfficer(officialId: string) {
  try {
    await apiDismissOfficial(officialId)
    await loadCourtData()
  } catch { console.warn('罢免官员失败') }
}

async function executeOfficer(officialId: string) {
  try {
    await apiExecuteOfficial(officialId)
    await loadCourtData()
  } catch { console.warn('处决官员失败') }
}

async function publishDecree() {
  if (!decreeText.value.trim()) return
  const decreeContent = decreeText.value.trim()
  try {
    const result = await apiIssueDecree({
      faction_id: store.playerFactionId,
      text: decreeContent,
    })
    // 使用后端返回的敕令数据更新本地列表
    if (result.decree) {
      store.decrees.push({
        id: result.decree.id,
        title: result.decree.text,
        round: result.decree.round,
        year: result.decree.year,
        month: result.decree.month,
      })
    }
    // 添加事件到大事记
    store.addEvent({
      event_id: `decree_${result.decree?.id || Date.now()}`,
      event_type: 'decree',
      severity: 'major',
      round: store.currentRound,
      title: '颁布敕令',
      description: decreeContent,
      faction_id: store.playerFactionId,
      tile_id: '',
      effects: {},
      narrative: `天子颁布敕令：${decreeContent}`,
    })
    // Toast 提示
    showToast(`敕令已颁布：${decreeContent.slice(0, 30)}${decreeContent.length > 30 ? '...' : ''}`, 'success')
    decreeText.value = ''
  } catch (e: any) {
    console.error('颁布敕令失败:', e)
    showToast(`颁布敕令失败：${e?.response?.data?.msg || e?.message || '未知错误'}`, 'error')
  }
}

function issueDecree() {
  courtTab.value = 'decrees'
}

function openCourtDebate() {
  refreshCourtData()
  // 触发 AdvisorPanel 的廷议模式
  const event = new CustomEvent('open-court-debate', { detail: {} })
  window.dispatchEvent(event)
}

function getStance(fid: string): string {
  if (fid === store.playerFactionId) return 'self'
  // 从 relations 中查找真实外交姿态
  const rel = findRelation(fid)
  return rel?.stance || 'neutral'
}

function getStanceLabel(fid: string): string {
  if (fid === store.playerFactionId) return '本朝'
  const stances: Record<string, string> = {
    war: '交战', neutral: '中立', truce: '停战', alliance: '同盟', vassal: '附庸', self: '本朝',
  }
  return stances[getStance(fid)] || '中立'
}

// ===== 外交操作 =====
const diploCosts: Record<string, { cost: number; costType: string; gainLabel: string; label: string }> = {
  tribute: { cost: 500, costType: '银', gainLabel: '好感+10', label: '纳贡' },
  alliance: { cost: 800, costType: '银', gainLabel: '缔结同盟', label: '结盟' },
  trade: { cost: 200, costType: '银', gainLabel: '+100银/回合', label: '通商' },
  marriage: { cost: 500, costType: '银', gainLabel: '好感+25,声望+5', label: '联姻' },
  truce: { cost: 300, costType: '银', gainLabel: '停战和好', label: '停战' },
  war: { cost: 10, costType: '声望', gainLabel: '宣战攻伐', label: '宣战' },
  vassal_offer: { cost: 1000, costType: '银', gainLabel: '建立附庸', label: '提议附庸' },
  vassal_cancel: { cost: 200, costType: '银', gainLabel: '解除附庸', label: '取消附庸' },
  trade_close: { cost: 0, costType: '银', gainLabel: '终止通商', label: '关闭贸易' },
  hostage: { cost: 300, costType: '银', gainLabel: '好感+15', label: '派遣质子' },
  hostage_recall: { cost: 0, costType: '声望', gainLabel: '关系-25', label: '召回质子' },
  annex: { cost: 5000, costType: '银', gainLabel: '合并领土', label: '吞并附庸' },
}

async function doDiplomacy(targetFactionId: string, dipType: string) {
  const targetFaction = store.livingFactions.find(f => f.faction_id === targetFactionId)
  const targetName = targetFaction?.name || targetFactionId

  // P1 高级外交功能 - 直接调用专用API
  if (dipType === 'hostage') {
    try {
      const result = await sendHostage(store.playerFactionId, targetFactionId)
      const data = result?.data || result
      if (data?.success) {
        showToast(data.message || '质子已派遣', 'success')
        diploFeedback.value = { text: `已向「${targetName}」派遣质子，关系+15。`, type: 'success' }
        await store.refreshWorldState()
      } else {
        showToast(data?.message || data?.msg || '派遣质子失败', 'error')
        diploFeedback.value = { text: `派遣质子失败：${data?.message || data?.msg}`, type: 'error' }
      }
    } catch { showToast('派遣质子失败', 'error') }
    if (diploTimer.value) clearTimeout(diploTimer.value)
    diploTimer.value = setTimeout(() => { diploFeedback.value = { text: '', type: '' } }, 5000)
    return
  }
  if (dipType === 'hostage_recall') {
    try {
      const result = await recallHostage(store.playerFactionId, targetFactionId)
      const data = result?.data || result
      if (data?.success) {
        showToast(data.message || '质子已召回', 'success')
        diploFeedback.value = { text: `已从「${targetName}」召回质子，关系-25。`, type: 'warn' }
        await store.refreshWorldState()
      } else {
        showToast(data?.message || data?.msg || '召回质子失败', 'error')
        diploFeedback.value = { text: `召回质子失败：${data?.message || data?.msg}`, type: 'error' }
      }
    } catch { showToast('召回质子失败', 'error') }
    if (diploTimer.value) clearTimeout(diploTimer.value)
    diploTimer.value = setTimeout(() => { diploFeedback.value = { text: '', type: '' } }, 5000)
    return
  }
  if (dipType === 'annex') {
    try {
      const result = await annexVassal(store.playerFactionId, targetFactionId)
      const data = result?.data || result
      if (data?.success) {
        showToast(data.message || '吞并成功！', 'success')
        diploFeedback.value = { text: `已吞并附庸「${targetName}」！`, type: 'success' }
        await store.refreshWorldState()
      } else {
        showToast(data?.message || data?.msg || '吞并失败', 'error')
        diploFeedback.value = { text: `吞并失败：${data?.message || data?.msg}`, type: 'error' }
      }
    } catch { showToast('吞并附庸失败', 'error') }
    if (diploTimer.value) clearTimeout(diploTimer.value)
    diploTimer.value = setTimeout(() => { diploFeedback.value = { text: '', type: '' } }, 5000)
    return
  }



  // 原有外交功能
  const info = diploCosts[dipType]
  if (!info) return

  // 检查资源
  if (info.costType === '银' && (playerFaction.value?.treasury || 0) < info.cost) {
    diploFeedback.value = { text: `银两不足！${info.label}需要银${info.cost}两，现有银${playerFaction.value?.treasury || 0}两。`, type: 'error' }
    showToast(`银两不足：需要${info.cost}两`, 'error')
    return
  }
  if (info.costType === '声望' && (playerFaction.value?.reputation || 0) < info.cost) {
    diploFeedback.value = { text: `声望不足！${info.label}需要声望${info.cost}。`, type: 'error' }
    showToast('声望不足', 'error')
    return
  }

  // 单方面行动（无需对方同意，直接调用外交API即刻执行）
  const unilateralActions = ['war', 'tribute', 'vassal_cancel', 'trade_close']
  if (unilateralActions.includes(dipType)) {
    try {
      const apiResp = await apiClient.post('/diplomacy/action', {
        faction_id: store.playerFactionId,
        target_faction: targetFactionId,
        action_type: dipType,
        action: dipType,
      })
      const result = apiResp?.data?.data || apiResp?.data || apiResp
      if (result?.success === false || result?.status === 'rejected') {
        diploFeedback.value = { text: `${info.label}失败：${result?.message || '操作被拒绝'}`, type: 'error' }
        showToast(`${info.label}失败`, 'error')
      } else {
        const costText = info.costType === '声望' ? `声望${info.cost}` : `银${info.cost}两`
        diploFeedback.value = { text: `已向「${targetName}」${info.label}（消耗${costText}，${info.gainLabel}）。`, type: 'success' }
        showToast(`已向「${targetName}」${info.label}`, 'success')
        await store.refreshWorldState()
      }
    } catch (e: any) {
      diploFeedback.value = { text: `${info.label}失败：${e?.message || '服务异常'}`, type: 'error' }
      showToast(`${info.label}失败`, 'error')
    }
    if (diploTimer.value) clearTimeout(diploTimer.value)
    diploTimer.value = setTimeout(() => { diploFeedback.value = { text: '', type: '' } }, 5000)
    return
  }

  // 双方行动（需对方同意，通过AI判定+即刻执行）
  const needsApproval = ['alliance', 'truce', 'trade', 'marriage', 'vassal_offer']
  if (needsApproval.includes(dipType)) {
    try {
      const aiResp = await apiClient.post('/diplomacy/action', {
        faction_id: store.playerFactionId,
        target_faction: targetFactionId,
        action_type: dipType,
        action: dipType,
      })
      const aiResponse = aiResp?.data?.data || aiResp?.data || aiResp

      if (aiResponse?.success === false || aiResponse?.status === 'rejected') {
        diploFeedback.value = {
          text: `「${targetName}」拒绝了${info.label}提议：${aiResponse?.message || '对方无意接受'}`,
          type: 'error',
        }
        showToast(`${targetName}拒绝了${info.label}`, 'error')
        if (diploTimer.value) clearTimeout(diploTimer.value)
        diploTimer.value = setTimeout(() => { diploFeedback.value = { text: '', type: '' } }, 5000)
        return
      }

      // AI接受，操作已通过API即刻执行
      const costText = info.costType === '声望' ? `声望${info.cost}` : `银${info.cost}两`
      const aiReason = aiResponse?.ai_reason ? `（${aiResponse.ai_reason}）` : ''
      diploFeedback.value = {
        text: `「${targetName}」同意了${info.label}${aiReason}（消耗${costText}）。`,
        type: 'success',
      }
      showToast(`${targetName}同意了${info.label}`, 'success')
      await store.refreshWorldState()

      // 加入事件记录
      store.addEvent({
        event_id: `diplo_${dipType}_${Date.now()}`,
        event_type: 'diplomacy',
        severity: 'major',
        round: store.currentRound,
        title: `外交：${targetName}同意了${info.label}`,
        description: `消耗${costText}，${targetName}同意了${info.label}提案。`,
        faction_id: store.playerFactionId,
        tile_id: '',
        effects: { diplomacy_type: dipType, target: targetFactionId },
        narrative: `天子向「${targetName}」提出${info.label}，对方应允。耗费${costText}。`,
      })

    } catch (aiErr) {
      // AI判定失败，降级：使用 submitCommand 排队
      console.warn('AI外交判定失败，降级为指令排队:', aiErr)
      await store.submitCommand('diplomacy', {
        target_faction: targetFactionId,
        diplomacy_type: dipType,
      })
      const costText = info.costType === '声望' ? `声望${info.cost}` : `银${info.cost}两`
      diploFeedback.value = {
        text: `已下旨：向「${targetName}」${info.label}（消耗${costText}，${info.gainLabel}），将在回合推进时执行。`,
        type: 'success',
      }
      showToast(`已向「${targetName}」${info.label}`, 'success')

      store.addEvent({
        event_id: `diplo_${dipType}_${Date.now()}`,
        event_type: 'diplomacy',
        severity: dipType === 'war' ? 'critical' : 'major',
        round: store.currentRound,
        title: `外交：向${targetName}${info.label}`,
        description: `消耗${costText}，向${targetName}${info.label}。预期收益：${info.gainLabel}。`,
        faction_id: store.playerFactionId,
        tile_id: '',
        effects: { diplomacy_type: dipType, target: targetFactionId },
        narrative: `天子下旨向「${targetName}」${info.label}，耗费${costText}。`,
      })
    }
    if (diploTimer.value) clearTimeout(diploTimer.value)
    diploTimer.value = setTimeout(() => { diploFeedback.value = { text: '', type: '' } }, 5000)
    return
  }


  // 兜底：通过 submitCommand 排队执行（不常见的情况）
  try {
    await store.submitCommand('diplomacy', {
      target_faction: targetFactionId,
      diplomacy_type: dipType,
    })

    const costText = info.costType === '声望' ? `声望${info.cost}` : `银${info.cost}两`
    diploFeedback.value = {
      text: `已下旨：向「${targetName}」${info.label}（消耗${costText}，${info.gainLabel}），将在回合推进时执行。`,
      type: 'success',
    }
    showToast(`已向「${targetName}」${info.label}`, 'success')

    store.addEvent({
      event_id: `diplo_${dipType}_${Date.now()}`,
      event_type: 'diplomacy',
      severity: dipType === 'war' ? 'critical' : 'major',
      round: store.currentRound,
      title: `外交：向${targetName}${info.label}`,
      description: `消耗${costText}，向${targetName}${info.label}。预期收益：${info.gainLabel}。`,
      faction_id: store.playerFactionId,
      tile_id: '',
      effects: { diplomacy_type: dipType, target: targetFactionId },
      narrative: `天子下旨向「${targetName}」${info.label}，耗费${costText}。`,
    })
  } catch (e: any) {
    diploFeedback.value = { text: `${info.label}失败：${e?.message || '未知错误'}`, type: 'error' }
    showToast(`${info.label}失败`, 'error')
  }

  if (diploTimer.value) clearTimeout(diploTimer.value)
  diploTimer.value = setTimeout(() => { diploFeedback.value = { text: '', type: '' } }, 5000)
}

function getAttitude(fid: string): number {
  const rel = findRelation(fid)
  return rel?.attitude || 50
}

function findRelation(fid: string): any {
  const rels = store.relations
  if (!rels) return null
  // 后端 relation_key 使用 "|" 拼接：fid_a|fid_b
  const pid = store.playerFactionId
  const key1 = `${pid}|${fid}`
  const key2 = `${fid}|${pid}`
  if (rels[key1]) return rels[key1]
  if (rels[key2]) return rels[key2]
  // 遍历查找（兼容 faction_a/faction_b 字段格式）
  for (const [key, val] of Object.entries(rels)) {
    if (typeof val === 'object' && val) {
      const r = val as any
      if ((r.faction_a === pid && r.faction_b === fid) || (r.faction_a === fid && r.faction_b === pid)) {
        return r
      }
    }
  }
  return null
}

async function runStrategyAnalysis() {
  if (!playerFaction.value) return
  aiLoading.value = true
  try {
    const result = await strategyAnalyze({
      faction_id: store.playerFactionId,
      faction_name: playerFaction.value.name,
      turn: store.currentRound,
      season: store.currentSeason,
      tile_count: store.playerTiles.length,
      troops: store.totalTroops,
      treasury: playerFaction.value.treasury,
      reputation: playerFaction.value.reputation,
    })
    aiResult.value = result
  } catch {
    console.warn('策略分析失败')
    aiResult.value = {
      threats: '谋士暂时无法推演（AI服务未就绪）。',
      opportunities: '请稍后再试。',
      recommendations: '可先手动操作，等待AI服务恢复。',
    }
  } finally {
    aiLoading.value = false
  }
}

// 组件卸载时清理定时器
onUnmounted(() => {
  if (buildTimer.value) clearTimeout(buildTimer.value)
  if (diploTimer.value) clearTimeout(diploTimer.value)
})
</script>

<style scoped>
.float-panel {
  position: fixed;
  z-index: 2000;
  overflow: hidden;
  max-width: 90vw;
}

.fp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-light);
  background: linear-gradient(180deg, var(--bg-hover) 0%, var(--border-main) 100%);
  position: relative;
}
/* 卷轴边框装饰：所有面板标题栏底部 */
.fp-header::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 4px;
  background: url('/assets/ui/ai_ui_scroll_border.png') center/cover no-repeat;
  opacity: 0.25;
  pointer-events: none;
}

.fp-header h3 {
  font-size: 15px;
  font-weight: normal;
  color: var(--text-main);
  letter-spacing: 2px;
}

.fp-close {
  width: 24px;
  height: 24px;
  border: none;
  background: none;
  font-size: 16px;
  cursor: pointer;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.fp-close:hover { color: #8b0000; }

/* === UI装饰：军事面板战旗 === */
.fp-header-deco {
  margin-right: 8px;
  display: flex;
  align-items: center;
}
.fp-war-banner {
  width: 36px;
  height: 36px;
  object-fit: contain;
  opacity: 0.7;
  filter: drop-shadow(0 0 4px rgba(180, 120, 40, 0.3));
}
/* === UI装饰：邸报面板印章 === */
.fp-seal-stamp {
  width: 32px;
  height: 32px;
  object-fit: contain;
  opacity: 0.6;
  flex-shrink: 0;
}
/* === UI装饰：面板身体云纹底纹 === */
.fp-body {
  padding: 12px 16px;
  position: relative;
}
.fp-body::before {
  content: '';
  position: absolute;
  inset: 0;
  background: url('/assets/ui/ai_ui_cloud_bg.png') center/200px repeat;
  opacity: 0.03;
  pointer-events: none;
  z-index: 0;
}

.kv-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px dotted var(--border-light);
  font-size: 13px;
}

.kv-row.small {
  font-size: 12px;
}

.kv-label {
  color: var(--text-secondary);
}

.kv-value {
  color: var(--text-main);
  font-weight: bold;
}

.kv-divider {
  height: 1px;
  background: var(--border-light);
  margin: 10px 0;
}

.gold-text { color: #b8860b; }
.grain-text { color: #5b8c5a; }
.troop-text { color: #c44b3c; }
.disaster-text { color: #c44b3c; }
.stat-good { color: #5b8c5a; }
.stat-warn { color: #c9a94e; }
.stat-bad { color: #c44b3c; }

.section-subtitle {
  font-size: 13px;
  font-weight: normal;
  color: var(--text-secondary);
  letter-spacing: 2px;
  margin-bottom: 6px;
}

/* 军事面板操作 */
.military-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.military-actions .btn-small {
  flex: 1;
  min-width: 80px;
}

.empty-note {
  text-align: center;
  padding: 16px;
  color: var(--text-dim);
  font-size: 12px;
  letter-spacing: 2px;
}

.empty-note.warn {
  color: #d4a040;
  background: rgba(184, 150, 62, 0.06);
  border-radius: 4px;
  border: 1px solid rgba(184, 150, 62, 0.15);
}

/* 叛军卡片 */
.rebel-card {
  padding: 10px 12px;
  margin-bottom: 8px;
  background: rgba(180, 60, 50, 0.12);
  border: 1px solid rgba(180, 60, 50, 0.3);
  border-radius: 3px;
}

.rebel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.rebel-leader {
  font-size: 14px;
  font-weight: bold;
  color: #d44;
}

.rebel-cause {
  font-size: 10px;
  color: #a08070;
  background: rgba(200, 80, 60, 0.15);
  padding: 1px 6px;
  border-radius: 2px;
}

.rebel-stats {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #b0a090;
  margin-bottom: 8px;
}

.rebel-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.input-tiny {
  padding: 4px 8px;
  font-size: 12px;
  background: rgba(0,0,0,0.3);
  border: 1px solid rgba(139, 115, 85, 0.4);
  border-radius: 2px;
  color: #eae3d6;
  font-family: "SimSun", serif;
}

/* 俘虏列表 */
.prisoner-item {
  padding: 8px 0;
  border-bottom: 1px dotted rgba(139, 115, 85, 0.2);
}

.prisoner-actions {
  display: flex;
  gap: 4px;
  margin-top: 4px;
}

.btn-tiny {
  padding: 2px 8px;
  font-size: 11px;
  background: rgba(60, 40, 20, 0.6);
  border: 1px solid rgba(160, 130, 90, 0.3);
  color: #c4bcae;
  cursor: pointer;
  border-radius: 2px;
  font-family: "SimSun", serif;
  transition: all 0.15s;
}

.btn-tiny:hover {
  background: rgba(184, 155, 104, 0.2);
  border-color: rgba(184, 155, 104, 0.5);
  color: #eae3d6;
}

.input-select {
  padding: 4px 8px;
  font-size: 12px;
  background: rgba(0,0,0,0.3);
  border: 1px solid rgba(139, 115, 85, 0.4);
  border-radius: 2px;
  color: #eae3d6;
  font-family: "SimSun", serif;
  min-width: 140px;
}

.input-select option {
  background: #2a1f14;
  color: #eae3d6;
}

/* 势力卡片 */
.faction-card {
  padding: 8px 10px;
  margin-bottom: 6px;
  background: rgba(240, 228, 204, 0.6);
  border-left: 3px solid;
  border-radius: 2px;
}

.faction-card.is-player {
  background: rgba(201, 169, 78, 0.08);
}

.fc-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.fc-name {
  font-size: 15px;
  font-weight: bold;
}

.fc-title {
  font-size: 11px;
  color: var(--text-secondary);
}

.fc-badge {
  font-size: 10px;
  padding: 1px 6px;
  background: rgba(139, 0, 0, 0.12);
  color: #8b0000;
  border: 1px solid rgba(139, 0, 0, 0.3);
  border-radius: 2px;
}

/* 情报未知标记 */
.fc-intel-tag {
  font-size: 10px;
  padding: 1px 6px;
  background: rgba(100, 100, 100, 0.15);
  color: #888;
  border: 1px solid rgba(100, 100, 100, 0.25);
  border-radius: 2px;
  margin-left: 6px;
}

.fc-intel-hint {
  font-size: 10px;
  color: #999;
  font-style: italic;
  margin-left: 4px;
}

.fc-stats-unknown {
  color: #777 !important;
}

.faction-card.intel-hidden {
  opacity: 0.85;
  background: rgba(60, 60, 60, 0.08);
}

.fc-stats {
  font-size: 11px;
  color: var(--text-dim);
  margin-top: 4px;
}

.fc-stance {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 2px;
}

.stance-neutral { background: rgba(139, 115, 85, 0.1); color: var(--text-secondary); }
.stance-self { background: rgba(139, 0, 0, 0.1); color: #8b0000; }
.stance-war { background: rgba(220, 20, 60, 0.1); color: #DC143C; }
.stance-alliance { background: rgba(91, 140, 90, 0.1); color: #5b8c5a; }
.stance-truce { background: rgba(201, 169, 78, 0.1); color: #c9a94e; }
.stance-vassal { background: rgba(147, 112, 219, 0.1); color: #9370DB; }

/* 外交操作按钮 */
.diplo-actions {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 4px;
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px dotted var(--border-light);
}

.diplo-act-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 4px;
  font-size: 10px;
  font-family: "SimSun", serif;
  background: rgba(240, 228, 204, 0.15);
  border: 1px solid var(--border-light);
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 3px;
  transition: all 0.15s;
  text-align: center;
}

.diplo-act-btn:hover:not(:disabled) {
  background: rgba(184, 155, 104, 0.12);
  border-color: var(--gold);
  color: var(--text-main);
}

.diplo-act-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.diplo-act-btn.danger-act {
  border-color: rgba(220, 20, 60, 0.3);
  background: rgba(220, 20, 60, 0.06);
}

.diplo-act-btn.danger-act:hover:not(:disabled) {
  background: rgba(220, 20, 60, 0.12);
  border-color: #DC143C;
  color: #DC143C;
}

.dab-icon { font-size: 15px; }
.dab-label { font-size: 10px; font-weight: bold; letter-spacing: 1px; }
.dab-cost { font-size: 9px; color: #E07060; }
.dab-gain { font-size: 9px; color: #81C784; }

/* 外交资源栏 */
.diplo-res-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
}

.diplo-res-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 6px 4px;
  background: rgba(240, 228, 204, 0.12);
  border-radius: 3px;
  border: 1px solid rgba(139, 115, 85, 0.15);
}

.diplo-res-icon { font-size: 14px; }
.diplo-res-val { font-size: 15px; font-weight: bold; color: #D4C490; }
.diplo-res-lbl { font-size: 10px; color: #8B7B6B; margin-top: 2px; }

.diplo-card {
  margin-bottom: 8px;
  padding-bottom: 4px;
}

.fc-tags {
  display: flex;
  gap: 4px;
  margin-top: 4px;
  flex-wrap: wrap;
}

.fc-tag {
  font-size: 10px;
  padding: 1px 6px;
  background: rgba(139, 115, 85, 0.08);
  color: var(--text-secondary);
  border-radius: 2px;
}

/* 外交推荐 */
.diplo-rec-section {
  margin-bottom: 8px;
}

.diplo-rec-item {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 5px 8px;
  margin-bottom: 4px;
  background: rgba(240, 228, 204, 0.06);
  border-radius: 3px;
  border-left: 3px solid #8B7B6B;
}

.diplo-rec-item.rec-high {
  border-left-color: #C44B3C;
  background: rgba(196, 75, 60, 0.06);
}

.diplo-rec-item.rec-medium {
  border-left-color: #C9A94E;
  background: rgba(201, 169, 78, 0.06);
}

.diplo-rec-item.rec-low {
  border-left-color: #5B8C5A;
  background: rgba(91, 140, 90, 0.06);
}

.rec-priority {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  font-size: 10px;
  font-weight: bold;
  border-radius: 2px;
  color: #fff;
  background: #8B7B6B;
  flex-shrink: 0;
}

.rec-priority.high { background: #C44B3C; }
.rec-priority.medium { background: #C9A94E; }
.rec-priority.low { background: #5B8C5A; }

.rec-text {
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.diplo-quick-links {
  margin-bottom: 4px;
}

.diplo-quick-links .btn-small {
  background: rgba(139, 115, 85, 0.1);
  border: 1px solid rgba(139, 115, 85, 0.2);
  color: #C9A94E;
  font-family: "STKaiti","KaiTi",serif;
  letter-spacing: 2px;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: 3px;
  font-size: 13px;
  transition: all 0.2s;
}

.diplo-quick-links .btn-small:hover {
  background: rgba(139, 115, 85, 0.2);
  color: #D4C490;
}

.policy-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.policy-tag {
  font-size: 11px;
  padding: 2px 8px;
  background: rgba(91, 140, 90, 0.1);
  color: #5b8c5a;
  border: 1px solid rgba(91, 140, 90, 0.2);
  border-radius: 2px;
}

/* 建造选项 */
.build-options {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.build-option {
  display: flex;
  justify-content: space-between;
  padding: 6px 10px;
  font-size: 12px;
  background: rgba(240, 228, 204, 0.5);
  border-radius: 2px;
  cursor: pointer;
  transition: background 0.15s;
}

.build-option:hover {
  background: rgba(201, 169, 78, 0.1);
}

.build-option .cost {
  color: var(--text-dim);
  font-size: 11px;
}

/* 建造地块选择器 */
.build-tile-select {
  width: 100%;
  padding: 6px 8px;
  background: var(--bg-card);
  border: 1px solid var(--border-dim);
  color: var(--text);
  font-family: "SimSun", serif;
  font-size: 12px;
  border-radius: 4px;
  outline: none;
  cursor: pointer;
}

.build-tile-select:focus {
  border-color: var(--gold);
}

/* 建造反馈 */
.build-feedback {
  padding: 8px 10px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.5;
  font-family: "SimSun", serif;
}

.build-feedback.success {
  background: rgba(76, 175, 80, 0.15);
  color: #81c784;
  border: 1px solid rgba(76, 175, 80, 0.3);
}

.build-feedback.error {
  background: rgba(244, 67, 54, 0.15);
  color: #e57373;
  border: 1px solid rgba(244, 67, 54, 0.3);
}

/* 建筑卡片网格 */
.building-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin-top: 6px;
}

.building-card {
  background: rgba(139, 115, 85, 0.06);
  border: 1px solid rgba(139, 115, 85, 0.15);
  border-radius: 4px;
  padding: 8px;
  transition: border-color 0.2s;
}

.building-card:hover {
  border-color: var(--gold);
}

.building-card.building-owned {
  border-color: rgba(76, 175, 80, 0.3);
  background: rgba(76, 175, 80, 0.06);
}

.building-card.building-locked {
  opacity: 0.5;
  pointer-events: none;
}

.bc-header {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 4px;
}

.bc-icon {
  font-size: 16px;
}

.bc-name {
  font-size: 13px;
  font-weight: bold;
  color: var(--text);
}

.bc-level {
  font-size: 10px;
  padding: 1px 5px;
  background: rgba(76, 175, 80, 0.15);
  color: #81c784;
  border-radius: 2px;
  margin-left: auto;
}

.bc-level.bc-none {
  background: rgba(139, 115, 85, 0.1);
  color: var(--text-dim);
}

.bc-effect {
  font-size: 10px;
  color: var(--text-dim);
  line-height: 1.4;
  margin-bottom: 4px;
}

.bc-cost {
  font-size: 10px;
  margin-bottom: 4px;
}

.bc-cost .cost-label {
  color: var(--text-dim);
}

.bc-cost .cost-value {
  color: var(--gold);
  font-weight: bold;
}

.bc-cost .cost-req {
  color: var(--text-secondary);
  font-size: 9px;
}

.bc-current-effect {
  font-size: 9px;
  color: #81C784;
  margin-bottom: 4px;
  padding: 2px 4px;
  background: rgba(91, 140, 90, 0.06);
  border-radius: 2px;
}

.bce-label { color: #6B8B6A; }
.bce-value { color: #81C784; }

.bc-locked-hint {
  font-size: 10px;
  color: #e57373;
  margin-bottom: 4px;
}

.bc-btn {
  width: 100%;
  font-size: 11px;
}

/* AI推演 */
.ai-loading {
  text-align: center;
  padding: 24px;
  color: var(--text-secondary);
  font-size: 13px;
  letter-spacing: 2px;
}

.loading-spinner {
  display: inline-block;
  animation: spin 1.5s linear infinite;
  font-size: 20px;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.ai-section {
  margin-bottom: 12px;
}

.ai-section h5 {
  font-size: 13px;
  font-weight: bold;
  color: var(--text-main);
  margin-bottom: 4px;
  letter-spacing: 2px;
}

.ai-section p {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.btn-small {
  padding: 6px 16px;
  font-size: 12px;
  font-family: "SimSun", serif;
  background: linear-gradient(180deg, var(--bg-card) 0%, var(--bg-card) 100%);
  border: 1px solid #c9a94e;
  color: var(--text-main);
  cursor: pointer;
  border-radius: 2px;
  letter-spacing: 2px;
}

.btn-small:hover {
  background: linear-gradient(180deg, var(--bg-card) 0%, var(--bg-hover) 100%);
}

/* 律法 */
.law-refs {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.law-ref {
  padding: 6px 10px;
  font-size: 12px;
  color: var(--text-secondary);
  background: rgba(240, 228, 204, 0.5);
  border-radius: 2px;
  cursor: pointer;
}

.law-ref:hover {
  background: rgba(139, 115, 85, 0.1);
}

.law-ref.disabled {
  opacity: 0.4;
  cursor: not-allowed;
  pointer-events: none;
}

/* 律法：选中囚犯 */
.law-selected-prisoner {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  background: rgba(139, 115, 85, 0.15);
  border-radius: 4px;
  margin-bottom: 4px;
}
.law-selected-prisoner .ls-label { font-size: 11px; color: var(--text-secondary); }
.law-selected-prisoner .ls-name { font-weight: 600; color: var(--accent-gold); }
.law-selected-prisoner .ls-from { font-size: 11px; color: var(--text-secondary); }

/* 律法：囚犯选择列表 */
.prisoner-select-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
  max-height: 160px;
  overflow-y: auto;
}
.prisoner-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 8px;
  font-size: 12px;
  border-radius: 3px;
  cursor: pointer;
  background: rgba(240, 228, 204, 0.3);
  transition: background 0.15s;
}
.prisoner-row:hover { background: rgba(139, 115, 85, 0.1); }
.prisoner-row.selected { background: rgba(139, 115, 85, 0.2); border: 1px solid var(--accent-gold); }
.prisoner-row .pr-select-mark { margin-left: auto; font-size: 14px; }

/* 律法：结果提示 */
.law-result {
  margin-top: 8px;
  padding: 6px 10px;
  font-size: 12px;
  border-radius: 3px;
}
.law-result.success { background: rgba(76, 175, 80, 0.15); color: #66bb6a; }
.law-result.error { background: rgba(244, 67, 54, 0.15); color: #ef5350; }

/* 工坊列表 */
.workshop-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.workshop-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  font-size: 12px;
  border-bottom: 1px dotted var(--border-light);
}

.ws-name {
  color: var(--text-main);
  font-weight: bold;
  flex: 1;
}

.ws-tag {
  font-size: 10px;
  padding: 1px 6px;
  background: rgba(91, 140, 90, 0.1);
  color: #5b8c5a;
  border-radius: 2px;
}

/* 工坊：详情条目 */
.workshop-item-detail {
  padding: 6px 8px;
  border: 1px solid var(--border-light);
  border-radius: 4px;
  margin-bottom: 4px;
  background: rgba(240, 228, 204, 0.2);
}
.workshop-item-detail .ws-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.workshop-item-detail .ws-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

/* 工坊：产量总览 */
.workshop-summary {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}
.ws-summary-item {
  flex: 1;
  text-align: center;
  padding: 8px 4px;
  background: rgba(240, 228, 204, 0.3);
  border-radius: 4px;
}
.ws-summary-label { display: block; font-size: 10px; color: var(--text-secondary); margin-bottom: 2px; }
.ws-summary-val { display: block; font-size: 13px; font-weight: 600; color: var(--accent-gold); }

/* 工坊：生产侧重 */
.workshop-focus-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  margin-bottom: 6px;
}
.ws-focus-btn {
  padding: 6px 8px;
  font-size: 11px;
  border: 1px solid var(--border-light);
  border-radius: 3px;
  background: rgba(240, 228, 204, 0.3);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}
.ws-focus-btn:hover { background: rgba(139, 115, 85, 0.15); }
.ws-focus-btn.active {
  border-color: var(--accent-gold);
  color: var(--accent-gold);
  background: rgba(200, 160, 80, 0.15);
  font-weight: 600;
}
.focus-result {
  margin-top: 6px;
  padding: 6px 10px;
  font-size: 12px;
  border-radius: 3px;
}
.focus-result.success { background: rgba(76, 175, 80, 0.15); color: #66bb6a; }

/* 藩镇卡片 */
.vassal-card {
  padding: 8px 10px;
  margin-bottom: 6px;
  border: 1px solid var(--border-light);
  border-left: 3px solid var(--border-light);
  border-radius: 4px;
  background: rgba(240, 228, 204, 0.2);
}
.vassal-card .vc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.vassal-card .vc-name { font-weight: 600; font-size: 13px; }
.vassal-card .vc-stats { font-size: 11px; color: var(--text-secondary); }
.vassal-card .vc-body { margin-bottom: 6px; }
.vassal-card .vc-loyalty { font-size: 11px; color: var(--text-secondary); }
.vassal-card .vc-actions {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.vassal-risk-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 0;
}
.tribute-item {
  display: flex;
  justify-content: space-between;
  padding: 3px 8px;
  font-size: 12px;
  border-bottom: 1px dotted var(--border-light);
}
.tribute-item .tribute-amount { color: var(--accent-gold); }

/* 囚犯列表 */
.prisoner-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.prisoner-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  font-size: 12px;
  border-bottom: 1px dotted var(--border-light);
}

.pr-name {
  color: var(--text-main);
  font-weight: bold;
}

.pr-from {
  color: var(--text-dim);
  font-size: 11px;
  flex: 1;
}

.pr-status {
  font-size: 10px;
  padding: 1px 6px;
  background: rgba(201, 169, 78, 0.1);
  color: var(--gold);
  border-radius: 2px;
}

/* 操作按钮 */
.action-btns {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}

.animate-fade-in {
  animation: fadeIn 0.25s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 邸报事件面板 */
.generated-events {
  padding: 12px;
  background: rgba(184, 155, 104, 0.04);
  border: 1px solid rgba(184, 155, 104, 0.12);
  border-radius: var(--radius-sm);
}

.event-text {
  font-size: 13px;
  line-height: 1.9;
  color: var(--text-main);
  white-space: pre-wrap;
  font-family: "FangSong", "FangSong_GB2312", "SimSun", serif;
}

.event-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 8px;
  font-size: 12px;
  border-bottom: 1px dotted var(--border-light);
}

.evt-title {
  color: var(--gold-dim);
  font-weight: bold;
}

.evt-desc {
  color: var(--text-dim);
  font-size: 11px;
}

/* 律法审讯面板 */
.prisoner-select {
  padding: 6px 8px;
  cursor: pointer;
  border-bottom: 1px dotted var(--border-light);
  transition: background var(--duration-fast);
}

.prisoner-select:hover {
  background: rgba(184, 155, 104, 0.06);
}

.prisoner-select span {
  font-size: 12px;
  color: var(--text-dim);
}

.prisoner-select .pr-selected {
  color: var(--gold);
  font-weight: bold;
}

.interrogate-input-row {
  display: flex;
  gap: 6px;
  margin: 8px 0;
}

.interrogate-input {
  flex: 1;
  padding: 6px 10px;
  background: var(--bg-input);
  border: 1px solid var(--border-main);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-main);
  font-family: "FangSong", "FangSong_GB2312", serif;
}

.interrogate-input:focus {
  outline: none;
  border-color: var(--gold);
}

.interrogate-result {
  margin-top: 10px;
  padding: 10px;
  background: rgba(184, 155, 104, 0.04);
  border: 1px solid rgba(184, 155, 104, 0.1);
  border-radius: var(--radius-sm);
}

.ir-label {
  font-size: 11px;
  color: var(--gold-dim);
  margin-bottom: 6px;
}

.ir-content {
  font-size: 13px;
  color: var(--text-main);
  line-height: 1.8;
  white-space: pre-wrap;
}

/* 音效面板 */
.audio-btn {
  padding: 4px 14px;
  font-family: "FangSong", serif;
  font-size: 12px;
  background: rgba(184, 155, 104, 0.08);
  border: 1px solid rgba(184, 155, 104, 0.2);
  color: #8B7355;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.15s;
}
.audio-btn:hover { background: rgba(184, 155, 104, 0.15); color: #C9A94E; }
.audio-btn.active { background: rgba(184, 155, 104, 0.2); border-color: #C9A94E; color: #C9A94E; }

.audio-slider {
  width: 120px;
  height: 4px;
  -webkit-appearance: none;
  appearance: none;
  background: linear-gradient(90deg, #3A2E1E, #C9A94E);
  border-radius: 2px;
  outline: none;
}
.audio-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  background: #C9A94E;
  border-radius: 50%;
  cursor: pointer;
}

.audio-status {
  padding: 8px 10px;
  background: rgba(184, 155, 104, 0.04);
  border: 1px solid rgba(184, 155, 104, 0.1);
  border-radius: 3px;
}
.audio-status-row {
  display: flex;
  justify-content: space-between;
  padding: 2px 0;
}
.audio-status-label {
  font-size: 11px;
  color: #8B7B6B;
}
.audio-status-value {
  font-size: 11px;
  font-weight: bold;
}

.audio-controls {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}
.audio-controls .btn-small {
  flex: 1;
}

.audio-vol-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}
.audio-vol-label {
  font-size: 12px;
  color: #8B7B6B;
  min-width: 40px;
}
.audio-vol-pct {
  font-size: 11px;
  color: #C9A94E;
  min-width: 34px;
  text-align: right;
}

.bgm-track-list {
  margin-top: 6px;
  border: 1px solid rgba(184, 155, 104, 0.1);
  border-radius: 3px;
  overflow: hidden;
}
.bgm-track-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  cursor: pointer;
  transition: background 0.12s;
  border-bottom: 1px solid rgba(184, 155, 104, 0.06);
}
.bgm-track-item:last-child { border-bottom: none; }
.bgm-track-item:hover { background: rgba(184, 155, 104, 0.08); }
.bgm-track-item.active { background: rgba(201, 169, 78, 0.12); }
.bgm-track-icon {
  font-size: 12px;
  color: #C9A94E;
  min-width: 16px;
}
.bgm-track-item.active .bgm-track-icon { color: #FFD700; }
.bgm-track-name {
  flex: 1;
  font-size: 12px;
  color: #C8B898;
}
.bgm-track-item.active .bgm-track-name { color: #FFD700; }
.bgm-track-tag {
  font-size: 10px;
  color: #8B7355;
  background: rgba(184, 155, 104, 0.1);
  padding: 1px 6px;
  border-radius: 2px;
}

/* ===== AI智能体监控面板样式 ===== */
.agent-stats-row {
  display: flex; gap: 8px; margin-bottom: 14px;
}
.agent-stat-card {
  flex: 1; text-align: center;
  background: rgba(46,41,30,0.5);
  border: 1px solid rgba(120,100,60,0.2);
  border-radius: 4px; padding: 8px 4px;
}
.agent-stat-card.warn {
  border-color: rgba(192,64,40,0.4);
  background: rgba(192,64,40,0.08);
}
.agent-stat-val {
  font-size: 16px; font-weight: bold; color: #b89b68; letter-spacing: 1px;
}
.agent-stat-label {
  font-size: 10px; color: #6a5a3a; margin-top: 2px;
}

.agent-list-title {
  font-size: 12px; color: #8a7a5a; letter-spacing: 2px;
  margin-bottom: 8px; padding-bottom: 4px;
  border-bottom: 1px solid rgba(120,100,60,0.15);
}

.agent-list {
  display: flex; flex-direction: column; gap: 6px; margin-bottom: 14px;
}

.agent-card {
  background: rgba(30,27,20,0.6);
  border: 1px solid rgba(100,80,40,0.2);
  border-radius: 4px; padding: 8px 10px;
  transition: border-color 0.2s;
}
.agent-card:hover { border-color: rgba(120,100,50,0.4); }
.agent-card.degraded { border-color: rgba(192,64,40,0.5); background: rgba(192,64,40,0.06); }
.agent-card.disabled { opacity: 0.5; }

.agent-card-header {
  display: flex; align-items: center; gap: 6px; margin-bottom: 4px;
}
.agent-key {
  font-size: 11px; font-weight: bold; color: #b89b68;
  background: rgba(184,150,62,0.12); padding: 1px 5px; border-radius: 2px;
}
.agent-name {
  font-size: 13px; color: #c4b898;
}
.agent-model {
  font-size: 9px; color: #6a5a3a; margin-left: auto;
  background: rgba(100,80,40,0.15); padding: 1px 4px; border-radius: 2px;
}
.agent-trigger-badge {
  font-size: 9px; padding: 1px 5px; border-radius: 3px;
}
.agent-trigger-badge.auto { background: rgba(74,108,138,0.2); color: #6a9aaa; }
.agent-trigger-badge.manual { background: rgba(138,108,74,0.2); color: #aa9a6a; }
.agent-trigger-badge.both { background: rgba(74,138,74,0.2); color: #6aaa6a; }

.agent-card-body {
  font-size: 10px; color: #6a5a4a; line-height: 1.4; margin-bottom: 4px;
}
.agent-desc { }

.agent-card-stats {
  display: flex; gap: 10px; font-size: 10px; color: #6a5a3a;
}
.agent-circuit.CLOSED { color: #6a9a6a; }
.agent-circuit.OPEN { color: #c06050; font-weight: bold; }
.agent-circuit.HALF_OPEN { color: #ca9a4a; }

.agent-section-title {
  font-size: 12px; color: #8a7a5a; letter-spacing: 2px;
  margin-bottom: 6px; margin-top: 12px;
  padding-bottom: 4px;
  border-bottom: 1px solid rgba(120,100,60,0.15);
}

.agent-edict-item {
  display: flex; align-items: center; gap: 8px;
  padding: 3px 0; font-size: 10px;
  border-bottom: 1px solid rgba(100,80,40,0.06);
}
.agent-edict-round {
  color: #6a5a3a; white-space: nowrap;
}
.agent-edict-text {
  flex: 1; color: #8a7a5a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.agent-edict-result {
  color: #6a9a6a; white-space: nowrap; font-weight: bold;
}
.agent-edict-result.fail { color: #c06050; }

.fp-header-actions {
  display: flex; align-items: center; gap: 6px;
}
.btn-tiny {
  font-size: 10px; padding: 3px 8px;
  background: rgba(184,150,62,0.1);
  border: 1px solid rgba(184,150,62,0.2);
  color: #8a7a5a; cursor: pointer; border-radius: 3px;
}
.btn-tiny:hover { background: rgba(184,150,62,0.2); color: #b89b68; }
.btn-tiny:disabled { opacity: 0.4; cursor: not-allowed; }

/* ========== 领土面板样式 ========== */
.territory-tabs {
  display: flex; border-bottom: 1px solid var(--border-light);
}
.territory-tab {
  flex: 1; padding: 8px 0;
  background: transparent; border: none; border-bottom: 2px solid transparent;
  color: var(--text-secondary); font-size: 13px; letter-spacing: 2px;
  cursor: pointer; transition: all 0.2s;
}
.territory-tab:hover { color: var(--text-main); }
.territory-tab.active {
  color: #b8963e; border-bottom-color: #b8963e;
}

/* 统计卡 */
.territory-stat-cards {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px;
  margin-bottom: 14px;
}
.territory-stat-card {
  text-align: center;
  padding: 12px 6px;
  background: rgba(0,0,0,0.25);
  border: 1px solid rgba(184,150,62,0.08);
}
.tsc-val { font-size: 20px; color: #b8963e; font-weight: bold; }
.tsc-label { font-size: 10px; color: rgba(184,150,62,0.35); letter-spacing: 2px; margin-top: 3px; }

/* 分段标题 */
.territory-section { margin-bottom: 14px; }
.territory-section-title {
  font-size: 12px; color: rgba(184,150,62,0.45); letter-spacing: 3px;
  margin-bottom: 8px; padding-bottom: 4px;
  border-bottom: 1px solid rgba(184,150,62,0.08);
}

/* 都城卡 */
.capital-card {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; background: rgba(184,150,62,0.06);
  border: 1px solid rgba(184,150,62,0.15);
}
.capital-name { font-size: 15px; color: #e0d5b8; letter-spacing: 3px; }
.capital-id { font-size: 10px; color: rgba(184,150,62,0.3); }

/* 边境列表 */
.border-list { display: flex; flex-direction: column; gap: 4px; }
.border-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 6px 10px; background: rgba(0,0,0,0.2);
  border-left: 3px solid;
}
.border-faction { font-size: 13px; letter-spacing: 2px; }
.border-count { font-size: 11px; color: var(--text-secondary); }

/* 变更条目 */
.change-item {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 0; font-size: 12px;
}
.change-round { color: rgba(184,150,62,0.4); min-width: 36px; }
.change-tile { color: var(--text-main); }
.change-arrow { color: rgba(184,150,62,0.3); }
.change-result.gained { color: #5b8c5a; }
.change-result.lost { color: #c44b3c; }

/* 地区列表 */
.regions-list { display: flex; flex-direction: column; gap: 6px; }
.region-group { border: 1px solid rgba(184,150,62,0.06); }
.region-header {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px; cursor: pointer;
  background: rgba(0,0,0,0.2); transition: background 0.2s;
}
.region-header:hover { background: rgba(184,150,62,0.05); }
.region-arrow { font-size: 9px; color: rgba(184,150,62,0.35); transition: transform 0.25s; }
.region-arrow.expanded { transform: rotate(90deg); }
.region-name { font-size: 14px; color: #e0d5b8; letter-spacing: 2px; flex: 1; }
.region-count { font-size: 11px; color: #b8963e; }
.region-pop { font-size: 10px; color: rgba(184,150,62,0.3); }

.region-tiles { padding: 4px 0 4px 20px; }
.region-tile {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 8px; font-size: 12px; color: var(--text-secondary);
  border-bottom: 1px dotted rgba(184,150,62,0.04);
}
.region-tile.capital { background: rgba(184,150,62,0.05); }
.rt-icon { font-size: 10px; min-width: 16px; }
.rt-name { flex: 1; color: var(--text-main); }
.rt-type { font-size: 10px; color: rgba(184,150,62,0.3); }
.rt-troops { font-size: 10px; color: #c44b3c; }
.rt-fort { font-size: 10px; color: #6a5a3a; }

/* 变更记录 */
.changes-summary { margin-bottom: 10px; }
.changes-counts { display: flex; gap: 14px; font-size: 12px; }
.cc-gained { color: #5b8c5a; }
.cc-lost { color: #c44b3c; }
.cc-total { color: var(--text-secondary); }

.changes-list { display: flex; flex-direction: column; gap: 4px; }
.change-record {
  padding: 6px 10px; background: rgba(0,0,0,0.15);
  border-left: 3px solid rgba(184,150,62,0.2);
}
.cr-header { display: flex; align-items: center; gap: 8px; margin-bottom: 3px; }
.cr-round { font-size: 11px; color: rgba(184,150,62,0.4); }
.cr-type { font-size: 10px; padding: 1px 5px; border-radius: 2px; background: rgba(184,150,62,0.08); color: var(--text-secondary); letter-spacing: 1px; }
.cr-body { display: flex; align-items: center; gap: 6px; font-size: 13px; }
.cr-tile { color: var(--text-main); }
.cr-arrow { font-size: 11px; }
.cr-arrow.gained { color: #5b8c5a; }
.cr-arrow.lost { color: #c44b3c; }
.cr-arrow.neutral { color: var(--text-secondary); }
.cr-narrative { font-size: 11px; color: rgba(184,150,62,0.35); margin-top: 2px; font-style: italic; }

/* 群雄领地排名 */
.faction-territory-list { display: flex; flex-direction: column; gap: 4px; }
.ft-item {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px; background: rgba(0,0,0,0.2);
  border-left: 3px solid;
  border-bottom: 1px solid rgba(184,150,62,0.04);
}
.ft-item.is-player { background: rgba(184,150,62,0.06); }
.ft-rank {
  width: 22px; height: 22px; border-radius: 50%;
  background: rgba(184,150,62,0.1); display: flex; align-items: center; justify-content: center;
  font-size: 11px; color: #b8963e; flex-shrink: 0;
}
.ft-info { flex: 1; min-width: 0; }
.ft-name { font-size: 14px; letter-spacing: 2px; }
.ft-stats { font-size: 11px; color: var(--text-secondary); display: flex; gap: 10px; margin-top: 2px; }
.ft-tiles { color: #b8963e; }
.ft-troops { color: #c44b3c; }
.ft-bar-wrap { width: 80px; height: 4px; background: rgba(255,255,255,0.05); border-radius: 2px; flex-shrink: 0; }
.ft-bar { height: 100%; border-radius: 2px; transition: width 0.5s ease; }

/* ========== 朝堂总览 - 派系忠诚度 ========== */
.loyalty-row {
  display: flex; align-items: center; gap: 6px;
  padding: 5px 0; font-size: 12px;
}
.loyalty-bar-wrap {
  width: 60px; height: 4px; background: rgba(255,255,255,0.04);
  border-radius: 2px; flex-shrink: 0;
}
.loyalty-bar { height: 100%; border-radius: 2px; transition: width 0.4s ease; }
.loyalty-name { flex: 1; color: #e0d5b8; letter-spacing: 2px; }
.loyalty-val { min-width: 28px; text-align: right; font-weight: bold; }
.loyalty-count { color: rgba(184,150,62,0.25); font-size: 10px; }

/* ========== 朝堂总览 - 廷议历史 ========== */
.debate-history-item {
  padding: 6px 8px; border-left: 3px solid rgba(184,150,62,0.15);
  background: rgba(0,0,0,0.12); margin-bottom: 4px;
}
.dh-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 2px;
}
.dh-round { font-size: 10px; color: rgba(184,150,62,0.35); }
.dh-resolution {
  font-size: 10px; padding: 1px 5px; border-radius: 2px;
  background: rgba(184,150,62,0.08); letter-spacing: 1px;
}
.dh-resolution.accept_consensus { color: #5b8c5a; }
.dh-resolution.partial_accept { color: #b8963e; }
.dh-resolution.table_discussion { color: #888; }
.dh-resolution.override_decision { color: #c44b3c; }
.dh-topic { font-size: 12px; color: #e0d5b8; letter-spacing: 1px; margin: 2px 0; }
.dh-meta { font-size: 10px; color: rgba(184,150,62,0.25); }

/* ========== 迁都面板样式 ========== */
.capital-current-card {
  background: rgba(184,150,62,0.06); border: 1px solid rgba(184,150,62,0.15);
  border-radius: 4px; padding: 10px 12px; margin-bottom: 10px;
}
.cc-header { font-size: 11px; color: rgba(184,150,62,0.35); letter-spacing: 2px; margin-bottom: 4px; }
.cc-name { font-size: 16px; color: #b8963e; font-family: "STKaiti","KaiTi",serif; letter-spacing: 3px; margin-bottom: 8px; }
.cc-stats { display: flex; gap: 14px; flex-wrap: wrap; }
.cc-stat { display: flex; flex-direction: column; gap: 2px; font-size: 11px; }
.cc-stat span:first-child { color: rgba(184,150,62,0.3); }
.cc-stat span:last-child { color: #e0d5b8; font-weight: bold; font-size: 13px; }

.adviser-recommend {
  display: flex; gap: 8px; padding: 8px 10px;
  background: rgba(91,140,90,0.06); border: 1px solid rgba(91,140,90,0.12);
  border-radius: 4px; margin-bottom: 10px; align-items: flex-start;
}
.ar-icon { font-size: 14px; flex-shrink: 0; }
.ar-text { font-size: 12px; color: #5b8c5a; line-height: 1.5; }

.capital-cost-bar {
  display: flex; gap: 10px; flex-wrap: wrap;
  padding: 8px 10px; background: rgba(0,0,0,0.15);
  border: 1px solid rgba(184,150,62,0.08); border-radius: 4px; margin-bottom: 12px;
}
.cost-item { display: flex; flex-direction: column; gap: 1px; }
.cost-label { font-size: 10px; color: rgba(184,150,62,0.3); }
.cost-val { font-size: 12px; color: #e0d5b8; font-weight: bold; }

.candidate-section { margin-bottom: 10px; }
.section-label {
  font-size: 12px; color: #b8963e; letter-spacing: 2px;
  margin-bottom: 8px; padding-bottom: 4px;
  border-bottom: 1px solid rgba(184,150,62,0.1);
  font-family: "STKaiti","KaiTi",serif;
}

.candidate-card {
  padding: 10px 12px; margin-bottom: 6px;
  background: rgba(0,0,0,0.15); border: 1px solid rgba(184,150,62,0.08);
  border-radius: 4px; cursor: pointer; transition: all 0.2s;
}
.candidate-card:hover { background: rgba(184,150,62,0.06); border-color: rgba(184,150,62,0.2); }
.candidate-card.candidate-selected {
  background: rgba(184,150,62,0.1); border-color: #b8963e;
  box-shadow: 0 0 6px rgba(184,150,62,0.12);
}

.cand-top { margin-bottom: 8px; }
.cand-name-row { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.cand-name { font-size: 14px; color: #e0d5b8; font-family: "STKaiti","KaiTi",serif; letter-spacing: 2px; }
.cand-grade {
  font-size: 10px; padding: 1px 5px; border-radius: 2px; font-weight: bold;
}
.cand-grade.grade-top { color: #5b8c5a; background: rgba(91,140,90,0.1); }
.cand-grade.grade-mid { color: #b8963e; background: rgba(184,150,62,0.1); }
.cand-grade.grade-low { color: #c44b3c; background: rgba(196,75,60,0.08); }
.cand-grade.grade-bottom { color: #666; background: rgba(255,255,255,0.03); }
.cand-score { font-size: 10px; color: rgba(184,150,62,0.4); margin-left: auto; }
.cand-advice { font-size: 11px; color: rgba(184,150,62,0.35); }

.cand-stats-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4px 12px; }
.cand-stat-item { display: flex; flex-direction: column; gap: 1px; }
.csi-label { font-size: 10px; color: rgba(184,150,62,0.25); }
.csi-val { font-size: 12px; color: #e0d5b8; font-weight: bold; }
.csi-bar { height: 3px; background: rgba(255,255,255,0.03); border-radius: 1.5px; margin-top: 2px; }
.csi-fill { display: block; height: 100%; border-radius: 1.5px; background: #b8963e; transition: width 0.3s; }

.cand-compare {
  display: flex; flex-wrap: wrap; margin-top: 6px; padding-top: 6px;
  border-top: 1px solid rgba(184,150,62,0.05); font-size: 10px;
}
.comp-adv { color: #5b8c5a; }
.comp-dis { color: #c44b3c; }

.confirm-area {
  padding: 10px 12px; background: rgba(184,150,62,0.08);
  border: 1px solid rgba(184,150,62,0.2); border-radius: 4px;
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.confirm-info { font-size: 12px; color: #e0d5b8; }
.confirm-info .gold-text { color: #b8963e; font-weight: bold; }

.cap-history-item {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 8px; font-size: 11px;
  background: rgba(0,0,0,0.1); margin-bottom: 3px;
}
.ch-round { color: rgba(184,150,62,0.25); }
.ch-arrow { color: #e0d5b8; flex: 1; }
.ch-cost { color: rgba(184,150,62,0.3); }

/* ===== 面板弹出方向定位 ===== */
.fp-panel-group > .float-panel {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.3s ease-out;
}

/* 左侧面板：贴在左工具栏右侧弹出 */
.fp-side-left > .float-panel {
  left: 52px !important;
  right: auto !important;
  animation: fpSlideInLeft 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

/* 右侧面板：贴在右工具栏左侧弹出 */
.fp-side-right > .float-panel {
  right: 52px !important;
  left: auto !important;
  animation: fpSlideInRight 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes fpSlideInLeft {
  from { opacity: 0; transform: translateX(-28px); }
  to   { opacity: 1; transform: translateX(0); }
}

@keyframes fpSlideInRight {
  from { opacity: 0; transform: translateX(28px); }
  to   { opacity: 1; transform: translateX(0); }
}

/* ===== 细作情报列表 ===== */
.spy-section-title {
  font-size: 12px;
  font-weight: bold;
  color: var(--gold);
  margin-bottom: 8px;
}

.spy-intel-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 280px;
  overflow-y: auto;
}

.spy-intel-card {
  background: rgba(45, 40, 32, 0.6);
  border: 1px solid rgba(139, 115, 85, 0.3);
  border-radius: 4px;
  padding: 8px 10px;
}

.spy-intel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.spy-intel-faction {
  font-size: 13px;
  font-weight: bold;
}

.spy-intel-round {
  font-size: 10px;
  color: #94a3b8;
  background: rgba(100, 116, 139, 0.15);
  padding: 1px 6px;
  border-radius: 3px;
}

.spy-intel-infiltration {
  font-size: 10px;
  color: #a5b4fc;
  background: rgba(99, 102, 241, 0.15);
  padding: 1px 6px;
  border-radius: 3px;
  margin-left: auto;
}

.spy-intel-data {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
}

.intel-field {
  font-size: 11px;
  color: #c8b896;
  font-family: "SimSun", serif;
}

/* ===== 国库增强样式 ===== */
.treasury-summary-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin-bottom: 8px;
}
.tsc-card {
  background: rgba(139, 115, 85, 0.08);
  border: 1px solid rgba(139, 115, 85, 0.15);
  border-radius: 4px;
  padding: 8px;
  text-align: center;
}
.tsc-card.gold-bg { background: rgba(201, 169, 78, 0.08); border-color: rgba(201, 169, 78, 0.25); }
.tsc-card.grain-bg { background: rgba(139, 115, 85, 0.08); border-color: rgba(139, 115, 85, 0.25); }
.tsc-val { font-size: 18px; font-weight: bold; color: var(--text); }
.tsc-lbl { font-size: 10px; color: var(--text-dim); margin-top: 2px; }
.treasury-actions { display: flex; gap: 6px; }
.income-list { display: flex; flex-direction: column; gap: 6px; }
.income-item {
  display: flex; align-items: center; gap: 10px;
  background: rgba(139, 115, 85, 0.06); border: 1px solid rgba(139, 115, 85, 0.1);
  border-radius: 4px; padding: 8px 10px; transition: border-color 0.2s;
}
.income-item:hover { border-color: var(--gold); }
.income-item.expense-item { border-left: 2px solid rgba(196, 75, 60, 0.3); }
.income-icon { font-size: 20px; flex-shrink: 0; }
.income-info { flex: 1; min-width: 0; }
.income-name { display: block; font-size: 12px; font-weight: bold; color: var(--text); }
.income-desc { display: block; font-size: 10px; color: var(--text-dim); margin-top: 1px; }
.income-val { font-size: 12px; font-weight: bold; white-space: nowrap; }

/* ===== 灾荒增强样式 ===== */
.disaster-index-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.di-label { font-size: 11px; color: var(--text-dim); white-space: nowrap; }
.di-bar-wrap { flex: 1; height: 12px; background: rgba(255,255,255,0.08); border-radius: 6px; overflow: hidden; }
.di-bar-fill { height: 100%; border-radius: 6px; transition: width 0.5s; }
.di-val { font-size: 14px; font-weight: bold; white-space: nowrap; }
.disaster-card {
  background: rgba(139, 115, 85, 0.06); border: 1px solid rgba(139, 115, 85, 0.12);
  border-radius: 4px; padding: 8px 10px; margin-bottom: 6px;
}
.disaster-card.severity-高 { border-left: 3px solid #C44B3C; }
.disaster-card.severity-中 { border-left: 3px solid #C9A94E; }
.disaster-card.severity-低 { border-left: 3px solid #5B8C5A; }
.dc-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.dc-name { font-size: 13px; font-weight: bold; color: var(--text); }
.dc-severity { font-size: 11px; padding: 1px 6px; border-radius: 2px; background: rgba(255,255,255,0.06); }
.dc-info { font-size: 10px; color: var(--text-dim); margin-bottom: 2px; }
.dc-actions { display: flex; gap: 6px; margin-top: 6px; }
.dc-relief-result { margin-top: 6px; font-size: 11px; padding: 4px 8px; background: rgba(255,255,255,0.04); border-radius: 3px; }
.disaster-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.forecast-result { margin-top: 8px; padding: 8px 10px; background: rgba(139, 115, 85, 0.06); border-radius: 4px; }
.fr-label { font-size: 11px; color: var(--gold); margin-bottom: 4px; }
.fr-content { font-size: 11px; color: var(--text-secondary); line-height: 1.5; }

/* ===== 人物面板增强样式 ===== */
.personnel-stats { display: flex; gap: 8px; margin-bottom: 8px; }
.pstat { flex: 1; text-align: center; padding: 6px 4px; background: rgba(139, 115, 85, 0.08); border-radius: 4px; }
.pstat-val { display: block; font-size: 18px; font-weight: bold; color: var(--text); }
.pstat-lbl { display: block; font-size: 10px; color: var(--text-dim); margin-top: 2px; }
.official-card {
  background: rgba(139, 115, 85, 0.05); border: 1px solid rgba(139, 115, 85, 0.12);
  border-radius: 4px; padding: 8px 10px; margin-bottom: 6px; cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}
.official-card:hover { border-color: var(--gold); }
.official-card.expanded { border-color: var(--gold); background: rgba(139, 115, 85, 0.1); }
.oc-header { display: flex; align-items: center; gap: 6px; }
.oc-name { font-size: 13px; font-weight: bold; color: var(--text); }
.oc-position { font-size: 11px; color: var(--text-dim); background: rgba(255,255,255,0.06); padding: 1px 6px; border-radius: 2px; }
.oc-expand { margin-left: auto; font-size: 12px; color: var(--text-dim); }
.oc-bars { margin-top: 6px; display: flex; flex-direction: column; gap: 3px; }
.oc-bar-row { display: flex; align-items: center; gap: 6px; font-size: 10px; }
.oc-bar-label { width: 28px; color: var(--text-dim); flex-shrink: 0; }
.oc-bar-wrap { flex: 1; height: 6px; background: rgba(255,255,255,0.08); border-radius: 3px; overflow: hidden; }
.oc-bar-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
.oc-bar-val { width: 24px; text-align: right; color: var(--text-secondary); flex-shrink: 0; }
.oc-detail { margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(139, 115, 85, 0.15); }
.oc-detail-actions { display: flex; gap: 4px; margin-top: 8px; }

/* ===== 皇族面板样式 ===== */
.ruler-card { display: flex; align-items: center; gap: 12px; padding: 10px; background: linear-gradient(135deg, rgba(201,169,78,0.1), rgba(139,115,85,0.06)); border-radius: 6px; margin-bottom: 8px; }
.ruler-avatar { font-size: 32px; }
.ruler-name { font-size: 16px; font-weight: bold; color: var(--text); }
.ruler-meta { font-size: 11px; color: var(--text-dim); margin-top: 2px; }
.royal-stats { display: flex; gap: 6px; }
.royal-stat { flex: 1; text-align: center; padding: 6px 4px; background: rgba(139,115,85,0.08); border-radius: 4px; }
.rs-val { display: block; font-size: 16px; font-weight: bold; color: var(--text); }
.rs-lbl { display: block; font-size: 10px; color: var(--text-dim); margin-top: 2px; }
.prince-card {
  background: rgba(139, 115, 85, 0.05); border: 1px solid rgba(139, 115, 85, 0.12);
  border-radius: 4px; padding: 8px 10px; margin-bottom: 6px; cursor: pointer;
  transition: border-color 0.2s;
}
.prince-card:hover { border-color: var(--gold); }
.prince-card.expanded { border-color: var(--gold); background: rgba(139, 115, 85, 0.1); }
.pc-header { display: flex; align-items: center; gap: 6px; }
.pc-name { font-size: 13px; font-weight: bold; color: var(--text); }
.pc-age { font-size: 11px; color: var(--text-dim); }
.pc-status { font-size: 10px; padding: 1px 6px; border-radius: 2px; background: rgba(255,255,255,0.06); color: var(--text-dim); }
.pc-bars { margin-top: 6px; display: flex; flex-direction: column; gap: 3px; }
.pc-bar-row { display: flex; align-items: center; gap: 6px; font-size: 10px; }
.pc-bar-label { width: 28px; color: var(--text-dim); flex-shrink: 0; }
.pc-detail { margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(139, 115, 85, 0.15); }
.pc-actions { display: flex; gap: 4px; flex-wrap: wrap; }
.prince-result { margin-top: 8px; font-size: 11px; padding: 4px 8px; background: rgba(255,255,255,0.04); border-radius: 3px; }

/* ===== 纳妃求嗣对话框 ===== */
.spawn-prince-dialog {
  position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
  width: 440px; max-height: 70vh; z-index: 9999;
  background: linear-gradient(180deg, #1a1410 0%, #0d0b08 100%);
  border: 2px solid var(--gold, #c9a94e); border-radius: 8px;
  box-shadow: 0 0 40px rgba(0, 0, 0, 0.6), 0 0 80px rgba(201, 169, 78, 0.15);
  display: flex; flex-direction: column;
}
.spawn-prince-dialog .fp-header { flex-shrink: 0; }
.spawn-prince-dialog .fp-body { overflow-y: auto; max-height: 55vh; padding: 16px 20px; }
.spawn-tabs { display: flex; gap: 0; margin-bottom: 12px; border-bottom: 1px solid rgba(139,115,85,0.2); }
.spawn-tab {
  flex: 1; padding: 8px 0; text-align: center; font-size: 12px; cursor: pointer;
  background: none; border: none; color: var(--text-dim, #8b7355);
  border-bottom: 2px solid transparent; transition: all 0.2s;
}
.spawn-tab:hover { color: var(--text, #d4c5a9); }
.spawn-tab.active {
  color: var(--gold, #c9a94e); border-bottom-color: var(--gold, #c9a94e); font-weight: bold;
}
.prince-option {
  padding: 10px 12px; margin-bottom: 6px; cursor: pointer;
  background: rgba(139,115,85,0.05); border: 1px solid rgba(139,115,85,0.12);
  border-radius: 4px; transition: all 0.2s;
}
.prince-option:hover { border-color: var(--gold, #c9a94e); background: rgba(139,115,85,0.1); }
.prince-option.selected {
  border-color: var(--gold, #c9a94e); background: rgba(201,169,78,0.12);
  box-shadow: 0 0 8px rgba(201,169,78,0.15);
}
.po-header { display: flex; align-items: center; gap: 8px; }
.po-name { font-size: 14px; font-weight: bold; color: var(--text, #d4c5a9); }
.po-year { font-size: 11px; color: var(--text-dim, #8b7355); }
.po-meta { display: flex; gap: 12px; margin-top: 4px; font-size: 11px; color: var(--text-secondary, #a89880); }
.po-talent { color: var(--gold, #c9a94e); }
.po-note { color: var(--text-dim, #8b7355); font-style: italic; }
.spawn-custom { padding: 8px 0; }
.custom-name-label { display: block; font-size: 12px; color: var(--text-dim, #8b7355); margin-bottom: 6px; }
.custom-name-input {
  width: 100%; padding: 10px 12px; font-size: 15px;
  background: rgba(139,115,85,0.08); border: 1px solid rgba(139,115,85,0.25);
  border-radius: 4px; color: var(--text, #d4c5a9);
  outline: none; font-family: 'STSong', 'SimSun', serif;
}
.custom-name-input:focus { border-color: var(--gold, #c9a94e); box-shadow: 0 0 6px rgba(201,169,78,0.15); }
.custom-name-input::placeholder { color: var(--text-dim, #8b7355); font-size: 13px; }
.spawn-actions {
  display: flex; gap: 8px; justify-content: flex-end;
}
.spawn-actions .btn-primary {
  background: linear-gradient(135deg, rgba(201,169,78,0.25), rgba(139,115,85,0.15));
  border-color: var(--gold, #c9a94e); color: var(--gold, #c9a94e);
}
.spawn-actions .btn-primary:disabled {
  opacity: 0.4; cursor: not-allowed;
}

/* ===== 疾医面板样式 ===== */
.medical-stats { display: flex; gap: 8px; margin-bottom: 8px; }
.mstat { flex: 1; text-align: center; padding: 8px 4px; background: rgba(139,115,85,0.08); border-radius: 4px; }
.mstat-val { display: block; font-size: 18px; font-weight: bold; color: var(--text); }
.mstat-lbl { display: block; font-size: 10px; color: var(--text-dim); margin-top: 2px; }
.clinic-card {
  background: rgba(139, 115, 85, 0.05); border: 1px solid rgba(139, 115, 85, 0.12);
  border-radius: 4px; padding: 8px 10px; margin-bottom: 6px;
}
.cc-header { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.cc-name { font-size: 13px; font-weight: bold; color: var(--text); }
.cc-level { font-size: 10px; padding: 1px 6px; background: rgba(76,175,80,0.15); color: #81c784; border-radius: 2px; margin-left: auto; }
.cc-stats { display: flex; gap: 12px; font-size: 10px; color: var(--text-secondary); margin-bottom: 4px; }
.cc-info { font-size: 10px; margin-bottom: 4px; }
.cc-actions { display: flex; gap: 4px; }

/* ===== 海策面板样式 ===== */
.sea-summary-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 8px; }
.ssc-card { background: rgba(139,115,85,0.08); border: 1px solid rgba(139,115,85,0.15); border-radius: 4px; padding: 8px; text-align: center; }
.ssc-card.gold-bg { background: rgba(201,169,78,0.08); border-color: rgba(201,169,78,0.25); }
.ssc-val { font-size: 18px; font-weight: bold; color: var(--text); }
.ssc-lbl { font-size: 10px; color: var(--text-dim); margin-top: 2px; }
.port-card {
  background: rgba(139, 115, 85, 0.05); border: 1px solid rgba(139, 115, 85, 0.12);
  border-radius: 4px; padding: 8px 10px; margin-bottom: 6px; cursor: pointer;
  transition: border-color 0.2s;
}
.port-card:hover { border-color: var(--gold); }
.port-card.expanded { border-color: var(--gold); background: rgba(139, 115, 85, 0.1); }
.pc-ships { font-size: 11px; color: #81c784; }
.pc-expand { margin-left: auto; font-size: 12px; color: var(--text-dim); }
.port-stats { display: flex; gap: 12px; font-size: 10px; color: var(--text-secondary); margin-top: 4px; }
.port-detail { margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(139, 115, 85, 0.15); }
.port-actions { display: flex; gap: 4px; flex-wrap: wrap; }

/* ===== 民俗面板样式 ===== */
.culture-era-card { text-align: center; padding: 10px; background: linear-gradient(135deg, rgba(201,169,78,0.1), rgba(139,115,85,0.06)); border-radius: 6px; margin-bottom: 8px; }
.era-main { margin-bottom: 8px; }
.era-name { font-size: 20px; font-weight: bold; }
.era-year { display: block; font-size: 12px; color: var(--text-dim); margin-top: 2px; }
.culture-stats { display: flex; gap: 6px; }
.cstat { flex: 1; text-align: center; padding: 6px 4px; background: rgba(139,115,85,0.06); border-radius: 4px; }
.cstat-val { display: block; font-size: 16px; font-weight: bold; color: var(--text); }
.cstat-lbl { display: block; font-size: 10px; color: var(--text-dim); margin-top: 2px; }
.culture-event { cursor: pointer; }
.culture-event:hover { background: rgba(139, 115, 85, 0.1); border-radius: 3px; padding: 2px 4px; margin: -2px -4px; }
.event-expand { margin-left: auto; font-size: 10px; color: var(--text-dim); }
.event-detail-popup {
  margin-top: 6px; padding: 8px 10px;
  background: rgba(139, 115, 85, 0.08); border: 1px solid rgba(139, 115, 85, 0.2);
  border-radius: 4px;
}
.edp-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.edp-title { font-size: 13px; font-weight: bold; color: var(--text); }
.edp-body { font-size: 11px; }
.chronicle-actions { display: flex; gap: 6px; margin-top: 8px; }
</style>
