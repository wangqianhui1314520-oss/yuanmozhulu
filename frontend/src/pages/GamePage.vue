<template>
  <!-- 游戏错误 -->
  <div v-if="gameError" class="game-error-overlay">
    <div class="game-error-box">
      <p class="error-title">舆图破损</p>
      <p class="error-hint">{{ gameError }}</p>
      <button v-audio class="btn-retry" @click="retryInit">重绘舆图</button>
      <button v-audio class="btn-back" @click="$router.push('/faction-select')">另择明主</button>
    </div>
  </div>

  <!-- 主游戏界面 -->
  <div v-else class="game-container">

    <!-- 新手引导浮层（首次访问一次性提示） -->
    <OnboardingOverlay />

    <!-- 新手教程引导（后端状态机驱动，逐步引导核心操作） -->
    <TutorialOverlay />



    <!-- ============ 顶层：天命气象 ============ -->
    <div class="top-bar">
      <div class="top-left">
        <div class="dynasty-banner">
          <div class="banner-emblem"
            :style="{ borderColor: playerFactionColor }">
            <img src="/assets/ui/ai_ui_dragon_badge.png" alt="龙徽" class="dragon-badge-img" />
          </div>
          <div class="banner-info">
            <div class="dynasty-name" :style="{ color: playerFactionColor }">
              {{ store.playerFaction?.name || '—' }}
            </div>
            <div class="dynasty-title">{{ store.playerFaction?.title || '—' }}</div>
          </div>
        </div>
      </div>

      <div class="top-center">
        <div class="date-display">
          <span class="date-year">至正{{ store.currentYear }}年</span>
          <span class="date-sep">·</span>
          <span class="date-month">{{ store.currentMonth }}月</span>
          <span class="date-sep">·</span>
          <span class="date-season">{{ store.seasonName }}季</span>
          <span class="date-round">第{{ store.currentRound }}回合</span>
        </div>
      </div>

      <div class="top-right">
        <!-- 核心资源 -->
        <div class="resource-group">
          <div class="resource-item gold">
            <div class="res-icon"><span class="sprite sprite-gold"></span></div>
            <div class="res-value">{{ fmtNum(store.playerFaction?.treasury ?? 0) }}</div>
            <div class="res-label">库银</div>
          </div>
          <div class="resource-item grain">
            <div class="res-icon"><span class="sprite sprite-grain"></span></div>
            <div class="res-value">{{ fmtNum(store.playerFaction?.grain ?? 0) }}</div>
            <div class="res-label">粮草</div>
          </div>
          <div class="resource-item prestige">
            <div class="res-icon"><span class="sprite sprite-prestige"></span></div>
            <div class="res-value">{{ store.playerFaction?.reputation ?? 0 }}</div>
            <div class="res-label">声望</div>
          </div>
        </div>
        <div class="resource-divider"></div>
        <div class="resource-group">
          <div class="resource-item troops">
            <div class="res-icon"><span class="sprite sprite-troops"></span></div>
            <div class="res-value">{{ fmtNum(store.totalTroops) }}</div>
            <div class="res-label">兵力</div>
          </div>
          <div class="resource-item horses">
            <div class="res-icon"><span class="sprite sprite-horses"></span></div>
            <div class="res-value">{{ store.playerFaction?.horses ?? 0 }}</div>
            <div class="res-label">战马</div>
          </div>
          <div class="resource-item arms">
            <div class="res-icon"><span class="sprite sprite-arms"></span></div>
            <div class="res-value">{{ store.playerFaction?.arms ?? 0 }}</div>
            <div class="res-label">军械</div>
          </div>
        </div>
        <div class="resource-divider"></div>
        <!-- 状态指标 -->
        <div class="status-group">
          <div class="status-item" :class="stabilityClass(store.playerFaction?.realm_stability)">
            <div class="status-bar">
              <div class="status-fill" :style="{ width: (store.playerFaction?.realm_stability ?? 50) + '%' }"></div>
            </div>
            <span class="status-label">民心</span>
          </div>
          <div class="status-item" :class="stabilityClass(store.playerFaction?.court_stability)">
            <div class="status-bar">
              <div class="status-fill" :style="{ width: (store.playerFaction?.court_stability ?? 50) + '%' }"></div>
            </div>
            <span class="status-label">朝纲</span>
          </div>
        </div>
        <!-- 功能按钮 -->
        <div class="top-buttons">
          <button v-audio class="top-btn war-btn" @click="closeAllPanels(); store.showWarPanel = true; panelSide = 'right'" title="天下兵戈">战</button>
          <span class="top-btn-divider"></span>
          <button v-audio class="top-btn" @click="closeAllPanels(); showPolicy = true; panelSide = 'right'" title="国策">策</button>
          <button v-audio class="top-btn" @click="openAdvisorPopupFn(); panelSide = 'right'" title="谋臣献策">谋</button>
          <button v-audio class="top-btn" @click="closeAllPanels(); store.togglePanel('factions'); panelSide = 'right'" title="大势">势</button>
          <button v-audio class="top-btn" @click="closeAllPanels(); showMuseum = true; panelSide = 'right'" title="史馆札记">史</button>
          <button v-audio class="top-btn" @click="quickSaveHandler" title="快速存档" :disabled="quickSaving">存</button>
          <button v-audio class="top-btn" @click="navigateToSaveManager" title="存档管理">档</button>
          <button v-audio class="top-btn" @click="closeAllPanels(); showSettings = true; panelSide = 'right'" title="设置">⚙</button>
          <button v-audio class="top-btn" @click="closeAllPanels(); showSecurity = true; panelSide = 'right'" title="EdgeOne安全态势">🛡</button>
          <span class="top-btn-divider"></span>
          <button v-audio class="top-btn" title="切换全屏" @click="toggleFullscreen">
            {{ isFullscreen ? '⤡' : '⤢' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ============ 中层：舆图主体 + 右侧工具栏 ============ -->
    <div class="map-section">
      <!-- 左侧工具栏：军政大事 -->
      <div class="left-toolbar">
        <div class="toolbar-scroll">
          <button
            v-for="tool in leftToolbarItems" :key="tool.id"
            v-audio
            class="tool-btn"
            :class="{ active: isToolActive(tool.id) }"
            @click="onLeftToolClick(tool)"
            :title="tool.label"
          >
            <span class="tool-icon">{{ tool.icon }}</span>
            <span class="tool-label">{{ tool.label }}</span>
          </button>
        </div>
      </div>

      <!-- 中央：沙盘舆图 -->
      <div class="map-surface">

        <!-- 加载中 -->  
        <div v-if="isMapLoading" class="map-status-overlay">
          <div class="map-status-content">
            <div class="map-status-spinner"></div>
            <div class="map-status-text">舆图加载中…</div>
            <div class="map-status-hint">首次加载需获取地图数据<span v-if="mapLoadTimeout">（加载超时，请<button class="btn-reload-map" @click="loadStaticMap()">重试</button>）</span></div>
          </div>
        </div>

        <!-- 加载失败 / 空数据 -->
        <div v-else-if="hexMapTiles.length === 0" class="map-status-overlay">
          <div class="map-status-content">
            <div class="map-status-icon">🗺️</div>
            <div class="map-status-text">舆图数据为空</div>
            <div class="map-status-hint">
              后端可能未启动，或地图数据未生成<br/>
              请运行 <code>python -m server.map.generate_map</code> 并重启后端
            </div>
            <button class="btn-reload-map" @click="loadStaticMap()">重新加载</button>
          </div>
        </div>

        <HexMapView
          ref="hexMapRef"
          v-if="hexMapTiles.length > 0"
          :tiles="hexMapTiles"
          :selectedTileId="store.selectedTile"
          :layers="mapLayers"
          :boundaries="staticBoundaries"
          :outlines="staticOutlines"
          :playerFactionId="store.playerFactionId"
          :fogVisibleIds="store.fogVisibleTileIds"
          :marchRoutes="store.activeMarchRoutes"
          :supplyLines="store.activeSupplyLines"
          :diplomacyRelations="store.activeDiploRelations"
          :garrisonData="store.tileGarrisonData"
          :claimTiles="store.playerClaimTiles"
          :disasterTiles="store.tileDisasterData"
          :waterRoutes="store.waterRoutes"
          :buildingData="store.tileBuildingData"
          @tileClick="onTileClick"
          @tileRightClick="onTileRightClick"
          @toggleLayer="onToggleLayer"
          @setLayerMode="onSetLayerMode"
        />
        <!-- ===== 地图右键上下文菜单 ===== -->
        <div
          v-if="ctxMenu.visible"
          class="tile-context-menu"
          :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }"
          @click.stop
        >
          <div class="ctx-menu-title">{{ ctxTileName }}</div>
          <div class="ctx-menu-divider"></div>
          <!-- 己方领地操作 -->
          <template v-if="ctxMenu.owner === 'own'">
            <button v-audio class="ctx-menu-item" @click="ctxAction('recruit')">
              <span class="ctx-icon">🏇</span>招兵买马
            </button>
            <button v-audio class="ctx-menu-item" @click="ctxAction('build')">
              <span class="ctx-icon">🏗️</span>修筑建筑
            </button>
            <button v-audio class="ctx-menu-item" @click="ctxAction('inspect')">
              <span class="ctx-icon">📋</span>体察民情
            </button>
            <button v-audio class="ctx-menu-item" @click="ctxAction('fortify')">
              <span class="ctx-icon">🏰</span>加固城防
            </button>
            <div class="ctx-menu-divider"></div>
            <button v-audio class="ctx-menu-item" @click="ctxAction('march_from')">
              <span class="ctx-icon">⚔️</span>从此出征
            </button>
          </template>
          <!-- 敌方领地操作 -->
          <template v-else-if="ctxMenu.owner === 'enemy'">
            <button v-audio class="ctx-menu-item danger" @click="ctxAction('march_to')">
              <span class="ctx-icon">⚔️</span>出兵征伐
            </button>
            <button v-audio class="ctx-menu-item" @click="ctxAction('spy')">
              <span class="ctx-icon">🕵️</span>派遣细作
            </button>
            <button v-audio class="ctx-menu-item" @click="ctxAction('scout')">
              <span class="ctx-icon">🔭</span>侦查敌情
            </button>
            <button v-audio class="ctx-menu-item" @click="ctxAction('sabotage')">
              <span class="ctx-icon">💣</span>暗中破坏
            </button>
          </template>
          <!-- 中立/无主领地操作 -->
          <template v-else-if="ctxMenu.owner === 'neutral'">
            <button v-audio class="ctx-menu-item" @click="ctxAction('march_to')">
              <span class="ctx-icon">⚔️</span>出兵占领
            </button>
            <button v-audio class="ctx-menu-item" @click="ctxAction('inspect')">
              <span class="ctx-icon">📋</span>体察民情
            </button>
            <button v-audio class="ctx-menu-item" @click="ctxAction('claim')">
              <span class="ctx-icon">📜</span>宣示主权
            </button>
          </template>
          <!-- 海域操作 -->
          <template v-else-if="ctxMenu.owner === 'sea'">
            <button v-audio class="ctx-menu-item" @click="ctxAction('navy_patrol')">
              <span class="ctx-icon">⛵</span>派遣水师
            </button>
            <button v-audio class="ctx-menu-item" @click="ctxAction('sea_trade')">
              <span class="ctx-icon">📦</span>贸易航线
            </button>
            <button v-audio class="ctx-menu-item" @click="ctxAction('sea_explore')">
              <span class="ctx-icon">🔭</span>探索海域
            </button>
            <button v-audio class="ctx-menu-item" @click="ctxAction('sea_fish')">
              <span class="ctx-icon">🎣</span>渔业征调
            </button>
            <div class="ctx-menu-divider"></div>
            <button v-audio class="ctx-menu-item" @click="ctxAction('build_port')">
              <span class="ctx-icon">⚓</span>修建港口
            </button>
          </template>
        </div>
        <!-- 点击空白区域关闭菜单 -->
        <div v-if="ctxMenu.visible" class="ctx-backdrop" @click="closeCtxMenu" @contextmenu.prevent="closeCtxMenu"></div>

        <!-- 完整图层控制面板 -->
        <LayerPanel
          :layers="mapLayers"
          :layersByCategory="layersByCategory"
          @toggleLayer="onToggleLayer"
          @setOpacity="onSetOpacity"
          @toggleLock="onToggleLock"
          @toggleFade="onToggleFade"
          @resetAll="onResetAll"
          @applyPreset="onApplyPreset"
        />

        <!-- 空过回合按钮（不下旨时推进月份） -->
        <button
          v-audio
          class="advance-turn-btn"
          :class="{ processing: store.isProcessing }"
          :disabled="store.isProcessing"
          @click="handleAdvanceTurn"
        >
          <span class="advance-icon">▶</span>
          <span class="advance-text">{{ store.isProcessing ? '天下推演中…' : '空过回合' }}</span>
        </button>

        <!-- 地图缩放控制 -->
        <div class="zoom-controls" v-if="hexMapTiles.length > 0">
          <button v-audio class="zoom-btn" @click="onZoomIn" title="放大舆图">
            <span class="zoom-icon">＋</span>
          </button>
          <div class="zoom-level" title="当前缩放比例">{{ zoomPercent }}%</div>
          <button v-audio class="zoom-btn" @click="onZoomOut" title="缩小舆图">
            <span class="zoom-icon">－</span>
          </button>
          <button v-audio class="zoom-btn zoom-reset" @click="onResetView" title="复位舆图">
            <span class="zoom-icon">⟲</span>
          </button>
        </div>
      </div>

      <!-- 右侧工具栏：内政谋略 -->
      <div class="right-toolbar">
        <div class="toolbar-scroll">
          <button
            v-for="tool in rightToolbarItems" :key="tool.id"
            class="tool-btn"
            :class="{ active: isToolActive(tool.id) }"
            @click="onRightToolClick(tool)"
            :title="tool.label"
          >
            <span class="tool-icon">{{ tool.icon }}</span>
            <span class="tool-label">{{ tool.label }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- ============ 圣旨台面板（中下方弹出） ============ -->
    <Transition name="edict-drawer-slide">
      <div v-if="edictDrawerOpen" class="edict-drawer artifact-edict" :class="{ 'new-commands': pendingCmdAdded }">
        <div class="edict-drawer-body">
          <div class="edict-drawer-header">
            <span class="edict-drawer-title">📜 本回圣旨</span>
            <div class="edict-drawer-header-right">
              <span class="edict-drawer-count" :class="{ 'pulse-count': pendingCmdAdded }">{{ store.pendingEdictCommands.length + pendingDecisions.length }} 道</span>
              <button class="edict-drawer-close" @click="edictDrawerOpen = false" title="收起圣旨台">&times;</button>
            </div>
          </div>
          <!-- 待定决策区域 -->
          <div v-if="pendingDecisions.length" class="edict-drawer-decisions">
            <div class="edict-drawer-subtitle">🏛 待定决策</div>
            <div
              v-for="d in pendingDecisions"
              :key="d.id"
              class="edict-item decision-item"
              @click="applyDecision(d)"
              title="点击填入圣旨"
            >
              <span class="edict-item-num decision-num">决</span>
              <span class="edict-item-text">{{ d.label }}</span>
              <button class="edict-item-remove" @click.stop="removeDecision(d.id)" title="移除决策">✕</button>
            </div>
          </div>
          <div v-if="!store.pendingEdictCommands.length && !pendingDecisions.length" class="edict-drawer-empty">
            尚未草拟圣旨<br><small>可在地图上右键格子下达指令</small>
          </div>
          <div
            v-for="(cmd, i) in store.pendingEdictCommands"
            :key="i"
            class="edict-item"
            :class="{ 'new-item': pendingCmdAdded && i === store.pendingEdictCommands.length - 1 }"
          >
            <span class="edict-item-num">{{ i + 1 }}</span>
            <span class="edict-item-text">{{ cmd.label }}</span>
            <button class="edict-item-remove" @click="removeEdict(i)" title="撤销此旨">✕</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- ============ 圣旨台把手（页面中下方固定） ============ -->
    <div
      class="edict-drawer-handle"
      :class="{ 'has-pending': store.pendingEdictCommands.length || pendingDecisions.length, 'drawer-open': edictDrawerOpen }"
      @click="toggleEdictDrawer"
    >
      <span class="handle-arrow">{{ edictDrawerOpen ? '▼' : '▲' }}</span>
      <span class="handle-text">圣旨台</span>
      <span v-if="store.pendingEdictCommands.length || pendingDecisions.length" class="handle-badge" :class="{ 'pulse': handlePulse }">{{ store.pendingEdictCommands.length + pendingDecisions.length }}</span>
    </div>

    <!-- ============ 底层：君主面板 + 圣旨栏 ============ -->
    <div class="bottom-bar">
      <!-- 左：君主面板 -->
      <div class="ruler-panel">
        <div class="ruler-portrait">
          <div class="portrait-frame" :style="{ borderColor: playerFactionColor }">
            <img
              v-if="rulerImage"
              :src="rulerImage"
              :alt="store.playerFaction?.name || '君主'"
              class="ruler-image"
              @error="($event.target as HTMLImageElement).style.display='none'; onRulerImgError()"
            />
            <div v-if="!rulerImage || rulerImgFailed" class="portrait-placeholder">🐉</div>
          </div>
          <div class="ruler-details">
            <div class="ruler-name" :style="{ color: playerFactionColor }">
              {{ store.playerFaction?.name || '未知' }}
            </div>
            <div class="ruler-title-text">{{ store.playerFaction?.title || '—' }}</div>
            <div class="ruler-stats">
              <div class="ruler-stat">
                <span class="stat-val">{{ store.playerTiles.length }}</span>
                <span class="stat-lbl">领地</span>
              </div>
              <div class="ruler-stat">
                <span class="stat-val">{{ fmtNum(store.totalPopulation) }}</span>
                <span class="stat-lbl">人口</span>
              </div>
              <div class="ruler-stat">
                <span class="stat-val">{{ store.playerFaction?.development_level ?? 0 }}</span>
                <span class="stat-lbl">发展</span>
              </div>
            </div>
            <!-- Buffs/Debuffs -->
            <div class="ruler-buffs" v-if="playerBuffs.length || playerDebuffs.length">
              <span v-for="b in playerBuffs" :key="'buf-'+b.name" class="buff-tag buff">{{ b.name }}</span>
              <span v-for="d in playerDebuffs" :key="'deb-'+d.name" class="buff-tag debuff">{{ d.name }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右：圣旨输入栏 -->
      <div class="edict-bar">
        <div class="edict-input-wrap">
          <!-- 玉玺印章图标 -->
          <div class="edict-seal">
            <svg viewBox="0 0 36 36" width="36" height="36">
              <rect x="1" y="1" width="34" height="34" rx="4" fill="none" stroke="#b89b68" stroke-width="1.5" opacity="0.6"/>
              <rect x="4" y="4" width="28" height="28" rx="2" fill="none" stroke="#b89b68" stroke-width="0.6" opacity="0.35"/>
              <text x="18" y="24" text-anchor="middle" fill="#c8a84a" font-size="18" font-family="STKaiti,KaiTi,serif" font-weight="bold">敕</text>
            </svg>
          </div>
          <textarea
            v-model="edictText"
            class="edict-input"
            :class="{ 'edict-major': isMajorEdict, 'edict-needs-info': edictNeedsClarify }"
            placeholder="草拟圣旨…（自然语言指令，AI推演执行）"
            rows="2"
            @keydown.ctrl.enter="executeEdict"
            @input="onEdictInput"
          ></textarea>
        </div>
        <!-- NL实时校验提示 -->
        <div v-if="edictValidationHint" class="edict-validation-hint" :class="{ 'edict-hint-error': edictNeedsClarify, 'edict-hint-info': !edictNeedsClarify }">
          <span class="hint-icon">{{ edictNeedsClarify ? '⚠' : '📜' }}</span>
          <span class="hint-text">{{ edictValidationHint }}</span>
        </div>
        <div class="edict-buttons">
          <button class="edict-btn primary" @click="executeEdict" :disabled="!edictText.trim() || store.isProcessing">
            颁布圣旨
          </button>
          <button v-if="edictText.trim()" class="edict-btn cancel-btn" @click="cancelEdictInput" title="清空圣旨">
            清空
          </button>
          <div class="pending-commands" v-if="store.pendingEdictCommands.length">
            <span
              v-for="(cmd, i) in store.pendingEdictCommands.slice(0, 3)" :key="i"
              class="pending-tag"
              @click="edictText += '；' + cmd.label"
            >{{ cmd.label }}</span>
          </div>
          <!-- 待定决策标签 -->
          <div class="pending-decisions" v-if="pendingDecisions.length">
            <span
              v-for="d in pendingDecisions" :key="d.id"
              class="decision-tag"
              @click="applyDecision(d)"
              :title="'点击填入圣旨：' + d.content"
            >
              <span class="decision-tag-icon">{{ decisionTypeIcon(d.type) }}</span>
              {{ d.label }}
              <button class="decision-tag-remove" @click.stop="removeDecision(d.id)" title="移除">✕</button>
            </span>
          </div>
        </div>
      </div>

      <!-- 快捷命令面板 -->
      <div class="quick-cmd-panel">
        <div class="qcp-tabs">
          <button
            v-for="cat in quickCmdCategories"
            :key="cat.id"
            class="qcp-tab"
            :class="{ active: activeQuickCmdCat === cat.id }"
            @click="activeQuickCmdCat = cat.id"
          >{{ cat.label }}</button>
        </div>
        <div class="qcp-commands">
          <button
            v-for="cmd in activeQuickCmds"
            :key="cmd.label"
            class="qcp-cmd"
            @click="fillQuickCmd(cmd)"
            :title="cmd.desc"
          >
            <span class="qcp-cmd-icon">{{ cmd.icon }}</span>
            <span class="qcp-cmd-label">{{ cmd.label }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- ============ 弹窗面板 ============ -->
    <PolicyPanel :visible="showPolicy" @close="showPolicy = false" />
    <AdvisorPopup
      :visible="showAdvisorPopup"
      :advisor-name="'幕僚团'"
      @close="showAdvisorPopup = false"
      @approve-edict="onAdvisorApproveEdict"
      @open-panel="showAdvisor = true"
    />
    <AdvisorPanel :visible="showAdvisor" @close="showAdvisor = false" />
    <SettingsPanel :visible="showSettings" @close="showSettings = false" />
    <SecurityPanel :visible="showSecurity" @close="showSecurity = false" />
    <ReplayPanel :visible="showReplay" @close="showReplay = false" />
    <FloatPanels :panelSide="panelSide" @open-diplomacy-deep="showDiplomacyDeep = true" @open-talent-market="showTalentMarket = true" />
    <RecruitPanel v-if="store.activePanel === 'recruit'" />
    <MarchPanel
      :visible="store.showMarchPanel"
      :target-tile-id="store.marchTargetTileId"
      @close="store.showMarchPanel = false"
    />
    <BatchBuildPanel
      :visible="showBatchBuild"
      @close="showBatchBuild = false"
      @edict-fill="onBatchEdictFill"
    />
    <BatchRecruitPanel
      :visible="showBatchRecruit"
      @close="showBatchRecruit = false"
      @edict-fill="onBatchEdictFill"
    />
    <GeneralPanel :visible="showGenerals" @close="showGenerals = false" />
    <TalentMarketPanel :visible="showTalentMarket" @close="showTalentMarket = false" />
    <DiplomacyDeepPanel :visible="showDiplomacyDeep" @close="showDiplomacyDeep = false" />
    <HistoryAnchorPanel :visible="showHistory" @close="showHistory = false" />
    <AIControlPanel :visible="showAIControl" @close="showAIControl = false" />
    <AchievementPanel :visible="showAchievement" :faction-id="store.playerFactionId" @close="showAchievement = false" />
    <TechTreePanel :visible="showTechTree" :faction-id="store.playerFactionId" @close="showTechTree = false" />
    <MuseumPanel :visible="showMuseum" @close="showMuseum = false" />
    <EndingPanel v-if="store.showEnding" />
    <!-- 回合大事录圣旨弹窗 -->
    <TurnSummaryScroll
      :visible="store.showTurnSummary"
      :year="store.turnSummaryYear"
      :month="store.turnSummaryMonth"
      :round="store.turnSummaryRound"
      :season="store.turnSummarySeason"
      :narrative="store.turnSummaryNarrative"
      :minister-name="store.turnSummaryMinister"
      :minister-title="store.turnSummaryTitle"
      :loading="store.turnSummaryLoading"
      :ai-generated="store.turnSummaryAiGenerated"
      @close="store.closeTurnSummary()"
    />
    <WarPanel
      :visible="store.showWarPanel"
      @close="store.showWarPanel = false"
      @openPeace="onOpenPeaceFromWar"
    />
    <PeaceNegotiation
      :visible="store.showPeacePanel"
      :war="store.warPanelData"
      @close="store.showPeacePanel = false"
    />
    <!-- 事件详情弹窗 -->
    <div v-if="eventDetail" class="event-detail-overlay" @click.self="eventDetail = null">
      <div class="event-detail-dialog animate-fade-in">
        <div class="edd-header">
          <h3 :class="'severity-' + eventDetail.severity">📋 {{ eventDetail.title }}</h3>
          <button class="edd-close" @click="eventDetail = null">✕</button>
        </div>
        <div class="edd-body">
          <div class="edd-meta">
            <span>第{{ eventDetail.round }}回合</span>
            <span>类型：{{ eventTypeName(eventDetail.event_type) }}</span>
            <span>严重程度：{{ severityName(eventDetail.severity) }}</span>
          </div>
          <div class="edd-narrative">{{ eventDetail.narrative || eventDetail.description }}</div>
        </div>
      </div>
    </div>

    <!-- 圣旨卷轴弹窗 —— 展示AI生成的正式圣旨语言，关闭后推进回合 -->
    <div v-if="edictResult" class="edict-result-overlay is-major" @click.self="closeEdictScroll">
      <div class="edict-scroll-wrapper">
        <!-- 卷轴顶部轴杆 -->
        <div class="er-scroll-rod er-scroll-rod-top">
          <div class="er-rod-knob"></div>
          <div class="er-rod-bar"></div>
          <div class="er-rod-knob"></div>
        </div>
        <!-- 卷轴纸面 -->
        <div class="edict-result-dialog animate-edict-unfurl">
          <div class="er-header">
            <div class="er-header-deco">&#x269C;</div>
            <h3>{{ edictFormatHeader }}</h3>
          </div>
          <div class="er-body">
            <!-- 正式圣旨正文（AI生成） -->
            <div class="edict-language-body">
              {{ edictResult.ai_analysis?.edict_language || edictResult.ai_analysis?.narrative || '圣旨已颁行，天下震动。' }}
            </div>

            <!-- 执行摘要（可选折叠） -->
            <div v-if="edictResult.execution" class="edict-exec-summary">
              <div class="ees-label" @click="showExecDetail = !showExecDetail">
                {{ showExecDetail ? '▾' : '▸' }} 尚书省执行附注
                <span class="ees-counter">
                  已行{{ edictResult.execution.total_executed || 0 }}项
                  <template v-if="edictResult.execution.total_failed">，未行{{ edictResult.execution.total_failed }}项</template>
                </span>
              </div>
              <div v-if="showExecDetail" class="ees-detail">
                <div v-for="(ex, i) in edictResult.execution.executed" :key="'ex-'+i" class="ees-item ok">
                  <span class="ees-tag">{{ actionLabel(ex.action) }}</span>
                  {{ ex.result?.message || ex.action }}
                </div>
                <div v-for="(fa, i) in edictResult.execution.failed" :key="'fa-'+i" class="ees-item fail">
                  <span class="ees-tag">{{ actionLabel(fa.action) }}</span>
                  {{ fa.reason }}
                </div>
              </div>
            </div>

            <!-- 4.0 新增：AI战略推演详情（可选折叠） -->
            <div v-if="edictResult.simulation_used && edictResult.simulation" class="edict-simulation-panel">
              <div class="sim-label" @click="showSimDetail = !showSimDetail">
                {{ showSimDetail ? '▾' : '▸' }} AI 战略推演详情
                <span class="sim-confidence">
                  置信度{{ ((edictResult.simulation.ai_confidence || 0) * 100).toFixed(0) }}%
                  <span v-if="edictResult.simulation.overall_risk_level" class="sim-risk sim-risk-{{ edictResult.simulation.overall_risk_level }}">
                    | 风险: {{ { low:'低', medium:'中', high:'高', critical:'危急' }[edictResult.simulation.overall_risk_level] || edictResult.simulation.overall_risk_level }}
                  </span>
                </span>
              </div>
              <div v-if="showSimDetail" class="sim-detail">
                <div v-if="edictResult.simulation.situation_analysis" class="sim-section">
                  <div class="sim-section-title">态势分析</div>
                  <div class="sim-text">{{ edictResult.simulation.situation_analysis }}</div>
                </div>
                <div v-if="edictResult.simulation.primary_plan_steps?.length" class="sim-section">
                  <div class="sim-section-title">主方案步骤</div>
                  <div v-for="(step, i) in edictResult.simulation.primary_plan_steps" :key="'step-'+i" class="sim-step">
                    <span class="sim-step-num">{{ i + 1 }}.</span>
                    {{ step.description }}
                    <span v-if="step.expected_effect" class="sim-step-effect">→ {{ step.expected_effect }}</span>
                  </div>
                </div>
                <div v-if="edictResult.simulation.risk_matrix?.length" class="sim-section">
                  <div class="sim-section-title">风险评估</div>
                  <div v-for="(r, i) in edictResult.simulation.risk_matrix" :key="'risk-'+i" class="sim-risk-item">
                    <span class="sim-risk-type">{{ { military:'军事', economic:'经济', diplomatic:'外交', stability:'民心' }[r.type] || r.type }}</span>
                    <span class="sim-risk-prob">概率{{ (r.probability * 100).toFixed(0) }}%</span>
                    <span class="sim-risk-impact" :class="'sim-impact-'+r.impact">影响: {{ { low:'低', medium:'中', high:'高', critical:'致命' }[r.impact] || r.impact }}</span>
                    {{ r.description }}
                  </div>
                </div>
                <div v-if="edictResult.simulation.geopolitical_impacts?.length" class="sim-section">
                  <div class="sim-section-title">地缘影响</div>
                  <div v-for="(g, i) in edictResult.simulation.geopolitical_impacts" :key="'geo-'+i" class="sim-geo-item">
                    <strong>{{ g.faction }}</strong> ({{ { hostile:'敌视', neutral:'中立', friendly:'友善', opportunistic:'观望投机' }[g.reaction] || g.reaction }})：
                    {{ g.description }}
                  </div>
                </div>
                <div v-if="edictResult.simulation.resource_projection" class="sim-section">
                  <div class="sim-section-title">资源投影</div>
                  <div class="sim-resource-grid">
                    <span>银两 {{ edictResult.simulation.resource_projection.treasury.before }} → {{ edictResult.simulation.resource_projection.treasury.after }}</span>
                    <span>粮草 {{ edictResult.simulation.resource_projection.grain.before }} → {{ edictResult.simulation.resource_projection.grain.after }}</span>
                    <span>兵力 {{ edictResult.simulation.resource_projection.troops.before }} → {{ edictResult.simulation.resource_projection.troops.after }}</span>
                  </div>
                </div>
                <div v-if="edictResult.simulation.consequence_analysis" class="sim-section">
                  <div class="sim-section-title">后果推演</div>
                  <div class="sim-text">{{ edictResult.simulation.consequence_analysis }}</div>
                </div>
                <div v-if="edictResult.feedback_report" class="sim-section sim-feedback">
                  <div class="sim-section-title">执行反馈</div>
                  <div class="sim-text">{{ edictResult.feedback_report.report_text }}</div>
                  <div v-if="edictResult.feedback_report.adjustment_suggestion" class="sim-suggestion">
                    💡 {{ edictResult.feedback_report.adjustment_suggestion }}
                  </div>
                </div>
              </div>
            </div>

            <!-- 关闭按钮 → 推进回合 -->
            <button class="er-advance-main" @click="closeEdictScroll">
              臣等遵旨 · 推进次月
            </button>
          </div>
        </div>
        <!-- 卷轴底部轴杆 -->
        <div class="er-scroll-rod er-scroll-rod-bot">
          <div class="er-rod-knob"></div>
          <div class="er-rod-bar"></div>
          <div class="er-rod-knob"></div>
        </div>
      </div>
    </div>

    <!-- 游戏事件通知叠加层 -->
    <GameEventOverlay ref="eventOverlayRef" />

    <!-- 全局加载覆盖层（回合推进/读档时显示） -->
    <LoadingOverlay
      :visible="showLoadingOverlay"
      :title="loadingTitle"
      :message="loadingMessage"
      :progress="loadingProgress"
      :show-progress="loadingShowProgress"
    />

    <!-- v4.4: 回合过渡动画 -->
    <TurnTransition
      :visible="store.showTurnTransition"
      :prev-round="store.lastRound"
      :prev-year="store.lastYear"
      :prev-month="store.lastMonth"
      :prev-season="store.lastSeason"
      :new-round="store.currentRound"
      :new-year="store.currentYear"
      :new-month="store.currentMonth"
      :new-season="store.currentSeason"
      @done="store.closeTurnTransition()"
    />

    <!-- v4.4: 上回合总结报告 -->
    <TurnReport
      :visible="store.showTurnReport"
      :round="store.currentRound"
      :year="store.currentYear"
      :month="store.currentMonth"
      :season="store.currentSeason"
      :snapshot="store.lastSnapshot"
      :battle-events="store.lastBattleEvents"
      :tile-changes="store.lastTileChanges"
      :other-events="store.lastOtherEvents"
      :faction-configs="store.factionConfigMap"
      :player-faction-id="store.playerFactionId"
      :narrative="store.turnSummaryNarrative"
      :narrative-minister="store.turnSummaryMinister"
      :narrative-title="store.turnSummaryTitle"
      :loading-narrative="store.turnSummaryLoading"
      @close="store.closeTurnReport()"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * GamePage - 元末逐鹿·帝王权谋
 *
 * 完全重构后的对局页面：
 * - 顶部：王朝信息 + 资源条 + 状态指标
 * - 中部：政治舆图 (PoliticalMap) + 右侧工具栏
 * - 底部：君主面板 + 环形行动按钮 + 圣旨输入栏
 *
 * API 对接规范保持不变：
 * - 开局调用 store.startGame() → /api/game/init
 * - 每回合推进调用 store.advanceTurn() → /api/game/advance-turn
 * - 圣旨 AI 推演 store.executeEdictAI()
 */
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useGameStore } from '@/stores/gameStore'
import { loadFactionsConfig, getStaticMap, quickSave, nlValidateEdict, nlProcessEdict, nlCancelCommands } from '@/services/api'
import { generateRegionTiles } from '@/utils/regionTileGenerator'
import { useFullscreen } from '@/composables/useFullscreen'
import type { GameEvent, FactionState, TileState } from '@/types'
import type { HexTile } from '@/utils/flatTopHexUtils'
import { useMapLayers, loadLayerConfig } from '@/utils/layerUtils'
import type { BoundaryData, AdminOutline } from '@/components/game/HexMapView.vue'

import PolicyPanel from '@/components/PolicyPanel.vue'
import AdvisorPanel from '@/components/AdvisorPanel.vue'
import AdvisorPopup from '@/components/AdvisorPopup.vue'
import SettingsPanel from '@/components/SettingsPanel.vue'
import SecurityPanel from '@/components/SecurityPanel.vue'
import ReplayPanel from '@/components/ReplayPanel.vue'
import FloatPanels from '@/components/FloatPanels.vue'
import RecruitPanel from '@/components/RecruitPanel.vue'
import MarchPanel from '@/components/MarchPanel.vue'
import HexMapView from '@/components/game/HexMapView.vue'
import LayerPanel from '@/components/game/LayerPanel.vue'

import BatchBuildPanel from '@/components/BatchBuildPanel.vue'
import BatchRecruitPanel from '@/components/BatchRecruitPanel.vue'
import GeneralPanel from '@/components/GeneralPanel.vue'
import TalentMarketPanel from '@/components/TalentMarketPanel.vue'
import DiplomacyDeepPanel from '@/components/DiplomacyDeepPanel.vue'
import HistoryAnchorPanel from '@/components/HistoryAnchorPanel.vue'
import AIControlPanel from '@/components/AIControlPanel.vue'
import EndingPanel from '@/components/EndingPanel.vue'
import TurnSummaryScroll from '@/components/TurnSummaryScroll.vue'
import TurnTransition from '@/components/TurnTransition.vue'
import TurnReport from '@/components/TurnReport.vue'
import WarPanel from '@/components/WarPanel.vue'
import PeaceNegotiation from '@/components/PeaceNegotiation.vue'
import GameEventOverlay from '@/components/GameEventOverlay.vue'
import LoadingOverlay from '@/components/LoadingOverlay.vue'
import AchievementPanel from '@/components/AchievementPanel.vue'
import TechTreePanel from '@/components/TechTreePanel.vue'
import MuseumPanel from '@/components/MuseumPanel.vue'
import OnboardingOverlay from '@/components/OnboardingOverlay.vue'
import TutorialOverlay from '@/components/TutorialOverlay.vue'
import { useTutorialStore } from '@/stores/tutorialStore'
import type { GameEvent as GameEventType } from '@/components/GameEventOverlay.vue'
import { audioManager } from '@/utils/audioManager'
import { storeToRefs } from 'pinia'
import { useGameAudioBridge } from '@/audio/gameAudioBridge'
import {
  sfxTerritoryGain, sfxTerritoryLose, sfxBattleVictory, sfxBattleDefeat,
  sfxDiplomacyTreaty, sfxDiplomacyBreak, sfxTurnAdvance, sfxTurnSummary,
  sfxRebellion, sfxDisaster, sfxWarDeclaration, sfxPeaceTreaty,
} from '@/audio/gameSfx'

const route = useRoute()
const router = useRouter()
const store = useGameStore()
const tutorialStore = useTutorialStore()

const showPolicy = ref(false)
const showAdvisor = ref(false)
const showAdvisorPopup = ref(false)
const showSettings = ref(false)
const showReplay = ref(false)
const showSecurity = ref(false)
const showBatchBuild = ref(false)
const showBatchRecruit = ref(false)
const quickSaving = ref(false)
const showGenerals = ref(false)
const showTalentMarket = ref(false)
const showDiplomacyDeep = ref(false)
const showHistory = ref(false)
const showAIControl = ref(false)
const showAchievement = ref(false)
const showTechTree = ref(false)
const showMuseum = ref(false)

// ===== 游戏音频桥接（场景氛围 + 事件音效） =====
const { showWarPanel, showEnding, endingData, isProcessing, currentRound } = storeToRefs(store)
const gameAudio = useGameAudioBridge({
  showWarPanel,
  showDiplomacyPanel: showDiplomacyDeep,
  showPolicyPanel: showPolicy,
  showEnding,
  endingData,
  isProcessing,
  currentRound,
  isBgmMuted: computed(() => !audioManager.isBgmPlaying()),
})

// ===== 游戏手感增强（3.0 完善） =====
const eventOverlayRef = ref<InstanceType<typeof GameEventOverlay> | null>(null)
const showLoadingOverlay = ref(false)
const loadingTitle = ref('')
const loadingMessage = ref('')
const loadingProgress = ref(0)
const loadingShowProgress = ref(false)

/** 推送游戏事件通知 */
function pushGameEvent(evt: Omit<GameEventType, 'id'>) {
  eventOverlayRef.value?.push(evt)
}

/** 显示加载覆盖层 */
function showLoading(title: string, message = '', withProgress = false) {
  loadingTitle.value = title
  loadingMessage.value = message
  loadingProgress.value = 0
  loadingShowProgress.value = withProgress
  showLoadingOverlay.value = true
}

/** 更新加载进度 */
function updateLoadingProgress(pct: number, msg?: string) {
  loadingProgress.value = Math.min(100, Math.max(0, pct))
  if (msg) loadingMessage.value = msg
}

/** 隐藏加载覆盖层 */
function hideLoading() {
  showLoadingOverlay.value = false
}
const eventDetail = ref<GameEvent | null>(null)
const gameError = ref('')
const edictText = ref('')
const edictResult = ref<any>(null)
const isMajorEdict = ref(false)
const showExecDetail = ref(false)
const showSimDetail = ref(false)  // 4.0 新增：AI推演详情折叠
const edictValidationHint = ref('')
const edictNeedsClarify = ref(false)
let edictValidateTimer: ReturnType<typeof setTimeout> | null = null

/** 从 edict_language 中自动提取圣旨文体头部（诏曰/敕曰/制曰/诰曰/令曰/密敕等） */
const edictFormatHeader = computed(() => {
  const raw = edictResult.value?.ai_analysis?.edict_language || ''
  // 匹配 "奉天承运皇帝，X曰：" 或 "奉天承运皇帝，XX："
  const m = raw.match(/奉天承运皇帝[，,]\s*([^：:]+)[：:]/)
  if (m && m[1].trim()) {
    return `奉天承运皇帝　${m[1].trim()}`
  }
  // 降级：手动查找关键词
  if (raw.includes('诏曰') || raw.includes('诏')) return '奉天承运皇帝　诏曰'
  if (raw.includes('敕曰') || raw.includes('敕')) return '奉天承运皇帝　敕曰'
  if (raw.includes('制曰') || raw.includes('制')) return '奉天承运皇帝　制曰'
  if (raw.includes('诰曰') || raw.includes('诰')) return '奉天承运皇帝　诰曰'
  if (raw.includes('令曰') || raw.includes('令')) return '奉天承运皇帝　令曰'
  if (raw.includes('密敕')) return '奉天承运皇帝　密敕'
  if (raw.includes('册曰') || raw.includes('册')) return '奉天承运皇帝　册曰'
  return '奉天承运皇帝　诏曰'
})

// 圣旨抽屉面板（可拉起/收合）
const edictDrawerOpen = ref(false)
const handlePulse = ref(false)       // 把手徽标脉动动画
const pendingCmdAdded = ref(false)   // 新命令加入标记

// 待定决策（来自各面板的决策结果，显示在颁布圣旨下方和圣旨台中）
interface PendingDecision {
  id: string
  type: 'debate' | 'move_capital' | 'other'
  label: string
  content: string
  timestamp: number
}
const pendingDecisions = ref<PendingDecision[]>([])

/** 从其他面板接收决策 */
function addDecision(d: Omit<PendingDecision, 'id' | 'timestamp'>) {
  const id = `decision_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`
  pendingDecisions.value.push({ ...d, id, timestamp: Date.now() })
  // 自动打开圣旨台
  if (!edictDrawerOpen.value) {
    edictDrawerOpen.value = true
  }
}

/** 点击决策标签 → 填入圣旨文本 */
function applyDecision(d: PendingDecision) {
  const prefix = edictText.value ? '；' : ''
  edictText.value = edictText.value + prefix + d.content
  // 应用后移除该决策
  removeDecision(d.id)
  // 聚焦圣旨输入框
  nextTick(() => {
    const el = document.querySelector('.edict-input') as HTMLTextAreaElement
    if (el) el.focus()
  })
}

/** 移除单条决策 */
function removeDecision(id: string) {
  const idx = pendingDecisions.value.findIndex(d => d.id === id)
  if (idx >= 0) pendingDecisions.value.splice(idx, 1)
}

/** 监听来自子组件的决策事件 */
function onAddEdictDecision(e: Event) {
  const detail = (e as CustomEvent).detail
  if (detail && detail.label && detail.content) {
    addDecision({
      type: detail.type || 'other',
      label: detail.label,
      content: detail.content,
    })
  }
}

function toggleEdictDrawer() {
  edictDrawerOpen.value = !edictDrawerOpen.value
  if (edictDrawerOpen.value) {
    pendingCmdAdded.value = false
  }
}
function removeEdict(index: number) {
  store.pendingEdictCommands.splice(index, 1)
}

// ===== 快捷命令面板 =====
interface QuickCmd {
  icon: string
  label: string
  desc: string
  text: string
}

interface QuickCmdCategory {
  id: string
  label: string
  icon: string
  commands: QuickCmd[]
}

const quickCmdCategories: QuickCmdCategory[] = [
  {
    id: 'military', label: '军事', icon: '⚔️', commands: [
      { icon: '🔰', label: '征兵', desc: '在指定地块招募新兵', text: '于{tile}征募新兵一千，充实军营' },
      { icon: '⚔️', label: '出征', desc: '从出发地块行军至目标地块', text: '命{from}出兵{to}，发兵两千，攻取敌境' },
      { icon: '🛡️', label: '加固城防', desc: '提升地块防御等级', text: '着令{tile}加固城防，增筑城墙' },
      { icon: '🐎', label: '买马', desc: '购买战马充实骑军', text: '命有司购置战马二百匹，以实骑军' },
      { icon: '🎯', label: '训练', desc: '训练士兵提升战力', text: '令{tile}整训士卒一千，厉兵秣马' },
      { icon: '🔍', label: '侦查', desc: '侦查目标地块军情', text: '遣斥候侦查{tile}军情虚实' },
      { icon: '🏴', label: '劫掠', desc: '劫掠敌方地块夺取资源', text: '遣轻骑劫掠{tile}，夺取粮饷辎重' },
      { icon: '🌲', label: '伏击', desc: '在指定地块设伏待敌', text: '于{tile}设伏两千精兵，待敌入瓮' },
    ]
  },
  {
    id: 'internal', label: '内政', icon: '🏛️', commands: [
      { icon: '🌾', label: '屯田', desc: '开发地块农业设施', text: '命{tile}屯田垦荒，开发农田水利' },
      { icon: '🏗️', label: '建造粮仓', desc: '建造粮仓储存粮食', text: '着工部于{tile}兴建粮仓，以实仓储' },
      { icon: '🏥', label: '医政', desc: '配置医馆防治瘟疫', text: '令{tile}设置医馆，防治疫病' },
      { icon: '💛', label: '赈灾', desc: '救济灾民恢复民心', text: '着令赈济{tile}灾民，开仓放粮' },
      { icon: '📜', label: '税政', desc: '调整税率政策', text: '诏令减税轻赋，与民休息' },
      { icon: '👷', label: '徭役', desc: '征发民夫进行工程', text: '征发{tile}民夫修筑工事，以固城防' },
      { icon: '📚', label: '文教', desc: '推行文化教育政策', text: '着礼部开科举、兴书院，以文教化' },
      { icon: '🚢', label: '海策', desc: '推行海洋贸易政策', text: '诏令开海贸，设市舶司以通番商' },
    ]
  },
  {
    id: 'diplomacy', label: '外交', icon: '🤝', commands: [
      { icon: '🔥', label: '宣战', desc: '对目标势力宣战', text: '传檄天下，{target}背信弃义，即日宣战讨伐' },
      { icon: '🤝', label: '同盟', desc: '与目标势力结盟', text: '遣使往{target}议和结盟，共御外敌' },
      { icon: '🕊️', label: '停战', desc: '与目标势力停战', text: '遣使往{target}议和罢兵，休养生息' },
      { icon: '📦', label: '通商', desc: '与目标势力开通贸易', text: '着令与{target}通商互市，互通有无' },
      { icon: '💒', label: '联姻', desc: '与目标势力联姻', text: '遣使往{target}议亲联姻，永结盟好' },
      { icon: '🎁', label: '纳贡', desc: '向目标势力纳贡示好', text: '遣使携礼金往{target}通好纳贡' },
    ]
  },
  {
    id: 'espionage', label: '细作', icon: '🕵️', commands: [
      { icon: '🕵️', label: '派遣细作', desc: '向目标势力派遣间谍', text: '遣细作潜入{target}境内，潜伏待机' },
      { icon: '📋', label: '情报刺探', desc: '刺探目标势力情报', text: '令潜入{target}之细作刺探军机要情' },
      { icon: '💣', label: '破坏', desc: '破坏目标势力设施', text: '令细作于{target}境内纵火破坏粮草辎重' },
      { icon: '🗡️', label: '刺杀', desc: '刺杀目标势力要员', text: '密令细作刺杀{target}军中要员' },
    ]
  },
  {
    id: 'court', label: '朝堂', icon: '🏯', commands: [
      { icon: '🎖️', label: '分封', desc: '分封官员治理地块', text: '分封{name}治理{tile}，赐爵授印' },
      { icon: '🕊️', label: '大赦', desc: '大赦天下释放囚犯', text: '颁诏大赦天下，释放在押囚犯，与民更始' },
      { icon: '🏰', label: '迁都', desc: '将都城迁至指定地块', text: '诏告天下，迁都{tile}，改元建制' },
    ]
  },
]

const activeQuickCmdCat = ref<string>('military')

const activeQuickCmds = computed<QuickCmd[]>(() => {
  const cat = quickCmdCategories.find(c => c.id === activeQuickCmdCat.value)
  return cat?.commands ?? []
})

/** 将快捷命令填入圣旨文本框并聚焦 */
function fillQuickCmd(cmd: QuickCmd) {
  // 如果已有文本则追加，否则直接设置
  const prefix = edictText.value ? (edictText.value.endsWith('；') || edictText.value.endsWith(';') ? '' : '；') : ''
  edictText.value = edictText.value + prefix + cmd.text
  // 清除校验状态
  edictValidationHint.value = ''
  edictNeedsClarify.value = false
  // 检查是否为重大决策
  const majors = ['称帝', '北伐', '中原', '一统', '天下', '迁都', '改元', '登基', '禅让',
    '讨伐', '尽起', '兴师', '誓师', '大都', '御驾', '亲征', '鼎定', '皇位',
    '宣战', '迁都', '传檄', '讨伐']
  isMajorEdict.value = majors.some(k => cmd.text.includes(k))
  // 聚焦到输入框
  nextTick(() => {
    const el = document.querySelector('.edict-input') as HTMLTextAreaElement
    if (el) el.focus()
  })
}

/** 监听待办命令：有新命令加入时自动打开圣旨台 */
watch(() => store.pendingEdictCommands.length, (newLen, oldLen) => {
  if (newLen > 0 && newLen > (oldLen || 0)) {
    // 有新命令加入 → 自动打开圣旨台
    if (!edictDrawerOpen.value) {
      edictDrawerOpen.value = true
      pendingCmdAdded.value = true
    }
    // 触发把手徽标脉动
    handlePulse.value = true
    setTimeout(() => { handlePulse.value = false }, 600)
  }
  // 命令全部被移除时自动关闭
  if (newLen === 0 && edictDrawerOpen.value) {
    edictDrawerOpen.value = false
    pendingCmdAdded.value = false
  }
})

/** 监听待定决策：新决策加入时脉动，全部清空时关闭 */
watch(() => pendingDecisions.value.length, (newLen, oldLen) => {
  if (newLen > 0 && newLen > (oldLen || 0)) {
    handlePulse.value = true
    setTimeout(() => { handlePulse.value = false }, 600)
  }
  if (newLen === 0 && store.pendingEdictCommands.length === 0 && edictDrawerOpen.value) {
    edictDrawerOpen.value = false
    pendingCmdAdded.value = false
  }
})

/** 检测圣旨是否为重大决策 + NL实时校验 */
function onEdictInput() {
  const t = edictText.value

  // 重大决策检测
  const majors = ['称帝', '北伐', '中原', '一统', '天下', '迁都', '改元', '登基', '禅让',
    '讨伐', '尽起', '兴师', '誓师', '大都', '御驾', '亲征', '鼎定', '皇位']
  isMajorEdict.value = majors.some(k => t.includes(k))

  // 防抖实时校验（输入停顿800ms后触发）
  if (edictValidateTimer) clearTimeout(edictValidateTimer)
  edictValidationHint.value = ''
  edictNeedsClarify.value = false

  if (t.trim().length >= 5) {
    edictValidateTimer = setTimeout(async () => {
      try {
        // 4.0: 优先使用 AI 轻量预览（与执行端一致的意图分类）
        try {
          const { simulationPreview: simPreview } = await import('@/services/api')
          const preview = await simPreview(t)
          if (preview?.ai_preview) {
            const p = preview.ai_preview
            const feasibilityMap: Record<string, string> = {
              'feasible': '可执行',
              'constrained': '受限',
              'infeasible': '不可行',
            }
            const feasLabel = feasibilityMap[p.feasibility] || p.feasibility
            const conf = p.confidence ? ` | 置信度${(p.confidence * 100).toFixed(0)}%` : ''
            const riskStr = p.risk_flags?.length ? ` | ⚠${p.risk_flags[0]}` : ''
            const categoryMap: Record<string, string> = {
              'military': '军事征伐', 'civil': '内政建设', 'diplomacy': '邦交纵横',
              'personnel': '人事调度', 'national_policy': '国策大政',
              'strategic_consult': '谋略问策', 'mixed': '综合施政',
              'cancel': '撤回前旨',
            }
            const catName = categoryMap[p.intent_category] || p.intent_category
            edictValidationHint.value = `[${preview.preview_type === 'ai' ? 'AI预览' : '本地'}] ${catName} | ${feasLabel}${conf}${riskStr}`
            edictNeedsClarify.value = p.needs_clarification || false
            if (p.resource_warning) {
              edictValidationHint.value += `\n${p.resource_warning}`
            }
            return
          }
        } catch {
          // AI预览不可用，降级到本地校验
        }
        // 降级：本地关键词校验
        const v = await nlValidateEdict(t)
        if (v.needs_clarification && v.error_prompt) {
          edictValidationHint.value = v.error_prompt.replace(/【.*?】/g, '').trim().slice(0, 200)
          edictNeedsClarify.value = true
        } else if (v.classification?.primary) {
          const clsMap: Record<string, string> = {
            'single_tile': '已识别：地方治理',
            'military': '已识别：军事征伐',
            'diplomacy': '已识别：邦交纵横',
            'personnel': '已识别：人事调度',
            'national_policy': '已识别：国策大政',
            'strategic_consult': '已识别：谋略问策',
            'mixed': '已识别：综合施政',
            'cancel': '已识别：撤回前旨',
          }
          const clsName = clsMap[v.classification.primary] || v.classification.primary
          const conf = v.classification.confidence ? ` (置信度${(v.classification.confidence * 100).toFixed(0)}%)` : ''
          edictValidationHint.value = `[本地] ${clsName}${conf}`
          edictNeedsClarify.value = false
        }
      } catch {
        // 校验静默失败
      }
    }, 800)
  }
}

/** 清空圣旨输入 */
function cancelEdictInput() {
  edictText.value = ''
  edictValidationHint.value = ''
  edictNeedsClarify.value = false
  if (edictValidateTimer) clearTimeout(edictValidateTimer)
}

// ===== 地图右键上下文菜单 =====
const ctxMenu = ref<{
  visible: boolean
  x: number; y: number
  tileId: string; owner: 'own' | 'enemy' | 'neutral' | 'sea'
}>({ visible: false, x: 0, y: 0, tileId: '', owner: 'neutral' })

/** 右键菜单标题（地块名称） */
const ctxTileName = computed(() => {
  const t = store.tiles[ctxMenu.value.tileId]
  if (t) return t.tile_name
  // 海域：从 staticMapTiles 查找
  const st = staticMapTiles.value[ctxMenu.value.tileId]
  if (st && st.terrain === 'sea') {
    return (st as any).sea_zone_name || st.tile_name || '海域'
  }
  return '未知地块'
})

/** 地图左键点击 → 选中地块，行军面板打开时通知 MarchPanel */
function onTileClick(tileId: string) {
  store.selectTile(tileId)
  // 如果行军面板正在显示，通知 MarchPanel 进行出发地/目标选择
  if (store.showMarchPanel) {
    window.dispatchEvent(new CustomEvent('march-panel-select-tile', { detail: { tileId } }))
  }
}

/** 地图六边形右键 → 弹出上下文菜单（行军面板打开时直接选目标） */
function onTileRightClick(tileId: string, event: MouseEvent) {
  store.selectTile(tileId)

  // 行军面板打开时：非己方地块视为目标选择，己方地块视为出发地选择
  if (store.showMarchPanel) {
    window.dispatchEvent(new CustomEvent('march-panel-select-tile', { detail: { tileId } }))
    return
  }

  const tile = store.tiles[tileId]
  const playerFid = store.playerFactionId
  let owner: 'own' | 'enemy' | 'neutral' | 'sea' = 'neutral'

  if (tileId.startsWith('sea_')) {
    owner = 'sea'
  } else if (tile && tile.faction_id) {
    owner = tile.faction_id === playerFid ? 'own' : 'enemy'
  }
  // 计算菜单位置（保持在视口内）
  const menuH = owner === 'own' ? 210 : owner === 'enemy' ? 170 : owner === 'sea' ? 190 : 130
  const menuW = 200
  let mx = event.clientX
  let my = event.clientY
  if (mx + menuW > window.innerWidth - 10) mx = window.innerWidth - menuW - 10
  if (my + menuH > window.innerHeight - 10) my = window.innerHeight - menuH - 10
  ctxMenu.value = { visible: true, x: mx, y: my, tileId, owner }
}

/** 关闭右键菜单 */
function closeCtxMenu() {
  ctxMenu.value.visible = false
}

/** v3.0: 从战争面板打开和平谈判 */
function onOpenPeaceFromWar(war: any) {
  store.warPanelData.value = war
  store.showPeacePanel.value = true
}

/** 右键菜单操作分发 */
function ctxAction(action: string) {
  const tileId = ctxMenu.value.tileId
  const tile = store.tiles[tileId]
  const tileName = tile?.tile_name || '该地'
  closeCtxMenu()

  switch (action) {
    case 'recruit':
      // 打开招兵买马面板 + 加入圣旨指令
      store.selectTile(tileId)
      store.togglePanel('recruit' as any)
      store.pendingEdictCommands.push({
        action: 'recruit',
        params: { tile_id: tileId },
        label: `在${tileName}招兵买马`
      })
      break
    case 'build':
      // 打开营造司面板 + 加入圣旨指令
      store.selectTile(tileId)
      store.togglePanel('construction' as any)
      store.pendingEdictCommands.push({
        action: 'build',
        params: { tile_id: tileId },
        label: `在${tileName}修筑建筑`
      })
      break
    case 'inspect':
      // 体察民情 → 加入圣旨指令队列
      store.pendingEdictCommands.push({
        action: 'inspect',
        params: { tile_id: tileId },
        label: `体察${tileName}民情`
      })
      break
    case 'fortify':
      // 加固城防 → 加入圣旨指令队列
      store.pendingEdictCommands.push({
        action: 'fortify',
        params: { tile_id: tileId },
        label: `加固${tileName}城防`
      })
      break
    case 'march_from':
      // "从此出征"：打开行军面板，该地块预填为出发地
      store.selectTile(tileId)
      store.marchTargetTileId = ''
      store.showMarchPanel = true
      store.pendingEdictCommands.push({
        action: 'march_from',
        params: { from_tile: tileId },
        label: `从${tileName}发兵`
      })
      // 短暂延迟后设置出发地（等 MarchPanel 初始化）
      setTimeout(() => {
        window.dispatchEvent(new CustomEvent('march-panel-set-from', {
          detail: { tileId }
        }))
      }, 100)
      break
    case 'march_to':
      // 出兵征伐/占领：打开行军面板 + 加入圣旨指令
      store.marchTargetTileId = tileId
      store.showMarchPanel = true
      store.pendingEdictCommands.push({
        action: 'march_to',
        params: { target_tile: tileId },
        label: `出兵${tileName}`
      })
      break
    case 'spy':
      // 派遣细作：打开谍报面板 + 加入圣旨指令
      store.selectTile(tileId)
      store.togglePanel('spy' as any)
      const spyTargetFaction = store.tiles[tileId]?.faction_id || ''
      store.pendingEdictCommands.push({
        action: 'spy',
        params: { tile_id: tileId, target_faction: spyTargetFaction },
        label: `向${tileName}派遣细作`
      })
      break
    case 'scout':
      // 侦查敌情 → 加入圣旨指令队列
      store.pendingEdictCommands.push({
        action: 'scout',
        params: { tile_id: tileId },
        label: `侦查${tileName}敌情`
      })
      break
    case 'sabotage':
      // 暗中破坏 → 加入圣旨指令队列
      store.pendingEdictCommands.push({
        action: 'sabotage',
        params: { tile_id: tileId },
        label: `暗中破坏${tileName}`
      })
      break
    case 'claim':
      // 宣示主权 → 加入圣旨指令队列
      store.pendingEdictCommands.push({
        action: 'claim',
        params: { tile_id: tileId },
        label: `宣示${tileName}主权`
      })
      break
    case 'navy_patrol':
      // 派遣水师巡逻海域
      store.pendingEdictCommands.push({
        action: 'navy_patrol',
        params: { tile_id: tileId },
        label: `派遣水师巡逻${tileName}`
      })
      break
    case 'sea_trade':
      // 开辟贸易航线
      store.pendingEdictCommands.push({
        action: 'sea_trade',
        params: { tile_id: tileId },
        label: `开辟经过${tileName}的贸易航线`
      })
      break
    case 'sea_explore':
      // 探索海域
      store.pendingEdictCommands.push({
        action: 'sea_explore',
        params: { tile_id: tileId },
        label: `探索${tileName}海域`
      })
      break
    case 'sea_fish':
      // 渔业征调
      store.pendingEdictCommands.push({
        action: 'sea_fish',
        params: { tile_id: tileId },
        label: `征调${tileName}渔业资源`
      })
      break
    case 'build_port':
      // 在沿海修建港口
      store.pendingEdictCommands.push({
        action: 'build_port',
        params: { tile_id: tileId },
        label: `在${tileName}修建港口`
      })
      break
  }
}

// ===== 图层系统 (14层) =====
const {
  layers: mapLayers,
  layersByCategory,
  toggleLayer,
  setLayerMode,
  setLayerOpacity,
  toggleLayerLock,
  toggleLayerFade,
  resetAllLayers,
  applyPreset,
  updateZoomAdaptive,
} = useMapLayers()

function onToggleLayer(layerId: string) { toggleLayer(layerId) }
function onSetLayerMode(mode: string) { setLayerMode(mode as any) }
function onSetOpacity(layerId: string, opacity: number) { setLayerOpacity(layerId, opacity) }
function onToggleLock(layerId: string) { toggleLayerLock(layerId) }
function onToggleFade(layerId: string) { toggleLayerFade(layerId) }
function onResetAll() { resetAllLayers() }
function onApplyPreset(presetId: string) { applyPreset(presetId) }

// ===== 静态六边形地图数据 =====
const staticMapMeta = ref<any>(null)
const staticMapTiles = ref<Record<string, HexTile>>({})  // tile_id → HexTile
const staticBoundaries = ref<BoundaryData | null>(null)
const staticOutlines = ref<AdminOutline[] | null>(null)
const isMapLoading = ref(true)
const mapLoadTimeout = ref(false)  // 30秒超时后显示重试按钮

/** 合并静态地图 + 运行时势力归属 → 供 HexMapView 渲染 */
const hexMapTiles = computed<HexTile[]>(() => {
  const tiles: HexTile[] = []
  const factionTileMap = buildFactionTileMap()

  for (const [hexId, st] of Object.entries(staticMapTiles.value)) {
    const tile = { ...st }
    // 尝试用 store 中的势力数据覆盖 faction_id
    for (const [fid, ownedKeys] of Object.entries(factionTileMap)) {
      if (matchTileToFaction(tile, ownedKeys)) {
        tile.faction_id = fid
        break
      }
    }
    tiles.push(tile)
  }
  return tiles
})

/** 从 store.tiles（实时游戏状态）构建势力→地名列表映射
 * 
 * 修复：原先读取 FactionState 的 tiles/conquered_tiles 动态字段，
 * 但后端从未设置这些字段，导致地图始终显示静态烘焙的势力归属，
 * 与左下角 store.playerTiles.length 统计不一致。
 * 现在改用 store.tiles（WorldState.tiles 全量地块字典），
 * 按 faction_id 分组收集 tile_name，确保地图与 UI 统计同源。
 */
function buildFactionTileMap(): Record<string, string[]> {
  const result: Record<string, string[]> = {}
  for (const tile of Object.values(store.tiles)) {
    const fid = tile.faction_id
    if (!fid) continue
    const name = (tile.tile_name || '').toLowerCase().replace(/\s/g, '')
    if (!name) continue
    if (!result[fid]) result[fid] = []
    if (!result[fid].includes(name)) result[fid].push(name)
  }
  return result
}

/** 检查 hex tile 是否属于某个势力的领地 */
function matchTileToFaction(tile: HexTile, ownedKeys: string[]): boolean {
  const names = [
    (tile.tile_name || '').toLowerCase().replace(/\s/g, ''),
    (tile.prefecture || '').toLowerCase().replace(/\s/g, ''),
    (tile.province || '').toLowerCase().replace(/\s/g, ''),
  ].filter(Boolean)
  return ownedKeys.some(k => names.some(n => n.includes(k) || k.includes(n)))
}

/** 本地加载 JSON (三级回退: API → 本地 JSON) */
async function fetchLocalJson(path: string): Promise<any> {
  const resp = await fetch(path + '?t=' + Date.now())
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 解析地图数据为 HexTile 字典 */
function ingestMapTiles(data: any) {
  if (!data?.tiles) return
  staticMapMeta.value = data.meta || null
  const map: Record<string, HexTile> = {}
  for (const t of data.tiles) map[t.tile_id] = t as HexTile
  staticMapTiles.value = map
}

/** 加载静态地图数据 + 边界线数据 */
async function loadStaticMap() {
  if (Object.keys(staticMapTiles.value).length > 0) return  // 已加载
  isMapLoading.value = true
  mapLoadTimeout.value = false
  // 30秒超时：若地图数据迟迟未到，显示重试按钮
  const timeoutTimer = setTimeout(() => { mapLoadTimeout.value = true }, 30000)

  let tilesLoaded = false

  // 1) 静态地图 (优先加载含海域的完整版)
  //    三级回退: map_full → 本地map_full → 本地map_final
  //    修复: API 竞速3秒超时，避免后端离线时地图卡死120秒
  try {
    const { default: api } = await import('@/services/api')
    const rFull = await Promise.race([
      (api as any).get('/map/static-full'),
      new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 3000)),
    ])
    if (rFull?.ok !== false && rFull?.data?.data?.tiles) {
      ingestMapTiles(rFull.data.data)
      tilesLoaded = true
      if (import.meta.env.DEV) console.log('[GamePage] 完整地图加载完成 (API):', Object.keys(staticMapTiles.value).length, '个格子')
    } else {
      throw new Error('无完整地图API')
    }
  } catch {
    try {
      // 回退: 本地 map_full.json
      ingestMapTiles(await fetchLocalJson('/data/map/map_full.json'))
      tilesLoaded = true
      if (import.meta.env.DEV) console.log('[GamePage] 完整地图加载完成 (本地):', Object.keys(staticMapTiles.value).length, '个格子')
    } catch {
      // 再回退: map_final.json（仅陆地）
      try {
        ingestMapTiles(await fetchLocalJson('/data/map/map_final.json'))
        tilesLoaded = true
        if (import.meta.env.DEV) console.log('[GamePage] 静态地图加载完成 (本地 map_final):', Object.keys(staticMapTiles.value).length, '个格子')
      } catch (e) {
        console.warn('[GamePage] 静态地图加载全部失败:', e)
      }
    }
  }

  // ✓ 地块数据就绪 → 立即显示地图，边界线/图层配置后台异步加载
  if (tilesLoaded) {
    isMapLoading.value = false
    clearTimeout(timeoutTimer)
  }

  // 2) 边界线 + 行省轮廓 (API → 本地 JSON，3秒超时竞速)
  try {
    const { default: api } = await import('@/services/api')
    const r = await Promise.race([
      (api as any).get('/map/boundaries'),
      new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 3000)),
    ])
    staticBoundaries.value = r?.data?.data?.boundaries || null
    // 行省聚合轮廓 (用于最小缩放视图)
    const rawOutlines = r?.data?.data?.outlines || null
    if (rawOutlines) staticOutlines.value = convertOutlines(rawOutlines)
    if (staticBoundaries.value && import.meta.env.DEV) console.log('[GamePage] 边界线加载完成 (API)')
  } catch {
    try {
      const d = await fetchLocalJson('/data/map/boundaries.json')
      staticBoundaries.value = d?.boundaries || null
      const rawOutlines = d?.outlines || null
      if (rawOutlines) staticOutlines.value = convertOutlines(rawOutlines)
      if (staticBoundaries.value && import.meta.env.DEV) console.log('[GamePage] 边界线加载完成 (本地)')
    } catch {
      console.warn('[GamePage] 边界线加载失败 (地图将无边界线)')
    }
  }

  /** 将后端 outlines dict {pid: [{x,y},...]} 转换为 AdminOutline[] */
  function convertOutlines(raw: Record<string, Array<{x: number; y: number}>>): AdminOutline[] {
    const result: AdminOutline[] = []
    for (const [pid, pts] of Object.entries(raw)) {
      if (!pts || pts.length < 3) continue
      result.push({
        admin_id: pid,
        point_count: pts.length,
        path: pts.map(p => [p.x, p.y]),
      })
    }
    if (import.meta.env.DEV) console.log('[GamePage] 行省轮廓加载完成:', result.length, '个省')
    return result
  }

  // 3) 图层配置 (API → 本地 JSON，3秒超时竞速)
  try {
    await Promise.race([
      loadLayerConfig(),
      new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 3000)),
    ])
    if (import.meta.env.DEV) console.log('[GamePage] 图层配置加载完成')
  } catch {
    console.warn('[GamePage] 图层配置加载失败 (使用本地默认值)')
  }

  isMapLoading.value = false
  mapLoadTimeout.value = false
  clearTimeout(timeoutTimer)
}

