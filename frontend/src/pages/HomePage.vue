<template>
  <div class="home-page">
    <!-- 动态背景：用户上传的元末乱世图 -->
    <ImageDynamicBg src="/assets/images/home-bg.jpg" quality="high" />

    <!-- 顶部工具栏 -->
    <header class="top-bar">
      <div class="version-badge">
        <span class="badge-seal">元末</span>
        <span class="version-text">逐鹿 3.0</span>
      </div>
      <div class="top-actions">
        <button v-audio class="icon-btn" :title="muted ? '开启音效' : '静音'" @click="toggleMute">
          <span class="icon">{{ muted ? '🔇' : '🔊' }}</span>
        </button>
        <button v-audio class="icon-btn" title="切换全屏" @click="toggleFullscreen">
          <span class="icon">{{ isFullscreen ? '⤡' : '⤢' }}</span>
        </button>
        <button v-audio class="icon-btn" title="设置" @click="showSettings = true">
          <span class="icon">⚙</span>
        </button>
      </div>
    </header>

    <!-- 服务器状态 -->
    <div class="server-status" :class="{ online: serverOnline, ready: aiAvailable }">
      <span class="status-dot"></span>
      <span class="status-label">
        {{ serverOnline ? (aiAvailable ? '幕府·云Agent 已就绪' : '服务器在线') : '幕府离线' }}
      </span>
    </div>

    <!-- 主内容 -->
    <main class="home-main">
      <div class="title-card" :class="{ 'animate-in': mounted }">
        <div class="seal-mark">
          <div class="seal-border"></div>
          <span class="seal-char">敕</span>
        </div>
        <h1 class="game-title">
          <span v-for="(c, i) in titleChars" :key="i" class="title-char" :style="{ animationDelay: `${0.6 + i * 0.15}s` }">{{ c }}</span>
        </h1>
        <p class="game-subtitle">大元至正十一年 · 六边形乱世AI国策</p>
        <div class="divider">
          <span class="line"></span>
          <span class="knot">◇</span>
          <span class="line"></span>
        </div>
        <p class="game-desc">
          至正十一年，黄河决堤，红巾烽火遍燃南北。<br/>
          大元社稷风雨飘摇，九大势力割据四方。<br/>
          幕府主官，运筹帷幄，谁能力挽狂澜，一统山河？
        </p>
      </div>

      <!-- 按钮矩阵 -->
      <div class="action-grid" :class="{ 'has-continue': hasContinue }">
        <button v-audio class="btn btn-primary" @click="startNew">
          <span class="btn-label">启卷入世</span>
          <span class="btn-sub">择主入世 · 逐鹿天下</span>
        </button>
        <button v-if="hasContinue" v-audio class="btn btn-primary btn-continue" @click="continueGame">
          <span class="btn-label">继续征程</span>
          <span class="btn-sub">{{ continueInfo }}</span>
        </button>
        <button v-audio class="btn btn-secondary" @click="$router.push('/save-manager')">
          <span class="btn-label">展卷读档</span>
          <span class="btn-sub">读取存档</span>
        </button>
        <button v-audio class="btn btn-secondary" @click="$router.push('/faction-gallery')">
          <span class="btn-label">势力图鉴</span>
          <span class="btn-sub">九大势力·群雄列传</span>
        </button>

      </div>
    </main>

    <!-- 底部势力走马灯 -->
    <div class="faction-strip">
      <div class="strip-track">
        <div
          v-for="f in builtinFactions"
          :key="'a-' + f.id"
          class="strip-item"
          :style="{ '--accent': f.color }"
          @click="previewFaction(f)"
        >
          <span class="strip-dot"></span>
          <span class="strip-name">{{ f.name }}</span>
          <span class="strip-title">{{ f.title }}</span>
        </div>
        <div
          v-for="f in builtinFactions"
          :key="'b-' + f.id"
          class="strip-item"
          :style="{ '--accent': f.color }"
          @click="previewFaction(f)"
        >
          <span class="strip-dot"></span>
          <span class="strip-name">{{ f.name }}</span>
          <span class="strip-title">{{ f.title }}</span>
        </div>
      </div>
    </div>

    <!-- 底部邸报 -->
    <div class="home-dibao">
      <span class="dibao-stamp">邸</span>
      <span class="dibao-text">联网智能体模式 · 九大势力 · 东亚全图·逐鹿天下</span>
      <span class="dibao-date">至正十一年(1351) — 洪武元年(1368)</span>
    </div>

    <!-- 势力图鉴弹窗 -->
    <Teleport to="body">
      <div v-if="showFactionBrief" class="modal-overlay" @click.self="showFactionBrief = false">
        <div class="modal-dialog faction-dialog">
          <div class="modal-header">
            <h2>◆ 天下群雄 ◆</h2>
            <button class="modal-close" @click="showFactionBrief = false">✕</button>
          </div>
          <div class="faction-grid">
            <div
              v-for="f in builtinFactions"
              :key="f.id"
              class="faction-card"
              :style="{ '--accent': f.color }"
              @click="selectFactionFromBrief(f)"
            >
              <div class="card-accent"></div>
              <div class="card-info">
                <h3>{{ f.name }}</h3>
                <p class="card-title">{{ f.title }}</p>
                <p class="card-diff" :class="'diff-' + diffClass(f.difficulty)">{{ f.difficulty }}</p>
                <div class="card-tags">
                  <span v-for="tag in f.personality_tags.slice(0, 2)" :key="tag">{{ tag }}</span>
                </div>
              </div>
            </div>
          </div>
          <p class="modal-hint">点击势力可前往选择</p>
        </div>
      </div>
    </Teleport>

    <!-- 人物生平事迹卷轴弹窗（点击底部走马灯） -->
    <Teleport to="body">
      <div v-if="previewFactionData" class="modal-overlay" @click.self="previewFactionData = null">
        <div class="bio-scroll-wrapper">
          <!-- 卷轴顶部轴杆 -->
          <div class="bio-rod bio-rod-top">
            <div class="bio-rod-knob"></div>
            <div class="bio-rod-bar"></div>
            <div class="bio-rod-knob"></div>
          </div>
          <!-- 卷轴纸面 -->
          <div class="bio-panel" :style="{ '--bio-accent': previewFactionData.color }">
            <button class="bio-close" @click="previewFactionData = null">✕</button>
            <!-- 头部 -->
            <div class="bio-header">
              <div class="bio-illustrious">{{ previewFactionData.title }}</div>
              <h2 class="bio-name">{{ previewFactionData.name }}</h2>
            </div>
            <!-- 基本信息 -->
            <div class="bio-meta">
              <div class="bio-meta-item"><span class="meta-label">生卒</span><span>{{ previewFactionData.born }} — {{ previewFactionData.died }}</span></div>
              <div class="bio-meta-item"><span class="meta-label">籍贯</span><span>{{ previewFactionData.origin }}</span></div>
              <div class="bio-meta-item"><span class="meta-label">难度</span><span :class="'diff-' + diffClass(previewFactionData.difficulty)">{{ previewFactionData.difficulty }}</span></div>
            </div>
            <!-- 个性 -->
            <div class="bio-tags">
              <span v-for="tag in previewFactionData.personality_tags" :key="tag" class="bio-tag">{{ tag }}</span>
            </div>
            <div class="bio-divider">
              <span class="div-line"></span>
              <span class="div-mark">◆</span>
              <span class="div-line"></span>
            </div>
            <!-- 生平正文 -->
            <div class="bio-text">
              <p v-for="(para, i) in previewFactionData.biography.split('\n').filter(Boolean)" :key="i" class="bio-para">{{ para }}</p>
            </div>
            <!-- 尾部图鉴入口 -->
            <div class="bio-footer">
              <span class="bio-stamp">史</span>
              <span class="bio-footer-text">九大势力 · 元末群雄图鉴</span>
            </div>
          </div>
          <!-- 卷轴底部轴杆 -->
          <div class="bio-rod bio-rod-bot">
            <div class="bio-rod-knob"></div>
            <div class="bio-rod-bar"></div>
            <div class="bio-rod-knob"></div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 设置面板 -->
    <SettingsPanel :visible="showSettings" @close="showSettings = false" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import ImageDynamicBg from '@/components/bg/ImageDynamicBg.vue'
