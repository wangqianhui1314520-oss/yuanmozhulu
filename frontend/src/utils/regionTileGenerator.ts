/**
 * 区域地块生成器 - 基于真实元代行政区划
 * 
 * 替代六边形格子地图，使用 GeoJSON 行省/路府边界生成地块。
 * 每个行省和路府都是一个"地块"，支持交互操作。
 */

export interface RegionTile {
  tile_id: string
  tile_name: string
  tile_type: 'farmland' | 'grassland' | 'mountain' | 'desert' | 'coast' | 'pass' | 'water'
  region: string
  province_id: string
  prefecture_id: string
  faction_id: string
  population: number
  troops: number
  grain: number
  morale: number
  treasury: number
  refugee_ratio: number
  water_works: number
  granary: number
  clinic: number
  fortification: number
  is_capital: boolean
  is_port: boolean
  is_pass: boolean
  special_effect: string
  longitude: number
  latitude: number
}

/** 势力默认值 */
const FACTION_DEFAULTS: Record<string, {
  troops: number
  grain: number
  treasury: number
  morale: number
  population_per_tile: number
}> = {
  faction_yuan:          { troops: 35000, grain: 8000, treasury: 20000, morale: 55, population_per_tile: 400000 },
  faction_zhuyuanzhang:  { troops: 15000, grain: 4000, treasury: 8000,  morale: 65, population_per_tile: 250000 },
  faction_chenyouliang:  { troops: 25000, grain: 6000, treasury: 12000, morale: 50, population_per_tile: 350000 },
  faction_zhangshicheng: { troops: 12000, grain: 7000, treasury: 15000, morale: 65, population_per_tile: 300000 },
  faction_fangguozhen:   { troops: 8000,  grain: 5000, treasury: 10000, morale: 60, population_per_tile: 150000 },
  faction_xushouhui:     { troops: 18000, grain: 5000, treasury: 7000,  morale: 55, population_per_tile: 300000 },
  faction_mingyuzhen:    { troops: 10000, grain: 3500, treasury: 7000,  morale: 55, population_per_tile: 200000 },
  faction_wangbaobao:    { troops: 20000, grain: 5000, treasury: 8000,  morale: 60, population_per_tile: 300000 },
  faction_mobei:         { troops: 18000, grain: 2000, treasury: 5000,  morale: 60, population_per_tile: 100000 },
}

/** 行省地形类型 */
const PROVINCE_TERRAIN: Record<string, string> = {
  zhongshu: 'farmland',
  henanjiang: 'farmland',
  huguang: 'farmland',
  jiangxi: 'farmland',
  jiangzhe: 'farmland',
  shanxi: 'grassland',
  sichuan: 'mountain',
  yunnan: 'mountain',
  gansu: 'desert',
  lingbei: 'grassland',
  liaoyang: 'grassland',
  xiyu: 'desert',
  xuanzheng: 'mountain',
}

/**
 * 从GeoJSON数据生成区域地块
 * 每个行省是一个大地块，路府是子地块
 */