// 玩家势力颜色
const playerFactionColor = computed(() => store.playerFaction?.color || '#b89b68')

// 君主画像加载失败标记
const rulerImgFailed = ref(false)
function onRulerImgError() {
  rulerImgFailed.value = true
}

/** faction_id → ruler_*.jpg 映射表（势力君主画像） */
const RULER_IMAGE_MAP: Record<string, string> = {
  faction_zhuyuanzhang: '/assets/factions/ruler_zhuyuan.jpg',
  faction_yuan: '/assets/factions/ruler_yuan.jpg',
  faction_chenyouliang: '/assets/factions/ruler_chen.jpg',
  faction_zhangshicheng: '/assets/factions/ruler_zhang.jpg',
  faction_fangguozhen: '/assets/factions/ruler_fang.jpg',
  faction_mingyuzhen: '/assets/factions/ruler_ming.jpg',
  faction_wangbaobao: '/assets/factions/ruler_wang.jpg',
  faction_mobei: '/assets/factions/ruler_tatar.jpg',
  faction_xushouhui: '/assets/factions/ruler_xushou.jpg',
  // 旧格式兼容
  ruler_zhuyuan: '/assets/factions/ruler_zhuyuan.jpg',
  ruler_yuan: '/assets/factions/ruler_yuan.jpg',
  ruler_chen: '/assets/factions/ruler_chen.jpg',
  ruler_zhang: '/assets/factions/ruler_zhang.jpg',
  ruler_fang: '/assets/factions/ruler_fang.jpg',
  ruler_ming: '/assets/factions/ruler_ming.jpg',
  ruler_tatar: '/assets/factions/ruler_tatar.jpg',
  ruler_wang: '/assets/factions/ruler_wang.jpg',
  ruler_xushou: '/assets/factions/ruler_xushou.jpg',
}