import SettingsPanel from '@/components/SettingsPanel.vue'
import { healthCheck, listSaves } from '@/services/api'
import { audioManager } from '@/utils/audioManager'
import { useFullscreen } from '@/composables/useFullscreen'

const router = useRouter()

const titleChars = ['元', '末', '逐', '鹿']
const mounted = ref(false)

const serverOnline = ref(false)
const aiAvailable = ref(false)
const hasContinue = ref(false)
const continueInfo = ref('')
const showSettings = ref(false)
const showFactionBrief = ref(false)
const previewFactionData = ref<BriefFaction | null>(null)
const muted = ref(false)
const { isFullscreen, toggleFullscreen } = useFullscreen()

interface BriefFaction {
  id: string
  name: string
  title: string
  color: string
  difficulty: string
  personality_tags: string[]
  description: string
  biography: string
  born: string
  died: string
  origin: string
}

const builtinFactions: BriefFaction[] = [
  {
    id: 'faction_yuan', name: '元顺帝', title: '大元皇帝', color: '#8B0000', difficulty: '地狱',
    personality_tags: ['蒙古铁骑', '正统名分', '勋贵侵蚀'],
    description: '大元正统，坐拥中原与北方草原，铁骑精锐但朝堂腐败，需在四面起义中力挽狂澜。',
    born: '泰定三年（1326年）', died: '宣光八年（1378年）', origin: '元上都（今内蒙古正蓝旗）',
    biography: '元顺帝孛儿只斤·妥懽帖睦尔，元朝末代皇帝，也是蒙古帝国第十五位大汗。幼年被流放高丽、广西，历尽颠沛。至顺四年（1333年）即位，年仅七岁，朝政初由权相伯颜把持。至元六年（1340年）亲政后，一度励精图治，推行"至正新政"，编纂《宋史》《辽史》《金史》，被誉为中兴之主。\n\n然至正四年（1344年）黄河屡次决口，灾民遍野；至正十一年（1351年），韩山童、刘福通发动红巾起义，天下响应。此后十余年，元顺帝在剿抚之间举棋不定，朝廷内斗不休，察罕帖木儿、扩廓帖木儿等名将虽屡建战功，却难挽全局。\n\n至正二十八年（1368年），朱元璋遣徐达、常遇春北伐，攻破大都。顺帝携后妃太子北遁上都，建立北元政权。此后十年偏安漠北，忧郁而终。明太祖以其"知顺天命，退避而去"，谥号"顺帝"。他的一生，是大元帝国从极盛走向覆灭的完整缩影——即位时坐拥万里江山，离世时只剩草原残阳。',
  },
  {
    id: 'faction_zhuyuanzhang', name: '朱元璋', title: '吴国公', color: '#DC143C', difficulty: '普通',
    personality_tags: ['深谋远虑', '严刑峻法', '知人善任'],
    description: '起于淮右，据有金陵，手下谋士如云、猛将如雨，是未来逐鹿天下的最大黑马。',
    born: '天历元年（1328年）', died: '洪武三十一年（1398年）', origin: '濠州钟离（今安徽凤阳）',
    biography: '朱元璋，原名朱重八，濠州钟离（今安徽凤阳）人，出身贫苦农家，幼年父母双亡，入皇觉寺为僧，后游方乞食，遍尝人间疾苦。至正十二年（1352年），投奔濠州红巾军郭子兴部，骁勇善战，迅速积功升迁，娶郭子兴养女马氏（即后来的马皇后）。\n\n至正十五年（1355年），郭子兴病逝，朱元璋统领其众，渡江攻占采石、太平，次年攻克集庆路（今南京），改称应天府。以"高筑墙、广积粮、缓称王"九字方针韬光养晦，广纳贤才——刘基、李善长、徐达、常遇春等皆为所用。先灭陈友谅（1363年鄱阳湖大战），再平张士诚（1367年），尽收江南。\n\n至正二十八年（1368年）正月，于应天称帝，国号大明，年号洪武。同年北伐，攻破大都，结束元朝统治。洪武元年至二十三年，先后平定四川明玉珍、云南梁王、辽东纳哈出，统一全国。在位三十一年，严刑峻法、铁腕治吏，废除丞相制度，集皇权于一身，奠定了明清五百年的政治格局。',
  },
  {
    id: 'faction_chenyouliang', name: '陈友谅', title: '汉帝', color: '#1E90FF', difficulty: '困难',
    personality_tags: ['野心勃勃', '猜忌多疑', '水战精通'],
    description: '据江汉之地，水军冠绝群雄，势力强盛但内部不稳，欲与朱元璋争雄东南。',
    born: '延祐七年（1320年）', died: '至正二十三年（1363年）', origin: '沔阳（今湖北仙桃）',
    biography: '陈友谅，沔阳渔家子出身，少时读书略通文墨，初为县衙小吏。至正十一年（1351年），徐寿辉起兵于蕲黄，陈友谅率乡人投奔红巾军天完政权，隶属倪文俊麾下。因作战勇猛、善于权谋，逐渐从底层军官升至领兵元帅。\n\n至正十七年（1357年），倪文俊谋害徐寿辉未遂，陈友谅趁机杀倪文俊，吞并其部众，成为天完政权实际掌控者。至正二十年（1360年），弑徐寿辉自立为帝，国号汉，据有湖广、江西、江浙部分，号称"江南最强势力"，水军六十万，巨舰如云。\n\n然而陈友谅猜忌成性，弑主自立失了人心；穷兵黩武，百姓苦于苛政。至正二十三年（1363年）率大军六十万与朱元璋决战于鄱阳湖，被朱元璋用火攻破阵，在突围时中流矢而亡，年仅四十三岁。其子陈理降于武昌，大汉政权覆灭。陈友谅是元末最强劲的割据势力，若非性格缺陷，鹿死谁手尚未可知。',
  },
  {
    id: 'faction_zhangshicheng', name: '张士诚', title: '周王', color: '#FF8C00', difficulty: '简单',
    personality_tags: ['富甲一方', '安于现状', '盐商出身'],
    description: '据富庶的江浙之地，盐铁之利甲于天下，但胸无大志，守成有余而进取不足。',
    born: '至治元年（1321年）', died: '至正二十七年（1367年）', origin: '泰州白驹场（今江苏大丰）',
    biography: '张士诚，泰州白驹场盐民出身，与弟张士德、张士信以私盐贩运为生，因不堪官吏勒索，于至正十三年（1353年）率盐丁起事，攻占泰州、高邮，次年称诚王，国号大周。至正十五年（1355年），元丞相脱脱率百万大军围攻高邮，张士诚坚守三月，适逢脱脱被元廷罢黜，百万大军溃散，张士诚由此声威大震。\n\n至正十六年（1356年），渡江南下，攻占平江（今苏州），定都于此。此后据有江浙富庶之地，减免赋税、兴修水利、开办学校，颇得民心。苏州在其治下成为元末乱世中的一处富庶乐土。\n\n然而张士诚胸无大志，满足于偏安一隅，坐观朱元璋与陈友谅相争而不取渔利。至正二十六年（1366年），朱元璋扫平陈友谅后挥师东进，张士诚困守平江孤城，坚拒投降。至正二十七年城破被俘，押送应天府途中自缢而死，终年四十六岁。他的一生是乱世富商守成之道的写照——富可敌国却难敌枭雄。',
  },
  {
    id: 'faction_fangguozhen', name: '方国珍', title: '浙东节度', color: '#20B2AA', difficulty: '中等',
    personality_tags: ['海商巨贾', '首鼠两端', '水战精通'],
    description: '控扼浙东海道，以海上贸易起家，纵横于各大势力之间，待机而动。',
    born: '延祐六年（1319年）', died: '洪武七年（1374年）', origin: '台州黄岩（今浙江台州）',
    biography: '方国珍，台州黄岩人，世代以航海经商为业。至正八年（1348年），因仇家诬告其为海盗，被迫逃亡海上，聚众数千人劫掠漕运船只，元廷数次征讨皆被其击败。至正十一年（1351年），元廷招安封其为海道漕运万户，方国珍由此开始其独特的"受招—反叛—再受招"循环之路，先后数次降元、叛元，每次都获得更高官爵。\n\n他控扼浙东温、台、庆元三州，凭借强大的海上力量垄断海上贸易，富可敌国。在朱元璋与张士诚争夺江南期间，方国珍周旋于二者之间，既接受朱元璋的册封，又与元廷保持联络，还暗中与张士诚通好。他建造大型海船，将浙东打造成元末最活跃的海上贸易中心。\n\n至正二十七年（1367年），朱元璋平定张士诚后挥师南征，方国珍率部不战而降。明初被迁居应天府，洪武七年病逝，葬于南京。他是元末群雄中唯一高寿善终者，以灵活多变的政治手腕在乱世中保全了身家性命。',
  },
  {
    id: 'faction_xushouhui', name: '徐寿辉', title: '天完皇帝', color: '#996633', difficulty: '困难',
    personality_tags: ['弥勒信徒', '红巾领袖', '仁厚之主'],
    description: '红巾军领袖，以弥勒信仰凝聚人心，率先称帝建国，但内忧外患并存。',
    born: '不详', died: '至正二十年（1360年）', origin: '蕲州罗田（今湖北罗田）',
    biography: '徐寿辉，蕲州罗田人，以贩布为业，为人忠厚，在乡里颇有威望。至正十一年（1351年），与彭莹玉（彭和尚）、邹普胜等人以白莲教弥勒下生之说组织民众，在蕲黄发动起义，以红巾为号，迅速攻占蕲水、黄州等地。同年十月，在蕲水称帝，国号"天完"（寓意压"大元"一头），是中国历史上第一个以推翻元朝为明确目标的割据政权。\n\n天完政权鼎盛时期疆域西起四川、东至江浙、北抵河南、南达湖南。然而徐寿辉虽为皇帝，实权却掌握在丞相倪文俊、太师邹普胜等将领手中。至正十七年（1357年），倪文俊谋逆未遂，陈友谅趁机杀倪文俊而取代其位。此后徐寿辉沦为陈友谅的傀儡君主，于至正二十年（1360年）被陈友谅弑于采石矶。\n\n徐寿辉是元末红巾起义的精神先驱，其开启的反元洪流深刻改变了中国历史走向。他虽然最终死于部将之手，但天完政权的组织框架和军事基础，为后来陈友谅的汉政权乃至朱元璋的明朝建立提供了重要的经验。',
  },
  {
    id: 'faction_mingyuzhen', name: '明玉珍', title: '大夏皇帝', color: '#B8860B', difficulty: '简单',
    personality_tags: ['偏安一隅', '仁厚之主', '蜀道天险'],
    description: '据蜀地天险，易守难攻，但远离中原，欲图天下需先出川问鼎。',
    born: '至顺二年（1331年）', died: '至正二十六年（1366年）', origin: '随州（今湖北随州）',
    biography: '明玉珍，随州人，本为乡里富户。至正十一年（1351年）红巾乱起，明玉珍组织乡兵自保，后被徐寿辉的天完政权招纳，授统兵征虏大元帅，镇守沔阳。至正十七年（1357年），奉命率军万余入川筹粮，因重庆空虚而一举攻占，从此开启了他在四川的独立经营之路。\n\n至正二十年（1360年），陈友谅弑徐寿辉自立，明玉珍遂与陈友谅决裂，据四川称陇蜀王。至正二十三年（1363年）在重庆称帝，国号大夏，年号天统。明玉珍治蜀期间，轻徭薄赋、兴修水利、重开科举，恢复了被战乱破坏的四川经济，蜀中百姓得以休养生息。他还派兵南征云南，试图打通西南通道，但未能攻克大理。\n\n明玉珍在位仅六年，于至正二十六年（1366年）病逝，年仅三十五岁。其子明升继位，年仅十岁。洪武四年（1371年），朱元璋遣汤和、傅友德伐蜀，明升降于重庆，大夏国亡。明玉珍的一生虽短暂，却为四川留下了一段乱世中难得的安定岁月。',
  },
  {
    id: 'faction_wangbaobao', name: '王保保', title: '河南王', color: '#666699', difficulty: '中等',
    personality_tags: ['忠勇无双', '骑兵统帅', '元廷柱石'],
    description: '元末第一名将扩廓帖木儿，统率蒙古铁骑，为元室中流砥柱。',
    born: '至正五年（约1345年）', died: '洪武八年（1375年）', origin: '河南沈丘（今属河南）',
    biography: '王保保，蒙古名扩廓帖木儿，河南沈丘人，其父赛因赤答忽为元朝翰林学士，母为察罕帖木儿之姊，后被察罕帖木儿收为养子，遂改蒙古姓名。自幼习骑射、读兵书，文武兼备，深得养父器重。至正二十二年（1362年），察罕帖木儿被降将田丰刺杀，扩廓帖木儿继承其军，年仅十七岁即统率数十万大军。\n\n此后数年，扩廓帖木儿东征西讨，平定山东、河南各路红巾，成为元廷倚重的军事支柱。至正二十五年受封河南王、总天下兵马。然而元廷内部皇太子与顺帝争权，扩廓帖木儿卷入宫廷斗争，被削夺兵权、下诏讨伐。至正二十八年（1368年），徐达北伐时，扩廓帖木儿因内乱无法全力应战，退守山西、甘肃。\n\n北元时期，扩廓帖木儿率蒙古残部退守漠北和林，屡挫明军北伐。洪武五年（1372年），明将徐达率十五万大军深入漠北，扩廓帖木儿诱敌深入，大破明军于岭北，杀明军数万，保全了北元政权。明太祖朱元璋对其评价极高，称"元臣中无出其右者"。洪武八年（1375年）病逝于漠北。王保保是元末明初最杰出的军事统帅，其忠勇不二的气节尤为后世敬重。',
  },
  {
    id: 'faction_mobei', name: '漠北诸部', title: '草原大汗', color: '#887766', difficulty: '困难',
    personality_tags: ['游牧骑射', '劫掠为生', '草原雄风'],
    description: '蒙古草原部落联盟，骑射如风，以战养战，纵横大漠伺机南下。',
    born: '世代传承', died: '延续至今', origin: '漠北草原（今蒙古高原）',
    biography: '漠北诸部是元朝退往草原后蒙古各部族的总称。自成吉思汗统一蒙古高原以来，草原各部虽然名义上隶属大汗，但始终保持半独立的部落自治传统。元末天下大乱，中原汉地烽烟四起，漠北草原反而成为蒙古力量最稳定的后方基地。\n\n漠北诸部主要包括鞑靼（东蒙古）、瓦剌（西蒙古）、兀良哈三部，以及散布于漠北的众多中小部落。他们保持了蒙古传统的游牧生活方式——逐水草而居，善骑射，以部落为单位组织生产和军事。每逢秋冬马肥，各部往往会联合南下劫掠中原边境，这是他们千百年来赖以生存的经济模式。\n\n至正二十八年（1368年）元顺帝北遁后，漠北诸部成为北元政权的核心支撑力量。在扩廓帖木儿等名将的统率下，几度挫败了明军的北伐，迫使朱元璋由攻转守。此后二百余年，漠北蒙古始终是明朝的心腹大患，直至明末才被后金（清朝）逐步收服。选择漠北诸部，意味着放弃中原农耕文明，回归传统的草原游牧征服之路。',
  },
]

