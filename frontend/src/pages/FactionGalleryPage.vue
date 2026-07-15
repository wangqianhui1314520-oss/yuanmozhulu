<template>
  <div class="gallery-page">
    <div class="bg-overlay"></div>

    <!-- 顶部导航 -->
    <header class="gallery-topbar">
      <button v-audio class="back-btn" @click="$router.back()">
        <span>&#x25C0;</span> 返回
      </button>
      <div class="topbar-title">
        <span class="title-main">九 大 势 力 图 鉴</span>
        <span class="title-sub">元末逐鹿 · 群雄列传</span>
      </div>
      <div class="topbar-spacer"></div>
    </header>

    <!-- 图鉴内容区 -->
    <div class="gallery-scroll">
      <!-- 时代背景序幕 -->
      <section class="prologue-section">
        <div class="prologue-card">
          <div class="prologue-year">至正十一年 · 1351</div>
          <h2 class="prologue-title">天 下 大 乱</h2>
          <p class="prologue-text">
            元顺帝在位，黄河屡决，饿殍遍野。朝廷强征十五万民夫修治黄河，白莲教韩山童、刘福通凿独眼石人埋于河堤——
          </p>
          <p class="prologue-quote">"石人一只眼，挑动黄河天下反"</p>
          <p class="prologue-text">
            红巾烽火，由此燎原。大元社稷，风雨飘摇。九州大地，九大势力割据四方，群雄逐鹿中原。
          </p>
        </div>
      </section>

      <!-- 势力卡片列表 -->
      <section class="faction-cards-section">
        <div
          v-for="f in factions" :key="f.id"
          class="faction-gallery-card"
          :style="{ '--faction-color': f.color }"
        >
          <!-- 左侧：肖像占位区 + AI 美术标签 -->
          <div class="fgc-portrait">
            <div class="portrait-placeholder" :style="{ borderColor: f.color }">
              <span class="portrait-emblem">{{ f.emblem }}</span>
              <span class="portrait-name">{{ f.name }}</span>
            </div>
            <div class="portrait-ai-badge" title="AI生成概念图">AI</div>
          </div>

          <!-- 右侧：势力档案 -->
          <div class="fgc-dossier">
            <div class="dossier-header">
              <h3 class="dossier-name" :style="{ color: f.color }">{{ f.name }}</h3>
              <span class="dossier-title">{{ f.title }}</span>
              <span class="dossier-difficulty" :class="'diff-' + f.difficulty">{{ f.difficultyLabel }}</span>
            </div>

            <!-- 势力标签 -->
            <div class="dossier-tags">
              <span v-for="t in f.tags" :key="t" class="dossier-tag">{{ t }}</span>
            </div>

            <!-- 势力列传 -->
            <div class="dossier-bio">
              <p v-for="(para, pi) in f.bio" :key="pi" class="bio-para">{{ para }}</p>
            </div>

            <!-- 初始实力 -->
            <div class="dossier-stats">
              <div class="stat-col">
                <div class="stat-item"><span class="si-label">初始兵力</span><span class="si-value">{{ fmtNum(f.troops) }}</span></div>
                <div class="stat-item"><span class="si-label">国库银两</span><span class="si-value gold">{{ fmtNum(f.treasury) }}</span></div>
                <div class="stat-item"><span class="si-label">粮草储备</span><span class="si-value grain">{{ fmtNum(f.grain) }}</span></div>
              </div>
              <div class="stat-col">
                <div class="stat-item"><span class="si-label">领地数量</span><span class="si-value">{{ f.tiles }}块</span></div>
                <div class="stat-item"><span class="si-label">初始声望</span><span class="si-value">{{ f.reputation }}</span></div>
                <div class="stat-item"><span class="si-label">战马军械</span><span class="si-value">{{ f.horses }}马{{ f.arms }}械</span></div>
              </div>
            </div>

            <!-- 优势 / 劣势 -->
            <div class="dossier-modifiers">
              <div class="mod-section buffs">
                <h5>🟢 势力优势</h5>
                <ul>
                  <li v-for="b in f.buffs" :key="b.name">
                    <strong>{{ b.name }}：</strong>{{ b.effect }}
                  </li>
                </ul>
              </div>
              <div class="mod-section debuffs">
                <h5>🔴 势力劣势</h5>
                <ul>
                  <li v-for="d in f.debuffs" :key="d.name">
                    <strong>{{ d.name }}：</strong>{{ d.effect }}
                  </li>
                </ul>
              </div>
            </div>

            <!-- 谋士团 -->
            <div class="dossier-advisers">
              <h5>🎓 谋士团</h5>
              <p>{{ f.advisers }}</p>
            </div>

            <!-- 战略分析 -->
            <div class="dossier-strategy">
              <h5>📊 战略定位</h5>
              <div class="strategy-bars">
                <div class="strategy-bar" v-for="s in f.strategies" :key="s.label">
                  <span class="sb-label">{{ s.label }}</span>
                  <div class="sb-track"><div class="sb-fill" :style="{ width: s.value + '%', background: f.color }"></div></div>
                  <span class="sb-val">{{ s.value }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 结语 -->
      <section class="epilogue-section">
        <div class="epilogue-card">
          <div class="orn-divider">━ ◆ ━</div>
          <p class="epilogue-text">
            九州烽烟四起，群雄逐鹿中原。<br/>
            历史的笔锋，已握于君手。<br/>
            或北伐中原，一统天下；或偏安江南，固守一方。
          </p>
          <button v-audio class="enter-btn" @click="$router.push('/faction-select')">
            启卷入世 · 择主逐鹿
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface FactionCard {
  id: string; name: string; title: string; emblem: string
  color: string; difficulty: string; difficultyLabel: string
  tags: string[]; bio: string[]
  troops: number; treasury: number; grain: number; horses: number; arms: number
  tiles: number; reputation: number
  buffs: { name: string; effect: string }[]
  debuffs: { name: string; effect: string }[]
  advisers: string
  strategies: { label: string; value: number }[]
}

const factions = ref<FactionCard[]>([
  {
    id: 'faction_yuan', name: '元廷', title: '大元皇帝', emblem: '元',
    color: '#8B0000', difficulty: '地狱', difficultyLabel: '地狱难度',
    tags: ['蒙古铁骑', '正统名分', '勋贵侵蚀', '民族隔阂', '朝堂腐败'],
    bio: [
      '至正十一年，元顺帝妥懽帖睦尔在位已近二十年。大元帝国曾横跨欧亚，如今却风雨飘摇——黄河屡决、饿殍遍野，江南半壁已非朝廷所有。',
      '虽据大都而号令天下，实已政令不出京畿。勋贵内斗不已，国库空虚，回天乏术。脱脱丞相主政，察罕帖木儿统军平叛，然红巾烽火已燃遍大江南北。',
      '北有漠北诸部蠢蠢欲动，西有王保保半独立，南有朱元璋、陈友谅等群雄虎视眈眈。大厦将倾，是力挽狂澜还是明哲保身？',
    ],
    troops: 6000, treasury: 20000, grain: 8000, horses: 200, arms: 300, tiles: 19, reputation: 60,
    buffs: [
      { name: '北地铁骑', effect: '骑兵战力+35%' },
      { name: '正统名分', effect: '初始声望+20' },
    ],
    debuffs: [
      { name: '勋贵侵蚀', effect: '每月国库流失2%银两' },
      { name: '民族隔阂', effect: '汉人地块每月民心-5' },
      { name: '朝堂腐败', effect: '朝堂稳定度每月-2' },
    ],
    advisers: '脱脱（丞相主政）、察罕帖木儿（统军平叛）、哈麻（把持宫廷）',
    strategies: [
      { label: '扩张', value: 20 }, { label: '固守', value: 60 },
      { label: '外交', value: 30 }, { label: '军事', value: 50 }, { label: '经济', value: 20 },
    ],
  },
  {
    id: 'faction_zhuyuanzhang', name: '朱元璋', title: '吴国公', emblem: '朱',
    color: '#DC143C', difficulty: '普通', difficultyLabel: '普通难度',
    tags: ['深谋远虑', '严刑峻法', '知人善任', '从僧到帝'],
    bio: [
      '濠州钟离人，幼年家贫，父母兄死于饥荒瘟疫，曾入皇觉寺为僧，流浪乞食。至正十二年投郭子兴红巾军，屡立战功，自领一军。',
      '取集庆（今南京）为根基，奉行「高筑墙、广积粮、缓称王」之策，于群雄中最为深谋远虑，步步为营。麾下人才济济：刘基运筹帷幄，李善长坐镇后方，徐达常遇春统兵征伐。',
      '西有陈友谅虎视，东有张士诚盘踞，北有元廷压境。三面受敌，却最有可能成就不世之功——驱除鞑虏、恢复中华。',
    ],
    troops: 3000, treasury: 8000, grain: 4000, horses: 30, arms: 80, tiles: 11, reputation: 40,
    buffs: [
      { name: '安民之治', effect: '流民转化率+30%' },
      { name: '屯田养兵', effect: '驻军粮草消耗-20%' },
    ],
    debuffs: [
      { name: '文武党争', effect: '朝堂派系冲突概率+20%' },
      { name: '根基未固', effect: '初始兵力较少' },
    ],
    advisers: '刘基（运筹帷幄）、李善长（坐镇后方）、徐达、常遇春（统兵征伐）、朱升（定鼎国策）',
    strategies: [
      { label: '扩张', value: 60 }, { label: '固守', value: 40 },
      { label: '外交', value: 40 }, { label: '军事', value: 60 }, { label: '经济', value: 50 },
    ],
  },
  {
    id: 'faction_chenyouliang', name: '陈友谅', title: '汉帝', emblem: '陈',
    color: '#1E90FF', difficulty: '困难', difficultyLabel: '困难难度',
    tags: ['野心勃勃', '猜忌多疑', '水战精通', '弑主自立'],
    bio: [
      '沔阳渔家子，初为县吏，后投徐寿辉麾下。野心勃勃，弑主自立，国号大汉，据荆楚而拥长江水师之利。',
      '兵锋最盛时号六十万众，巨舰如城。鄱阳湖水战名震天下——只可惜那一战，败给了朱元璋的火攻奇谋。',
      '水师之利天下无双，然苛政失心、弑主之名难消。若能戒骄戒躁、收拢人心，未必不能卷土重来。',
    ],
    troops: 5000, treasury: 12000, grain: 6000, horses: 50, arms: 150, tiles: 14, reputation: 35,
    buffs: [
      { name: '倾国水师', effect: '水战战力+50%' },
      { name: '荆楚粮仓', effect: '粮食产量+20%' },
    ],
    debuffs: [
      { name: '苛政失心', effect: '民心下降速度+30%' },
      { name: '弑主之名', effect: '外交好感度-15' },
    ],
    advisers: '张定边（忠勇无双）、邹普胜（谋划方略）、张必先（保障后勤）',
    strategies: [
      { label: '扩张', value: 70 }, { label: '固守', value: 20 },
      { label: '外交', value: 20 }, { label: '军事', value: 80 }, { label: '经济', value: 30 },
    ],
  },
  {
    id: 'faction_zhangshicheng', name: '张士诚', title: '周王', emblem: '张',
    color: '#FF8C00', difficulty: '简单', difficultyLabel: '简单难度',
    tags: ['偏安一隅', '富甲一方', '优柔寡断', '盐贩出身'],
    bio: [
      '泰州盐贩出身，率盐丁起兵，克平江（今苏州）而据江南膏腴之地。富甲一方，坐拥吴越繁华。',
      '江南财税甲于天下，海运通商日进斗金。却优柔寡断、偏安一隅，坐拥吴越繁华而无意北伐，在元廷与各方势力间首鼠两端。',
      '若能破偏安之心、立北伐之志，以江南之富养百战之师，未必不能成就霸业。',
    ],
    troops: 3500, treasury: 15000, grain: 7000, horses: 40, arms: 100, tiles: 9, reputation: 45,
    buffs: [
      { name: '江南富庶', effect: '税收+30%' },
      { name: '海运通商', effect: '贸易收入+25%' },
    ],
    debuffs: [
      { name: '偏安惰性', effect: '扩张意愿-40%' },
      { name: '盐贩出身', effect: '士绅支持度-20%' },
    ],
    advisers: '张士德（统军作战）、吕珍（经营财政）、潘元明（周旋外交）',
    strategies: [
      { label: '扩张', value: 20 }, { label: '固守', value: 70 },
      { label: '外交', value: 50 }, { label: '军事', value: 30 }, { label: '经济', value: 80 },
    ],
  },
  {
    id: 'faction_fangguozhen', name: '方国珍', title: '浙东节度', emblem: '方',
    color: '#20B2AA', difficulty: '中等', difficultyLabel: '中等难度',
    tags: ['海上枭雄', '投机善变', '重利轻义', '水师精锐'],
    bio: [
      '台州人，贩盐浮海为业。率先起兵反元，割据浙东三路——庆元、台州、温州。拥舟师之利，时叛时降、投机取利。',
      '海上通商日进斗金，水师精锐甲于东南。然根据浅薄、领地狭小，夹在元廷与群雄之间，每一步都必须精打细算。',
      '进退自如的海上枭雄——是困守一隅，还是乘风破浪、纵横四海？',
    ],
    troops: 2000, treasury: 6000, grain: 3000, horses: 20, arms: 60, tiles: 4, reputation: 30,
    buffs: [
      { name: '海上通商', effect: '海上贸易收入+50%' },
      { name: '水师精锐', effect: '水战战力+40%' },
    ],
    debuffs: [
      { name: '海运命脉', effect: '海上封锁时经济崩溃' },
      { name: '根基浅薄', effect: '领地防御薄弱' },
    ],
    advisers: '方国珍以海上贸易立足，善于投机应变，独立经营浙东海域',
    strategies: [
      { label: '扩张', value: 30 }, { label: '固守', value: 50 },
      { label: '外交', value: 60 }, { label: '军事', value: 30 }, { label: '经济', value: 70 },
    ],
  },
  {
    id: 'faction_wangbaobao', name: '王保保', title: '河南王', emblem: '王',
    color: '#666699', difficulty: '中等', difficultyLabel: '中等难度',
    tags: ['忠勇无双', '骑兵统帅', '元廷柱石', '蒙古铁骑'],
    bio: [
      '扩廓帖木儿，元末第一名将。继其养父察罕帖木儿之军，受封河南王，总制天下兵马。善用骑兵，骁勇善战。',
      '铁骑无双，忠义之名传遍天下。然而两线作战——南御红巾、北防漠北——使得这位名将疲于奔命。朝堂之上亦有猜忌掣肘。',
      '大元最后的柱石。是效忠到底、力挽狂澜，还是另起炉灶、自立为王？',
    ],
    troops: 4000, treasury: 8000, grain: 5000, horses: 150, arms: 120, tiles: 6, reputation: 45,
    buffs: [
      { name: '铁骑无双', effect: '骑兵战力+40%' },
      { name: '忠义之名', effect: '将领忠诚度+20%' },
    ],
    debuffs: [
      { name: '两线作战', effect: '资源消耗+30%' },
      { name: '朝堂猜忌', effect: '元廷内部掣肘' },
    ],
    advisers: '扩廓帖木儿亲统蒙古精锐铁骑，以骑兵战术称雄天下',
    strategies: [
      { label: '扩张', value: 50 }, { label: '固守', value: 40 },
      { label: '外交', value: 30 }, { label: '军事', value: 80 }, { label: '经济', value: 30 },
    ],
  },
  {
    id: 'faction_xushouhui', name: '徐寿辉', title: '天完皇帝', emblem: '徐',
    color: '#996633', difficulty: '困难', difficultyLabel: '困难难度',
    tags: ['弥勒信徒', '红巾领袖', '仁厚之主', '根基不稳'],
    bio: [
      '罗田布贩，白莲教南方首领。蕲州起义建国，国号天完——意为"大元之上，天完代之"。席卷湖广，声势浩大。',
      '以弥勒降世号召民众，红巾军中最先称帝者。然而大权旁落，终为部将陈友谅所弑——这是历史，但在你的经营下，一切皆有可能。',
      '弥勒信仰的号召力无人能及，若能稳固根基、驾驭群下，未必不能重现红巾荣光。',
    ],
    troops: 3500, treasury: 6000, grain: 4000, horses: 40, arms: 90, tiles: 6, reputation: 35,
    buffs: [
      { name: '弥勒号召', effect: '流民征兵效率+50%' },
      { name: '红巾正统', effect: '占领地块民心转化+20%' },
    ],
    debuffs: [
      { name: '根基不稳', effect: '朝堂稳定度每月-3' },
      { name: '四面楚歌', effect: '邻国关系初始-10' },
    ],
    advisers: '徐寿辉以弥勒降世号召民众，红巾军中最先称帝者，虽后为陈友谅所弑',
    strategies: [
      { label: '扩张', value: 50 }, { label: '固守', value: 30 },
      { label: '外交', value: 30 }, { label: '军事', value: 60 }, { label: '经济', value: 30 },
    ],
  },
  {
    id: 'faction_mingyuzhen', name: '明玉珍', title: '大夏皇帝', emblem: '明',
    color: '#B8860B', difficulty: '简单', difficultyLabel: '简单难度',
    tags: ['仁厚之主', '蜀道自守', '偏安一隅', '天府粮仓'],
    bio: [
      '徐寿辉旧部，奉命入川。闻陈友谅弑主，遂据蜀自立，国号大夏。保境安民，蜀中赖以安宁。',
      '蜀道天险易守难攻，天府粮仓富甲一方。然而封闭桎梏——出川艰难，贸易不通。是固守巴蜀、静观其变，还是图谋中原、争霸天下？',
      '最安全的开局——但安全也意味着被时代遗忘。',
    ],
    troops: 3000, treasury: 6500, grain: 5000, horses: 30, arms: 90, tiles: 8, reputation: 40,
    buffs: [
      { name: '蜀道天险', effect: '防御战力+40%' },
      { name: '天府粮仓', effect: '粮食产量+25%' },
    ],
    debuffs: [
      { name: '封闭桎梏', effect: '贸易收入-30%' },
      { name: '出川艰难', effect: '进攻行军消耗+50%' },
    ],
    advisers: '明玉珍仁厚爱民、刘桢辅佐建制，蜀中大治',
    strategies: [
      { label: '扩张', value: 20 }, { label: '固守', value: 70 },
      { label: '外交', value: 40 }, { label: '军事', value: 30 }, { label: '经济', value: 60 },
    ],
  },
  {
    id: 'faction_mobei', name: '漠北诸部', title: '草原大汗', emblem: '漠',
    color: '#887766', difficulty: '困难', difficultyLabel: '困难难度',
    tags: ['游牧骑射', '劫掠为生', '草原雄风', '成吉思汗之梦'],
    bio: [
      '和林故都，游牧铁骑。元室衰微，草原枭雄蠢蠢欲动，欲复成吉思汗之荣光，再饮马黄河。',
      '游牧骑射如风，以战养战，骑兵战力冠绝天下。然而无固定根基——非草原地块收益锐减，部落内斗消耗不断。',
      '是南下牧马、重建成吉思汗的帝国，还是固守草原、做一个自在的大汗？选择在你手中。',
    ],
    troops: 4500, treasury: 5000, grain: 2000, horses: 200, arms: 80, tiles: 5, reputation: 25,
    buffs: [
      { name: '游牧骑射', effect: '骑兵战力+45%' },
      { name: '以战养战', effect: '战斗胜利获得额外银两+30%' },
    ],
    debuffs: [
      { name: '无固定根基', effect: '非草原地块收益-40%' },
      { name: '部落内斗', effect: '朝堂稳定度每月-2' },
    ],
    advisers: '草原部落联盟，游牧骑射如风，以战养战',
    strategies: [
      { label: '扩张', value: 70 }, { label: '固守', value: 20 },
      { label: '外交', value: 20 }, { label: '军事', value: 80 }, { label: '经济', value: 20 },
    ],
  },
])

function fmtNum(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString()
}
</script>

<style scoped>
.gallery-page {
  width: 100vw; min-height: 100vh;
  background: #0a0806;
  color: #e0d5b8;
  font-family: 'STKaiti', 'KaiTi', 'SimSun', serif;
  position: relative;
}
.bg-overlay {
  position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background:
    radial-gradient(ellipse at 50% 0%, rgba(180,140,60,0.04) 0%, transparent 60%),
    repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(180,140,60,0.01) 3px, rgba(180,140,60,0.01) 6px);
}