const rulerImage = computed(() => {
  const id = store.playerFactionId
  if (!id) return ''
  // 优先映射表查找
  if (RULER_IMAGE_MAP[id]) return RULER_IMAGE_MAP[id]
  // 尝试直接拼接路径
  return `/assets/factions/${id}.jpg`
})


const playerBuffs = computed(() => store.playerFaction?.buffs || [])
const playerDebuffs = computed(() => store.playerFaction?.debuffs || [])

// ---- 工具栏按钮 ----
const toolbarItems = [
  { id: 'treasury', icon: '💰', label: '国库' },
  { id: 'territory', icon: '🗺️', label: '领土' },
  { id: 'court', icon: '🏯', label: '朝堂' },
  { id: 'military', icon: '⚔️', label: '军事' },
  { id: 'diplomacy', icon: '🤝', label: '外交' },
  { id: 'spy', icon: '🕵️', label: '谍报' },
  { id: 'construction', icon: '🏗️', label: '营造' },
  { id: 'recruit', icon: '🏇', label: '招兵' },
  { id: 'batch-build', icon: '🔄', label: '批量建' },
  { id: 'batch-recruit', icon: '🔄', label: '批量征' },
  { id: 'disaster', icon: '🌪️', label: '灾异' },
  { id: 'royal', icon: '👑', label: '宗室' },
  { id: 'vassal', icon: '🏰', label: '藩镇' },
  { id: 'workshop', icon: '🔧', label: '工坊' },
  { id: 'rebel', icon: '🔥', label: '叛军' },
  { id: 'culture', icon: '📜', label: '民俗' },
  { id: 'events', icon: '📋', label: '邸报' },
  { id: 'law', icon: '⚖️', label: '律法' },
  { id: 'prisoner', icon: '⛓️', label: '俘虏' },
  { id: 'medical', icon: '🏥', label: '疾医' },
  { id: 'sea', icon: '⛵', label: '海策' },
  { id: 'personnel', icon: '👤', label: '人事' },
  { id: 'agent', icon: '🧠', label: 'AI中枢' },
  { id: 'general', icon: '🏯', label: '武将' },
  { id: 'talent-market', icon: '🏛', label: '人才' },
  { id: 'diplomacy-deep', icon: '🕊️', label: '权谋' },
  { id: 'history', icon: '📜', label: '青史' },
  { id: 'ai-control', icon: '🤖', label: 'AI中控' },
] as const

