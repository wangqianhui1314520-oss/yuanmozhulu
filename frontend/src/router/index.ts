import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/pages/HomePage.vue'),
    },
    {
      path: '/faction-select',
      name: 'faction-select',
      component: () => import('@/pages/FactionSelectPage.vue'),
    },
    // 势力选择电影镜头（15秒全国沙盘→聚焦行省→跳转对局）
    {
      path: '/faction-select-cinematic',
      name: 'faction-select-cinematic',
      component: () => import('@/pages/FactionSelectCinematic.vue'),
    },
    // 沙盘势力镜头动画（势力选择后 → 故事背景 → 游戏对局前）
    {
      path: '/sandbox-intro',
      name: 'sandbox-intro',
      component: () => import('@/pages/SandboxIntroPage.vue'),
    },
    // 元末历史背景故事介绍（加载动画后 → 游戏开始前）
    {
      path: '/story-intro',
      name: 'story-intro',
      component: () => import('@/pages/StoryIntroPage.vue'),
    },
    {
      path: '/game',
      name: 'game',
      component: () => import('@/pages/GamePage.vue'),
    },
    // 兼容 /game/tactics-ruler/:factionId 子路由格式
    {
      path: '/game/:mode(tactics-ruler|sandbox)/:factionId',
      name: 'game-mode',
      component: () => import('@/pages/GamePage.vue'),
    },
    {
      path: '/faction-gallery',
      name: 'faction-gallery',
      component: () => import('@/pages/FactionGalleryPage.vue'),
    },
    {
      path: '/save-manager',
      name: 'save-manager',
      component: () => import('@/pages/SaveManagerPage.vue'),
    },
    // 404 通配路由
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/pages/HomePage.vue'),
    },
  ],
})

// 路由守卫：游戏页需要选择势力后才可进入
router.beforeEach((to, _from, next) => {
  // 兼容 /game 和 /game/tactics-ruler/:factionId 两种路由格式
  if (to.name === 'game' || to.name === 'game-mode') {
    const factionId = localStorage.getItem('yuanmo_player_faction')
    const routeFaction = (to.query.faction as string) || (to.params.factionId as string)
    if (!factionId && !routeFaction) {
      next({ name: 'faction-select' })
      return
    }
  }
  next()
})

export default router