function diffClass(diff: string): string {
  const map: Record<string, string> = { '简单': 'easy', '普通': 'normal', '中等': 'medium', '困难': 'hard', '地狱': 'hell' }
  return map[diff] || 'normal'
}

function previewFaction(f: BriefFaction) {
  previewFactionData.value = f
}

function selectFactionFromBrief(f: BriefFaction) {
  localStorage.setItem('yuanmo_player_faction', f.id)
  router.push(`/sandbox-intro?faction=${f.id}`)
}

function startNew() {
  localStorage.removeItem('yuanmo_preview_faction')
  router.push('/faction-select')
}

function continueGame() {
  const factionId = localStorage.getItem('yuanmo_player_faction')
  if (factionId) {
    router.push(`/game?faction=${factionId}`)
  } else {
    router.push('/game')
  }
}

function toggleMute() {
  muted.value = audioManager.toggleMute()
  try {
    const saved = localStorage.getItem('yuanmo_audio')
    const audio = saved ? JSON.parse(saved) : {}
    audio.muted = muted.value
    localStorage.setItem('yuanmo_audio', JSON.stringify(audio))
  } catch { /* ignore */ }
}

async function checkServer() {
  try {
    const d = await healthCheck()
    serverOnline.value = d?.status === 'ok' || d?.ai_available === true
    aiAvailable.value = d?.ai_available === true
  } catch {
    serverOnline.value = false
    aiAvailable.value = false
  }
}