/** 左侧工具栏：军国大事 */
const leftToolbarItems = [
  { id: 'military', icon: '⚔️', label: '军事' },
  { id: 'ambush', icon: '🌲', label: '伏击' },
  { id: 'plunder', icon: '🏴', label: '劫掠' },
  { id: 'diplomacy', icon: '🤝', label: '外交' },
  { id: 'treasury', icon: '💰', label: '国库' },
  { id: 'court', icon: '🏯', label: '朝堂' },
  { id: 'moveCapital', icon: '🏛', label: '迁都' },
  { id: 'construction', icon: '🏗️', label: '营造' },
  { id: 'recruit', icon: '🏇', label: '招兵' },
  { id: 'personnel', icon: '👤', label: '人事' },
  { id: 'general', icon: '🏯', label: '武将' },
  { id: 'talent-market', icon: '🏛', label: '人才' },
  { id: 'rebel', icon: '🔥', label: '叛军' },
  { id: 'vassal', icon: '🏰', label: '藩镇' },
  { id: 'disaster', icon: '🌪️', label: '灾异' },
  { id: 'events', icon: '📋', label: '邸报' },
  { id: 'ai-control', icon: '🤖', label: 'AI中控' },
] as const

/** 右侧工具栏：内政谋略 */
const rightToolbarItems = [
  { id: 'diplomacy-deep', icon: '🕊️', label: '权谋' },
  { id: 'spy', icon: '🕵️', label: '谍报' },
  { id: 'culture', icon: '📜', label: '民俗' },
  { id: 'law', icon: '⚖️', label: '律法' },
  { id: 'law-interrogate', icon: '🔍', label: '刑讯' },
  { id: 'royal', icon: '👑', label: '宗室' },
  { id: 'territory', icon: '🗺️', label: '领土' },
  { id: 'faction_network', icon: '🕸️', label: '势力图' },
  { id: 'prisoner', icon: '⛓️', label: '俘虏' },
  { id: 'medical', icon: '🏥', label: '疾医' },
  { id: 'sea', icon: '⛵', label: '海策' },
  { id: 'workshop', icon: '🔧', label: '工坊' },
  { id: 'agent', icon: '🧠', label: 'AI中枢' },
  { id: 'ai-strategy', icon: '📊', label: 'AI推演' },
  { id: 'batch-build', icon: '🔄', label: '批量建' },
  { id: 'batch-recruit', icon: '🔄', label: '批量征' },
  { id: 'history', icon: '📜', label: '青史' },
  { id: 'audio', icon: '🔊', label: '音效' },
  { id: 'replay', icon: '⏪', label: '回放' },
  { id: 'achievement', icon: '🏆', label: '功勋' },
  { id: 'techTree', icon: '🌳', label: '国策' },
  { id: 'museum', icon: '🏛', label: '史馆' },
] as const

/** 当前弹出面板所在侧 */
const panelSide = ref<'left'|'right'|''>('')

function isToolActive(id: string): boolean {
  // 独立面板
  if (id === 'batch-build') return showBatchBuild.value
  if (id === 'batch-recruit') return showBatchRecruit.value
  if (id === 'general') return showGenerals.value
  if (id === 'talent-market') return showTalentMarket.value
  if (id === 'diplomacy-deep') return showDiplomacyDeep.value
  if (id === 'history') return showHistory.value
  if (id === 'ai-control') return showAIControl.value
  if (id === 'policy') return showPolicy.value
  if (id === 'advisor') return showAdvisor.value
  if (id === 'settings') return showSettings.value
  if (id === 'replay') return showReplay.value
  if (id === 'security') return showSecurity.value
  if (id === 'achievement') return showAchievement.value
  if (id === 'techTree') return showTechTree.value
  if (id === 'museum') return showMuseum.value
  return store.activePanel === id
}

/** 统一关闭所有面板（store-managed + 独立 ref） */
function closeAllPanels() {
  store.activePanel = ''
  showPolicy.value = false
  showAdvisor.value = false
  showAdvisorPopup.value = false
  showGenerals.value = false
  showTalentMarket.value = false
  showBatchBuild.value = false
  showBatchRecruit.value = false
  showDiplomacyDeep.value = false
  showHistory.value = false
  showAIControl.value = false
  showSettings.value = false
  showSecurity.value = false
  showReplay.value = false
  showAchievement.value = false
  showTechTree.value = false
  showMuseum.value = false
  // 关闭 store 管理的面板（行军/战争/和平谈判/结局/回合大事录）
  store.showMarchPanel = false
  store.showWarPanel = false
  store.showPeacePanel = false
  store.showEnding = false
  store.showTurnSummary = false
  // 关闭事件详情 / 圣旨结果 / 圣旨抽屉
  eventDetail.value = null
  edictResult.value = null
  edictDrawerOpen.value = false
  panelSide.value = ''
}

/** 导航至存档管理页：先清理全部面板 → 等待 DOM 卸载 → 再跳转。
 *  确保 GamePage 的 Konva 重 DOM 在 Vue 过渡前进入干净状态，
 *  避免 mode="out-in" 因大量 canvas 拆卸卡住 transitionend。 */
async function navigateToSaveManager() {
  closeAllPanels()
  await nextTick()
  sessionStorage.setItem('_skip_transition', '1')
  router.push('/save-manager')
}

/** 一键快速存档 */
async function quickSaveHandler() {
  if (quickSaving.value || !store.isGameStarted) return
  quickSaving.value = true
  try {
    const result = await quickSave()
    // 轻提示（不阻塞操作）
    const toast = document.createElement('div')
    toast.className = 'quick-save-toast'
    toast.textContent = `已存档 · 槽${result.slot + 1} (第${result.round}回合)`
    document.body.appendChild(toast)
    setTimeout(() => toast.remove(), 2500)
  } catch (e: any) {
    console.warn('快速存档失败:', e)
  } finally {
    quickSaving.value = false
  }
}

/** 打开面板：先关闭全部 → 等待 DOM 更新 → 再打开目标（互斥） */
async function onToolClick(tool: { id: string }) {
  const wasActive = isToolActive(tool.id)
  closeAllPanels()
  await nextTick()       // 等待旧的 v-if 卸载完成
  if (wasActive) return  // 重复点击 = 仅关闭

  if (tool.id === 'batch-build') { showBatchBuild.value = true; return }
  if (tool.id === 'batch-recruit') { showBatchRecruit.value = true; return }
  if (tool.id === 'general') { showGenerals.value = true; return }
  if (tool.id === 'talent-market') { showTalentMarket.value = true; return }
  if (tool.id === 'diplomacy-deep') { showDiplomacyDeep.value = true; return }
  if (tool.id === 'history') { showHistory.value = true; return }
  if (tool.id === 'ai-control') { showAIControl.value = true; return }
  if (tool.id === 'replay') { showReplay.value = true; return }
  if (tool.id === 'security') { showSecurity.value = true; return }
  if (tool.id === 'achievement') { showAchievement.value = true; return }
  if (tool.id === 'techTree') { showTechTree.value = true; return }
  if (tool.id === 'museum') { showMuseum.value = true; return }
  store.activePanel = tool.id as any
}

/** 左侧工具栏点击 → 面板从左侧弹出 */
async function onLeftToolClick(tool: { id: string }) {
  const wasActive = isToolActive(tool.id)
  await onToolClick(tool)
  if (!wasActive) panelSide.value = 'left'
}

/** 右侧工具栏点击 → 面板从右侧弹出 */
async function onRightToolClick(tool: { id: string }) {
  const wasActive = isToolActive(tool.id)
  await onToolClick(tool)
  if (!wasActive) panelSide.value = 'right'
}

