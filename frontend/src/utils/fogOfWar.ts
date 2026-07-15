/**
 * 三级战争迷雾机制
 *
 * 1. 未探索 (UNEXPLORED) - 全羊皮遮挡，不可见任何信息
 * 2. 已探索褪色 (EXPLORED) - 半透明蒙版，地块褪色但可辨识
 * 3. 完全可视 (VISIBLE) - 无蒙版，完整显示
 *
 * 可见性规则:
 * - 玩家己方地块: 完全可视
 * - 己方地块2格邻接范围: 完全可视
 * - 有细作网络的目标势力地块: 完全可视
 * - 已探索过但不在视野内: 已探索褪色
 * - 未探索: 全羊皮遮挡
 */

import { hexNeighbors, type HexTile, type HexCoord } from './hexUtils'

export enum VisibilityLevel {
  UNEXPLORED = 0,
  EXPLORED = 1,
  VISIBLE = 2,
}

export interface FogState {
  exploredTiles: Set<string>
  visibleTiles: Set<string>
  spyVisibleTiles: Set<string>
}

/**
 * 创建战争迷雾状态
 */
export function createFogState(): FogState {
  return {
    exploredTiles: new Set(),
    visibleTiles: new Set(),
    spyVisibleTiles: new Set(),
  }
}

/**
 * 根据玩家势力和细作网络计算每个地块的可见性等级
 */
export function computeVisibility(
  tile: HexTile,
  fogState: FogState,
  _playerFactionId: string,
): VisibilityLevel {
  const tileId = tile.tile_id

  // 1. 完全可视：可见集或细作可见集中
  if (fogState.visibleTiles.has(tileId) || fogState.spyVisibleTiles.has(tileId)) {
    return VisibilityLevel.VISIBLE
  }

  // 2. 已探索但不可见
  if (fogState.exploredTiles.has(tileId)) {
    return VisibilityLevel.EXPLORED
  }

  // 3. 未探索
  return VisibilityLevel.UNEXPLORED
}

/**
 * 更新战争迷雾：基于玩家势力领地计算视野
 * 己方地块 + 2格邻接 = 完全可视
 * 新发现的加入已探索集
 */
export function updateFogOfWar(
  fogState: FogState,
  allTiles: Record<string, HexTile>,
  playerFactionId: string,
  spyNetworks?: Array<{ target_faction_id: string; network_level?: number }>,
): FogState {
  const newVisible = new Set<string>()

  // 遍历所有己方地块
  for (const tile of Object.values(allTiles)) {
    if (tile.faction_id !== playerFactionId) continue

    // 己方地块本身完全可视
    newVisible.add(tile.tile_id)

    // 2格邻接范围完全可视
    const center: HexCoord = { q: tile.q, r: tile.r }
    for (let radius = 1; radius <= 2; radius++) {
      const neighbors = hexNeighbors(center.q, center.r)
      for (const n of neighbors) {
        // 递归查找邻居的邻居
        const nKey = `${n.q},${n.r}`
        // 查找对应 tile_id
        for (const [tid, t] of Object.entries(allTiles)) {
          if (t.q === n.q && t.r === n.r) {
            newVisible.add(tid)
            if (radius === 2) {
              // 第二圈邻居
              const n2s = hexNeighbors(n.q, n.r)
              for (const n2 of n2s) {
                for (const [tid2, t2] of Object.entries(allTiles)) {
                  if (t2.q === n2.q && t2.r === n2.r) {
                    newVisible.add(tid2)
                  }
                }
              }
            }
          }
        }
      }
    }
  }

  // 细作网络：高等级细作可见目标势力所有地块
  if (spyNetworks) {
    for (const spy of spyNetworks) {
      if ((spy.network_level ?? 0) >= 3) {
        for (const tile of Object.values(allTiles)) {
          if (tile.faction_id === spy.target_faction_id) {
            fogState.spyVisibleTiles.add(tile.tile_id)
          }
        }
      }
    }
  }

  // 新增可见地块加入已探索集
  for (const tid of newVisible) {
    fogState.exploredTiles.add(tid)
  }

  fogState.visibleTiles = newVisible
  return fogState
}

/**
 * 获取地块战争迷雾蒙版配置
 */
export function getFogMask(
  visibility: VisibilityLevel,
): { fill: string; opacity: number; showDetails: boolean } {
  switch (visibility) {
    case VisibilityLevel.UNEXPLORED:
      return { fill: '#d4c4a0', opacity: 0.92, showDetails: false }
    case VisibilityLevel.EXPLORED:
      return { fill: '#e0d4b8', opacity: 0.55, showDetails: true }
    case VisibilityLevel.VISIBLE:
      return { fill: 'transparent', opacity: 0, showDetails: true }
  }
}