async function checkContinue() {
  const localFaction = localStorage.getItem('yuanmo_player_faction')
  hasContinue.value = false
  continueInfo.value = ''

  // 优先读取后端存档
  try {
    const data = await listSaves()
    const saves = data?.saves || []
    if (saves.length > 0) {
      const latest = saves.sort((a: any, b: any) => new Date(b.saved_at).getTime() - new Date(a.saved_at).getTime())[0]
      hasContinue.value = true
      continueInfo.value = `${latest.faction || '未知势力'} · 第${latest.round}回合`
      return
    }
  } catch { /* 后端不可用则降级本地 */ }

  // 本地有faction也算可继续
  if (localFaction) {
    const f = builtinFactions.find(x => x.id === localFaction)
    hasContinue.value = true
    continueInfo.value = f ? `${f.name} · 上次游玩` : '上次游玩'
  }
}

onMounted(async () => {
  setTimeout(() => { mounted.value = true }, 100)
  await checkServer()
  await checkContinue()

  // 读取音频静音状态
  try {
    const saved = localStorage.getItem('yuanmo_audio')
    if (saved) {
      const parsed = JSON.parse(saved)
      muted.value = parsed.muted || false
      if (parsed.muted && !audioManager.isMuted) {
        audioManager.toggleMute()
      }
    }
  } catch { /* ignore */ }

  // 启动首页背景音乐（循环播放）
  if (!audioManager.isBgmPlaying()) {
    audioManager.playBgm('main_menu', 1.5)
  }

  // 监听全屏变化
  document.addEventListener('fullscreenchange', onFullscreenChange)
})