// ---- 圣旨执行（增强NL管道：支持校验提示/批量/撤回/长文本拆解） ----
async function executeEdict() {
  if (!edictText.value.trim() || store.isProcessing) return

  // P0修复: 设置 isProcessing 防止并发执行
  store.isProcessing = true

  // 如果有待办指令（右键菜单、面板操作等），自动合并到圣旨文本
  let fullText = edictText.value
  if (store.pendingEdictCommands.length > 0) {
    const cmdText = store.pendingEdictCommands.map(c => c.label).join('；')
    // 避免与圣旨框已有内容重复
    if (!fullText.includes(cmdText)) {
      fullText = fullText + (fullText.endsWith('。') ? '' : '。') + cmdText
    }
  }
  const text = fullText
  const factionId = store.playerFaction?.faction_id || ''

  try {
    // 使用统一NL管道（4.0 启用AI战略推演）
    const result = await nlProcessEdict({
      edict_text: text,
      faction_id: factionId,
      direct_execute: true,
      use_ai: true,
      use_simulation: true,
    })

    // 处理撤回指令
    if (result.is_cancel) {
      await nlCancelCommands({ cancel_all: true })
      edictText.value = ''
      edictValidationHint.value = ''
      edictResult.value = {
        ai_analysis: {
          edict_language: result.edict_language || '奉天承运皇帝，诏曰：前旨收回，着各有司停止施行。钦此。',
          narrative: result.summary || '前旨已撤回',
          summary: '前旨已撤回',
        },
        execution: { total_executed: 0, total_failed: 0, executed: [], failed: [] },
      }
      showExecDetail.value = false
      store.pendingEdictCommands.splice(0, store.pendingEdictCommands.length)
      return
    }

    // 处理谋略问询 → 路由到谋臣面板
    if (result.route_to_advisor) {
      edictText.value = ''
      edictValidationHint.value = ''
      showAdvisorPopup.value = true
      return
    }

    // 处理信息缺失提示
    if (result.needs_clarification && result.error_prompt) {
      edictValidationHint.value = result.error_prompt.replace(/【.*?】/g, '').trim().slice(0, 500)
      edictNeedsClarify.value = true
      // 不清空输入，让玩家补充信息
      return
    }

    // 清空输入
    edictText.value = ''
    edictValidationHint.value = ''
    edictNeedsClarify.value = false

    // 构建展示结果（4.0 增加推演和反馈数据）
    edictResult.value = {
      ai_analysis: {
        edict_language: result.edict_language || result.ai_analysis?.edict_language || `奉天承运皇帝，诏曰：${text.slice(0, 60)}。钦此。`,
        narrative: result.ai_analysis?.narrative || result.summary || '',
        intent_analysis: result.ai_analysis?.intent_analysis || '',
        summary: result.ai_analysis?.summary || result.summary || '',
        resource_assessment: result.ai_analysis?.resource_assessment || '',
        risk_warning: result.ai_analysis?.risk_warning || '',
        follow_up_suggestion: result.ai_analysis?.follow_up_suggestion || '',
        commands_count: result.commands_count,
        invalid_count: result.validation?.filter((v: any) => !v.valid).length || 0,
        ai_generated: result.ai_analysis?.ai_generated ?? false,
      },
      execution: result.execution || { total_executed: 0, total_failed: 0, executed: [], failed: [] },
      classification: result.classification,
      decomposed_steps: result.decomposed_steps,
      simulation_used: result.simulation_used || false,
      simulation: result.simulation || null,
      feedback_report: result.feedback_report || null,
    }
    showExecDetail.value = false

    // 同步世界状态到 store（使用公开方法 refreshWorldState 获取最新后端状态）
    if (result.execution?.total_executed) {
      await store.refreshWorldState()
    }

    // 清空本回待办（圣旨卷轴关闭后推进回合）
    store.pendingEdictCommands.splice(0, store.pendingEdictCommands.length)
  } catch {
    edictResult.value = buildErrorEdictResult('网络或后端异常')
    edictText.value = ''
    edictValidationHint.value = ''
  } finally {
    // P0修复: 确保无论成功/失败都释放 isProcessing
    store.isProcessing = false
  }
}

/** 归一化圣旨结果，确保所有必需字段存在 */
function normalizeEdictResult(result: any): any {
  const analysis = result.ai_analysis || {}
  return {
    ai_analysis: {
      edict_language: analysis.edict_language || analysis.narrative || '圣旨已颁行，天下震动。',
      narrative: analysis.narrative || '',
      intent_analysis: analysis.intent_analysis || '',
      summary: analysis.summary || '圣旨已颁行',
      resource_assessment: analysis.resource_assessment || '',
      risk_warning: analysis.risk_warning || '',
      follow_up_suggestion: analysis.follow_up_suggestion || '',
      commands_count: analysis.commands_count || 0,
      invalid_count: analysis.invalid_count || 0,
      ai_generated: analysis.ai_generated ?? true,
    },
    execution: result.execution || {
      executed: [], failed: [], total_executed: 0, total_failed: 0,
    },
    global_deduction: result.global_deduction || null,
    world_state: result.world_state || null,
    tile_changes: result.tile_changes || [],
    locked_actions: result.locked_actions || [],
    cooling_tiles: result.cooling_tiles || {},
  }
}

/** 构造降级圣旨结果（AI 返回不完整数据时） */
function buildFallbackEdictResult(partial: any, edictText: string): any {
  return {
    ai_analysis: {
      edict_language: (partial?.ai_analysis?.edict_language)
        || (partial?.edict_text)
        || `奉天承运皇帝，诏曰：${edictText.slice(0, 100)}。钦此。`,
      narrative: partial?.ai_analysis?.narrative || '圣旨已颁行。',
      summary: partial?.ai_analysis?.summary || edictText.slice(0, 40),
      intent_analysis: partial?.ai_analysis?.intent_analysis || '',
      resource_assessment: '',
      risk_warning: '',
      follow_up_suggestion: '',
      commands_count: partial?.execution?.total_executed || 0,
      invalid_count: 0,
      ai_generated: true,
    },
    execution: partial?.execution || { executed: [], failed: [], total_executed: 0, total_failed: 0 },
    global_deduction: partial?.global_deduction || null,
    world_state: partial?.world_state || null,
    tile_changes: partial?.tile_changes || [],
    locked_actions: partial?.locked_actions || [],
    cooling_tiles: partial?.cooling_tiles || {},
  }
}

/** 构造错误圣旨结果（网络异常时） */
function buildErrorEdictResult(reason: string): any {
  return {
    ai_analysis: {
      edict_language: '奉天承运皇帝，诏曰：圣旨颁行受阻，有司速查驿传，务使政令通达。钦此。',
      narrative: '圣旨颁行受阻，请重试。',
      summary: '系统异常',
      intent_analysis: '',
      resource_assessment: '',
      risk_warning: '',
      follow_up_suggestion: '',
      commands_count: 0,
      invalid_count: 0,
      ai_generated: false,
    },
    execution: {
      executed: [],
      failed: [{ reason }],
      total_executed: 0,
      total_failed: 1,
    },
  }
}

/** 关闭圣旨卷轴并推进回合 */
async function closeEdictScroll() {
  // P0修复: 防止与 handleAdvanceTurn 并发
  if (store.isProcessing) return

  edictResult.value = null
  isMajorEdict.value = false
  try {
    await store.advanceTurn()
  } catch (e: any) {
    console.warn('[GamePage] 回合推进失败:', e?.message || e)
    // V4.3: 推进失败时尝试刷新世界状态保持 UI 同步
    try { await store.refreshWorldState() } catch { console.warn('[GamePage] 刷新世界状态失败') }
  }
}

/** 圣旨操作类型中文标签映射 */
const ACTION_LABELS: Record<string, string> = {
  recruit: '征兵', buy_horses: '买马', train_troops: '训练', march: '行军', fortify: '加固',
  scout: '侦查', develop: '开发', build: '建造', relief: '赈灾', tax: '税政',
  diplomacy: '外交', spy: '细作', enfeoff: '分封', amnesty: '大赦',
  ambush: '伏击', plunder: '劫掠', move_capital: '迁都',
  cultural_policy: '文教', sea_policy: '海策', medical: '医政', convict_labor: '徭役',
}

function actionLabel(action: string): string {
  return ACTION_LABELS[action] || action
}

/** 将首辅建言快速填入圣旨栏 */
function quickFillEdict(suggestion: string) {
  edictText.value = suggestion
}

// ---- 回合推进 ----
async function handleAdvanceTurn() {
  if (store.isProcessing) return

  // 回合推进音效
  sfxTurnAdvance()

  // 显示加载覆盖层
  showLoading('天下推演', 'AI 正在推演天下大势，请稍候…', true)

  try {
    // 后端 AI 推演（实际进度由服务端控制，前端仅等待）
    await store.advanceTurn()

    updateLoadingProgress(95, '誊写邸报...')

    // 检测并推送关键事件通知
    detectAndPushEvents()

    updateLoadingProgress(100, '完成')
  } catch (e: any) {
    console.warn('回合推进失败:', e?.message || e)
    try { await store.refreshWorldState() } catch { console.warn('[GamePage] 刷新世界状态失败') }
  } finally {
    // 短暂延迟后隐藏加载层，让玩家看到"完成"状态
    setTimeout(() => hideLoading(), 500)
  }
}

/** 检测回合结果并推送事件通知 */
function detectAndPushEvents() {
  // 领土变化
  if (store.tileChangesThisRound && store.tileChangesThisRound.length > 0) {
    const gains = store.tileChangesThisRound.filter((c: any) => c.new_owner === store.playerFactionId)
    const losses = store.tileChangesThisRound.filter((c: any) => c.old_owner === store.playerFactionId && c.new_owner !== store.playerFactionId)

    if (gains.length > 0) {
      pushGameEvent({
        type: 'territory_gain',
        title: `新得${gains.length}处领地`,
        detail: gains.slice(0, 3).map((g: any) => g.tile_name || g.tile_id).join('、') + (gains.length > 3 ? ` 等${gains.length}处` : ''),
        duration: 6000,
      })
      sfxTerritoryGain()
    }
    if (losses.length > 0) {
      pushGameEvent({
        type: 'territory_lose',
        title: `失去${losses.length}处领地`,
        detail: losses.slice(0, 3).map((l: any) => l.tile_name || l.tile_id).join('、') + (losses.length > 3 ? ` 等${losses.length}处` : ''),
        duration: 6000,
      })
      sfxTerritoryLose()
    }
  }

  // 新事件
  const newEvts = store.events.slice(0, 3) // 最近3个事件
  for (const evt of newEvts) {
    if ((evt as any).event_type === 'battle') {
      const isWin = (evt as any).result === 'victory' || (evt as any).outcome === 'win'
      pushGameEvent({
        type: isWin ? 'battle_win' : 'battle_lose',
        title: isWin ? '大捷！' + ((evt as any).title || '') : '兵败' + ((evt as any).title || ''),
        detail: (evt as any).narrative || (evt as any).description || '',
        duration: 7000,
      })
      if (isWin) sfxBattleVictory()
      else sfxBattleDefeat()
    } else if ((evt as any).event_type === 'disaster') {
      pushGameEvent({
        type: 'disaster',
        title: (evt as any).title || '天降灾祸',
        detail: (evt as any).narrative || (evt as any).description || '',
        duration: 6000,
      })
      sfxDisaster()
    } else if ((evt as any).event_type === 'diplomacy') {
      pushGameEvent({
        type: 'diplomacy',
        title: (evt as any).title || '外交变故',
        detail: (evt as any).narrative || (evt as any).description || '',
        duration: 5000,
      })
      sfxDiplomacyTreaty()
    }
  }

  // 叛军检测
  if (store.rebelArmies && store.rebelArmies.length > 0) {
    pushGameEvent({
      type: 'rebellion',
      title: '境内出现叛军',
      detail: `共${store.rebelArmies.length}支叛军需要清剿`,
      duration: 6000,
    })
    sfxRebellion()
  }

  // 灾害检测
  if (store.activeDisasters && store.activeDisasters.length > 0) {
    const latest = store.activeDisasters[store.activeDisasters.length - 1]
    if (latest) {
      pushGameEvent({
        type: 'disaster',
        title: (latest as any).name || '灾害发生',
        detail: (latest as any).description || `影响${(latest as any).affected_tiles || '?'}个地块`,
        duration: 6000,
      })
      sfxDisaster()
    }
  }
}

// ---- factionId 规范化 (V3.0) ----
/** 将短名/别称统一为带 faction_ 前缀的规范势力ID */
function normalizeFactionId(raw: string): string {
  if (!raw) return 'faction_zhuyuanzhang'
  // 已经是规范格式
  if (raw.startsWith('faction_')) return raw
  // 兼容旧格式 ruler_ → 自动转换
  if (raw.startsWith('ruler_')) {
    const legacy: Record<string, string> = {
      ruler_yuan: 'faction_yuan', ruler_zhuyuan: 'faction_zhuyuanzhang',
      ruler_chen: 'faction_chenyouliang', ruler_zhang: 'faction_zhangshicheng',
      ruler_fang: 'faction_fangguozhen', ruler_wang: 'faction_wangbaobao',
      ruler_ming: 'faction_mingyuzhen', ruler_tatar: 'faction_mobei',
      ruler_xushou: 'faction_xushouhui',
    }
    return legacy[raw] || 'faction_zhuyuanzhang'
  }
  // 常见短名映射
  const alias: Record<string, string> = {
    zhuyuan: 'faction_zhuyuanzhang', zhu: 'faction_zhuyuanzhang', 朱元璋: 'faction_zhuyuanzhang',
    chen: 'faction_chenyouliang', chenyoul: 'faction_chenyouliang', 陈友谅: 'faction_chenyouliang',
    yuan: 'faction_yuan', yuanshun: 'faction_yuan', 元顺帝: 'faction_yuan', 元廷: 'faction_yuan',
    zhang: 'faction_zhangshicheng', zhangshicheng: 'faction_zhangshicheng', 张士诚: 'faction_zhangshicheng',
    fang: 'faction_fangguozhen', fangguozhen: 'faction_fangguozhen', 方国珍: 'faction_fangguozhen',
    xushou: 'faction_xushouhui', xushouhui: 'faction_xushouhui', 徐寿辉: 'faction_xushouhui',
    ming: 'faction_mingyuzhen', mingyuzhen: 'faction_mingyuzhen', 明玉珍: 'faction_mingyuzhen',
    wang: 'faction_wangbaobao', wangbaobao: 'faction_wangbaobao', 王保保: 'faction_wangbaobao',
    mobei: 'faction_mobei', 漠北: 'faction_mobei', 漠北诸部: 'faction_mobei',
  }
  return alias[raw.toLowerCase()] || ('faction_' + raw)
}

// ---- 初始加载 ----
async function doInit(rawFactionId: string) {
  const factionId = normalizeFactionId(rawFactionId)
  if (import.meta.env.DEV) console.log('[GamePage] doInit factionId:', rawFactionId, '→', factionId)
  
  gameError.value = ''

  // 并行加载静态六边形地图（不阻塞开局逻辑）
  loadStaticMap().catch(err => console.warn('[GamePage] 静态地图独立加载失败:', err))

  // V4.3: 若已开局且势力一致则跳过重复初始化；势力变更则重置后重新开局
  if (store.isGameStarted) {
    if (store.playerFactionId === factionId) {
      if (import.meta.env.DEV) console.log('[GamePage] 已初始化，跳过')
      return
    }
    // 切换势力 → 重置旧状态
    if (import.meta.env.DEV) console.log('[GamePage] 切换势力，重置状态:', store.playerFactionId, '→', factionId)
    await store.resetGame()
  }

  // 先执行本地 fallback，确保数据立即可用
  try {
    await initLocalFallback(factionId)
    if (import.meta.env.DEV) console.log('[GamePage] 本地地图数据初始化完成，地块数:', Object.keys(store.tiles).length)
  } catch (e) {
    console.warn('[GamePage] 本地 fallback 失败:', e)
  }

  // 验证本地数据完整性
  if (!store.tiles || Object.keys(store.tiles).length === 0) {
    gameError.value = '地图数据加载失败，请刷新重试'
    return
  }
  if (!store.playerFaction) {
    gameError.value = '玩家势力数据加载失败'
    return
  }

  // 后台尝试连接后端获取更完整的世界状态（不阻塞UI）
  try {
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('后端响应超时')), 6000)
    )
    await Promise.race([store.startGame(factionId, 'player_turn'), timeoutPromise])
    if (import.meta.env.DEV) console.log('[GamePage] 后端开局同步完成，地块数:', Object.keys(store.tiles).length)
  } catch (err: any) {
    console.warn('[GamePage] 后端开局未完成，使用本地数据继续:', err?.message || String(err))
  }
}

async function retryInit() {
  const factionId = (route.query.faction as string) || localStorage.getItem('yuanmo_player_faction') || ''
  gameError.value = ''
  await doInit(factionId)
}

const { isFullscreen, toggleFullscreen } = useFullscreen()

// 地图缩放控制
const hexMapRef = ref<InstanceType<typeof HexMapView> | null>(null)
const zoomPercent = computed(() => {
  const s = hexMapRef.value?.scale ?? 1
  return Math.round(s * 100)
})

function onZoomIn() {
  hexMapRef.value?.zoomIn()
}
function onZoomOut() {
  hexMapRef.value?.zoomOut()
}
function onResetView() {
  hexMapRef.value?.resetView()
}

// 全屏由 useFullscreen composable 统一管理

onMounted(async () => {
  // 兼容 /game?faction=xxx 和 /game/tactics-ruler/xxx 两种路由格式
  const factionId = (route.query.faction as string) || (route.params.factionId as string) || localStorage.getItem('yuanmo_player_faction') || ''
  if (!factionId) {
    console.warn('[GamePage] 未检测到玩家势力，重定向到势力选择页')
    router.push('/faction-select')
    return
  }
  // 在 await doInit 之前立即启动 BGM，确保浏览器用户手势上下文有效（避免自动播放策略拦截）
  audioManager.stopAll()
  audioManager.playBgm('gameplay', 2.0)

  await doInit(factionId)
  // 全屏事件由 useFullscreen composable 内部管理，不再重复注册
  window.addEventListener('add-edict-decision', onAddEdictDecision)

  // 新手教程：等待 OnboardingOverlay 关闭后再启动，避免两个浮层叠加
  const ONBOARDING_KEY = 'yuanmo_onboarding_seen'
  const initTutorialWhenReady = () => {
    if (localStorage.getItem(ONBOARDING_KEY)) {
      tutorialStore.init(factionId)
    } else {
      setTimeout(initTutorialWhenReady, 500)
    }
  }
  setTimeout(initTutorialWhenReady, 1200)
})

onUnmounted(() => {
  window.removeEventListener('add-edict-decision', onAddEdictDecision)
  // 离开游玩界面时，停止游戏对局音频
  audioManager.stopAll()
  gameAudio.destroy()
})