export function generateRegionTiles(
  factionsData: Array<{
    faction_id: string
    provinces: string[]
    prefectures: string[]
  }>,
  citiesData?: Array<{
    id: string
    name: string
    type: string
    province_id: string
    prefecture_id?: string
    faction_id?: string
    longitude: number
    latitude: number
    population?: number
    troops?: number
    tax_revenue?: number
    morale?: number
    is_capital?: boolean
    is_port?: boolean
  }>,
): Map<string, RegionTile> {
  const tiles = new Map<string, RegionTile>()

  // 省份到势力的映射
  const provinceFactionMap = new Map<string, string>()
  const prefectureFactionMap = new Map<string, string>()
  for (const f of factionsData) {
    for (const pid of f.provinces) {
      provinceFactionMap.set(pid, f.faction_id)
    }
    for (const pfid of f.prefectures) {
      prefectureFactionMap.set(pfid, f.faction_id)
    }
  }

  // 势力拥有的行省数量（用于平均分配兵力）
  const factionProvinceCount = new Map<string, number>()
  const factionPrefectureCount = new Map<string, number>()
  for (const f of factionsData) {
    factionProvinceCount.set(f.faction_id, f.provinces.length)
    factionPrefectureCount.set(f.faction_id, f.prefectures.length)
  }

  // ---- 生成行省级地块 ----
  const provinces = [
    { id: 'zhongshu',   name: '中书省',   lng: 116.4, lat: 39.9 },
    { id: 'henanjiang', name: '河南江北', lng: 114.3, lat: 34.8 },
    { id: 'huguang',    name: '湖广行省', lng: 114.3, lat: 30.6 },
    { id: 'jiangxi',    name: '江西行省', lng: 115.9, lat: 28.7 },
    { id: 'jiangzhe',   name: '江浙行省', lng: 120.1, lat: 30.2 },
    { id: 'shanxi',     name: '陕西行省', lng: 108.9, lat: 34.2 },
    { id: 'sichuan',    name: '四川行省', lng: 104.0, lat: 30.6 },
    { id: 'yunnan',     name: '云南行省', lng: 102.7, lat: 25.0 },
    { id: 'gansu',      name: '甘肃行省', lng: 100.4, lat: 38.9 },
    { id: 'lingbei',    name: '岭北行省', lng: 102.8, lat: 47.2 },
    { id: 'liaoyang',   name: '辽阳行省', lng: 123.4, lat: 41.8 },
    { id: 'xiyu',       name: '西域',     lng: 87.6,  lat: 44.0 },
    { id: 'xuanzheng',  name: '宣政院辖地', lng: 91.1, lat: 29.6 },
  ]

  for (const prov of provinces) {
    const fid = provinceFactionMap.get(prov.id) || ''
    const defaults = FACTION_DEFAULTS[fid] || { troops: 2000, grain: 500, treasury: 1000, morale: 50, population_per_tile: 50000 }
    const provCount = factionProvinceCount.get(fid) || 1

    tiles.set(`prov_${prov.id}`, {
      tile_id: `prov_${prov.id}`,
      tile_name: prov.name,
      tile_type: (PROVINCE_TERRAIN[prov.id] || 'farmland') as RegionTile['tile_type'],
      region: prov.id,
      province_id: prov.id,
      prefecture_id: '',
      faction_id: fid,
      population: defaults.population_per_tile,
      troops: Math.floor(defaults.troops / provCount),
      grain: Math.floor(defaults.grain / provCount),
      morale: defaults.morale,
      treasury: Math.floor(defaults.treasury / provCount),
      refugee_ratio: 0.1,
      water_works: 0,
      granary: 0,
      clinic: 0,
      fortification: 20,
      is_capital: false,
      is_port: false,
      is_pass: false,
      special_effect: '',
      longitude: prov.lng,
      latitude: prov.lat,
    })
  }

  // ---- 生成路府级地块（V3.0 九大势力核心区域） ----
  const prefectures = [
    // 大元（北元）
    { id: 'dadoulu',      name: '大都路',   province: 'zhongshu',   lng: 116.4, lat: 39.9, faction: 'faction_yuan',    isCapital: true },
    { id: 'taiyuanlu',    name: '太原路',   province: 'zhongshu',   lng: 112.5, lat: 37.8, faction: 'faction_yuan' },
    { id: 'zhendinglu',   name: '真定路',   province: 'zhongshu',   lng: 114.5, lat: 38.1, faction: 'faction_yuan' },
    { id: 'dongpinglu',   name: '东平路',   province: 'zhongshu',   lng: 117.0, lat: 36.6, faction: 'faction_yuan' },
    { id: 'ganzhoulu',    name: '甘州路',   province: 'gansu',      lng: 100.4, lat: 38.9, faction: 'faction_yuan' },
    // 西吴（朱元璋）
    { id: 'jiqinglu',     name: '集庆路',   province: 'jiangzhe',   lng: 118.8, lat: 32.0, faction: 'faction_zhuyuanzhang', isCapital: true },
    // 陈汉（陈友谅）
    { id: 'wuchanglu',    name: '武昌路',   province: 'huguang',    lng: 114.3, lat: 30.6, faction: 'faction_chenyouliang', isCapital: true },
    { id: 'tianlinlu',    name: '天临路',   province: 'huguang',    lng: 113.0, lat: 28.2, faction: 'faction_chenyouliang' },
    { id: 'jingjianglu',  name: '静江路',   province: 'huguang',    lng: 110.3, lat: 25.2, faction: 'faction_chenyouliang' },
    { id: 'longxinglu',   name: '龙兴路',   province: 'jiangxi',    lng: 115.9, lat: 28.7, faction: 'faction_chenyouliang' },
    { id: 'guangzhoulu',  name: '广州路',   province: 'jiangxi',    lng: 113.2, lat: 23.1, faction: 'faction_chenyouliang' },
    // 大周（张士诚）
    { id: 'hangzhoulu',   name: '杭州路',   province: 'jiangzhe',   lng: 120.1, lat: 30.2, faction: 'faction_zhangshicheng', isCapital: true },
    // 方国珍
    { id: 'fuzhoulu',     name: '福州路',   province: 'jiangzhe',   lng: 119.3, lat: 26.0, faction: 'faction_fangguozhen', isCapital: true },
    // 徐寿辉
    { id: 'bianlianglu',  name: '汴梁路',   province: 'henanjiang', lng: 114.3, lat: 34.8, faction: 'faction_xushouhui' },
    { id: 'luzhoulu',     name: '庐州路',   province: 'henanjiang', lng: 117.3, lat: 31.8, faction: 'faction_xushouhui' },
    // 大夏（明玉珍）
    { id: 'chongqinglu',  name: '重庆路',   province: 'sichuan',    lng: 106.5, lat: 29.5, faction: 'faction_mingyuzhen', isCapital: true },
    { id: 'chengdulu',    name: '成都路',   province: 'sichuan',    lng: 104.0, lat: 30.6, faction: 'faction_mingyuzhen' },
    // 王保保
    { id: 'zhongqinglu',  name: '中庆路',   province: 'yunnan',     lng: 102.7, lat: 25.0, faction: 'faction_wangbaobao' },
    // 漠北诸部
    { id: 'quanzhoulu',   name: '泉州路',   province: 'jiangzhe',   lng: 118.6, lat: 24.9, faction: 'faction_mobei' },
  ]

  for (const pref of prefectures) {
    const fid = pref.faction
    const defaults = FACTION_DEFAULTS[fid] || { troops: 2000, grain: 500, treasury: 1000, morale: 50, population_per_tile: 50000 }
    const prefCount = factionPrefectureCount.get(fid) || 1

    tiles.set(`pref_${pref.id}`, {
      tile_id: `pref_${pref.id}`,
      tile_name: pref.name,
      tile_type: 'farmland',
      region: pref.province,
      province_id: pref.province,
      prefecture_id: pref.id,
      faction_id: fid,
      population: Math.floor(defaults.population_per_tile / 2),
      troops: Math.floor(defaults.troops / prefCount),
      grain: Math.floor(defaults.grain / prefCount),
      morale: defaults.morale,
      treasury: Math.floor(defaults.treasury / prefCount),
      refugee_ratio: 0.05,
      water_works: 0,
      granary: 0,
      clinic: 0,
      fortification: pref.isCapital ? 40 : 15,
      is_capital: pref.isCapital || false,
      is_port: false,
      is_pass: false,
      special_effect: '',
      longitude: pref.lng,
      latitude: pref.lat,
    })
  }

  // 为每个势力标记首都
  for (const [fid, fdata] of Object.entries(FACTION_DEFAULTS)) {
    const capitalTile = [...tiles.values()].find(t => t.faction_id === fid && t.is_capital)
    if (capitalTile) {
      // 首都兵力翻倍
      capitalTile.troops = Math.floor(capitalTile.troops * 1.5)
      capitalTile.fortification = 50
    }
  }

  return tiles
}

/**
 * 从JSON文件加载势力数据并生成区域地块
 */
export async function loadAndGenerateRegionTiles(): Promise<Map<string, RegionTile>> {
  try {
    const [factionsResp, citiesResp] = await Promise.all([
      fetch('/data/map/factions.json'),
      fetch('/data/map/cities.json'),
    ])
    const factionsData = await factionsResp.json()
    const citiesData = await citiesResp.json()
    return generateRegionTiles(factionsData.factions, citiesData.cities)
  } catch (err) {
    console.warn('[regionTileGenerator] 数据加载失败，使用默认数据:', err)
    return generateRegionTiles([])
  }
}