/* 顶栏 */
.gallery-topbar {
  position: sticky; top: 0; z-index: 100;
  display: flex; align-items: center; padding: 12px 24px;
  background: linear-gradient(180deg, rgba(10,8,6,0.98) 0%, rgba(10,8,6,0.85) 100%);
  border-bottom: 1px solid rgba(180,150,60,0.15);
  backdrop-filter: blur(10px);
}
.back-btn {
  padding: 6px 16px; cursor: pointer;
  background: rgba(184,155,104,0.06); border: 1px solid rgba(184,155,104,0.15);
  color: #B89B68; font-family: inherit; font-size: 13px; letter-spacing: 2px;
  border-radius: 3px; transition: all 0.2s;
}
.back-btn:hover { background: rgba(184,155,104,0.12); border-color: #B89B68; }
.topbar-title {
  flex: 1; text-align: center; display: flex; flex-direction: column; gap: 2px;
}
.title-main { font-size: 24px; letter-spacing: 12px; color: #c8a84a; }
.title-sub { font-size: 12px; letter-spacing: 6px; color: rgba(200,168,74,0.4); }
.topbar-spacer { width: 100px; }

/* 滚动区 */
.gallery-scroll { position: relative; z-index: 1; padding: 0 8vw 80px; }
.gallery-scroll::-webkit-scrollbar { width: 4px; }
.gallery-scroll::-webkit-scrollbar-thumb { background: rgba(180,150,60,0.15); border-radius: 2px; }

/* 序幕 */
.prologue-section { padding: 40px 0 20px; }
.prologue-card {
  max-width: 700px; margin: 0 auto; text-align: center;
  padding: 40px 30px;
  background: rgba(20,16,10,0.6); border: 1px solid rgba(180,150,60,0.1);
  border-radius: 4px;
}
.prologue-year { font-size: 15px; color: rgba(200,168,74,0.45); letter-spacing: 6px; }
.prologue-title { font-size: 32px; color: #c8a84a; letter-spacing: 16px; margin: 12px 0 20px; font-weight: normal; }
.prologue-text { font-size: 15px; line-height: 2; color: rgba(212,197,160,0.75); max-width: 500px; margin: 0 auto 12px; text-align: justify; text-indent: 2em; }
.prologue-quote { font-size: 20px; color: #c8a84a; letter-spacing: 4px; margin: 16px 0; text-shadow: 0 0 10px rgba(200,168,74,0.25); }

/* 势力卡片 */
.faction-cards-section { display: flex; flex-direction: column; gap: 32px; padding: 20px 0; }
.faction-gallery-card {
  display: flex; gap: 24px;
  padding: 28px; background: rgba(20,16,10,0.7);
  border: 1px solid rgba(180,150,60,0.1);
  border-radius: 4px; border-left: 3px solid var(--faction-color);
  transition: all 0.3s;
}
.faction-gallery-card:hover { border-color: rgba(180,150,60,0.25); box-shadow: 0 4px 20px rgba(0,0,0,0.3); }

/* 肖像区 */
.fgc-portrait {
  width: 180px; flex-shrink: 0; position: relative;
  display: flex; flex-direction: column; align-items: center; gap: 10px;
}
.portrait-placeholder {
  width: 160px; height: 200px;
  background: linear-gradient(135deg, rgba(0,0,0,0.4) 0%, rgba(30,20,10,0.2) 100%);
  border: 2px solid; border-radius: 4px;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;
}
.portrait-emblem { font-size: 48px; opacity: 0.6; font-weight: bold; }
.portrait-name { font-size: 20px; letter-spacing: 6px; opacity: 0.7; }
.portrait-ai-badge {
  position: absolute; top: 8px; right: 8px;
  background: rgba(184,155,104,0.2); border: 1px solid rgba(184,155,104,0.3);
  color: #B89B68; font-size: 9px; padding: 2px 6px; border-radius: 2px;
  letter-spacing: 1px;
}

/* 档案区 */
.fgc-dossier { flex: 1; min-width: 0; }
.dossier-header { display: flex; align-items: baseline; gap: 12px; margin-bottom: 10px; flex-wrap: wrap; }
.dossier-name { font-size: 26px; letter-spacing: 6px; margin: 0; font-weight: bold; }
.dossier-title { font-size: 13px; color: rgba(184,150,62,0.45); letter-spacing: 3px; }
.dossier-difficulty {
  font-size: 10px; padding: 2px 8px; border-radius: 2px; letter-spacing: 1px;
}
.diff-地狱 { background: rgba(196,58,58,0.15); color: #c43a3a; border: 1px solid rgba(196,58,58,0.3); }
.diff-困难 { background: rgba(212,112,80,0.12); color: #d47050; border: 1px solid rgba(212,112,80,0.25); }
.diff-中等 { background: rgba(184,150,62,0.12); color: #B89B68; border: 1px solid rgba(184,150,62,0.25); }
.diff-普通 { background: rgba(91,154,90,0.1); color: #5b9a5a; border: 1px solid rgba(91,154,90,0.2); }
.diff-简单 { background: rgba(91,154,90,0.06); color: #7ab87a; border: 1px solid rgba(91,154,90,0.15); }

.dossier-tags { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }
.dossier-tag {
  font-size: 10px; padding: 2px 8px;
  background: rgba(184,155,104,0.06); border: 1px solid rgba(184,155,104,0.15);
  color: rgba(200,180,140,0.6); border-radius: 2px; letter-spacing: 1px;
}
.dossier-bio { margin-bottom: 14px; }
.bio-para { font-size: 14px; line-height: 1.9; color: rgba(212,197,160,0.8); margin: 0 0 8px; text-align: justify; text-indent: 2em; }

/* 实力统计 */
.dossier-stats { display: flex; gap: 30px; margin-bottom: 14px; padding: 12px 16px; background: rgba(0,0,0,0.2); border-radius: 3px; }
.stat-col { flex: 1; }
.stat-item { display: flex; justify-content: space-between; padding: 3px 0; font-size: 13px; }
.si-label { color: #8c8068; }
.si-value { color: #e0d5b8; font-weight: bold; }
.si-value.gold { color: #D4B860; }
.si-value.grain { color: #8AB88A; }

/* 优劣 */
.dossier-modifiers { display: flex; gap: 20px; margin-bottom: 14px; }
.mod-section { flex: 1; }
.mod-section h5 { margin: 0 0 8px; font-size: 12px; letter-spacing: 2px; color: #B89B68; }
.mod-section ul { list-style: none; padding: 0; margin: 0; }
.mod-section li { font-size: 12px; padding: 2px 0; color: rgba(212,197,160,0.7); line-height: 1.6; }
.mod-section li strong { color: #c0b090; }

/* 谋士团 */
.dossier-advisers { margin-bottom: 14px; }
.dossier-advisers h5 { margin: 0 0 4px; font-size: 12px; letter-spacing: 2px; color: #B89B68; }
.dossier-advisers p { font-size: 12px; color: rgba(212,197,160,0.6); margin: 0; }

/* 战略分析 */
.dossier-strategy h5 { margin: 0 0 8px; font-size: 12px; letter-spacing: 2px; color: #B89B68; }
.strategy-bars { display: flex; flex-direction: column; gap: 5px; }
.strategy-bar { display: flex; align-items: center; gap: 8px; font-size: 11px; }
.sb-label { width: 32px; color: #8c8068; text-align: right; }
.sb-track { flex: 1; height: 8px; background: rgba(0,0,0,0.3); border-radius: 4px; overflow: hidden; }
.sb-fill { height: 100%; border-radius: 4px; transition: width 0.6s; }
.sb-val { width: 24px; color: rgba(212,197,160,0.5); }

/* 结语 */
.epilogue-section { padding: 40px 0 20px; }
.epilogue-card { max-width: 500px; margin: 0 auto; text-align: center; }
.orn-divider { color: rgba(200,160,60,0.2); letter-spacing: 8px; font-size: 14px; padding: 10px 0; }
.epilogue-text { font-size: 16px; line-height: 2.2; color: rgba(212,197,160,0.7); margin: 16px 0; }
.enter-btn {
  padding: 16px 40px; background: transparent;
  border: 2px solid rgba(200,168,74,0.35); color: #e0d5b8;
  font-family: inherit; font-size: 18px; letter-spacing: 6px;
  cursor: pointer; border-radius: 3px; transition: all 0.3s;
  margin-top: 12px;
}
.enter-btn:hover { border-color: rgba(200,168,74,0.6); box-shadow: 0 0 30px rgba(200,168,74,0.1); color: #c8a84a; }

@media (max-width: 860px) {
  .faction-gallery-card { flex-direction: column; align-items: center; }
  .fgc-portrait { width: 100%; }
  .dossier-modifiers { flex-direction: column; }
  .gallery-scroll { padding: 0 4vw 60px; }
}
</style>