// ---- 本地 fallback ----
async function initLocalFallback(factionId: string) {
  let config: any = null
  try { config = await loadFactionsConfig() } catch { console.warn('[GamePage] 加载势力配置失败，使用默认配置') }

  const DEFAULT_FACTIONS: Record<string, any> = {
    faction_yuan: { id: 'faction_yuan', name: '元顺帝', title: '大元皇帝', color: '#8B0000', capital_tile: 'tile_dadu', initial_treasury: 20000, initial_grain: 8000, initial_arms: 300, initial_horses: 200, initial_troops: 6000, initial_reputation: 60, tiles: ['tile_dadu','tile_shangdu','tile_taiyuan','tile_datong','tile_jinan','tile_zhending','tile_baoding','tile_hejian','tile_daming','tile_pingyang','tile_yanan','tile_xian','tile_ganzhou','tile_suzhou_gs','tile_ningxia','tile_liaoyang','tile_shenyang','tile_helin','tile_karakorum'], personality_tags: ['蒙古铁骑','正统名分'], buffs: [{name:'北地铁骑',effect:'骑兵战力+35%',type:'military'}], debuffs: [{name:'勋贵侵蚀',effect:'每月国库流失2%',type:'economy'}] },
    faction_zhuyuanzhang: { id: 'faction_zhuyuanzhang', name: '朱元璋', title: '吴国公', color: '#DC143C', capital_tile: 'tile_yingtian', initial_treasury: 8000, initial_grain: 4000, initial_arms: 80, initial_horses: 30, initial_troops: 3000, initial_reputation: 40, tiles: ['tile_yingtian','tile_chuzhou','tile_hezhou','tile_taiping','tile_zhenjiang','tile_changzhou','tile_huizhou','tile_ningguo','tile_guangde','tile_raozhou','tile_xinzhou'], personality_tags: ['深谋远虑','严刑峻法','知人善任'], buffs: [{name:'安民之治',effect:'流民转化率+30%',type:'civil'}], debuffs: [{name:'文武党争',effect:'朝堂派系冲突概率+20%',type:'court'}] },
    faction_chenyouliang: { id: 'faction_chenyouliang', name: '陈友谅', title: '汉帝', color: '#1E90FF', capital_tile: 'tile_wuchang', initial_treasury: 12000, initial_grain: 6000, initial_arms: 150, initial_horses: 50, initial_troops: 5000, initial_reputation: 35, tiles: ['tile_wuchang','tile_jiangzhou','tile_yuezhou','tile_changsha','tile_hengzhou','tile_jingjiang','tile_longxing','tile_jian','tile_ganzhou_jx','tile_xiangyang','tile_jingzhou','tile_yichang','tile_huangzhou','tile_de_an'], personality_tags: ['野心勃勃','水战精通'], buffs: [{name:'水师精锐',effect:'水域作战力+40%',type:'military'}], debuffs: [{name:'弑主之名',effect:'外交信任-20',type:'diplomacy'}] },
    faction_zhangshicheng: { id: 'faction_zhangshicheng', name: '张士诚', title: '周王', color: '#FF8C00', capital_tile: 'tile_pingjiang', initial_treasury: 15000, initial_grain: 7000, initial_arms: 100, initial_horses: 40, initial_troops: 4000, initial_reputation: 45, tiles: ['tile_pingjiang','tile_hangzhou','tile_songjiang','tile_huzhou','tile_jiaxin','tile_shaoxing','tile_gaoyou','tile_yangzhou','tile_taizhou_js'], personality_tags: ['富甲一方'], buffs: [{name:'盐铁之利',effect:'每回合额外收入+15%',type:'economy'}], debuffs: [{name:'胸无大志',effect:'扩张意愿-30%',type:'military'}] },
    faction_fangguozhen: { id: 'faction_fangguozhen', name: '方国珍', title: '浙东节度', color: '#20B2AA', capital_tile: 'tile_qingyuan', initial_treasury: 10000, initial_grain: 5000, initial_arms: 60, initial_horses: 20, initial_troops: 2500, initial_reputation: 30, tiles: ['tile_qingyuan','tile_taizhou_zj','tile_wenzhou','tile_zhoushan'], personality_tags: ['海商巨贾'], buffs: [{name:'海上贸易',effect:'通商收入+25%',type:'economy'}], debuffs: [{name:'反复无常',effect:'外交信誉-15',type:'diplomacy'}] },
    faction_xushouhui: { id: 'faction_xushouhui', name: '徐寿辉', title: '天完皇帝', color: '#996633', capital_tile: 'tile_xiangyang', initial_treasury: 6000, initial_grain: 4000, initial_arms: 90, initial_horses: 40, initial_troops: 3500, initial_reputation: 35, tiles: ['tile_xiangyang','tile_huangzhou','tile_de_an','tile_runing','tile_yingzhou','tile_nanyang'], personality_tags: ['弥勒信徒','红巾领袖'], buffs: [{name:'弥勒号召',effect:'流民征兵效率+50%',type:'military'}], debuffs: [{name:'根基不稳',effect:'朝堂稳定度每月-3',type:'court'}] },
    faction_mingyuzhen: { id: 'faction_mingyuzhen', name: '明玉珍', title: '大夏皇帝', color: '#B8860B', capital_tile: 'tile_chongqing', initial_treasury: 7000, initial_grain: 3500, initial_arms: 70, initial_horses: 25, initial_troops: 3000, initial_reputation: 40, tiles: ['tile_chongqing','tile_chengdu','tile_kuizhou','tile_baoning','tile_xuzhou_sc','tile_zunyi','tile_shunqing','tile_jiading'], personality_tags: ['仁厚爱民'], buffs: [{name:'巴蜀粮仓',effect:'粮食产量+20%',type:'economy'}], debuffs: [{name:'偏安蜀地',effect:'远征士气-15%',type:'military'}] },
    faction_wangbaobao: { id: 'faction_wangbaobao', name: '王保保', title: '河南王', color: '#666699', capital_tile: 'tile_taiyuan', initial_treasury: 8000, initial_grain: 5000, initial_arms: 120, initial_horses: 150, initial_troops: 4000, initial_reputation: 45, tiles: ['tile_taiyuan','tile_datong','tile_pingyang','tile_yanan','tile_ganzhou','tile_lintao'], personality_tags: ['忠勇无双','骑兵统帅'], buffs: [{name:'铁骑无双',effect:'骑兵战力+40%',type:'military'}], debuffs: [{name:'两线作战',effect:'资源消耗+30%',type:'military'}] },
    faction_mobei: { id: 'faction_mobei', name: '漠北诸部', title: '草原大汗', color: '#887766', capital_tile: 'tile_helin', initial_treasury: 5000, initial_grain: 2000, initial_arms: 80, initial_horses: 200, initial_troops: 4500, initial_reputation: 25, tiles: ['tile_helin','tile_karakorum','tile_shangdu','tile_liaoyang','tile_shenyang'], personality_tags: ['游牧骑射'], buffs: [{name:'游牧骑射',effect:'骑兵战力+45%',type:'military'}], debuffs: [{name:'无固定根基',effect:'非草原地块收益-40%',type:'economy'}] },
  }

  try {
    const factionsData = config?.factions || DEFAULT_FACTIONS
    const factions: Record<string, FactionState> = {}
    for (const [id, fc] of Object.entries(factionsData)) {
      const f = fc as any
      factions[id] = {
        faction_id: id, name: f.name, title: f.title,
        color: f.color, capital_tile: f.capital_tile,
        is_player: id === factionId, is_alive: true,
        treasury: f.initial_treasury || 5000, grain: f.initial_grain || 3000,
        arms: f.initial_arms || 100, horses: f.initial_horses || 50,
        reputation: f.initial_reputation || 40, total_troops: f.initial_troops || 3000,
        total_population: ((f.provinces?.length || 0) + (f.prefectures?.length || 0) + 1) * 50000,
        court_stability: 50, realm_stability: 50, development_level: 20,
        faction_loyalties: {}, personality_tags: f.personality_tags || [],
        unlocked_policies: [], officials: [], prisoners: [],
        buffs: f.buffs || [], debuffs: f.debuffs || [],
      }
    }
    store.factions = factions
    store.playerFactionId = factionId
    store.isGameStarted = true
    store.isGameActive = true

    // 使用真实元代行省/路府区域地块（替代六边形格子）
    const factionMappings = (config?.data?.factions || Object.values(DEFAULT_FACTIONS)).map((f: any) => ({
      faction_id: f.id || f.faction_id,
      provinces: f.provinces || [],
      prefectures: f.prefectures || [],
    }))
    const tiles = generateRegionTiles(factionMappings)
    const tilesObj: Record<string, TileState> = {}
    for (const [id, tile] of tiles) {
      tilesObj[id] = {
        tile_id: tile.tile_id, tile_name: tile.tile_name,
        tile_type: tile.tile_type as any, region: tile.region,
        faction_id: tile.faction_id, population: tile.population,
        troops: tile.troops, grain: tile.grain, morale: tile.morale,
        treasury: tile.treasury, refugee_ratio: tile.refugee_ratio,
        water_works: tile.water_works, granary: tile.granary,
        clinic: tile.clinic, fortification: tile.fortification,
        elite_ratio: 0, stable: 0, armory: 0,
        siege_state: null, garrison_resting: false, disasters: [],
        is_capital: tile.is_capital, is_port: tile.is_port,
        special_effect: tile.special_effect,
      }
    }
    store.tiles = tilesObj

    for (const [fid, f] of Object.entries(factions)) {
      const capitalTile = Object.values(tilesObj).find(t => t.is_capital && t.faction_id === fid)
      if (capitalTile) f.capital_tile = capitalTile.tile_id
    }

    store.addEvent({
      event_id: `game_start_${Date.now()}`, event_type: 'civil',
      severity: 'major', round: 1, title: '天下大乱，群雄并起',
      description: `至正十一年(1351年)，黄河决堤，红巾起义席卷中原。${store.playerFaction?.name || ''}起兵响应，逐鹿天下。`,
      faction_id: store.playerFactionId, tile_id: '', effects: {},
      narrative: `至正十一年(1351年)春，黄河决堤于曹州，百万灾民流离失所。韩山童、刘福通以"石人一只眼，挑动黄河天下反"为号，发动红巾起义。天下响应，群雄割据四方，逐鹿中原之战拉开序幕。`,
    })
  } catch (e: any) {
    console.error('[GamePage] initLocalFallback 内部异常:', e?.message || String(e))
    throw e // V4.2: 重新抛出，让外层感知失败
  }
}

// ---- 工具函数 ----
function openAdvisor() { showAdvisor.value = true }
function openAdvisorPopupFn() {
  closeAllPanels()
  showAdvisorPopup.value = true
}
function onAdvisorApproveEdict(text: string) {
  edictText.value = text
  showAdvisorPopup.value = false
}
function onBatchEdictFill(text: string) {
  edictText.value = text
  // 自动聚焦到圣旨输入框以便颁布
  setTimeout(() => {
    const el = document.querySelector('.edict-input') as HTMLTextAreaElement
    if (el) el.focus()
  }, 100)
}
function showEventDetail(event: GameEvent) { eventDetail.value = event }
function fmtNum(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(Math.floor(n))
}
function stabilityClass(val: number | undefined): string {
  if (val === undefined) return ''
  if (val >= 70) return 'good'
  if (val >= 40) return 'warn'
  return 'danger'
}
function eventTypeName(type: string): string {
  const m: Record<string, string> = { battle:'战斗', diplomacy:'外交', disaster:'灾荒', court:'朝堂', economy:'经济', spy:'谍报', civil:'内政', royal:'宗室', random:'奇遇', ending:'结局', game_start:'开局', policy:'国策', decree:'敕令' }
  return m[type] || type
}
function decisionTypeIcon(type: string): string {
  const m: Record<string, string> = { debate: '🏛', move_capital: '🏰', other: '📋' }
  return m[type] || '📋'
}

function severityName(s: string): string {
  const m: Record<string, string> = { trivial:'寻常', minor:'轻微', major:'重大', critical:'危急' }
  return m[s] || s
}
</script>

<style scoped>
/* ============================================================
   帝王权谋·全局布局
   ============================================================ */

.game-container {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #120d08;
  overflow: hidden;
  font-family: 'STKaiti', 'KaiTi', 'SimSun', serif;
  position: fixed;
  top: 0;
  left: 0;
}

/* ---- 龙纹徽章 ---- */
.banner-emblem .dragon-badge-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 50%;
}

/* ---- 顶层状态栏 ---- */
.top-bar {
  height: var(--topbar-h);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  background: linear-gradient(180deg, #1e1912 0%, #181410 100%);
  border-bottom: 1px solid #2a2418;
  flex-shrink: 0;
  z-index: 100;
  min-height: 36px;
}

.top-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 200px;
}

.dynasty-banner {
  display: flex;
  align-items: center;
  gap: 10px;
}

.banner-emblem {
  width: 44px;
  height: 44px;
  border: 2px solid #b89b68;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  background: rgba(0,0,0,0.3);
}

.dynasty-name {
  font-size: 18px;
  font-weight: bold;
  letter-spacing: 4px;
  color: #b89b68;
}

.dynasty-title {
  font-size: 11px;
  color: #6a5a3a;
  letter-spacing: 2px;
}

.top-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.date-display {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #8a7a5a;
  letter-spacing: 2px;
}