onUnmounted(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
})

function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
}
</script>

<style scoped>
.home-page {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-main, #e8e0d0);
  font-family: var(--font-body, "STKaiti", "KaiTi", serif);
}

/* ===== 顶部工具栏 ===== */
.top-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  pointer-events: none;
}

.version-badge, .top-actions { pointer-events: auto; }

.version-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  background: rgba(20, 16, 12, 0.6);
  border: 1px solid rgba(184, 150, 62, 0.3);
  border-radius: 2px;
  backdrop-filter: blur(4px);
}

.badge-seal {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--danger, #c43a3a);
  color: var(--danger, #c43a3a);
  font-family: var(--font-seal, "FangSong", serif);
  font-size: 14px;
  border-radius: 2px;
  transform: rotate(-3deg);
}

.version-text {
  font-size: 13px;
  color: var(--gold-dim, #b8a070);
  letter-spacing: 2px;
}

.top-actions {
  display: flex;
  gap: 10px;
}

.icon-btn {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(20, 16, 12, 0.55);
  border: 1px solid rgba(184, 150, 62, 0.25);
  border-radius: 2px;
  color: var(--gold-dim, #b8a070);
  cursor: pointer;
  transition: all 0.2s;
  backdrop-filter: blur(4px);
}

.icon-btn:hover {
  background: rgba(184, 150, 62, 0.12);
  border-color: rgba(184, 150, 62, 0.5);
  transform: translateY(-1px);
}

.icon-btn .icon { font-size: 14px; }

/* ===== 服务器状态 ===== */
.server-status {
  position: absolute;
  top: 64px;
  right: 24px;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  background: rgba(20, 16, 12, 0.55);
  border: 1px solid rgba(107, 100, 90, 0.4);
  border-radius: 2px;
  backdrop-filter: blur(4px);
  font-size: 11px;
  color: var(--text-muted, #8a8070);
  letter-spacing: 1px;
  transition: all 0.4s;
}

.server-status.online {
  border-color: rgba(91, 140, 90, 0.4);
  color: rgba(180, 210, 170, 0.9);
}

.server-status.ready {
  border-color: rgba(184, 150, 62, 0.5);
  color: var(--gold, #c9a848);
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #6b645a;
  box-shadow: 0 0 4px rgba(107, 100, 90, 0.5);
  transition: all 0.4s;
}

.server-status.online .status-dot {
  background: #5b8c5a;
  box-shadow: 0 0 6px rgba(91, 140, 90, 0.6);
}

.server-status.ready .status-dot {
  background: #c9a848;
  box-shadow: 0 0 6px rgba(201, 168, 72, 0.6);
}

/* ===== 主内容 ===== */
.home-main {
  position: relative;
  z-index: 5;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
  max-width: 520px;
  width: 90%;
  padding: 20px 0;
}

.title-card {
  text-align: center;
  opacity: 0;
  transform: translateY(24px);
  transition: all 0.8s cubic-bezier(0.22, 0.61, 0.36, 1);
}

.title-card.animate-in {
  opacity: 1;
  transform: translateY(0);
}

/* 印章 */
.seal-mark {
  width: 72px;
  height: 72px;
  margin: 0 auto 20px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: sealStamp 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) 0.4s both;
}

@keyframes sealStamp {
  0% { transform: scale(0) rotate(-45deg); opacity: 0; }
  60% { transform: scale(1.15) rotate(2deg); opacity: 1; }
  100% { transform: scale(1) rotate(-5deg); opacity: 1; }
}

.seal-border {
  position: absolute;
  inset: 0;
  border: 2px solid var(--danger, #c43a3a);
  border-radius: 4px;
  transform: rotate(-5deg);
  box-shadow: inset 0 0 0 2px rgba(196, 58, 58, 0.25), 0 2px 12px rgba(196, 58, 58, 0.2);
}

.seal-char {
  position: relative;
  z-index: 1;
  font-size: 40px;
  color: var(--danger, #c43a3a);
  font-family: var(--font-seal, "FangSong", serif);
  transform: rotate(-5deg);
  text-shadow: 2px 2px 0 rgba(139, 32, 32, 0.3);
}

/* 标题 */
.game-title {
  display: flex;
  justify-content: center;
  gap: 6px;
  font-family: var(--font-seal, "FangSong", serif);
  font-size: 52px;
  font-weight: normal;
  color: var(--gold, #c9a848);
  margin-bottom: 10px;
  text-shadow: 0 2px 8px rgba(0,0,0,0.6), 0 0 24px rgba(184, 150, 62, 0.25);
}

.title-char {
  opacity: 0;
  transform: translateY(20px);
  animation: charDrop 0.6s cubic-bezier(0.22, 0.61, 0.36, 1) forwards;
  display: inline-block;
}

@keyframes charDrop {
  to { opacity: 1; transform: translateY(0); }
}

.game-subtitle {
  font-size: 13px;
  color: var(--text-dim, #a09078);
  letter-spacing: 5px;
  font-family: var(--font-annotation, "SimSun", serif);
  margin-bottom: 14px;
}

/* 分割线 */
.divider {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 18px 0;
}

.line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(184, 150, 62, 0.5), transparent);
}

.knot {
  color: var(--gold, #c9a848);
  font-size: 10px;
  opacity: 0.7;
}

.game-desc {
  font-size: 15px;
  line-height: 2.2;
  color: rgba(232, 224, 208, 0.85);
  letter-spacing: 2px;
  text-shadow: 0 1px 4px rgba(0,0,0,0.6);
}

/* ===== 按钮矩阵 ===== */
.action-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  width: 100%;
}

/* 启卷入世始终独占第一排 */
.action-grid .btn-primary:first-child {
  grid-column: 1 / -1;
}

.btn {
  position: relative;
  padding: 14px 20px;
  border: none;
  border-radius: 3px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  transition: all 0.25s ease;
  overflow: hidden;
  font-family: var(--font-body, "STKaiti", "KaiTi", serif);
  min-height: 72px;
}

.btn-primary {
  background: linear-gradient(180deg, rgba(196, 58, 58, 0.95) 0%, rgba(139, 32, 32, 0.95) 100%);
  border: 1px solid rgba(160, 40, 40, 0.8);
  color: #f0e6d8;
  box-shadow: 0 4px 16px rgba(139, 32, 32, 0.35), inset 0 1px 0 rgba(255,255,255,0.08);
  animation: btnPulse 3s ease-in-out infinite;
}

@keyframes btnPulse {
  0%, 100% { box-shadow: 0 4px 16px rgba(139, 32, 32, 0.35); }
  50% { box-shadow: 0 6px 24px rgba(196, 58, 58, 0.5); }
}

.btn-primary:hover {
  transform: translateY(-2px);
  filter: brightness(1.1);
  box-shadow: 0 8px 28px rgba(196, 58, 58, 0.45);
}

.btn-primary:active {
  transform: translateY(1px) scale(0.98);
}

.btn-continue {
  background: linear-gradient(180deg, rgba(91, 140, 90, 0.95) 0%, rgba(60, 100, 55, 0.95) 100%) !important;
  border-color: rgba(70, 120, 65, 0.8) !important;
  animation: none;
}

.btn-continue:hover {
  box-shadow: 0 8px 28px rgba(91, 140, 90, 0.4) !important;
}

.btn-secondary {
  background: rgba(30, 26, 20, 0.75);
  border: 1px solid rgba(184, 150, 62, 0.35);
  color: var(--text-secondary, #d0c8b8);
  backdrop-filter: blur(4px);
}

.btn-secondary:hover {
  background: rgba(50, 42, 32, 0.85);
  border-color: rgba(184, 150, 62, 0.6);
  transform: translateY(-2px);
}

.btn-label {
  font-size: 18px;
  letter-spacing: 6px;
  font-weight: bold;
}

.btn-sub {
  font-size: 11px;
  opacity: 0.75;
  letter-spacing: 2px;
  color: rgba(255, 255, 255, 0.7);
}

.btn-secondary .btn-sub {
  color: var(--text-dim, #a09078);
}

/* ===== 底部势力走马灯 ===== */
.faction-strip {
  position: absolute;
  bottom: 68px;
  left: 0;
  right: 0;
  z-index: 5;
  overflow: hidden;
  padding: 8px 0;
  mask-image: linear-gradient(90deg, transparent, black 8%, black 92%, transparent);
  -webkit-mask-image: linear-gradient(90deg, transparent, black 8%, black 92%, transparent);
  pointer-events: auto;
}

.strip-track {
  display: flex;
  gap: 24px;
  width: max-content;
  animation: stripScroll 40s linear infinite;
}

.strip-track:hover {
  animation-play-state: paused;
}

@keyframes stripScroll {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}

.strip-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  background: rgba(20, 16, 12, 0.55);
  border: 1px solid rgba(184, 150, 62, 0.18);
  border-radius: 2px;
  color: var(--text-secondary, #d0c8b8);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  backdrop-filter: blur(4px);
  white-space: nowrap;
}

.strip-item:hover {
  background: rgba(30, 25, 18, 0.75);
  border-color: var(--accent, rgba(184, 150, 62, 0.6));
  transform: translateY(-2px);
}

.strip-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent, #c9a848);
  box-shadow: 0 0 6px var(--accent, #c9a848);
}

.strip-title {
  font-size: 11px;
  color: var(--text-dim, #a09078);
  opacity: 0.8;
}

/* ===== 底部邸报 ===== */
.home-dibao {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 18px;
  background: rgba(20, 16, 12, 0.65);
  border: 1px solid rgba(184, 150, 62, 0.22);
  border-radius: 2px;
  backdrop-filter: blur(4px);
  white-space: nowrap;
}

.dibao-stamp {
  width: 22px;
  height: 22px;
  border: 1px solid var(--danger, #c43a3a);
  border-radius: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: var(--danger, #c43a3a);
  font-family: var(--font-seal, "FangSong", serif);
  transform: rotate(-3deg);
  flex-shrink: 0;
}

.dibao-text {
  font-size: 11px;
  color: var(--text-dim, #a09078);
  letter-spacing: 2px;
}

.dibao-date {
  font-size: 10px;
  color: var(--text-muted, #8a8070);
  letter-spacing: 1px;
}

/* ===== 弹窗 ===== */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  animation: fadeIn 0.25s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.modal-dialog {
  background: linear-gradient(180deg, rgba(34, 29, 22, 0.98) 0%, rgba(24, 20, 16, 0.98) 100%);
  border: 1px solid rgba(184, 150, 62, 0.35);
  border-radius: 4px;
  max-width: 760px;
  width: 100%;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
  animation: scaleIn 0.3s cubic-bezier(0.22, 0.61, 0.36, 1);
}

@keyframes scaleIn {
  from { opacity: 0; transform: scale(0.96); }
  to { opacity: 1; transform: scale(1); }
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid rgba(184, 150, 62, 0.2);
}

.modal-header h2 {
  font-size: 18px;
  font-weight: normal;
  letter-spacing: 5px;
  color: var(--gold, #c9a848);
  margin: 0;
}

.modal-close {
  width: 28px;
  height: 28px;
  border: none;
  background: none;
  color: var(--text-dim, #a09078);
  font-size: 16px;
  cursor: pointer;
  transition: color 0.2s;
}

.modal-close:hover { color: var(--danger, #c43a3a); }

/* 势力图鉴网格 */
.faction-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
  padding: 18px;
  overflow-y: auto;
}

.faction-card {
  position: relative;
  background: rgba(30, 26, 20, 0.7);
  border: 1px solid rgba(184, 150, 62, 0.15);
  border-radius: 3px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s;
  overflow: hidden;
}

.faction-card:hover {
  background: rgba(40, 34, 26, 0.85);
  transform: translateY(-3px);
  border-color: var(--accent, rgba(184, 150, 62, 0.5));
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.3);
}

.card-accent {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--accent, #c9a848);
  box-shadow: 0 0 8px var(--accent, #c9a848);
}

.card-info h3 {
  font-size: 17px;
  color: var(--text-main, #e8e0d0);
  margin: 0 0 4px;
  letter-spacing: 2px;
}

.card-title {
  font-size: 11px;
  color: var(--text-dim, #a09078);
  margin-bottom: 8px;
  letter-spacing: 1px;
}

.card-diff {
  display: inline-block;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 2px;
  margin-bottom: 8px;
  letter-spacing: 1px;
}

.card-diff.diff-easy { color: #5b8c5a; background: rgba(91, 140, 90, 0.12); }
.card-diff.diff-normal { color: #b8a070; background: rgba(184, 160, 112, 0.12); }
.card-diff.diff-medium { color: #d9a050; background: rgba(217, 160, 80, 0.12); }
.card-diff.diff-hard { color: #c44b3c; background: rgba(196, 75, 60, 0.12); }

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.card-tags span {
  font-size: 10px;
  padding: 2px 6px;
  background: rgba(184, 150, 62, 0.08);
  border: 1px solid rgba(184, 150, 62, 0.15);
  color: var(--text-dim, #a09078);
  border-radius: 2px;
}

.modal-hint {
  text-align: center;
  font-size: 12px;
  color: var(--text-dim, #a09078);
  padding: 8px 18px 14px;
  letter-spacing: 2px;
}

/* ===== 生平事迹卷轴弹窗 ===== */
.bio-scroll-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  max-height: 88vh;
  animation: bioUnfurl 0.5s cubic-bezier(0.22, 0.61, 0.36, 1);
}

@keyframes bioUnfurl {
  from { opacity: 0; transform: scaleY(0.3); }
  to { opacity: 1; transform: scaleY(1); }
}

/* 卷轴轴杆 */
.bio-rod {
  display: flex;
  align-items: center;
  gap: 0;
  width: 580px;
  z-index: 2;
}

.bio-rod-knob {
  width: 20px; height: 20px;
  background: radial-gradient(circle at 40% 40%, #6b5a3a, #3a2a14);
  border-radius: 50%;
  box-shadow: 0 2px 6px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.1);
  flex-shrink: 0;
}

.bio-rod-bar {
  flex: 1; height: 8px;
  background: linear-gradient(180deg, #8b7a4a 0%, #5a4820 50%, #8b7a4a 100%);
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.08);
}

.bio-rod-top .bio-rod-knob:first-child { margin-right: -2px; }
.bio-rod-top .bio-rod-knob:last-child { margin-left: -2px; }
.bio-rod-bot .bio-rod-knob:first-child { margin-right: -2px; }
.bio-rod-bot .bio-rod-knob:last-child { margin-left: -2px; }

/* 卷轴纸面 */
.bio-panel {
  width: 560px;
  max-height: 72vh;
  overflow-y: auto;
  background: linear-gradient(180deg,
    rgba(45, 38, 28, 0.98) 0%,
    rgba(38, 32, 24, 0.97) 2%,
    rgba(34, 28, 20, 0.96) 50%,
    rgba(38, 32, 24, 0.97) 98%,
    rgba(45, 38, 28, 0.98) 100%
  );
  border-left: 3px solid rgba(184, 150, 62, 0.3);
  border-right: 3px solid rgba(184, 150, 62, 0.3);
  padding: 0 36px 28px;
  position: relative;
  box-shadow:
    0 0 30px rgba(0,0,0,0.5),
    inset 0 0 60px rgba(20, 14, 8, 0.4);
  /* 竹简纹理 */
  background-image:
    repeating-linear-gradient(
      0deg, transparent, transparent 43px, rgba(184, 150, 62, 0.04) 43px, rgba(184, 150, 62, 0.04) 44px
    );
}

.bio-panel::-webkit-scrollbar { width: 4px; }
.bio-panel::-webkit-scrollbar-track { background: transparent; }
.bio-panel::-webkit-scrollbar-thumb {
  background: rgba(184, 150, 62, 0.25);
  border-radius: 2px;
}

.bio-close {
  position: sticky;
  top: 12px;
  right: -28px;
  float: right;
  width: 30px; height: 30px;
  border: 1px solid rgba(184, 150, 62, 0.25);
  background: rgba(24, 20, 16, 0.85);
  color: rgba(200, 180, 130, 0.7);
  font-size: 14px; cursor: pointer;
  border-radius: 2px;
  z-index: 10;
  transition: all 0.2s;
  display: flex; align-items: center; justify-content: center;
}
.bio-close:hover {
  color: #c43a3a;
  border-color: rgba(196, 58, 58, 0.5);
}

/* 头部 */
.bio-header {
  text-align: center;
  padding-top: 40px;
  padding-bottom: 16px;
}

.bio-illustrious {
  font-family: var(--font-seal, 'FangSong', serif);
  font-size: 15px;
  color: var(--bio-accent, #c9a848);
  letter-spacing: 6px;
  margin-bottom: 8px;
  opacity: 0.8;
}

.bio-name {
  font-family: var(--font-seal, 'FangSong', serif);
  font-size: 38px;
  font-weight: normal;
  color: var(--bio-accent, #c9a848);
  letter-spacing: 10px;
  margin: 0;
  text-shadow: 0 2px 8px rgba(0,0,0,0.4);
}

/* 元信息 */
.bio-meta {
  display: flex;
  justify-content: center;
  gap: 24px;
  flex-wrap: wrap;
  padding: 10px 0;
  border-top: 1px solid rgba(184, 150, 62, 0.15);
  border-bottom: 1px solid rgba(184, 150, 62, 0.15);
  margin-bottom: 12px;
}

.bio-meta-item {
  font-size: 12px;
  color: rgba(180, 160, 120, 0.8);
  letter-spacing: 1px;
  display: flex; gap: 6px;
}

.meta-label {
  color: rgba(140, 120, 80, 0.6);
  font-size: 11px;
}

.bio-meta-item .diff-easy { color: #5b8c5a; }
.bio-meta-item .diff-normal { color: #b8a070; }
.bio-meta-item .diff-medium { color: #d9a050; }
.bio-meta-item .diff-hard { color: #c44b3c; }
.bio-meta-item .diff-hell { color: #c43a3a; }

/* 个性标签 */
.bio-tags {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0;
}

.bio-tag {
  font-size: 11px;
  padding: 3px 10px;
  background: rgba(184, 150, 62, 0.08);
  border: 1px solid rgba(184, 150, 62, 0.18);
  color: rgba(180, 160, 110, 0.8);
  border-radius: 2px;
  letter-spacing: 1px;
}

/* 分割线 */
.bio-divider {
  display: flex; align-items: center; gap: 12px;
  margin: 16px 0;
}
.bio-divider .div-line {
  flex: 1; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(184, 150, 62, 0.3), transparent);
}
.bio-divider .div-mark {
  font-size: 8px; color: rgba(184, 150, 62, 0.4);
}

/* 生平正文 */
.bio-text {
  font-family: 'STKaiti', 'KaiTi', serif;
  line-height: 2.1;
  color: rgba(200, 185, 150, 0.9);
}

.bio-para {
  text-indent: 2em;
  font-size: 15px;
  margin: 0 0 16px;
  letter-spacing: 0.5px;
  text-align: justify;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3);
}

.bio-para:first-of-type::first-letter {
  font-size: 28px;
  color: var(--bio-accent, #c9a848);
  font-family: var(--font-seal, 'FangSong', serif);
  float: left;
  line-height: 1;
  padding: 0 4px 0 0;
}

/* 尾部 */
.bio-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding-top: 20px;
  margin-top: 10px;
  border-top: 1px solid rgba(184, 150, 62, 0.12);
}

.bio-stamp {
  width: 24px; height: 24px;
  display: flex; align-items: center; justify-content: center;
  border: 1px solid var(--bio-accent, #c9a848);
  border-radius: 2px;
  font-size: 13px; color: var(--bio-accent, #c9a848);
  font-family: var(--font-seal, 'FangSong', serif);
  transform: rotate(-3deg);
  flex-shrink: 0;
}

.bio-footer-text {
  font-size: 11px;
  color: rgba(150, 130, 100, 0.5);
  letter-spacing: 3px;
}

/* 响应式 */
@media (max-width: 640px) {
  .bio-rod, .bio-panel { width: 94vw; }
  .bio-panel { padding: 0 20px 24px; max-height: 70vh; }
  .bio-name { font-size: 28px; letter-spacing: 6px; }
  .bio-para { font-size: 13px; }
  .bio-meta { gap: 12px; }
}

/* 保留弹窗通用覆盖样式 */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  animation: fadeIn 0.25s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* 响应式 */
@media (max-width: 640px) {
  .game-title { font-size: 38px; }
  .action-grid { grid-template-columns: 1fr; }
  .home-dibao { flex-direction: column; gap: 4px; padding: 8px 14px; }
  .faction-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
