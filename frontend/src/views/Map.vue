<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
const data = ref<any>(null)
const candidates = ref<any[]>([])
const violKeys = ref<Set<string>>(new Set())
const err = ref('')
async function run() {
  err.value = ''
  try {
    data.value = await api('/seating/run?hall_id=1', { method: 'POST' })
  } catch (e: any) {
    err.value = `排座失败：${e.message}`
    data.value = null
    violKeys.value = new Set()
    return
  }
  try {
    const v = await api('/seating/violations?hall_id=1')
    const keys = new Set<string>()
    for (const x of v.violations || []) {
      if (x.a_id != null) keys.add(String(x.a_id))
      if (x.b_id != null) keys.add(String(x.b_id))
    }
    violKeys.value = keys
  } catch { violKeys.value = new Set() }
}
onMounted(async () => {
  candidates.value = await api('/candidates')
  await run()
})
const gridStyle = computed(() => data.value ? ({ gridTemplateColumns: `repeat(${data.value.cols}, 72px)` }) : {})
const cells = computed(() => {
  if (!data.value) return []
  const map = new Map<string, any>()
  for (const a of data.value.assignments || []) map.set(a.row + ',' + a.col, a)
  const out: any[] = []
  for (let r = 0; r < data.value.rows; r++) {
    for (let c = 0; c < data.value.cols; c++) {
      out.push(map.get(r + ',' + c) || { empty: true, row: r, col: c })
    }
  }
  return out
})
const quotaRows = computed(() => data.value?.front_row_rows ?? 0)
function isQuota(cell: any) {
  return quotaRows.value > 0 && cell.row != null && cell.row < quotaRows.value
}
function isViol(cell: any) {
  if (cell.empty) return false
  const id = cell.candidate_id ?? cell.id
  return id != null && violKeys.value.has(String(id))
}
function paperClass(pid: number) {
  return pid % 2 === 0 ? 'b' : 'a'
}
</script>
<template>
  <h1>考场课桌网格</h1>
  <p class="sub">课桌网格为主视图 · 左侧考生名册夹板 · 违规课桌高亮 · 斜纹区为前排名额格</p>
  <button class="btn" @click="run">重新排座</button>
  <span v-if="data && quotaRows > 0" class="hs-quota">
    前 {{ quotaRows }} 行名额区 · 名额已耗 {{ data.quota.quota_used }}/{{ data.quota.quota_slots }}
  </span>
  <span v-else-if="data" class="hs-quota muted">名额账已关闭（前排行数 0）</span>
  <p v-if="err" class="hs-err">{{ err }}</p>
  <div class="hs-classroom" style="margin-top:0.85rem">
    <aside class="hs-clipboard">
      <h2>考生名册</h2>
      <div v-for="c in candidates" :key="c.id" class="hs-roster-row">
        <div>
          <div>
            {{ c.name }}
            <span v-if="c.special" class="badge badge-warn">特</span>
          </div>
          <div class="hs-ticket">{{ c.ticket_no }}</div>
        </div>
        <div>卷{{ c.paper_id }}</div>
      </div>
    </aside>
    <div class="hs-desk-stage" v-if="data">
      <div class="hs-grid-board" :style="gridStyle">
        <div
          v-for="(cell,i) in cells" :key="i"
          class="hs-desk"
          :class="{ empty: cell.empty, 'hs-viol': isViol(cell), 'hs-front': isQuota(cell) }"
        >
          <template v-if="!cell.empty">
            <span class="hs-paper-tag" :class="paperClass(cell.paper_id)">卷{{ cell.paper_id }}</span>
            <span v-if="cell.special" class="hs-special-tag">特</span>
            <div>{{ cell.name }}</div>
          </template>
          <template v-else>·</template>
        </div>
      </div>
    </div>
  </div>
</template>