.date-year { color: #c4a85a; }
.date-sep { color: #4a3a2a; font-size: 10px; }
.date-month { color: #b89b68; }
.date-season { color: #8a6a3a; }
.date-round {
  margin-left: 8px;
  padding: 2px 8px;
  background: rgba(184,150,62,0.1);
  border: 1px solid rgba(184,150,62,0.2);
  border-radius: 3px;
  font-size: 11px;
  color: #9a8a6a;
}

/* 资源区 */
.top-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 1;
  flex-wrap: wrap;
  justify-content: flex-end;
  overflow: hidden;
}

.resource-group {
  display: flex;
  gap: 10px;
}

.resource-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 50px;
}

.res-icon { font-size: 14px; line-height: 1; }
.res-value {
  font-size: 13px;
  font-weight: bold;
  color: #c4a87a;
  letter-spacing: 1px;
}
.res-label {
  font-size: 9px;
  color: #5a4a3a;
  letter-spacing: 1px;
}

.gold .res-value { color: #e8c868; }
.grain .res-value { color: #98c868; }
.prestige .res-value { color: #c888d8; }
.troops .res-value { color: #e07050; }
.horses .res-value { color: #d0b060; }
.arms .res-value { color: #80b0c0; }

.resource-divider {
  width: 1px;
  height: 36px;
  background: linear-gradient(180deg, transparent, #3a2a1a, transparent);
}

/* 状态指标 */
.status-group {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  color: #6a5a3a;
}

.status-bar {
  width: 40px;
  height: 5px;
  background: rgba(255,255,255,0.05);
  border-radius: 3px;
  overflow: hidden;
}

.status-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.status-item.good .status-fill { background: #4a8a4a; }
.status-item.good .status-label { color: #6a9a6a; }
.status-item.warn .status-fill { background: #c8a040; }
.status-item.warn .status-label { color: #c8a040; }
.status-item.danger .status-fill { background: #c04040; }
.status-item.danger .status-label { color: #c04040; }

/* 功能按钮 */
.top-buttons {
  display: flex;
  gap: 4px;
  margin-left: 8px;
}
.top-btn.war-btn {
  background: rgba(220, 50, 30, 0.25);
  border-color: rgba(220, 50, 30, 0.5);
  color: #f07060;
  font-weight: bold;
}
.top-btn.war-btn:hover {
  background: rgba(220, 50, 30, 0.4);
}

.top-btn {
  width: 32px;
  height: 32px;
  background: rgba(39,34,26,0.8);
  border: 1px solid rgba(184,150,62,0.25);
  color: #8a7a5a;
  font-size: 13px;
  cursor: pointer;
  border-radius: 4px;
  font-family: 'STKaiti','KaiTi',serif;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.top-btn:hover {
  background: rgba(50,43,32,0.95);
  border-color: #b89b68;
  color: #c4b898;
}

.top-btn-divider {
  width: 1px;
  height: 20px;
  background: rgba(184,150,62,0.18);
  margin: 0 4px;
  align-self: center;
}

/* ---- 中：舆图区域 ---- */
.map-section {
  flex: 1;
  display: flex;
  min-height: 0;
  position: relative;
  overflow: hidden;
}
.map-surface {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: #2a2520;
}

/* 地图加载/空状态覆盖 */
.map-status-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  background: rgba(18, 13, 8, 0.92);
}

.map-status-content {
  text-align: center;
  padding: 32px;
}

.map-status-spinner {
  width: 48px;
  height: 48px;
  margin: 0 auto 20px;
  border: 3px solid rgba(184, 150, 62, 0.2);
  border-top-color: #b89b68;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.map-status-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.map-status-text {
  font-size: 18px;
  color: #b89b68;
  letter-spacing: 4px;
  font-family: 'STKaiti', 'KaiTi', serif;
  margin-bottom: 8px;
}

.map-status-hint {
  font-size: 12px;
  color: #6a5a3a;
  line-height: 1.8;
  max-width: 380px;
  margin: 0 auto;
}

.map-status-hint code {
  background: rgba(184, 150, 62, 0.1);
  border: 1px solid rgba(184, 150, 62, 0.2);
  color: #c4a85a;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-family: 'Consolas', monospace;
}

.btn-reload-map {
  margin-top: 16px;
  padding: 8px 24px;
  background: rgba(184, 150, 62, 0.15);
  border: 1px solid rgba(184, 150, 62, 0.35);
  color: #b89b68;
  cursor: pointer;
  border-radius: 4px;
  font-family: 'STKaiti', 'KaiTi', serif;
  font-size: 13px;
  letter-spacing: 3px;
  transition: all 0.2s;
}

.btn-reload-map:hover {
  background: rgba(184, 150, 62, 0.3);
  border-color: #d4b868;
}


/* 舆图控制 */
.map-controls {
  position: absolute;
  bottom: 16px;
  right: 60px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  z-index: 50;
}

.map-ctrl-btn {
  width: 30px;
  height: 30px;
  background: rgba(28,24,18,0.9);
  border: 1px solid rgba(184,150,62,0.3);
  color: #8a7a5a;
  font-size: 15px;
  cursor: pointer;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: serif;
  transition: all 0.15s;
}

.map-ctrl-btn:hover {
  background: rgba(40,35,25,0.95);
  border-color: #b89b68;
  color: #c4b898;
}

/* 回合推进按钮 */
.advance-turn-btn {
  position: absolute;
  bottom: 16px;
  right: 16px;
  padding: 8px 20px;
  background: linear-gradient(135deg, rgba(184,150,62,0.2) 0%, rgba(184,150,62,0.05) 100%);
  border: 1px solid rgba(184,150,62,0.4);
  color: #c4a85a;
  font-size: 14px;
  cursor: pointer;
  border-radius: 4px;
  font-family: 'STKaiti','KaiTi',serif;
  letter-spacing: 2px;
  display: flex;
  align-items: center;
  gap: 8px;
  z-index: 50;
  transition: all 0.2s;
}

.advance-turn-btn:hover {
  background: rgba(184,150,62,0.3);
  border-color: #d4b868;
  box-shadow: 0 0 16px rgba(184,150,62,0.2);
}

.advance-turn-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.advance-turn-btn.processing {
  animation: pulse 1.5s infinite;
}

.advance-icon { font-size: 12px; }
.advance-text { letter-spacing: 3px; }

@keyframes pulse {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 1; }
}

/* ---- 地图缩放控制 ---- */
.zoom-controls {
  position: absolute;
  bottom: 60px;
  right: 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  z-index: 400;
  background: rgba(20, 16, 8, 0.85);
  border: 1px solid rgba(184, 150, 62, 0.3);
  border-radius: 6px;
  padding: 4px;
  backdrop-filter: blur(6px);
}

.zoom-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: #c4a85a;
  font-size: 18px;
  cursor: pointer;
  border-radius: 4px;
  font-family: 'STKaiti', 'KaiTi', serif;
  transition: all 0.2s;
}

.zoom-btn:hover {
  background: rgba(184, 150, 62, 0.2);
  color: #e8d48b;
}

.zoom-btn:active {
  background: rgba(184, 150, 62, 0.35);
}

.zoom-reset {
  border-top: 1px solid rgba(184, 150, 62, 0.15);
  margin-top: 2px;
  padding-top: 4px;
}

.zoom-level {
  font-size: 11px;
  color: #8a7a5a;
  padding: 2px 4px;
  font-family: 'STKaiti', 'KaiTi', serif;
  letter-spacing: 1px;
  user-select: none;
}

/* ---- 左侧工具栏 ---- */
.left-toolbar {
  width: var(--toolbar-w);
  min-width: 28px;
  background: linear-gradient(270deg, #1a1610 0%, #141008 100%);
  border-right: 1px solid #2a2418;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
  order: -1; /* 确保在地图左侧 */
}

.left-toolbar .tool-btn {
  border-left: none;
  border-right: 2px solid transparent;
}

.left-toolbar .tool-btn:hover {
  background: rgba(184,150,62,0.08);
  color: #8a7a5a;
}

.left-toolbar .tool-btn.active {
  background: rgba(184,150,62,0.12);
  border-right-color: #b89b68;
  color: #b89b68;
}

/* ---- 右侧工具栏 ---- */
.right-toolbar {
  width: var(--toolbar-w);
  min-width: 28px;
  background: linear-gradient(90deg, #1a1610 0%, #141008 100%);
  border-left: 1px solid #2a2418;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
  order: 1;
}

.toolbar-scroll {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  padding: 4px 0;
  gap: 2px;
}

.toolbar-scroll::-webkit-scrollbar { width: 2px; }
.toolbar-scroll::-webkit-scrollbar-thumb { background: rgba(184,150,62,0.15); }

.tool-btn {
  width: 100%;
  padding: 6px 4px;
  background: none;
  border: none;
  color: #5a4a3a;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  font-size: 10px;
  font-family: 'STKaiti','KaiTi',serif;
  transition: all 0.15s;
  border-left: 2px solid transparent;
}

.tool-btn:hover {
  background: rgba(184,150,62,0.08);
  color: #8a7a5a;
}

.tool-btn.active {
  background: rgba(184,150,62,0.12);
  border-left-color: #b89b68;
  color: #b89b68;
}

.tool-icon { font-size: 16px; line-height: 1; }
.tool-label { letter-spacing: 1px; }

/* ===== 圣旨台面板（页面中下方居中弹出） ===== */
.edict-drawer {
  position: fixed;
  bottom: 156px;
  left: 50%;
  transform: translateX(-50%);
  width: min(85vw, 720px);
  max-height: 52vh;
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  z-index: 110;
  overflow: hidden;
}

.edict-drawer-body {
  padding: 14px 20px;
  max-height: 52vh;
  overflow-y: auto;
}
.edict-drawer-body::-webkit-scrollbar { width: 4px; }
.edict-drawer-body::-webkit-scrollbar-track { background: transparent; }
.edict-drawer-body::-webkit-scrollbar-thumb {
  background: rgba(184, 150, 62, 0.2);
  border-radius: 2px;
}

.edict-drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(184, 150, 62, 0.15);
}

.edict-drawer-title {
  font-size: 16px;
  color: #c4a85a;
  letter-spacing: 4px;
  font-weight: bold;
}

.edict-drawer-count {
  font-size: 12px;
  color: #6a5a3a;
  letter-spacing: 2px;
}

.edict-drawer-header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.edict-drawer-close {
  background: none;
  border: 1px solid rgba(184, 150, 62, 0.2);
  color: #8a7a5a;
  font-size: 18px;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  padding: 0;
  transition: all 0.15s;
}
.edict-drawer-close:hover {
  background: rgba(184, 150, 62, 0.15);
  color: #c4a85a;
}

/* 新命令加入时计数脉动 */
.edict-drawer-count.pulse-count {
  animation: countPulse 0.5s ease;
  color: #d4c060;
}

@keyframes countPulse {
  0% { transform: scale(1); }
  50% { transform: scale(1.4); }
  100% { transform: scale(1); }
}

.edict-drawer-empty {
  text-align: center;
  color: #4a3a2a;
  padding: 20px 0;
  font-size: 13px;
  letter-spacing: 2px;
  line-height: 1.8;
}

/* 圣旨台中待定决策区域 */
.edict-drawer-decisions {
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px dashed rgba(184, 150, 62, 0.15);
}

.edict-drawer-subtitle {
  font-size: 11px;
  color: #8a7a5a;
  letter-spacing: 3px;
  margin-bottom: 6px;
}

/* 决策项样式 */
.edict-item.decision-item {
  border-color: rgba(184, 150, 62, 0.2);
  background: rgba(184, 150, 62, 0.04);
  cursor: pointer;
}

.edict-item.decision-item:hover {
  border-color: rgba(200, 168, 74, 0.4);
  background: rgba(184, 150, 62, 0.12);
}

.edict-item-num.decision-num {
  background: rgba(184, 150, 62, 0.18);
  color: #c4a85a;
}

/* 每条圣旨行 */
.edict-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  margin-bottom: 4px;
  background: rgba(184, 150, 62, 0.05);
  border: 1px solid rgba(184, 150, 62, 0.1);
  border-radius: 4px;
  transition: all 0.15s;
}

.edict-item:hover {
  background: rgba(184, 150, 62, 0.1);
  border-color: rgba(184, 150, 62, 0.25);
}

/* 最新加入的命令高亮 */
.edict-item.new-item {
  background: rgba(200, 168, 74, 0.12);
  border-color: rgba(200, 168, 74, 0.35);
  animation: newItemGlow 1.2s ease-out;
}

@keyframes newItemGlow {
  0% { background: rgba(200, 168, 74, 0.22); border-color: rgba(200, 168, 74, 0.5); }
  100% { background: rgba(184, 150, 62, 0.05); border-color: rgba(184, 150, 62, 0.1); }
}

.edict-item-num {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: #b89b68;
  background: rgba(184, 150, 62, 0.12);
  border-radius: 3px;
  flex-shrink: 0;
  font-weight: bold;
}

.edict-item-text {
  flex: 1;
  font-size: 13px;
  color: #c4b89a;
  letter-spacing: 1.5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.edict-item-remove {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid transparent;
  color: #6a4a3a;
  font-size: 14px;
  cursor: pointer;
  border-radius: 3px;
  flex-shrink: 0;
  transition: all 0.15s;
}

.edict-item-remove:hover {
  color: #c04040;
  border-color: rgba(192, 64, 64, 0.4);
  background: rgba(192, 64, 64, 0.08);
}

/* 圣旨台把手（页面中下方固定，居中） */
.edict-drawer-handle {
  position: fixed;
  bottom: 120px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 5px 24px;
  background: linear-gradient(180deg, rgba(24, 18, 10, 0.96) 0%, rgba(18, 13, 8, 0.96) 100%);
  border: 1px solid rgba(184, 150, 62, 0.3);
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  cursor: pointer;
  z-index: 120;
  user-select: none;
  transition: all 0.25s ease;
  min-width: 160px;
}

.edict-drawer-handle:hover {
  background: rgba(30, 22, 10, 0.96);
  border-color: rgba(184, 150, 62, 0.5);
  box-shadow: 0 0 14px rgba(184, 150, 62, 0.1);
}

/* 抽屉打开时把手提升到底部栏+抽屉高度之上 */
.edict-drawer-handle.drawer-open {
  border-color: rgba(184, 150, 62, 0.45);
}

.handle-arrow {
  font-size: 11px;
  color: #b89b68;
  transition: transform 0.3s;
}

.handle-text {
  font-size: 13px;
  color: #b89b68;
  letter-spacing: 4px;
  font-weight: bold;
}

.handle-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  font-size: 10px;
  font-weight: bold;
  color: #120d08;
  background: #c4a85a;
  border-radius: 9px;
  transition: transform 0.15s;
}

/* 把手徽标脉动动画 */
.handle-badge.pulse {
  animation: badgePulse 0.6s cubic-bezier(0.22, 0.61, 0.36, 1);
}

@keyframes badgePulse {
  0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(196, 168, 90, 0.6); }
  50% { transform: scale(1.35); box-shadow: 0 0 12px 3px rgba(196, 168, 90, 0.4); }
  100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(196, 168, 90, 0); }
}

/* 有待办命令时把手整体发光 */
.edict-drawer-handle.has-pending {
  border-color: rgba(184, 150, 62, 0.5);
  box-shadow: 0 0 8px rgba(184, 150, 62, 0.15);
}

/* 抽屉滑动过渡（中下方向上弹出） */
.edict-drawer-slide-enter-active,
.edict-drawer-slide-leave-active {
  transition: all 0.28s cubic-bezier(0.22, 0.61, 0.36, 1);
}
.edict-drawer-slide-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(30px);
}
.edict-drawer-slide-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(30px);
}

/* ---- 底层 ---- */
.bottom-bar {
  height: var(--bottombar-h);
  min-height: 56px;
  display: flex;
  align-items: stretch;
  background: linear-gradient(180deg, #1a1610 0%, #120d08 100%);
  border-top: 1px solid #2a2418;
  flex-shrink: 0;
  z-index: 100;
  position: relative;
}

/* 左：君主面板 — 可伸缩 */
.ruler-panel {
  width: 290px;
  min-width: 160px;
  padding: 8px 12px;
  display: flex;
  align-items: center;
  border-right: 1px solid #2a2418;
  flex-shrink: 1;
  overflow: hidden;
}

.ruler-portrait {
  display: flex;
  align-items: center;
  gap: 14px;
}

.portrait-frame {
  width: 72px;
  height: 72px;
  border: 2px solid #b89b68;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0,0,0,0.4);
  flex-shrink: 0;
  overflow: hidden;
  box-shadow: 0 0 16px rgba(184, 150, 62, 0.2);
}

.portrait-frame .ruler-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: top center;
  border-radius: 6px;
}

.portrait-placeholder {
  font-size: 38px;
}



.ruler-details {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.ruler-name {
  font-size: 20px;
  font-weight: bold;
  letter-spacing: 5px;
  text-shadow: 0 0 10px rgba(220, 180, 80, 0.3), 0 2px 4px rgba(0,0,0,0.8);
}

.ruler-title-text {
  font-size: 12px;
  color: rgba(184, 150, 62, 0.55);
  letter-spacing: 3px;
}

.ruler-stats {
  display: flex;
  gap: 10px;
  margin-top: 2px;
}

.ruler-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
}

.stat-val {
  font-size: 14px;
  color: #b89b68;
  font-weight: bold;
}

.stat-lbl {
  font-size: 9px;
  color: #5a4a3a;
}

.ruler-buffs {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  margin-top: 4px;
}

.buff-tag {
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 2px;
  letter-spacing: 1px;
}

.buff-tag.buff {
  background: rgba(74,138,74,0.2);
  color: #6a9a6a;
  border: 1px solid rgba(74,138,74,0.3);
}

.buff-tag.debuff {
  background: rgba(192,64,64,0.2);
  color: #c06050;
  border: 1px solid rgba(192,64,64,0.3);
}

/* 右：圣旨栏（铺展至剩余空间） */
.edict-bar {
  flex: 1;
  padding: 10px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-left: 1px solid #2a2418;
}

.edict-input-wrap {
  display: flex;
  gap: 8px;
  align-items: center;
  flex: 1;
  min-width: 0;
}

.edict-seal {
  flex-shrink: 0;
  width: 36px; height: 36px;
  filter: drop-shadow(0 0 4px rgba(200,168,74,0.25));
  transition: filter 0.3s;
}
.edict-seal:hover { filter: drop-shadow(0 0 8px rgba(200,168,74,0.45)); }

.edict-input {
  flex: 1;
  min-width: 0;
  background: rgba(0,0,0,0.3);
  border: 1px solid rgba(184,150,62,0.2);
  color: #B89B68;
  font-family: 'STKaiti','KaiTi','SimSun',serif;
  font-size: 13px;
  padding: 8px 10px;
  border-radius: 3px;
  resize: none;
  outline: none;
  letter-spacing: 1px;
  line-height: 20px;
  height: 80px;
}

.edict-input:focus {
  border-color: rgba(184,150,62,0.5);
  box-shadow: 0 0 8px rgba(184,150,62,0.1);
}

.edict-input::placeholder {
  color: #4a3a2a;
  letter-spacing: 1px;
}

/* 重大决策输入高亮 */
.edict-input.edict-major {
  border-color: rgba(200,150,50,0.45);
  box-shadow: 0 0 12px rgba(200,150,50,0.1), inset 0 0 20px rgba(200,150,50,0.03);
  background: rgba(40,25,10,0.45);
}
.edict-input.edict-major::placeholder {
  color: #7a5a30;
}

/* 信息缺失提示样式 */
.edict-input.edict-needs-info {
  border-color: rgba(220, 120, 40, 0.5);
  box-shadow: 0 0 12px rgba(220, 120, 40, 0.12), inset 0 0 16px rgba(220, 120, 40, 0.03);
}

/* NL实时校验提示 */
.edict-validation-hint {
  margin-top: 4px;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-line;
  font-family: STKaiti, KaiTi, serif;
}
.edict-validation-hint.edict-hint-error {
  background: rgba(180, 60, 30, 0.12);
  border: 1px solid rgba(220, 120, 40, 0.3);
  color: #e8a860;
}
.edict-validation-hint.edict-hint-info {
  background: rgba(160, 140, 60, 0.08);
  border: 1px solid rgba(184, 150, 62, 0.2);
  color: #b89b68;
}
.hint-icon { margin-right: 6px; }
.hint-text { letter-spacing: 0.5px; }

.edict-buttons {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.edict-btn {
  padding: 6px 16px;
  background: linear-gradient(135deg, rgba(184,150,62,0.25) 0%, rgba(184,150,62,0.1) 100%);
  border: 1px solid rgba(184,150,62,0.4);
  color: #c4a85a;
  cursor: pointer;
  border-radius: 4px;
  font-family: 'STKaiti','KaiTi',serif;
  font-size: 12px;
  letter-spacing: 3px;
  white-space: nowrap;
  transition: all 0.2s;
}

.edict-btn:hover:not(:disabled) {
  background: rgba(184,150,62,0.35);
  border-color: #d4b868;
  box-shadow: 0 0 12px rgba(184,150,62,0.2);
}

.edict-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.pending-commands {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.pending-tag {
  font-size: 10px;
  padding: 2px 6px;
  background: rgba(102,102,153,0.2);
  border: 1px solid rgba(102,102,153,0.3);
  color: #8877aa;
  border-radius: 3px;
  cursor: pointer;
  letter-spacing: 1px;
  white-space: nowrap;
  transition: all 0.15s;
}

.pending-tag:hover {
  background: rgba(102,102,153,0.35);
  color: #aa99cc;
}

/* ---- 快捷命令面板 ---- */
.quick-cmd-panel {
  width: 220px;
  padding: 6px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-left: 1px solid #2a2418;
  flex-shrink: 0;
  overflow: hidden;
}

.qcp-tabs {
  display: flex;
  gap: 2px;
  overflow-x: auto;
  scrollbar-width: none;
}
.qcp-tabs::-webkit-scrollbar { display: none; }

.qcp-tab {
  padding: 3px 8px;
  background: rgba(0,0,0,0.25);
  border: 1px solid rgba(100,80,50,0.25);
  color: rgba(160,140,100,0.7);
  font-family: 'STKaiti','KaiTi',serif;
  font-size: 11px;
  letter-spacing: 1px;
  cursor: pointer;
  border-radius: 3px;
  transition: all 0.2s;
  white-space: nowrap;
  flex-shrink: 0;
}

.qcp-tab:hover {
  background: rgba(184,150,62,0.12);
  border-color: rgba(184,150,62,0.35);
  color: #c4a85a;
}

.qcp-tab.active {
  background: rgba(184,150,62,0.2);
  border-color: rgba(184,150,62,0.5);
  color: #d4b868;
  box-shadow: 0 0 8px rgba(184,150,62,0.15);
}

.qcp-commands {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 3px;
  overflow-y: auto;
  flex: 1;
  scrollbar-width: thin;
  scrollbar-color: rgba(100,80,50,0.2) transparent;
}

.qcp-cmd {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 6px;
  background: rgba(0,0,0,0.2);
  border: 1px solid rgba(80,70,50,0.2);
  color: rgba(180,160,120,0.75);
  font-family: 'STKaiti','KaiTi',serif;
  font-size: 10px;
  letter-spacing: 0.5px;
  cursor: pointer;
  border-radius: 3px;
  transition: all 0.15s;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
}

.qcp-cmd:hover {
  background: rgba(184,150,62,0.15);
  border-color: rgba(184,150,62,0.4);
  color: #d4b868;
  box-shadow: 0 0 6px rgba(184,150,62,0.1);
}

.qcp-cmd:active {
  background: rgba(184,150,62,0.25);
  transform: scale(0.96);
}

.qcp-cmd-icon {
  font-size: 12px;
  flex-shrink: 0;
  width: 16px;
  text-align: center;
}

.qcp-cmd-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 待定决策标签（金色，区别于指令标签） */
.pending-decisions {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  max-width: 320px;
}

.decision-tag {
  font-size: 10px;
  padding: 2px 6px;
  background: rgba(184, 150, 62, 0.15);
  border: 1px solid rgba(184, 150, 62, 0.35);
  color: #c4a85a;
  border-radius: 3px;
  cursor: pointer;
  letter-spacing: 1px;
  white-space: nowrap;
  transition: all 0.15s;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.decision-tag:hover {
  background: rgba(184, 150, 62, 0.28);
  border-color: rgba(200, 168, 74, 0.55);
  color: #d4c080;
}

.decision-tag-icon {
  font-size: 11px;
  flex-shrink: 0;
}

.decision-tag-remove {
  width: 14px;
  height: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: rgba(160, 100, 60, 0.6);
  font-size: 9px;
  cursor: pointer;
  border-radius: 50%;
  padding: 0;
  margin-left: 2px;
  transition: all 0.15s;
}

.decision-tag-remove:hover {
  color: #c04040;
  background: rgba(192, 64, 64, 0.15);
}

/* ---- 圣旨结果弹窗（卷轴展开，中下方显示） ---- */
.edict-result-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.75);
  display: flex; align-items: flex-end; justify-content: center;
  padding-bottom: 12vh;
  z-index: 5000;
  backdrop-filter: blur(3px);
  transition: background 0.4s;
}
.edict-result-overlay.is-major {
  background: rgba(0,0,0,0.88);
  backdrop-filter: blur(6px);
}

/* 卷轴包装层 */
.edict-scroll-wrapper {
  display: flex; flex-direction: column; align-items: center;
  max-width: 600px; width: 90%;
  max-height: 60vh;
  animation: scrollDescend 0.5s cubic-bezier(0.22, 0.61, 0.36, 1);
}
@keyframes scrollDescend {
  from { opacity: 0; transform: translateY(40px) scale(0.94); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

/* 重大事件：更厚重登场 */
.edict-result-overlay.is-major .edict-scroll-wrapper {
  max-width: 660px;
  animation: scrollCrash 0.6s cubic-bezier(0.16, 0.46, 0.3, 1.2);
}
@keyframes scrollCrash {
  0% { opacity: 0; transform: translateY(60px) scale(0.85); }
  60% { transform: translateY(-8px) scale(1.03); }
  100% { opacity: 1; transform: translateY(0) scale(1); }
}

/* ---- 卷轴两端轴杆 ---- */
.er-scroll-rod {
  display: flex; align-items: center; gap: 0;
  width: 88%; height: 18px;
}
.er-rod-knob {
  width: 18px; height: 18px;
  background: radial-gradient(circle at 40% 40%, #5a4830, #2a1e10);
  border: 2px solid #7a6040;
  border-radius: 50%;
  box-shadow: 0 2px 6px rgba(0,0,0,0.5), inset 0 1px 2px rgba(255,220,160,0.15);
  flex-shrink: 0;
}
.er-rod-bar {
  flex: 1; height: 8px;
  background: linear-gradient(180deg, #4a3820 0%, #3a2818 50%, #4a3820 100%);
  border-radius: 2px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.4);
}

/* ---- 卷轴纸面 ---- */
.edict-result-dialog {
  background:
    linear-gradient(90deg, rgba(60,45,20,0.12) 0%, transparent 8%, transparent 92%, rgba(60,45,20,0.12) 100%),
    linear-gradient(180deg, #2a2418 0%, #1f1a10 100%);
  border-left: 3px solid rgba(184,150,62,0.3);
  border-right: 3px solid rgba(184,150,62,0.3);
  width: 100%;
  max-height: 50vh;
  overflow-y: auto;
  box-shadow:
    inset 0 0 40px rgba(0,0,0,0.3),
    0 8px 48px rgba(0,0,0,0.7);
  position: relative;
}
/* 卷轴纸面纹理 */
.edict-result-dialog::before {
  content: '';
  position: absolute; inset: 0; pointer-events: none;
  background: repeating-linear-gradient(
    0deg, transparent, transparent 28px, rgba(184,150,62,0.015) 28px, rgba(184,150,62,0.015) 29px
  );
  z-index: 1;
}

/* 重大事件弹窗：更宽更大 */
.edict-result-overlay.is-major .edict-result-dialog {
  border-left: 4px solid rgba(200,150,50,0.5);
  border-right: 4px solid rgba(200,150,50,0.5);
  box-shadow:
    0 0 0 1px rgba(200,150,50,0.15),
    0 0 40px rgba(200,150,50,0.08),
    0 16px 80px rgba(0,0,0,0.85);
}

/* 卷轴展开动画 */
.animate-edict-unfurl {
  animation: edictUnfurl 0.8s cubic-bezier(0.22, 0.61, 0.36, 1) both;
  transform-origin: top center;
}
@keyframes edictUnfurl {
  0% { opacity: 0; transform: scaleY(0.1) translateY(-10%); max-height: 0; }
  20% { opacity: 1; }
  100% { transform: scaleY(1) translateY(0); max-height: 68vh; }
}

.er-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid rgba(184,150,62,0.2);
  background: linear-gradient(180deg, rgba(184,150,62,0.08) 0%, transparent 100%);
  position: relative; z-index: 2;
}

.er-header-deco {
  font-size: 18px; color: #8a7040; margin-right: 8px; flex-shrink: 0;
}

.er-header h3 {
  flex: 1;
  font-family: 'STKaiti','KaiTi',serif;
  font-size: 16px; color: #b89b68; letter-spacing: 4px; text-align: center;
}
.edict-result-overlay.is-major .er-header h3 {
  font-size: 20px; color: #c8a84a; letter-spacing: 8px;
  text-shadow: 0 0 20px rgba(200,168,74,0.3);
}

.er-close {
  width: 28px; height: 28px; border: 1px solid rgba(120,100,60,0.2);
  background: rgba(0,0,0,0.2); border-radius: 50%;
  font-size: 14px; cursor: pointer; color: #6a5a3a;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s;
}
.er-close:hover { color: #c06050; border-color: #c06050; background: rgba(192,96,80,0.1); }

.er-body { padding: 18px 20px; position: relative; z-index: 2; }

/* ---- 卷轴内各内容区（parchment 暗纸风格） ---- */

/* AI 深度分析区 */
.er-ai-analysis {
  margin-bottom: 14px;
  padding: 10px 14px;
  background: linear-gradient(90deg, rgba(60,50,30,0.35) 0%, rgba(40,35,22,0.2) 100%);
  border-left: 3px solid rgba(140,160,120,0.4);
  border-radius: 0 3px 3px 0;
}
.er-ai-label {
  font-size: 10px; letter-spacing: 3px; color: rgba(160,180,140,0.7);
  margin-bottom: 4px;
}
.er-ai-content {
  font-size: 12px; color: rgba(180,170,140,0.8); line-height: 1.7;
}

/* 资源评估 */
.er-resource-box {
  margin-bottom: 14px; padding: 10px 14px;
  background: rgba(40,35,22,0.4);
  border: 1px solid rgba(140,120,70,0.25);
  border-radius: 3px;
}
.er-resource-title {
  font-size: 10px; letter-spacing: 3px; color: rgba(180,160,100,0.7);
  margin-bottom: 2px;
}
.er-resource-text {
  font-size: 11px; color: rgba(170,150,120,0.8); line-height: 1.6;
}

/* 尚书省批复正文 */
.er-narrative {
  font-family: 'STKaiti','KaiTi',serif;
  font-size: 15px; color: #c4b898; line-height: 2;
  margin-bottom: 14px; letter-spacing: 1px;
  padding: 12px 14px;
  background: rgba(184,150,62,0.04);
  border-radius: 3px;
  border: 1px solid rgba(184,150,62,0.12);
}
.er-narrative-icon { color: #b89b68; margin-right: 6px; }

/* 风险警示 */
.er-risk {
  margin-bottom: 14px; padding: 8px 14px;
  background: rgba(180,60,40,0.08);
  border: 1px solid rgba(180,60,40,0.25);
  border-radius: 3px;
  font-size: 11px; color: rgba(210,140,110,0.85);
}
.er-risk-icon { margin-right: 4px; }

/* 执行结果区 */
.er-section { margin-bottom: 14px; }

.er-section-title {
  font-size: 11px; margin-bottom: 6px;
  letter-spacing: 2px; color: rgba(170,150,120,0.8);
  display: flex; align-items: center; gap: 6px;
}
.er-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
.er-dot.green { background: rgba(130,180,130,0.7); }
.er-dot.red { background: rgba(200,100,80,0.7); }

.er-item {
  font-size: 11px; padding: 6px 10px; border-radius: 2px; margin-bottom: 4px;
  display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px;
}
.er-item.success {
  background: rgba(100,150,100,0.06); color: rgba(160,190,160,0.85);
  border-left: 2px solid rgba(130,180,130,0.3);
}
.er-item.fail {
  background: rgba(200,100,80,0.06); color: rgba(210,140,110,0.85);
  border-left: 2px solid rgba(200,100,80,0.3);
}
.er-action-tag {
  font-size: 10px; font-weight: bold; letter-spacing: 1px;
  background: rgba(184,150,62,0.12); color: rgba(190,165,110,0.85);
  padding: 1px 6px; border-radius: 2px; white-space: nowrap;
}
.er-action-msg {
  flex: 1; min-width: 0; word-break: break-all;
}
.er-action-reason {
  font-size: 10px; color: rgba(130,110,80,0.7); font-style: italic; width: 100%;
}
.er-fail-reason {
  color: rgba(210,130,100,0.85); font-weight: 500;
}

/* 圣旨总摘要 */
.er-summary-box {
  font-size: 12px; color: rgba(170,150,120,0.8); line-height: 1.7;
  padding: 10px 14px; margin-bottom: 14px;
  background: rgba(184,150,62,0.04);
  border-radius: 3px;
  border: 1px solid rgba(184,150,62,0.1);
}

/* 首辅建言 */
.er-followup {
  padding: 10px 14px; margin-bottom: 10px;
  background: linear-gradient(90deg, rgba(80,110,130,0.12) 0%, rgba(40,50,60,0.06) 100%);
  border-left: 3px solid rgba(120,150,170,0.35);
  border-radius: 0 3px 3px 0;
  font-size: 12px; color: rgba(160,180,200,0.8); line-height: 1.7;
}
.er-followup-label {
  font-size: 10px; color: rgba(140,170,190,0.7); letter-spacing: 2px; font-weight: bold;
}

/* 快捷填入 */
.er-quick-fill {
  margin-bottom: 8px;
}
.er-quick-btn {
  width: 100%; padding: 9px;
  background: rgba(100,150,150,0.08);
  border: 1px solid rgba(100,150,150,0.25);
  color: rgba(140,190,180,0.8); cursor: pointer;
  border-radius: 3px; font-size: 12px; letter-spacing: 2px;
  font-family: 'STKaiti','KaiTi',serif;
  transition: all 0.2s;
}
.er-quick-btn:hover {
  background: rgba(100,150,150,0.18);
  border-color: rgba(140,200,190,0.5);
}

/* 推进月份按钮 */
.er-advance {
  width: 100%; padding: 12px; margin-top: 10px;
  background: linear-gradient(135deg, rgba(200,160,50,0.15) 0%, rgba(200,160,50,0.04) 100%);
  border: 1px solid rgba(200,160,50,0.35);
  color: rgba(210,180,100,0.85); cursor: pointer;
  border-radius: 3px;
  font-family: 'STKaiti','KaiTi',serif;
  font-size: 15px; letter-spacing: 4px;
  transition: all 0.25s;
}
.er-advance:hover {
  background: rgba(200,160,50,0.25);
  border-color: rgba(220,190,120,0.6);
  box-shadow: 0 0 20px rgba(200,150,50,0.1);
}

/* ---- 圣旨正文（文言文卷轴核心展示） ---- */
.edict-language-body {
  font-family: 'STKaiti','KaiTi',serif;
  font-size: 18px; line-height: 2.2; color: #d4c898;
  padding: 20px 24px; margin-bottom: 16px;
  background:
    repeating-linear-gradient(
      0deg, transparent, transparent 41px, rgba(184,150,62,0.06) 41px, rgba(184,150,62,0.06) 42px
    );
  border: 1px solid rgba(184,150,62,0.2);
  border-radius: 2px;
  text-align: justify;
  letter-spacing: 2px;
  text-shadow: 0 1px 2px rgba(0,0,0,0.5);
  position: relative;
}

/* 尚书省执行附注（可折叠） */
.edict-exec-summary {
  margin-bottom: 12px;
}
.ees-label {
  font-size: 11px; color: rgba(160,140,100,0.7); cursor: pointer;
  letter-spacing: 2px; padding: 4px 0;
  display: flex; align-items: center; gap: 8px;
  font-family: 'STKaiti','KaiTi',serif;
  user-select: none;
  transition: color 0.2s;
}
.ees-label:hover { color: rgba(200,170,120,0.9); }
.ees-counter { font-size: 10px; color: rgba(140,120,80,0.6); }
.ees-detail {
  margin-top: 6px; padding-left: 16px;
  border-left: 2px solid rgba(184,150,62,0.15);
}
.ees-item {
  font-size: 11px; padding: 3px 0; display: flex; gap: 6px; align-items: baseline;
}
.ees-item.ok { color: rgba(140,180,140,0.75); }
.ees-item.fail { color: rgba(180,120,100,0.75); }
.ees-tag {
  font-size: 10px; font-weight: bold;
  background: rgba(184,150,62,0.12); color: rgba(180,160,110,0.8);
  padding: 1px 5px; border-radius: 2px; white-space: nowrap;
}

/* ============================================================
   4.0 AI战略推演面板
   ============================================================ */
.edict-simulation-panel {
  margin: 12px 0;
  border: 1px solid rgba(120,150,140,0.25);
  border-radius: 3px;
  background: rgba(30,45,40,0.3);
  overflow: hidden;
}
.sim-label {
  font-size: 11px; color: rgba(130,180,160,0.7); cursor: pointer;
  letter-spacing: 2px; padding: 6px 10px;
  display: flex; align-items: center; justify-content: space-between;
  background: rgba(40,60,50,0.25);
}
.sim-label:hover { color: rgba(160,210,180,0.9); }
.sim-confidence { 
  font-size: 10px; color: rgba(140,180,160,0.65);
  font-style: italic;
}
.sim-risk { margin-left: 6px; }
.sim-risk-low { color: rgba(120,180,120,0.8); }
.sim-risk-medium { color: rgba(200,180,100,0.8); }
.sim-risk-high { color: rgba(200,130,80,0.8); }
.sim-risk-critical { color: rgba(200,80,60,0.9); }

.sim-detail {
  padding: 10px 14px;
  font-size: 11px; color: rgba(200,190,170,0.75);
  line-height: 1.6;
  max-height: 320px; overflow-y: auto;
}
.sim-section {
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(120,150,140,0.1);
}
.sim-section:last-child { border-bottom: none; margin-bottom: 0; }
.sim-section-title {
  font-size: 10px; font-weight: bold; color: rgba(150,180,160,0.7);
  letter-spacing: 2px; margin-bottom: 4px;
  text-transform: uppercase;
}
.sim-text { color: rgba(180,170,150,0.7); }
.sim-step {
  padding: 2px 0; margin-bottom: 2px;
}
.sim-step-num {
  display: inline-block; width: 18px; color: rgba(160,180,140,0.6);
}
.sim-step-effect {
  display: block; margin-left: 18px; font-size: 10px;
  color: rgba(140,160,130,0.55); font-style: italic;
}
.sim-risk-item {
  padding: 2px 0; font-size: 10px;
}
.sim-risk-type {
  display: inline-block; padding: 0 4px; margin-right: 4px;
  background: rgba(184,150,62,0.12); color: rgba(180,160,110,0.7);
  border-radius: 2px; font-weight: bold;
}
.sim-risk-prob {
  margin: 0 4px; color: rgba(160,140,100,0.6); font-size: 9px;
}
.sim-risk-impact { margin: 0 4px; font-size: 9px; }
.sim-impact-low { color: rgba(120,180,120,0.8); }
.sim-impact-medium { color: rgba(200,180,100,0.8); }
.sim-impact-high { color: rgba(200,130,80,0.8); }
.sim-impact-critical { color: rgba(200,80,60,0.9); font-weight: bold; }

.sim-geo-item {
  padding: 1px 0; font-size: 10px;
}
.sim-resource-grid {
  display: flex; gap: 12px; flex-wrap: wrap;
  font-size: 10px; color: rgba(160,150,130,0.65);
}
.sim-feedback {
  background: rgba(40,50,40,0.2); border-radius: 2px; padding: 6px 8px;
}
.sim-suggestion {
  margin-top: 4px; font-size: 10px; color: rgba(200,180,130,0.7);
  font-style: italic;
}

/* 主关闭按钮 → 推进回合 */
.er-advance-main {
  width: 100%; padding: 14px; margin-top: 8px;
  background: linear-gradient(135deg, rgba(200,160,50,0.18) 0%, rgba(180,120,30,0.06) 100%);
  border: 1px solid rgba(200,160,50,0.4);
  color: rgba(220,190,120,0.9); cursor: pointer;
  border-radius: 3px;
  font-family: 'STKaiti','KaiTi',serif;
  font-size: 16px; letter-spacing: 6px;
  transition: all 0.3s;
  text-shadow: 0 0 10px rgba(200,150,50,0.2);
}
.er-advance-main:hover {
  background: linear-gradient(135deg, rgba(200,160,50,0.3) 0%, rgba(180,120,30,0.12) 100%);
  border-color: rgba(220,190,120,0.7);
  box-shadow: 0 0 24px rgba(200,150,50,0.15), inset 0 1px 0 rgba(255,220,160,0.08);
  color: rgba(240,220,160,1);
  letter-spacing: 8px;
}

/* ============================================================
   错误状态
   ============================================================ */
.game-error-overlay {
  position: fixed; inset: 0;
  display: flex; align-items: center; justify-content: center;
  background: #120d08; z-index: 10000;
}

.game-error-box {
  text-align: center; padding: 48px 40px;
  background: linear-gradient(180deg, #1e1912 0%, #181410 100%);
  border: 1px solid #3a2a1a;
  border-radius: 8px; max-width: 400px;
}

.game-error-box .error-title {
  font-size: 22px; letter-spacing: 6px;
  margin-bottom: 12px;
  font-family: 'STKaiti','KaiTi',serif;
  color: #e07060;
}

.game-error-box .error-hint {
  font-size: 13px; color: #6a5a3a;
  line-height: 1.8; margin-bottom: 20px;
}

.btn-retry, .btn-back {
  padding: 8px 24px; margin: 0 6px;
  border-radius: 4px; cursor: pointer;
  font-family: 'STKaiti','KaiTi',serif; font-size: 14px; letter-spacing: 3px;
}

.btn-retry {
  background: rgba(184,150,62,0.2);
  border: 1px solid rgba(184,150,62,0.4); color: #b89b68;
}

.btn-retry:hover {
  background: rgba(184,150,62,0.35); border-color: #d4b868;
}

.btn-back {
  background: none; border: 1px solid #3a2a1a; color: #6a5a3a;
}

.btn-back:hover { border-color: #6a5a3a; color: #8a7a5a; }

/* ---- 事件详情弹窗（保留） ---- */
.event-detail-overlay {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex; align-items: center; justify-content: center;
  z-index: 4000;
}

.event-detail-dialog {
  background: linear-gradient(180deg, #27221a 0%, #1c1812 100%);
  border: 2px solid #3a2a1a;
  border-radius: 6px; max-width: 500px; width: 90%;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.55);
}

.edd-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; border-bottom: 1px solid #2a2418;
  background: linear-gradient(180deg, #322b20 0%, #27221a 100%);
}

.edd-header h3 {
  font-family: 'STKaiti','KaiTi',serif;
  font-size: 16px; font-weight: normal;
  letter-spacing: 2px; color: #b89b68;
}

.edd-close {
  width: 24px; height: 24px; border: none; background: none;
  font-size: 16px; cursor: pointer; color: #8a7a5a;
}

.edd-close:hover { color: #e07060; }

.edd-body { padding: 16px; }

.edd-meta {
  display: flex; gap: 12px; font-size: 11px;
  color: #6a5a3a; margin-bottom: 12px;
}

.edd-narrative {
  font-size: 14px; color: #c4b898;
  line-height: 1.8; letter-spacing: 1px;
}

.animate-fade-in { animation: fadeIn 0.25s ease-out; }
@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.96); }
  to { opacity: 1; transform: scale(1); }
}

/* 面板弹出动画 —— 从工具栏一侧滑入 */
.animate-slide-left {
  animation: slideInLeft 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes slideInLeft {
  from { opacity: 0; transform: translateX(-24px); }
  to   { opacity: 1; transform: translateX(0); }
}

.animate-slide-right {
  animation: slideInRight 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes slideInRight {
  from { opacity: 0; transform: translateX(24px); }
  to   { opacity: 1; transform: translateX(0); }
}

/* ============================================================
   地图右键上下文菜单（古风竹简风格）
   ============================================================ */

/* 透明遮罩层：点击空白关闭菜单 */
.ctx-backdrop {
  position: fixed;
  inset: 0;
  z-index: 900;
  background: transparent;
}

.tile-context-menu {
  position: fixed;
  z-index: 1000;
  background: linear-gradient(180deg, #2a2418 0%, #1c1810 100%);
  border: 1px solid rgba(184, 150, 62, 0.4);
  border-radius: 6px;
  min-width: 180px;
  padding: 4px 0;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6), 0 0 16px rgba(184, 150, 62, 0.08);
  font-family: 'STKaiti', 'KaiTi', serif;
  user-select: none;
  animation: ctxFadeIn 0.12s ease-out;
}

@keyframes ctxFadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

.ctx-menu-title {
  padding: 8px 16px 4px;
  font-size: 13px;
  color: #c4a85a;
  letter-spacing: 3px;
  text-align: center;
  font-weight: bold;
}

.ctx-menu-divider {
  height: 1px;
  margin: 4px 10px;
  background: linear-gradient(90deg, transparent, rgba(184, 150, 62, 0.3), transparent);
}

.ctx-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 16px;
  background: none;
  border: none;
  color: #b8a880;
  font-size: 13px;
  letter-spacing: 2px;
  cursor: pointer;
  font-family: 'STKaiti', 'KaiTi', serif;
  transition: all 0.12s;
  text-align: left;
}

.ctx-menu-item:hover {
  background: rgba(184, 150, 62, 0.15);
  color: #d4c090;
}

.ctx-menu-item.danger {
  color: #e08060;
}

.ctx-menu-item.danger:hover {
  background: rgba(200, 80, 50, 0.15);
  color: #f0a080;
}

.ctx-icon {
  font-size: 15px;
  width: 20px;
  text-align: center;
  flex-shrink: 0;
}

/* 快速存档提示 */
.quick-save-toast {
  position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
  padding: 8px 20px;
  background: rgba(45, 106, 79, 0.92);
  color: #fff; font-size: 13px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  z-index: 9999;
  animation: toast-in 0.3s ease, toast-out 0.4s ease 2.1s forwards;
  pointer-events: none;
}
@keyframes toast-in { from { opacity: 0; transform: translateX(-50%) translateY(10px); } to { opacity: 1; transform: translateX(-50%) translateY(0); } }
@keyframes toast-out { from { opacity: 1; } to { opacity: 0; transform: translateX(-50%) translateY(-8px); } }
.top-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* ===== 响应式：全局布局 + 圣旨台 + 弹窗适配 ===== */
@media (max-width: 1280px) {
  .top-left { min-width: 140px; }
  .dynasty-banner { gap: 6px; }
  .banner-emblem { width: 32px; height: 32px; }
  .resource-item { min-width: 40px; }
  .res-value { font-size: 11px; }
  .res-label { font-size: 8px; }
}

@media (max-width: 1024px) {
  .banner-emblem { width: 28px; height: 28px; }
  .resource-group { gap: 4px; }
  .resource-item { min-width: 36px; }
  .func-btns { gap: 2px; }
}

@media (max-width: 768px) {
  .top-left { flex: 0 0 auto; min-width: 100px; }
  .banner-emblem { width: 24px; height: 24px; }
  .banner-name { font-size: var(--fs-sm); }
  .date-display { font-size: var(--fs-sm); }
  .resource-item { min-width: 32px; }
  .resource-divider { height: 24px; }
  .func-btns button { width: 26px; height: 26px; }
  .ruler-panel { width: auto; min-width: 120px; padding: 6px 8px; }
  .portrait-frame { width: 48px; height: 48px; }
  .ruler-portrait { gap: 8px; }
  .ruler-detail { font-size: 11px; }
  .edict-drawer-handle {
    bottom: 100px;
    padding: 4px 16px;
    min-width: 130px;
  }
  .handle-text { font-size: 12px; letter-spacing: 2px; }
  .edict-drawer {
    bottom: 132px;
    width: 94vw;
    max-height: 45vh;
    border-radius: 6px 6px 0 0;
  }
  .edict-drawer-body {
    padding: 10px 14px;
    max-height: 45vh;
  }
  .edict-result-overlay { padding-bottom: 8vh; }
  .edict-scroll-wrapper { max-width: 95vw; }
  .edict-result-dialog { max-height: 42vh; }
}

@media (max-width: 480px) {
  .top-left { min-width: 80px; }
  .banner-emblem { width: 20px; height: 20px; }
  .banner-name { display: none; }
  .resource-group { gap: 2px; }
  .resource-item { min-width: 28px; }
  .res-icon { font-size: 10px; }
  .res-value { font-size: 10px; }
  .res-label { display: none; }
  .func-btns button { width: 22px; height: 22px; }
  .ruler-panel { min-width: 80px; padding: 4px 6px; }
  .portrait-frame { width: 36px; height: 36px; }
  .ruler-detail { font-size: 10px; }
  .edict-drawer-handle {
    bottom: 90px;
    padding: 3px 12px;
    min-width: 110px;
  }
  .handle-text { font-size: 11px; letter-spacing: 2px; }
  .handle-arrow { font-size: 10px; }
  .edict-drawer {
    bottom: 118px;
    width: 96vw;
    max-height: 40vh;
  }
  .edict-drawer-body {
    padding: 8px 10px;
    max-height: 40vh;
  }
  .edict-drawer-title { font-size: 14px; letter-spacing: 2px; }
  .edict-item { padding: 6px 10px; }
  .edict-item-text { font-size: 11px; }
  .edict-result-overlay {
    padding-bottom: 5vh;
  }
  .edict-result-dialog {
    max-height: 38vh;
  }
}
</style>
