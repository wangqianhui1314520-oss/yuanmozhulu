/**
 * 数字格式化 composable
 * 统一处理游戏中的大数字显示
 */
export function useFormat() {
  function formatNum(n: number | undefined | null): string {
    if (n == null) return '0'
    if (n >= 10000) return (n / 10000).toFixed(1) + '万'
    if (n >= 1000) return (n / 1000).toFixed(1) + '千'
    return String(n)
  }

  function formatPercent(n: number | undefined | null): string {
    if (n == null) return '0%'
    return Math.round(n) + '%'
  }

  function formatRound(round: number): string {
    const year = 1351 + Math.floor((round - 1) / 4)
    const seasonNames = ['春', '夏', '秋', '冬']
    const season = seasonNames[(round - 1) % 4]
    return `至正${year - 1340}年${season}`
  }

  return { formatNum, formatPercent, formatRound }
}
